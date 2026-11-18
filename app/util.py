from math import ceil

from flask import current_app, request

from .validacion import ESTADOS_EJEMPLAR, MODALIDADES


def paginar(db, columnas, desde, params, orden, por_pagina=None):
    """Devuelve las filas de la página actual y los datos para los enlaces Anterior/Siguiente."""
    por_pagina = por_pagina or current_app.config["POR_PAGINA"]
    total = db.execute(f"SELECT COUNT(*) {desde}", params).fetchone()[0]
    paginas = max(1, ceil(total / por_pagina))
    try:
        pagina = min(max(1, int(request.args.get("pagina", 1))), paginas)
    except ValueError:
        pagina = 1
    filas = db.execute(f"SELECT {columnas} {desde} {orden} LIMIT ? OFFSET ?",
                       list(params) + [por_pagina, (pagina - 1) * por_pagina]).fetchall()
    return {"filas": filas, "pagina": pagina, "paginas": paginas, "total": total}


def estado_trabajo(total, disponibles, activo=1):
    """RF07: estado general que se muestra en la búsqueda y en la ficha."""
    if not activo:
        return ("baja", "De baja")
    if disponibles:
        return ("disponible", "Disponible")
    if total:
        return ("prestado", "En préstamo")
    return ("sin_ejemplares", "Sin ejemplares")


def enlaces_pagina(extra=None):
    """Parámetros de la URL actual sin 'pagina', para armar los enlaces de paginación."""
    from urllib.parse import urlencode
    p = {k: v for k, v in request.args.items() if k != "pagina" and v != ""}
    if extra:
        p.update(extra)
    return urlencode(p)


SQL_TRABAJOS = """
    FROM trabajo_grado t LEFT JOIN area_tematica a ON a.id_area = t.id_area
"""
COLS_TRABAJOS = """t.id_trabajo, t.titulo, t.gestion, t.modalidad, t.activo, t.resumen, t.autoriza_publicacion,
    a.nombre AS area,
    (SELECT group_concat(au.nombre, '; ') FROM trabajo_autor ta JOIN autor au ON au.id_autor = ta.id_autor
        WHERE ta.id_trabajo = t.id_trabajo) AS autores,
    (SELECT COUNT(*) FROM ejemplar e WHERE e.id_trabajo = t.id_trabajo AND e.estado != 'baja') AS total,
    (SELECT COUNT(*) FROM ejemplar e WHERE e.id_trabajo = t.id_trabajo AND e.estado = 'disponible') AS disp,
    (SELECT e.ubicacion FROM ejemplar e WHERE e.id_trabajo = t.id_trabajo ORDER BY e.id_ejemplar LIMIT 1) AS ubicacion"""


def filtrar_trabajos(args, solo_publicables=False):
    """RF06: arma el WHERE de la búsqueda por título/palabra clave, autor, año, área, modalidad y estado.

    Con solo_publicables=True (catálogo público) exige además autorización de publicación.
    """
    donde, p = ["t.activo = 1"], []
    if solo_publicables:
        donde.append("t.autoriza_publicacion = 1")
    q = (args.get("q") or "").strip()
    if q:
        donde.append("(norm(t.titulo) LIKE '%' || norm(?) || '%' OR norm(t.resumen) LIKE '%' || norm(?) || '%')")
        p += [q, q]
    autor = (args.get("autor") or "").strip()
    if autor:
        donde.append("EXISTS (SELECT 1 FROM trabajo_autor ta JOIN autor au ON au.id_autor = ta.id_autor "
                     "WHERE ta.id_trabajo = t.id_trabajo AND norm(au.nombre) LIKE '%' || norm(?) || '%')")
        p.append(autor)
    if (args.get("anio") or "").isdigit():
        donde.append("t.gestion = ?"); p.append(int(args["anio"]))
    if (args.get("area") or "").isdigit():
        donde.append("t.id_area = ?"); p.append(int(args["area"]))
    modalidad = args.get("modalidad")
    if modalidad in MODALIDADES:
        donde.append("t.modalidad = ?"); p.append(modalidad)
    estado = args.get("estado")
    if estado == "disponible":
        donde.append("EXISTS (SELECT 1 FROM ejemplar e WHERE e.id_trabajo = t.id_trabajo AND e.estado = 'disponible')")
    elif estado == "prestado":
        donde.append("NOT EXISTS (SELECT 1 FROM ejemplar e WHERE e.id_trabajo = t.id_trabajo AND e.estado = 'disponible') "
                     "AND EXISTS (SELECT 1 FROM ejemplar e WHERE e.id_trabajo = t.id_trabajo "
                     "AND e.estado IN ('en_prestamo','en_consulta'))")
    return " WHERE " + " AND ".join(donde), p
