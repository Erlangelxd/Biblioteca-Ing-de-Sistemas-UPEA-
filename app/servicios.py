"""Reglas de negocio del sistema (procesos 1.0 a 5.0 del diagrama cero)."""
from datetime import date, timedelta

from flask import current_app
from werkzeug.security import generate_password_hash

from .db import hoy, transaccion


class ErrorNegocio(Exception):
    """Un error que se muestra a la persona usuaria (por ejemplo, 'el ejemplar no está disponible')."""


# ------------------------------------------------------------------ proceso 1.0: usuarios
def crear_usuario(db, nombre, clave, rol="consulta"):
    nombre = (nombre or "").strip()
    if not 3 <= len(nombre) <= 30:
        raise ErrorNegocio("El nombre de usuario debe tener entre 3 y 30 caracteres.")
    if rol not in ("administrador", "consulta"):
        raise ErrorNegocio("Rol no válido.")
    validar_clave(clave)
    if db.execute("SELECT 1 FROM usuario WHERE nombre_usuario = ?", (nombre,)).fetchone():
        raise ErrorNegocio("Ya existe un usuario con ese nombre.")
    cur = db.execute("INSERT INTO usuario (nombre_usuario, contrasena, rol) VALUES (?,?,?)",
                     (nombre, generate_password_hash(clave), rol))
    return cur.lastrowid


def validar_clave(clave):
    if len(clave or "") < 8:
        raise ErrorNegocio("La contraseña debe tener al menos 8 caracteres.")


def cambiar_clave(db, id_usuario, clave):
    validar_clave(clave)
    db.execute("UPDATE usuario SET contrasena = ? WHERE id_usuario = ?", (generate_password_hash(clave), id_usuario))


# ------------------------------------------------------------------ proceso 2.0: trabajos y ejemplares
def _id_por_nombre(db, tabla, columna_id, nombre):
    fila = db.execute(f"SELECT {columna_id} FROM {tabla} WHERE lower(nombre) = lower(?)", (nombre,)).fetchone()
    if fila:
        return fila[0]
    return db.execute(f"INSERT INTO {tabla} (nombre) VALUES (?)", (nombre,)).lastrowid


def _guardar_autores(db, id_trabajo, autores):
    db.execute("DELETE FROM trabajo_autor WHERE id_trabajo = ?", (id_trabajo,))
    for nombre in autores:
        fila = db.execute("SELECT id_autor FROM autor WHERE lower(nombre) = lower(?)", (nombre,)).fetchone()
        id_autor = fila[0] if fila else db.execute("INSERT INTO autor (nombre) VALUES (?)", (nombre,)).lastrowid
        db.execute("INSERT OR IGNORE INTO trabajo_autor VALUES (?,?)", (id_trabajo, id_autor))


def _asignar_area_tutor(db, d):
    id_area = d["id_area"]
    if d["area_nueva"]:
        id_area = _id_por_nombre(db, "area_tematica", "id_area", d["area_nueva"])
    id_tutor = _id_por_nombre(db, "tutor", "id_tutor", d["tutor_nombre"]) if d["tutor_nombre"] else None
    return id_area, id_tutor


def existe_duplicado(db, titulo, gestion, excepto=None):
    fila = db.execute("SELECT id_trabajo FROM trabajo_grado WHERE lower(titulo) = lower(?) AND gestion = ? "
                      "AND id_trabajo != ?", (titulo, gestion, excepto or 0)).fetchone()
    return fila is not None


def registrar_trabajo(db, d):
    """RF03. d = datos ya validados."""
    with transaccion(db):
        if existe_duplicado(db, d["titulo"], d["gestion"]):
            raise ErrorNegocio("Ya existe un trabajo con ese título y esa gestión.")
        id_area, id_tutor = _asignar_area_tutor(db, d)
        id_trabajo = db.execute(
            "INSERT INTO trabajo_grado (titulo, resumen, gestion, modalidad, fecha_recepcion, cd_entregado, "
            "autoriza_publicacion, id_area, id_tutor) VALUES (?,?,?,?,?,?,?,?,?)",
            (d["titulo"], d["resumen"], d["gestion"], d["modalidad"], d["fecha_recepcion"], d["cd_entregado"],
             d["autoriza_publicacion"], id_area, id_tutor)).lastrowid
        _guardar_autores(db, id_trabajo, d["autores"])
        for n in range(1, d["num_ejemplares"] + 1):
            db.execute("INSERT INTO ejemplar (id_trabajo, codigo, ubicacion) VALUES (?,?,?)",
                       (id_trabajo, f"TG-{id_trabajo:04d}-{n}", d["ubicacion"]))
    return id_trabajo


def modificar_trabajo(db, id_trabajo, d):
    """RF04 (corrección de datos)."""
    with transaccion(db):
        if existe_duplicado(db, d["titulo"], d["gestion"], excepto=id_trabajo):
            raise ErrorNegocio("Ya existe otro trabajo con ese título y esa gestión.")
        id_area, id_tutor = _asignar_area_tutor(db, d)
        db.execute(
            "UPDATE trabajo_grado SET titulo=?, resumen=?, gestion=?, modalidad=?, fecha_recepcion=?, "
            "cd_entregado=?, autoriza_publicacion=?, id_area=?, id_tutor=? WHERE id_trabajo=?",
            (d["titulo"], d["resumen"], d["gestion"], d["modalidad"], d["fecha_recepcion"], d["cd_entregado"],
             d["autoriza_publicacion"], id_area, id_tutor, id_trabajo))
        _guardar_autores(db, id_trabajo, d["autores"])


def dar_de_baja(db, id_trabajo):
    """RF04 (baja lógica: el historial de préstamos se conserva)."""
    with transaccion(db):
        vigentes = db.execute(
            "SELECT COUNT(*) FROM prestamo p JOIN ejemplar e USING (id_ejemplar) "
            "WHERE e.id_trabajo = ? AND p.estado = 'vigente'", (id_trabajo,)).fetchone()[0]
        if vigentes:
            raise ErrorNegocio("No se puede dar de baja: tiene préstamos vigentes.")
        db.execute("UPDATE trabajo_grado SET activo = 0 WHERE id_trabajo = ?", (id_trabajo,))
        db.execute("UPDATE ejemplar SET estado = 'baja' WHERE id_trabajo = ?", (id_trabajo,))


def agregar_ejemplar(db, id_trabajo, ubicacion):
    ubicacion = (ubicacion or "").strip()
    if not ubicacion:
        raise ErrorNegocio("Indique la ubicación del nuevo ejemplar.")
    with transaccion(db):
        trabajo = db.execute("SELECT activo FROM trabajo_grado WHERE id_trabajo = ?", (id_trabajo,)).fetchone()
        if trabajo is None or not trabajo["activo"]:
            raise ErrorNegocio("El trabajo no existe o está dado de baja.")
        n = db.execute("SELECT COUNT(*) FROM ejemplar WHERE id_trabajo = ?", (id_trabajo,)).fetchone()[0] + 1
        while db.execute("SELECT 1 FROM ejemplar WHERE codigo = ?", (f"TG-{id_trabajo:04d}-{n}",)).fetchone():
            n += 1
        db.execute("INSERT INTO ejemplar (id_trabajo, codigo, ubicacion) VALUES (?,?,?)",
                   (id_trabajo, f"TG-{id_trabajo:04d}-{n}", ubicacion[:60]))


# ------------------------------------------------------------------ proceso 5.0: préstamos y devoluciones
def calcular_fecha_prevista(tipo, desde=None):
    desde = desde or date.today()
    if tipo == "interno":
        return desde.isoformat()           # consulta en sala: se devuelve el mismo día
    return (desde + timedelta(days=current_app.config["DIAS_PRESTAMO_EXTERNO"])).isoformat()


def estado_prestamo(p):
    """'devuelto', 'vencido' o 'vigente' (RF10). p es una fila o diccionario con los campos del préstamo."""
    if p["estado"] == "devuelto":
        return "devuelto"
    return "vencido" if p["fecha_devolucion_prevista"] < hoy() else "vigente"


def dias_retraso(p):
    if estado_prestamo(p) != "vencido":
        return 0
    return (date.today() - date.fromisoformat(p["fecha_devolucion_prevista"])).days


def puede_renovar(p):
    return (p["estado"] == "vigente" and p["tipo"] == "externo" and
            p["renovaciones"] < current_app.config["MAX_RENOVACIONES"] and estado_prestamo(p) == "vigente")


def buscar_solicitante(db, documento):
    documento = (documento or "").strip()
    if not documento:
        return None
    return db.execute("SELECT * FROM solicitante WHERE ci = ? OR (matricula != '' AND matricula = ?)",
                      (documento, documento)).fetchone()


def registrar_prestamo(db, id_ejemplar, documento, tipo, garantia, fecha_prevista, id_usuario):
    """RF09. Todo en una transacción: o se guarda el préstamo y cambia el ejemplar, o no se guarda nada."""
    if tipo not in ("interno", "externo") or garantia not in ("ci", "matricula", "ninguna"):
        raise ErrorNegocio("Tipo o garantía no válidos.")
    solicitante = buscar_solicitante(db, documento)
    if solicitante is None:
        raise ErrorNegocio("No hay un solicitante con esa CI o matrícula. Regístrelo primero.")
    if tipo == "interno":
        # La consulta en sala se devuelve el mismo día, sin importar la fecha que envíe el formulario.
        fecha_prevista = calcular_fecha_prevista("interno")
    elif fecha_prevista:
        try:
            date.fromisoformat(fecha_prevista)
        except ValueError:
            raise ErrorNegocio("La fecha de devolución prevista no es válida.")
        if fecha_prevista < hoy():
            raise ErrorNegocio("La fecha de devolución prevista no puede ser anterior a hoy.")
    else:
        fecha_prevista = calcular_fecha_prevista(tipo)
    with transaccion(db):
        if tipo == "externo":
            vigentes = db.execute("SELECT COUNT(*) FROM prestamo WHERE id_solicitante = ? AND estado = 'vigente' "
                                  "AND tipo = 'externo'", (solicitante["id_solicitante"],)).fetchone()[0]
            maximo = current_app.config["MAX_PRESTAMOS_EXTERNOS"]
            if vigentes >= maximo:
                raise ErrorNegocio(f"El solicitante ya tiene {vigentes} préstamos a domicilio vigentes (máximo {maximo}).")
        nuevo_estado = "en_consulta" if tipo == "interno" else "en_prestamo"
        cambio = db.execute(
            "UPDATE ejemplar SET estado = ? WHERE id_ejemplar = ? AND estado = 'disponible' "
            "AND id_trabajo IN (SELECT id_trabajo FROM trabajo_grado WHERE activo = 1)", (nuevo_estado, id_ejemplar))
        if cambio.rowcount != 1:                       # RNF05: no prestar un ejemplar que no está disponible
            raise ErrorNegocio("Ese ejemplar no está disponible.")
        return db.execute(
            "INSERT INTO prestamo (id_ejemplar, id_solicitante, id_usuario, tipo, garantia, fecha_prestamo, "
            "fecha_devolucion_prevista) VALUES (?,?,?,?,?,?,?)",
            (id_ejemplar, solicitante["id_solicitante"], id_usuario, tipo, garantia, hoy(), fecha_prevista)).lastrowid


def registrar_devolucion(db, id_prestamo):
    """RF10."""
    with transaccion(db):
        p = db.execute("SELECT * FROM prestamo WHERE id_prestamo = ? AND estado = 'vigente'", (id_prestamo,)).fetchone()
        if p is None:
            raise ErrorNegocio("El préstamo no existe o ya fue devuelto.")
        db.execute("UPDATE prestamo SET estado = 'devuelto', fecha_devolucion_real = ? WHERE id_prestamo = ?",
                   (hoy(), id_prestamo))
        db.execute("UPDATE ejemplar SET estado = 'disponible' WHERE id_ejemplar = ? AND estado != 'baja'",
                   (p["id_ejemplar"],))


def renovar_prestamo(db, id_prestamo):
    with transaccion(db):
        p = db.execute("SELECT * FROM prestamo WHERE id_prestamo = ?", (id_prestamo,)).fetchone()
        if p is None or not puede_renovar(p):
            raise ErrorNegocio("Este préstamo no se puede renovar.")
        nueva = date.fromisoformat(p["fecha_devolucion_prevista"]) + timedelta(days=current_app.config["DIAS_PRESTAMO_EXTERNO"])
        db.execute("UPDATE prestamo SET renovaciones = renovaciones + 1, fecha_devolucion_prevista = ? "
                   "WHERE id_prestamo = ?", (nueva.isoformat(), id_prestamo))
