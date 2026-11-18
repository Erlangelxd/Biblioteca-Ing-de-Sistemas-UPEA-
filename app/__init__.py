"""Fábrica de la aplicación (patrón creacional Factory Method).

La arquitectura es un monolito modular: fábrica → blueprints → servicios →
modelos ORM. `create_app` selecciona la configuración y compone los módulos.
"""
import os
from datetime import date

from flask import Flask, g, render_template, request

from . import models, seguridad  # noqa: F401  (registra los modelos en el metadata)
from .blueprints import registrar_blueprints
from .cli import registrar_comandos
from .config import CONFIGS, INSTANCE
from .extensions import db
from .services import dias_retraso, estado_prestamo, puede_renovar
from .validacion import (
    ESTADOS_EJEMPLAR,
    GARANTIAS,
    MODALIDADES,
    TIPOS_PRESTAMO,
    TIPOS_SOLICITANTE,
)


def create_app(config_name=None, overrides=None):
    """Factory Method: construye y configura una instancia de la aplicación."""
    app = Flask(__name__, instance_path=str(INSTANCE))
    nombre = config_name or os.environ.get("APP_ENV", "development")
    app.config.from_object(CONFIGS.get(nombre, CONFIGS["development"]))
    if overrides:
        app.config.update(overrides)

    db.init_app(app)
    registrar_blueprints(app)
    registrar_comandos(app)

    @app.teardown_appcontext
    def _cerrar_sesion(exc=None):
        db.session.remove()

    @app.before_request
    def _antes():
        seguridad.cargar_usuario()
        seguridad.verificar_csrf()

    @app.after_request
    def _cabeceras(respuesta):
        respuesta.headers.setdefault("X-Content-Type-Options", "nosniff")
        respuesta.headers.setdefault("X-Frame-Options", "DENY")
        respuesta.headers.setdefault("Referrer-Policy", "same-origin")
        return respuesta

    @app.context_processor
    def _contexto():
        usuario = g.get("usuario")
        return {
            "usuario": usuario,
            "puede_editar": bool(usuario and usuario.rol == "administrador"),
            "csrf_token": seguridad.token_csrf,
            "estado_prestamo": estado_prestamo,
            "dias_retraso": dias_retraso,
            "puede_renovar": puede_renovar,
            "MODALIDADES": MODALIDADES,
            "TIPOS_PRESTAMO": TIPOS_PRESTAMO,
            "GARANTIAS": GARANTIAS,
            "TIPOS_SOLICITANTE": TIPOS_SOLICITANTE,
            "ESTADOS_EJEMPLAR": ESTADOS_EJEMPLAR,
            "endpoint": request.endpoint or "",
        }

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
    def _error(error):
        codigo = getattr(error, "code", 500)
        mensaje = {
            400: getattr(error, "description", "Solicitud no válida."),
            404: "La página no existe.",
            500: "Ocurrió un error en el sistema.",
        }.get(codigo, "Error.")
        return render_template("error.html", codigo=codigo, mensaje=mensaje), codigo

    return app
