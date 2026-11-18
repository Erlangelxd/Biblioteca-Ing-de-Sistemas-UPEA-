"""Proceso 5.0: controlar préstamos y devoluciones (RF09, RF10)."""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .db import get_db, hoy
from .seguridad import admin_requerido, login_requerido
from .servicios import ErrorNegocio, calcular_fecha_prevista, registrar_devolucion, registrar_prestamo, renovar_prestamo
from .util import enlaces_pagina, paginar

bp = Blueprint("prestamos", __name__, url_prefix="/prestamos")

COLS = """p.*, e.codigo, t.titulo, s.nombre AS solicitante, s.ci"""
DESDE = """FROM prestamo p JOIN ejemplar e ON e.id_ejemplar = p.id_ejemplar JOIN trabajo_grado t ON t.id_trabajo = e.id_trabajo
           JOIN solicitante s ON s.id_solicitante = p.id_solicitante"""


@bp.route("/")
@login_requerido
def lista():
    ver = request.args.get("ver", "vigentes")
    donde, p = "", []
    if ver == "vigentes":
        donde = " WHERE p.estado = 'vigente'"
    elif ver == "vencidos":
        donde, p = " WHERE p.estado = 'vigente' AND p.fecha_devolucion_prevista < ?", [hoy()]
    pag = paginar(get_db(), COLS, DESDE + donde, p, "ORDER BY p.fecha_prestamo DESC, p.id_prestamo DESC")
    return render_template("prestamos/lista.html", pag=pag, ver=ver, parametros=enlaces_pagina())


@bp.route("/nuevo", methods=["GET", "POST"])
@admin_requerido
def nuevo():
    db = get_db()
    f = request.form if request.method == "POST" else {"tipo": "externo", "garantia": "ci",
                                                       "id_ejemplar": request.args.get("ejemplar", "")}
    if request.method == "POST":
        try:
            id_prestamo = registrar_prestamo(db, int(f.get("id_ejemplar") or 0), f.get("documento"), f.get("tipo"),
                                             f.get("garantia"), (f.get("fecha_devolucion_prevista") or "").strip(),
                                             g.usuario["id_usuario"])
            flash("Préstamo registrado.", "success")
            return redirect(url_for("prestamos.comprobante", id_prestamo=id_prestamo))
        except ErrorNegocio as e:
            flash(str(e), "error")
    ejemplares = db.execute(
        "SELECT e.id_ejemplar, e.codigo, e.ubicacion, t.titulo FROM ejemplar e JOIN trabajo_grado t ON t.id_trabajo = e.id_trabajo "
        "WHERE e.estado = 'disponible' AND t.activo = 1 ORDER BY t.titulo, e.codigo").fetchall()
    return render_template("prestamos/form.html", f=f, ejemplares=ejemplares,
                           prevista_externo=calcular_fecha_prevista("externo"))


@bp.route("/<int:id_prestamo>/devolver", methods=["POST"])
@admin_requerido
def devolver(id_prestamo):
    try:
        registrar_devolucion(get_db(), id_prestamo)
        flash("Devolución registrada. El ejemplar quedó disponible.", "success")
    except ErrorNegocio as e:
        flash(str(e), "error")
    return redirect(request.referrer or url_for("prestamos.lista"))


@bp.route("/<int:id_prestamo>/renovar", methods=["POST"])
@admin_requerido
def renovar(id_prestamo):
    try:
        renovar_prestamo(get_db(), id_prestamo)
        flash("Préstamo renovado.", "success")
    except ErrorNegocio as e:
        flash(str(e), "error")
    return redirect(url_for("prestamos.lista"))


@bp.route("/<int:id_prestamo>/comprobante")
@login_requerido
def comprobante(id_prestamo):
    p = get_db().execute("SELECT " + COLS + ", e.ubicacion, u.nombre_usuario " + DESDE +
                         " JOIN usuario u ON u.id_usuario = p.id_usuario WHERE p.id_prestamo = ?", (id_prestamo,)).fetchone()
    if p is None:
        abort(404)
    return render_template("prestamos/comprobante.html", p=p)
