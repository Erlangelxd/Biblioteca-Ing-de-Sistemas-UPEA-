"""Inicio y catálogo público."""
from datetime import date

from flask import Blueprint, abort, current_app, render_template, request
from sqlalchemy import func, select

from ...extensions import db
from ...models import AreaTematica, Prestamo, TrabajoGrado
from ...seguridad import login_requerido
from ...services.trabajos import consultar_trabajos
from ...utilidades import enlaces_pagina, fila_trabajo, paginar

bp = Blueprint("main", __name__)


@bp.route("/")
@login_requerido
def inicio():
    def contar(consulta):
        return db.session.scalar(consulta)

    return render_template(
        "inicio.html",
        total_trabajos=contar(
            select(func.count()).select_from(TrabajoGrado).where(TrabajoGrado.activo.is_(True))
        ),
        vigentes=contar(
            select(func.count()).select_from(Prestamo).where(Prestamo.estado == "vigente")
        ),
        vencidos=contar(
            select(func.count())
            .select_from(Prestamo)
            .where(
                Prestamo.estado == "vigente",
                Prestamo.fecha_devolucion_prevista < date.today().isoformat(),
            )
        ),
        recientes=contar(
            select(func.count())
            .select_from(TrabajoGrado)
            .where(func.substr(TrabajoGrado.fecha_recepcion, 1, 4) == str(date.today().year))
        ),
    )


@bp.route("/catalogo")
def catalogo():
    """Consulta pública de solo lectura, sin datos personales ni trabajos reservados."""
    if not current_app.config["CATALOGO_PUBLICO"]:
        abort(404)

    paginacion = paginar(consultar_trabajos(request.args, solo_publicables=True))
    areas = db.session.scalars(select(AreaTematica).order_by(AreaTematica.nombre)).all()
    anios = db.session.scalars(
        select(TrabajoGrado.gestion)
        .where(TrabajoGrado.activo.is_(True), TrabajoGrado.autoriza_publicacion.is_(True))
        .distinct()
        .order_by(TrabajoGrado.gestion.desc())
    ).all()
    return render_template(
        "catalogo.html",
        filas=[fila_trabajo(t) for t in paginacion.filas],
        pag=paginacion,
        g=request.args,
        areas=areas,
        anios=anios,
        parametros=enlaces_pagina(),
    )
