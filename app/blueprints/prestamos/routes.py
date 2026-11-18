"""Proceso 5.0: préstamos, devoluciones y renovaciones (RF09, RF10)."""
from datetime import date

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from ...extensions import db
from ...models import Ejemplar, Prestamo, TrabajoGrado
from ...seguridad import admin_requerido, login_requerido
from ...services import (
    ErrorNegocio,
    calcular_fecha_prevista,
    registrar_devolucion,
    registrar_prestamo,
    renovar_prestamo,
)
from ...utilidades import enlaces_pagina, paginar

bp = Blueprint("prestamos", __name__, url_prefix="/prestamos")


def _consulta_prestamos():
    return select(Prestamo).options(joinedload(Prestamo.ejemplar).joinedload(Ejemplar.trabajo),
                                    joinedload(Prestamo.solicitante))


@bp.route("/")
@login_requerido
def lista():
    ver = request.args.get("ver", "vigentes")
    consulta = _consulta_prestamos()
    if ver == "vigentes":
        consulta = consulta.where(Prestamo.estado == "vigente")
    elif ver == "vencidos":
        consulta = consulta.where(
            Prestamo.estado == "vigente",
            Prestamo.fecha_devolucion_prevista < date.today().isoformat(),
        )
    consulta = consulta.order_by(Prestamo.fecha_prestamo.desc(), Prestamo.id_prestamo.desc())
    paginacion = paginar(consulta)
    return render_template(
        "prestamos/lista.html",
        pag=paginacion,
        ver=ver,
        parametros=enlaces_pagina(),
    )


@bp.route("/nuevo", methods=["GET", "POST"])
@admin_requerido
def nuevo():
    formulario = (
        request.form
        if request.method == "POST"
        else {
            "tipo": "externo",
            "garantia": "ci",
            "id_ejemplar": request.args.get("ejemplar", ""),
        }
    )
    if request.method == "POST":
        try:
            id_prestamo = registrar_prestamo(
                int(request.form.get("id_ejemplar") or 0),
                request.form.get("documento"),
                request.form.get("tipo"),
                request.form.get("garantia"),
                (request.form.get("fecha_devolucion_prevista") or "").strip(),
                g.usuario.id_usuario,
            )
            flash("Préstamo registrado.", "success")
            return redirect(url_for("prestamos.comprobante", id_prestamo=id_prestamo))
        except ErrorNegocio as error:
            flash(str(error), "error")

    ejemplares = db.session.scalars(
        select(Ejemplar)
        .join(Ejemplar.trabajo)
        .where(Ejemplar.estado == "disponible", TrabajoGrado.activo.is_(True))
        .options(joinedload(Ejemplar.trabajo))
        .order_by(TrabajoGrado.titulo, Ejemplar.codigo)
    ).all()
    return render_template(
        "prestamos/form.html",
        f=formulario,
        ejemplares=ejemplares,
        prevista_externo=calcular_fecha_prevista("externo"),
    )


@bp.route("/<int:id_prestamo>/devolver", methods=["POST"])
@admin_requerido
def devolver(id_prestamo):
    try:
        registrar_devolucion(id_prestamo)
        flash("Devolución registrada. El ejemplar quedó disponible.", "success")
    except ErrorNegocio as error:
        flash(str(error), "error")
    return redirect(request.referrer or url_for("prestamos.lista"))


@bp.route("/<int:id_prestamo>/renovar", methods=["POST"])
@admin_requerido
def renovar(id_prestamo):
    try:
        renovar_prestamo(id_prestamo)
        flash("Préstamo renovado.", "success")
    except ErrorNegocio as error:
        flash(str(error), "error")
    return redirect(url_for("prestamos.lista"))


@bp.route("/<int:id_prestamo>/comprobante")
@login_requerido
def comprobante(id_prestamo):
    prestamo = db.session.scalar(
        _consulta_prestamos()
        .options(joinedload(Prestamo.usuario))
        .where(Prestamo.id_prestamo == id_prestamo)
    )
    if prestamo is None:
        abort(404)
    return render_template("prestamos/comprobante.html", p=prestamo)
