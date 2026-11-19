"""Procesos 2.0 y 4.0: trabajos de grado y ejemplares (RF03–RF07)."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy import desc, select
from sqlalchemy.orm import joinedload

from ... import validacion
from ...extensions import db
from ...models import AreaTematica, Ejemplar, Prestamo, TrabajoGrado
from ...seguridad import admin_requerido, login_requerido
from ...services import ErrorNegocio, agregar_ejemplar, dar_de_baja, modificar_trabajo, registrar_trabajo
from ...services.trabajos import consultar_trabajos
from ...utilidades import enlaces_pagina, estado_trabajo, fila_trabajo, paginar

bp = Blueprint("trabajos", __name__, url_prefix="/trabajos")


def _catalogos():
    return {"areas": db.session.scalars(select(AreaTematica).order_by(AreaTematica.nombre)).all()}


def _anios():
    return db.session.scalars(
        select(TrabajoGrado.gestion).distinct().order_by(TrabajoGrado.gestion.desc())
    ).all()


@bp.route("/")
@login_requerido
def lista():
    paginacion = paginar(consultar_trabajos(request.args))
    return render_template(
        "trabajos/lista.html",
        filas=[fila_trabajo(t) for t in paginacion.filas],
        pag=paginacion,
        g=request.args,
        parametros=enlaces_pagina(),
        anios=_anios(),
        **_catalogos(),
    )


@bp.route("/<int:id_trabajo>")
@login_requerido
def detalle(id_trabajo):
    trabajo = db.session.get(TrabajoGrado, id_trabajo)
    if trabajo is None:
        abort(404)

    historial = db.session.scalars(
        select(Prestamo)
        .join(Prestamo.ejemplar)
        .where(Ejemplar.id_trabajo == id_trabajo)
        .options(joinedload(Prestamo.solicitante), joinedload(Prestamo.ejemplar))
        .order_by(desc(Prestamo.fecha_prestamo), desc(Prestamo.id_prestamo))
        .limit(20)
    ).all()
    return render_template(
        "trabajos/detalle.html",
        t=trabajo,
        autores=[a.nombre for a in trabajo.autores],
        ejemplares=trabajo.ejemplares,
        historial=historial,
        estado=estado_trabajo(trabajo.total_ejemplares, trabajo.disponibles, trabajo.activo),
    )


def _form(titulo, f, errores, editar, trabajo=None):
    return render_template(
        "trabajos/form.html",
        titulo=titulo,
        f=f,
        errores=errores,
        editar=editar,
        t=trabajo,
        **_catalogos(),
    )


@bp.route("/nuevo", methods=["GET", "POST"])
@admin_requerido
def nuevo():
    if request.method == "POST":
        datos, errores = validacion.trabajo(request.form, nuevo=True)
        if not errores:
            try:
                id_trabajo = registrar_trabajo(datos)
                flash("Material registrado correctamente.", "success")
                return redirect(url_for("trabajos.detalle", id_trabajo=id_trabajo))
            except ErrorNegocio as error:
                errores["titulo"] = str(error)
        return _form("Registrar material bibliográfico", request.form, errores, False)
    return _form("Registrar material bibliográfico", {"num_ejemplares": 1, "modalidad": "proyecto"}, {}, False)


@bp.route("/<int:id_trabajo>/editar", methods=["GET", "POST"])
@admin_requerido
def editar(id_trabajo):
    trabajo = db.session.get(TrabajoGrado, id_trabajo)
    if trabajo is None or not trabajo.activo:
        abort(404)

    if request.method == "POST":
        datos, errores = validacion.trabajo(request.form, nuevo=False)
        if not errores:
            try:
                modificar_trabajo(id_trabajo, datos)
                flash("Datos del material actualizados.", "success")
                return redirect(url_for("trabajos.detalle", id_trabajo=id_trabajo))
            except ErrorNegocio as error:
                errores["titulo"] = str(error)
        return _form("Modificar material bibliográfico", request.form, errores, True, trabajo)

    formulario = {
        "titulo": trabajo.titulo,
        "resumen": trabajo.resumen,
        "gestion": trabajo.gestion,
        "modalidad": trabajo.modalidad,
        "fecha_recepcion": trabajo.fecha_recepcion,
        "autores": trabajo.autores_texto,
        "tutor_nombre": trabajo.tutor.nombre if trabajo.tutor else "",
        "id_area": trabajo.id_area,
        "area_nueva": "",
        "cd_entregado": trabajo.cd_entregado,
        "autoriza_publicacion": trabajo.autoriza_publicacion,
    }
    return _form("Modificar material bibliográfico", formulario, {}, True, trabajo)


@bp.route("/<int:id_trabajo>/baja", methods=["POST"])
@admin_requerido
def baja(id_trabajo):
    try:
        dar_de_baja(id_trabajo)
        flash("El trabajo fue dado de baja. Su historial se conserva.", "success")
        return redirect(url_for("trabajos.lista"))
    except ErrorNegocio as error:
        flash(str(error), "error")
        return redirect(url_for("trabajos.detalle", id_trabajo=id_trabajo))


@bp.route("/<int:id_trabajo>/ejemplar", methods=["POST"])
@admin_requerido
def ejemplar_nuevo(id_trabajo):
    try:
        agregar_ejemplar(id_trabajo, request.form.get("ubicacion"))
        flash("Ejemplar agregado.", "success")
    except ErrorNegocio as error:
        flash(str(error), "error")
    return redirect(url_for("trabajos.detalle", id_trabajo=id_trabajo))
