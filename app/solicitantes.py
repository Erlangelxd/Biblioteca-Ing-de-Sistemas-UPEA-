"""Proceso 3.0: registrar solicitantes (RF08)."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from . import validacion
from .db import get_db
from .seguridad import admin_requerido, login_requerido
from .util import enlaces_pagina, paginar

bp = Blueprint("solicitantes", __name__, url_prefix="/solicitantes")


@bp.route("/")
@login_requerido
def lista():
    q = (request.args.get("q") or "").strip()
    donde, p = "", []
    if q:
        donde = " WHERE norm(nombre) LIKE '%' || norm(?) || '%' OR ci LIKE '%' || ? || '%' OR matricula LIKE '%' || ? || '%'"
        p = [q, q, q]
    pag = paginar(get_db(), "*", "FROM solicitante" + donde, p, "ORDER BY nombre")
    return render_template("solicitantes/lista.html", pag=pag, q=q, parametros=enlaces_pagina())


def _guardar(id_solicitante=None):
    d, e = validacion.solicitante(request.form)
    if not e:
        db = get_db()
        repetido = db.execute("SELECT 1 FROM solicitante WHERE ci = ? AND id_solicitante != ?", (d["ci"], id_solicitante or 0)).fetchone()
        if repetido:
            e["ci"] = "Ya hay un solicitante con esa CI."
        else:
            if id_solicitante:
                db.execute("UPDATE solicitante SET nombre=?, ci=?, matricula=?, tipo=?, telefono=? WHERE id_solicitante=?",
                           (d["nombre"], d["ci"], d["matricula"], d["tipo"], d["telefono"], id_solicitante))
            else:
                db.execute("INSERT INTO solicitante (nombre, ci, matricula, tipo, telefono) VALUES (?,?,?,?,?)",
                           (d["nombre"], d["ci"], d["matricula"], d["tipo"], d["telefono"]))
            return True, e
    return False, e


@bp.route("/nuevo", methods=["GET", "POST"])
@admin_requerido
def nuevo():
    e = {}
    if request.method == "POST":
        ok, e = _guardar()
        if ok:
            flash("Solicitante registrado.", "success")
            return redirect(url_for("solicitantes.lista"))
    return render_template("solicitantes/form.html", titulo="Registrar solicitante", f=request.form or {"tipo": "estudiante"}, errores=e)


@bp.route("/<int:id_solicitante>/editar", methods=["GET", "POST"])
@admin_requerido
def editar(id_solicitante):
    s = get_db().execute("SELECT * FROM solicitante WHERE id_solicitante = ?", (id_solicitante,)).fetchone()
    if s is None:
        abort(404)
    s = dict(s)
    e = {}
    if request.method == "POST":
        ok, e = _guardar(id_solicitante)
        if ok:
            flash("Datos del solicitante actualizados.", "success")
            return redirect(url_for("solicitantes.lista"))
        s = request.form
    return render_template("solicitantes/form.html", titulo="Modificar solicitante", f=s, errores=e)
