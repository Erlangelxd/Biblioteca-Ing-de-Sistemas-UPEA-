"""Utilidades de presentación: paginación, estado y enlaces."""
from urllib.parse import urlencode

from flask import current_app, request

from .extensions import db
from .validacion import ESTADOS_EJEMPLAR


class Paginacion:
    """Adaptador con los nombres usados por las plantillas."""

    def __init__(self, paginacion):
        self.filas = paginacion.items
        self.pagina = paginacion.page
        self.paginas = paginacion.pages
        self.total = paginacion.total


def paginar(consulta, por_pagina=None):
    por_pagina = por_pagina or current_app.config["POR_PAGINA"]
    pagina = request.args.get("pagina", 1, type=int) or 1
    return Paginacion(db.paginate(consulta, page=pagina, per_page=por_pagina, error_out=False))


def estado_trabajo(total, disponibles, activo=1):
    """RF07: estado general que se muestra en la búsqueda y en la ficha."""
    if not activo:
        return ("baja", "De baja")
    if disponibles:
        return ("disponible", "Disponible")
    if total:
        return ("prestado", "En préstamo")
    return ("sin_ejemplares", "Sin ejemplares")


def fila_trabajo(trabajo):
    """Convierte el modelo ORM en el diccionario que consumen las plantillas."""
    total = trabajo.total_ejemplares
    disponibles = trabajo.disponibles
    return {
        "id_trabajo": trabajo.id_trabajo,
        "titulo": trabajo.titulo,
        "autores": trabajo.autores_texto,
        "gestion": trabajo.gestion,
        "area": trabajo.area.nombre if trabajo.area else None,
        "ubicacion": trabajo.ubicacion_principal,
        "resumen": trabajo.resumen,
        "autoriza_publicacion": trabajo.autoriza_publicacion,
        "activo": trabajo.activo,
        "estado": estado_trabajo(total, disponibles, trabajo.activo),
    }


def enlaces_pagina(extra=None):
    """Parámetros de la URL actual sin 'pagina', para los enlaces de paginación."""
    parametros = {k: v for k, v in request.args.items() if k != "pagina" and v != ""}
    if extra:
        parametros.update(extra)
    return urlencode(parametros)
