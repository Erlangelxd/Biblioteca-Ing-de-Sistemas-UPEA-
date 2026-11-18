"""Validación de los formularios. Cada función devuelve (datos, errores)."""
from datetime import date

MODALIDADES = {"tesis": "Tesis", "proyecto": "Proyecto de grado", "dirigido": "Trabajo dirigido"}
TIPOS_PRESTAMO = {"interno": "Interno (en sala)", "externo": "Externo (a domicilio)"}
GARANTIAS = {"ci": "CI", "matricula": "Carnet de matrícula", "ninguna": "Ninguna"}
TIPOS_SOLICITANTE = {"estudiante": "Estudiante", "docente": "Docente"}
ESTADOS_EJEMPLAR = {"disponible": "Disponible", "en_consulta": "En consulta", "en_prestamo": "En préstamo", "baja": "De baja"}
# Deben coincidir con el CHECK de trabajo_grado.gestion en schema.sql
GESTION_MIN = 1980
GESTION_MAX = 2100


def _t(f, nombre):
    return (f.get(nombre) or "").strip()


def _fecha(valor):
    try:
        return date.fromisoformat(valor).isoformat()
    except ValueError:
        return None


def trabajo(f, nuevo=True):
    d, e = {}, {}
    d["titulo"] = _t(f, "titulo")
    if not d["titulo"]: e["titulo"] = "El título es obligatorio."
    elif len(d["titulo"]) > 250: e["titulo"] = "Máximo 250 caracteres."
    try:
        d["gestion"] = int(_t(f, "gestion"))
        if not GESTION_MIN <= d["gestion"] <= GESTION_MAX: raise ValueError
    except ValueError:
        d["gestion"] = None; e["gestion"] = "Indique un año válido (por ejemplo, 2024)."
    d["modalidad"] = _t(f, "modalidad")
    if d["modalidad"] not in MODALIDADES: e["modalidad"] = "Elija una modalidad."
    raw = _t(f, "fecha_recepcion")
    d["fecha_recepcion"] = _fecha(raw) if raw else date.today().isoformat()
    if d["fecha_recepcion"] is None: e["fecha_recepcion"] = "Fecha no válida."
    d["autores"] = [a.strip() for a in _t(f, "autores").split(";") if a.strip()]
    if not d["autores"]: e["autores"] = "Escriba al menos un autor."
    elif any(len(a) > 80 for a in d["autores"]): e["autores"] = "Cada nombre admite hasta 80 caracteres."
    d["tutor_nombre"] = _t(f, "tutor_nombre")[:80]
    d["area_nueva"] = _t(f, "area_nueva")[:60]
    try: d["id_area"] = int(_t(f, "id_area")) if _t(f, "id_area") else None
    except ValueError: d["id_area"] = None
    d["resumen"] = _t(f, "resumen")
    d["cd_entregado"] = 1 if f.get("cd_entregado") else 0
    d["autoriza_publicacion"] = 1 if f.get("autoriza_publicacion") else 0
    if nuevo:
        try:
            d["num_ejemplares"] = int(_t(f, "num_ejemplares") or 1)
            if not 1 <= d["num_ejemplares"] <= 20: raise ValueError
        except ValueError:
            d["num_ejemplares"] = 1; e["num_ejemplares"] = "Entre 1 y 20 ejemplares."
        d["ubicacion"] = _t(f, "ubicacion")
        if not d["ubicacion"]: e["ubicacion"] = "Indique la ubicación (estante o sección)."
        elif len(d["ubicacion"]) > 60: e["ubicacion"] = "Máximo 60 caracteres."
    return d, e


def solicitante(f):
    d, e = {}, {}
    d["nombre"] = _t(f, "nombre")
    if not d["nombre"]: e["nombre"] = "El nombre es obligatorio."
    elif len(d["nombre"]) > 80: e["nombre"] = "Máximo 80 caracteres."
    d["ci"] = _t(f, "ci")
    if not d["ci"]: e["ci"] = "La CI es obligatoria."
    elif len(d["ci"]) > 15: e["ci"] = "Máximo 15 caracteres."
    d["matricula"] = _t(f, "matricula")[:15]
    d["tipo"] = _t(f, "tipo")
    if d["tipo"] not in TIPOS_SOLICITANTE: e["tipo"] = "Elija el tipo."
    d["telefono"] = _t(f, "telefono")[:15]
    return d, e
