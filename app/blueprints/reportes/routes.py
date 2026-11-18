"""Proceso 6.0: reportes, impresión y exportación CSV (RF11–RF20)."""
import csv
import io
from datetime import date

from flask import Blueprint, Response, abort, render_template, request

from ...seguridad import login_requerido
from ...services.reportes import REPORTES, _fmt

bp = Blueprint("reportes", __name__, url_prefix="/reportes")


@bp.route("/")
@login_requerido
def indice():
    return render_template(
        "reportes/indice.html",
        reportes=[(clave, datos[0], datos[1]) for clave, datos in REPORTES.items()],
    )


@bp.route("/<clave>")
@login_requerido
def ver(clave):
    if clave not in REPORTES:
        abort(404)

    datos = REPORTES[clave][2](request.args)
    datos["filas"] = [[_fmt(celda) for celda in fila] for fila in datos["filas"]]

    if request.args.get("formato") == "csv":  # exportación adicional
        salida = io.StringIO()
        escritor = csv.writer(salida)
        escritor.writerow(datos["columnas"])
        escritor.writerows(datos["filas"])
        return Response(
            "﻿" + salida.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={clave}.csv"},
        )

    barras = datos.get("barras") or []
    maximo = max([barra[1] for barra in barras], default=0) or 1
    datos["barras"] = [(etiqueta, valor, int(valor * 100 / maximo)) for etiqueta, valor in barras]
    return render_template("reportes/ver.html", clave=clave, hoy=date.today(), **datos)
