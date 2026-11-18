"""Proceso 6.0: generar reportes. Los nueve reportes del alcance (RF11 a RF19) y su impresión (RF20).
Cada reporte devuelve un diccionario: titulo, columnas, filas, total y, opcionalmente, barras (gráfico)."""
import csv
import io
from datetime import date, timedelta

from flask import Blueprint, Response, abort, render_template, request

from .db import get_db, hoy
from .seguridad import login_requerido
from .servicios import dias_retraso, estado_prestamo
from .validacion import TIPOS_PRESTAMO, MODALIDADES

bp = Blueprint("reportes", __name__, url_prefix="/reportes")

TXT_ESTADO = {"vigente": "Vigente", "vencido": "Vencido", "devuelto": "Devuelto"}


def _fecha(valor, defecto):
    try:
        return date.fromisoformat(valor) if valor else defecto
    except ValueError:
        return defecto


def _fmt(v):
    """Fecha ISO -> dd/mm/aaaa para mostrar."""
    try:
        return date.fromisoformat(v).strftime("%d/%m/%Y") if isinstance(v, str) and len(v) == 10 and v[4] == "-" else v
    except ValueError:
        return v


BASE_PRESTAMO = """FROM prestamo p JOIN ejemplar e ON e.id_ejemplar = p.id_ejemplar
    JOIN trabajo_grado t ON t.id_trabajo = e.id_trabajo JOIN solicitante s ON s.id_solicitante = p.id_solicitante"""


def prestamos_activos(args):
    qs = get_db().execute("SELECT p.*, e.codigo, t.titulo, s.nombre AS solicitante " + BASE_PRESTAMO +
                          " WHERE p.estado = 'vigente' ORDER BY p.fecha_devolucion_prevista").fetchall()
    filas = [[i, p["codigo"], p["titulo"], p["solicitante"], TIPOS_PRESTAMO[p["tipo"]], p["fecha_prestamo"],
              p["fecha_devolucion_prevista"], TXT_ESTADO[estado_prestamo(p)]] for i, p in enumerate(qs, 1)]
    return {"titulo": "Reporte de préstamos activos",
            "columnas": ["N.º", "Código", "Título del trabajo", "Solicitante", "Tipo", "Préstamo", "Devolución prevista", "Estado"],
            "filas": filas, "total": f"Total de préstamos activos: {len(filas)}"}


def historial_usuario(args):
    q = (args.get("q") or "").strip()
    sql, p = "SELECT p.*, t.titulo, s.nombre AS solicitante " + BASE_PRESTAMO, []
    if q:
        sql += " WHERE norm(s.nombre) LIKE '%' || norm(?) || '%' OR s.ci = ? OR s.matricula = ?"
        p = [q, q, q]
    qs = get_db().execute(sql + " ORDER BY p.fecha_prestamo DESC, p.id_prestamo DESC", p).fetchall()
    filas = [[i, r["solicitante"], r["titulo"], r["fecha_prestamo"], r["fecha_devolucion_real"] or "—",
              TXT_ESTADO[estado_prestamo(r)]] for i, r in enumerate(qs, 1)]
    return {"titulo": "Reporte de historial por usuario",
            "columnas": ["N.º", "Solicitante", "Trabajo", "Préstamo", "Devolución real", "Estado"],
            "filas": filas, "total": f"Total de préstamos: {len(filas)}", "filtro_q": True, "q": q}


def mas_prestados(args):
    hasta = _fecha(args.get("hasta"), date.today())
    desde = _fecha(args.get("desde"), hasta - timedelta(days=365))
    qs = get_db().execute(
        "SELECT t.titulo, t.gestion, COUNT(*) AS n " + BASE_PRESTAMO + " WHERE p.fecha_prestamo BETWEEN ? AND ? "
        "GROUP BY t.id_trabajo ORDER BY n DESC, t.titulo LIMIT 10", (desde.isoformat(), hasta.isoformat())).fetchall()
    return {"titulo": "Reporte de trabajos más prestados", "columnas": ["N.º", "Título", "Gestión", "Veces prestado"],
            "filas": [[i, r["titulo"], r["gestion"], r["n"]] for i, r in enumerate(qs, 1)],
            "total": f"Período: {desde:%d/%m/%Y} al {hasta:%d/%m/%Y}", "filtro_fechas": True,
            "desde": desde.isoformat(), "hasta": hasta.isoformat(), "barras": [(r["titulo"][:40], r["n"]) for r in qs]}


def disponibilidad(args):
    qs = get_db().execute(
        "SELECT t.titulo, SUM(e.estado != 'baja') AS total, SUM(e.estado = 'disponible') AS disp "
        "FROM trabajo_grado t LEFT JOIN ejemplar e ON e.id_trabajo = t.id_trabajo WHERE t.activo = 1 "
        "GROUP BY t.id_trabajo ORDER BY t.titulo").fetchall()
    filas = [[i, r["titulo"], r["total"] or 0, r["disp"] or 0, (r["total"] or 0) - (r["disp"] or 0)] for i, r in enumerate(qs, 1)]
    return {"titulo": "Reporte de disponibilidad de ejemplares",
            "columnas": ["N.º", "Trabajo", "Ejemplares", "Disponibles", "Prestados o en consulta"],
            "filas": filas, "total": f"Total de trabajos: {len(filas)}"}


def por_area(args):
    qs = get_db().execute(
        "SELECT COALESCE(a.nombre, 'Sin área asignada') AS area, COUNT(*) AS n FROM trabajo_grado t "
        "LEFT JOIN area_tematica a ON a.id_area = t.id_area WHERE t.activo = 1 GROUP BY a.id_area "
        "ORDER BY n DESC, area").fetchall()
    filas = [[i, r["area"], r["n"]] for i, r in enumerate(qs, 1)]
    return {"titulo": "Reporte de trabajos por área temática", "columnas": ["N.º", "Área temática", "Trabajos"],
            "filas": filas, "total": f"Total de trabajos activos: {sum(f[2] for f in filas)}",
            "barras": [(f[1], f[2]) for f in filas]}


def estadisticas(args):
    db = get_db()
    pre = dict(db.execute("SELECT strftime('%Y-%m', fecha_prestamo), COUNT(*) FROM prestamo GROUP BY 1").fetchall())
    dev = dict(db.execute("SELECT strftime('%Y-%m', fecha_devolucion_real), COUNT(*) FROM prestamo "
                          "WHERE fecha_devolucion_real IS NOT NULL GROUP BY 1").fetchall())
    meses = sorted(set(pre) | set(dev))
    filas = [[f"{m[5:]}/{m[:4]}", pre.get(m, 0), dev.get(m, 0)] for m in meses]
    return {"titulo": "Reporte de estadísticas de uso", "columnas": ["Mes", "Préstamos y consultas", "Devoluciones"],
            "filas": filas, "total": f"Total de préstamos registrados: {sum(pre.values())}",
            "barras": [(f[0], f[1]) for f in filas]}


def alertas_retraso(args):
    qs = get_db().execute("SELECT p.*, t.titulo, s.nombre AS solicitante, s.ci, s.telefono " + BASE_PRESTAMO +
                          " WHERE p.estado = 'vigente' AND p.fecha_devolucion_prevista < ? "
                          "ORDER BY p.fecha_devolucion_prevista", (hoy(),)).fetchall()
    filas = [[i, p["solicitante"], p["ci"], p["telefono"] or "—", p["titulo"], p["fecha_devolucion_prevista"],
              dias_retraso(p)] for i, p in enumerate(qs, 1)]
    return {"titulo": "Alertas de retraso en devoluciones",
            "columnas": ["N.º", "Solicitante", "CI", "Teléfono", "Trabajo", "Devolución prevista", "Días de retraso"],
            "filas": filas, "total": f"Fecha de corte: {date.today():%d/%m/%Y} — Total con retraso: {len(filas)}"}


def nuevas_adquisiciones(args):
    hasta = _fecha(args.get("hasta"), date.today())
    desde = _fecha(args.get("desde"), hasta - timedelta(days=90))
    qs = get_db().execute(
        "SELECT t.titulo, t.gestion, t.modalidad, t.fecha_recepcion, (SELECT group_concat(au.nombre, '; ') FROM trabajo_autor ta "
        "JOIN autor au ON au.id_autor = ta.id_autor WHERE ta.id_trabajo = t.id_trabajo) AS autores FROM trabajo_grado t "
        "WHERE t.fecha_recepcion BETWEEN ? AND ? ORDER BY t.fecha_recepcion DESC", (desde.isoformat(), hasta.isoformat())).fetchall()
    filas = [[i, r["titulo"], r["autores"], r["gestion"], MODALIDADES[r["modalidad"]], r["fecha_recepcion"]]
             for i, r in enumerate(qs, 1)]
    return {"titulo": "Reporte de nuevas adquisiciones",
            "columnas": ["N.º", "Título", "Autor(es)", "Gestión", "Modalidad", "Recepción"], "filas": filas,
            "total": f"Período: {desde:%d/%m/%Y} al {hasta:%d/%m/%Y} — Total: {len(filas)}",
            "filtro_fechas": True, "desde": desde.isoformat(), "hasta": hasta.isoformat()}


def comparativo_anual(args):
    db = get_db()
    q = lambda sql: dict(db.execute(sql).fetchall())
    pre = q("SELECT strftime('%Y', fecha_prestamo), COUNT(*) FROM prestamo GROUP BY 1")
    dev = q("SELECT strftime('%Y', fecha_devolucion_real), COUNT(*) FROM prestamo WHERE fecha_devolucion_real IS NOT NULL GROUP BY 1")
    rec = q("SELECT strftime('%Y', fecha_recepcion), COUNT(*) FROM trabajo_grado GROUP BY 1")
    filas = [[int(a), pre.get(a, 0), dev.get(a, 0), rec.get(a, 0)] for a in sorted(set(pre) | set(dev) | set(rec))]
    return {"titulo": "Reporte comparativo anual",
            "columnas": ["Año", "Préstamos y consultas", "Devoluciones", "Trabajos recibidos"], "filas": filas,
            "total": f"Años con movimiento: {len(filas)}", "barras": [(str(f[0]), f[1]) for f in filas]}


REPORTES = {
    "prestamos-activos": ("Préstamos activos", "RF11", prestamos_activos),
    "historial-usuario": ("Historial por usuario", "RF12", historial_usuario),
    "mas-prestados": ("Trabajos más prestados", "RF13", mas_prestados),
    "disponibilidad": ("Disponibilidad de ejemplares", "RF14", disponibilidad),
    "por-area": ("Trabajos por área temática", "RF15", por_area),
    "estadisticas": ("Estadísticas de uso", "RF16", estadisticas),
    "alertas-retraso": ("Alertas de retraso", "RF17", alertas_retraso),
    "nuevas-adquisiciones": ("Nuevas adquisiciones", "RF18", nuevas_adquisiciones),
    "comparativo-anual": ("Comparativo anual", "RF19", comparativo_anual),
}


@bp.route("/")
@login_requerido
def indice():
    return render_template("reportes/indice.html", reportes=[(k, v[0], v[1]) for k, v in REPORTES.items()])


@bp.route("/<clave>")
@login_requerido
def ver(clave):
    if clave not in REPORTES:
        abort(404)
    datos = REPORTES[clave][2](request.args)
    datos["filas"] = [[_fmt(c) for c in fila] for fila in datos["filas"]]
    if request.args.get("formato") == "csv":          # extra: exportar a CSV (se abre en Excel)
        salida = io.StringIO()
        w = csv.writer(salida)
        w.writerow(datos["columnas"])
        w.writerows(datos["filas"])
        return Response("﻿" + salida.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": f"attachment; filename={clave}.csv"})
    barras = datos.get("barras") or []
    maximo = max([b[1] for b in barras], default=0) or 1
    datos["barras"] = [(e, v, int(v * 100 / maximo)) for e, v in barras]
    return render_template("reportes/ver.html", clave=clave, hoy=date.today(), **datos)
