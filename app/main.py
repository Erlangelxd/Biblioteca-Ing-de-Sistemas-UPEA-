from datetime import date

from flask import Blueprint, current_app, abort, render_template, request

from .db import get_db, hoy
from .seguridad import login_requerido
from .util import COLS_TRABAJOS, SQL_TRABAJOS, enlaces_pagina, estado_trabajo, filtrar_trabajos, paginar

bp = Blueprint("main", __name__)


@bp.route("/")
@login_requerido
def inicio():
    db = get_db()
    q = lambda sql, *p: db.execute(sql, p).fetchone()[0]
    return render_template("inicio.html",
        total_trabajos=q("SELECT COUNT(*) FROM trabajo_grado WHERE activo = 1"),
        vigentes=q("SELECT COUNT(*) FROM prestamo WHERE estado = 'vigente'"),
        vencidos=q("SELECT COUNT(*) FROM prestamo WHERE estado = 'vigente' AND fecha_devolucion_prevista < ?", hoy()),
        recientes=q("SELECT COUNT(*) FROM trabajo_grado WHERE strftime('%Y', fecha_recepcion) = ?", str(date.today().year)))


@bp.route("/catalogo")
def catalogo():
    """Consulta pública de solo lectura (sin iniciar sesión, sin datos personales de solicitantes)."""
    if not current_app.config["CATALOGO_PUBLICO"]:
        abort(404)
    db = get_db()
    donde, p = filtrar_trabajos(request.args, solo_publicables=True)
    pag = paginar(db, COLS_TRABAJOS, SQL_TRABAJOS + donde, p, "ORDER BY t.gestion DESC, t.titulo")
    filas = [dict(f, estado=estado_trabajo(f["total"], f["disp"], f["activo"])) for f in pag["filas"]]
    return render_template("catalogo.html", filas=filas, pag=pag, g=request.args,
                           areas=db.execute("SELECT * FROM area_tematica ORDER BY nombre").fetchall(),
                           anios=[r[0] for r in db.execute(
                               "SELECT DISTINCT gestion FROM trabajo_grado "
                               "WHERE activo = 1 AND autoriza_publicacion = 1 ORDER BY gestion DESC")],
                           parametros=enlaces_pagina())
