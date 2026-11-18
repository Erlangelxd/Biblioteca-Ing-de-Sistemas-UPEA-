"""Proceso 3.0: registrar y editar solicitantes (RF08)."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy import func, or_, select

from ... import validacion
from ...extensions import db, normalizar
from ...models import Solicitante
from ...seguridad import admin_requerido, login_requerido
from ...services import ErrorNegocio, guardar_solicitante
from ...utilidades import enlaces_pagina, paginar

bp = Blueprint("solicitantes", __name__, url_prefix="/solicitantes")


@bp.route("/")
@login_requerido
def lista():
    q = (request.args.get("q") or "").strip()
    consulta = select(Solicitante)
    if q:
        patron = f"%{normalizar(q)}%"
        consulta = consulta.where(
            or_(
                func.norm(Solicitante.nombre).like(patron),
                Solicitante.ci.like(f"%{q}%"),
                Solicitante.matricula.like(f"%{q}%"),
            )
        )
    paginacion = paginar(consulta.order_by(Solicitante.nombre))
    return render_template(
        "solicitantes/lista.html",
        pag=paginacion,
        q=q,
        parametros=enlaces_pagina(),
    )


def _guardar(id_solicitante=None):
    datos, errores = validacion.solicitante(request.form)
    if not errores:
        try:
            guardar_solicitante(datos, id_solicitante)
            return True, errores
        except ErrorNegocio as error:
            errores["ci"] = str(error)
    return False, errores


@bp.route("/nuevo", methods=["GET", "POST"])
@admin_requerido
def nuevo():
    errores = {}
    if request.method == "POST":
        guardado, errores = _guardar()
        if guardado:
            flash("Solicitante registrado.", "success")
            return redirect(url_for("solicitantes.lista"))
    return render_template(
        "solicitantes/form.html",
        titulo="Registrar solicitante",
        f=request.form or {"tipo": "estudiante"},
        errores=errores,
    )


@bp.route("/<int:id_solicitante>/editar", methods=["GET", "POST"])
@admin_requerido
def editar(id_solicitante):
    solicitante = db.session.get(Solicitante, id_solicitante)
    if solicitante is None:
        abort(404)

    errores = {}
    formulario = {
        "nombre": solicitante.nombre,
        "ci": solicitante.ci,
        "matricula": solicitante.matricula,
        "tipo": solicitante.tipo,
        "telefono": solicitante.telefono,
    }
    if request.method == "POST":
        guardado, errores = _guardar(id_solicitante)
        if guardado:
            flash("Datos del solicitante actualizados.", "success")
            return redirect(url_for("solicitantes.lista"))
        formulario = request.form
    return render_template(
        "solicitantes/form.html",
        titulo="Modificar solicitante",
        f=formulario,
        errores=errores,
    )
