"""Registro centralizado de blueprints (monolito modular)."""
from .auth import bp as auth_bp
from .main import bp as main_bp
from .prestamos import bp as prestamos_bp
from .reportes import bp as reportes_bp
from .solicitantes import bp as solicitantes_bp
from .trabajos import bp as trabajos_bp


def registrar_blueprints(app):
    for blueprint in (main_bp, auth_bp, trabajos_bp, solicitantes_bp, prestamos_bp, reportes_bp):
        app.register_blueprint(blueprint)
