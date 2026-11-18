"""Procesos 2.0 (registrar trabajos) y 4.0 (buscar trabajos): RF03, RF04, RF05, RF06 y RF07."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from . import validacion
from .db import get_db
from .seguridad import admin_requerido, login_requerido
from .servicios import ErrorNegocio, agregar_ejemplar, dar_de_baja, modificar_trabajo, registrar_trabajo
from .util import COLS_TRABAJOS, SQL_TRABAJOS, enlaces_pagina, estado_trabajo, filtrar_trabajos, paginar

bp = Blueprint("trabajos", __name__, url_prefix="/trabajos")


def _catalogos(db):
    return {"areas": db.execute("SELECT * FROM area_tematica ORDER BY nombre").fetchall()}


@bp.route("/")
@login_requerido
def lista():
    db = get_db()
    donde, p = filtrar_trabajos(request.args)
    pag = paginar(db, COLS_TRABAJOS, SQL_TRABAJOS + donde, p, "ORDER BY t.gestion DESC, t.titulo")
    filas = [dict(f, estado=estado_trabajo(f["total"], f["disp"], f["activo"])) for f in pag["filas"]]
    return render_template("trabajos/lista.html", filas=filas, pag=pag, g=request.args, parametros=enlaces_pagina(),
                           anios=[r[0] for r in db.execute("SELECT DISTINCT gestion FROM trabajo_grado ORDER BY gestion DESC")],
                           **_catalogos(db))


@bp.route("/<int:id_trabajo>")
@login_requerido
def detalle(id_trabajo):
    db = get_db()
    t = db.execute("SELECT t.*, a.nombre AS area, tu.nombre AS tutor FROM trabajo_grado t "
                   "LEFT JOIN area_tematica a ON a.id_area = t.id_area LEFT JOIN tutor tu ON tu.id_tutor = t.id_tutor "
                   "WHERE t.id_trabajo = ?", (id_trabajo,)).fetchone()
    if t is None:
        abort(404)
    autores = [r[0] for r in db.execute("SELECT au.nombre FROM trabajo_autor ta JOIN autor au ON au.id_autor = ta.id_autor "
                                        "WHERE ta.id_trabajo = ? ORDER BY au.nombre", (id_trabajo,))]
    ejemplares = db.execute("SELECT * FROM ejemplar WHERE id_trabajo = ? ORDER BY codigo", (id_trabajo,)).fetchall()
    total = sum(1 for e in ejemplares if e["estado"] != "baja")
    disp = sum(1 for e in ejemplares if e["estado"] == "disponible")
    historial = db.execute(
        "SELECT p.*, s.nombre AS solicitante, e.codigo FROM prestamo p JOIN ejemplar e ON e.id_ejemplar = p.id_ejemplar "
        "JOIN solicitante s ON s.id_solicitante = p.id_solicitante WHERE e.id_trabajo = ? "
        "ORDER BY p.fecha_prestamo DESC, p.id_prestamo DESC LIMIT 20", (id_trabajo,)).fetchall()
    return render_template("trabajos/detalle.html", t=t, autores=autores, ejemplares=ejemplares, historial=historial,
                           estado=estado_trabajo(total, disp, t["activo"]))


def _form(titulo, f, errores, editar, t=None):
    db = get_db()
    return render_template("trabajos/form.html", titulo=titulo, f=f, errores=errores, editar=editar, t=t, **_catalogos(db))


@bp.route("/nuevo", methods=["GET", "POST"])
@admin_requerido
def nuevo():
    if request.method == "POST":
        d, e = validacion.trabajo(request.form, nuevo=True)
        if not e:
            try:
                id_trabajo = registrar_trabajo(get_db(), d)
                flash("Trabajo de grado registrado correctamente.", "success")
                return redirect(url_for("trabajos.detalle", id_trabajo=id_trabajo))
            except ErrorNegocio as ex:
                e["titulo"] = str(ex)
        return _form("Registrar trabajo de grado", request.form, e, False)
    return _form("Registrar trabajo de grado", {"num_ejemplares": 1, "modalidad": "proyecto"}, {}, False)


@bp.route("/<int:id_trabajo>/editar", methods=["GET", "POST"])
@admin_requerido
def editar(id_trabajo):
    db = get_db()
    t = db.execute("SELECT t.*, tu.nombre AS tutor_nombre FROM trabajo_grado t LEFT JOIN tutor tu ON tu.id_tutor = t.id_tutor "
                   "WHERE t.id_trabajo = ? AND t.activo = 1", (id_trabajo,)).fetchone()
    if t is None:
        abort(404)
    if request.method == "POST":
        d, e = validacion.trabajo(request.form, nuevo=False)
        if not e:
            try:
                modificar_trabajo(db, id_trabajo, d)
                flash("Datos del trabajo actualizados.", "success")
                return redirect(url_for("trabajos.detalle", id_trabajo=id_trabajo))
            except ErrorNegocio as ex:
                e["titulo"] = str(ex)
        return _form("Modificar trabajo de grado", request.form, e, True, t)
    autores = "; ".join(r[0] for r in db.execute(
        "SELECT au.nombre FROM trabajo_autor ta JOIN autor au ON au.id_autor = ta.id_autor WHERE ta.id_trabajo = ? "
        "ORDER BY au.nombre", (id_trabajo,)))
    f = dict(t, autores=autores)
    return _form("Modificar trabajo de grado", f, {}, True, t)


@bp.route("/<int:id_trabajo>/baja", methods=["POST"])
@admin_requerido
def baja(id_trabajo):
    try:
        dar_de_baja(get_db(), id_trabajo)
        flash("El trabajo fue dado de baja. Su historial se conserva.", "success")
        return redirect(url_for("trabajos.lista"))
    except ErrorNegocio as e:
        flash(str(e), "error")
        return redirect(url_for("trabajos.detalle", id_trabajo=id_trabajo))


@bp.route("/<int:id_trabajo>/ejemplar", methods=["POST"])
@admin_requerido
def ejemplar_nuevo(id_trabajo):
    try:
        agregar_ejemplar(get_db(), id_trabajo, request.form.get("ubicacion"))
        flash("Ejemplar agregado.", "success")
    except ErrorNegocio as e:
        flash(str(e), "error")
    return redirect(url_for("trabajos.detalle", id_trabajo=id_trabajo))
