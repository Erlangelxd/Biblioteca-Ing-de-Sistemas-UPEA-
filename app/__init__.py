"""Aplicación Flask (patrón application factory) del Sistema de Registro y Control de Trabajos de Grado."""
from datetime import date

from flask import Flask, g, render_template, request

from . import db, seguridad
from .config import INSTANCE, Config
from .servicios import dias_retraso, estado_prestamo, puede_renovar
from .validacion import (ESTADOS_EJEMPLAR, GARANTIAS, MODALIDADES, TIPOS_PRESTAMO, TIPOS_SOLICITANTE)


def create_app(config=None):
    app = Flask(__name__, instance_path=str(INSTANCE))
    app.config.from_object(Config)
    if config:
        app.config.update(config)
    db.registrar_comandos(app)

    from . import auth, main, prestamos, reportes, solicitantes, trabajos
    for bp in (main.bp, auth.bp, trabajos.bp, solicitantes.bp, prestamos.bp, reportes.bp):
        app.register_blueprint(bp)

    @app.before_request
    def _antes():
        seguridad.cargar_usuario()
        seguridad.verificar_csrf()

    @app.after_request
    def _cabeceras(r):
        r.headers.setdefault("X-Content-Type-Options", "nosniff")
        r.headers.setdefault("X-Frame-Options", "DENY")
        r.headers.setdefault("Referrer-Policy", "same-origin")
        return r

    @app.context_processor
    def _contexto():
        u = g.get("usuario")
        return {"usuario": u, "puede_editar": bool(u and u["rol"] == "administrador"),
                "csrf_token": seguridad.token_csrf, "estado_prestamo": estado_prestamo,
                "dias_retraso": dias_retraso, "puede_renovar": puede_renovar,
                "MODALIDADES": MODALIDADES, "TIPOS_PRESTAMO": TIPOS_PRESTAMO, "GARANTIAS": GARANTIAS,
                "TIPOS_SOLICITANTE": TIPOS_SOLICITANTE, "ESTADOS_EJEMPLAR": ESTADOS_EJEMPLAR,
                "endpoint": request.endpoint or ""}

    @app.template_filter("fecha")
    def _fecha(valor):
        if not valor:
            return "—"
        try:
            return date.fromisoformat(str(valor)).strftime("%d/%m/%Y")
        except ValueError:
            return valor

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(500)
    def _error(e):
        codigo = getattr(e, "code", 500)
        mensaje = {400: getattr(e, "description", "Solicitud no válida."), 404: "La página no existe.",
                   500: "Ocurrió un error en el sistema."}.get(codigo, "Error.")
        return render_template("error.html", codigo=codigo, mensaje=mensaje), codigo

    return app
