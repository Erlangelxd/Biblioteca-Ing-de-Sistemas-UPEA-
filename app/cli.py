"""Comandos de consola: init-db, crear-usuario, seed-demo y backup."""
import sqlite3
from datetime import datetime
from pathlib import Path

import click
from flask import current_app
from sqlalchemy.engine import make_url

from .extensions import db
from .services import crear_usuario


def _ruta_sqlite():
    url = make_url(current_app.config["SQLALCHEMY_DATABASE_URI"])
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        raise click.ClickException("El respaldo solo está implementado para archivos SQLite.")
    return Path(url.database)


def registrar_comandos(app):
    @app.cli.command("init-db")
    def _init():
        """Crea las tablas definidas por los modelos ORM (no borra datos)."""
        db.create_all()
        click.echo("Base de datos lista: " + current_app.config["SQLALCHEMY_DATABASE_URI"])

    @app.cli.command("crear-usuario")
    @click.argument("nombre")
    @click.option("--rol", type=click.Choice(["administrador", "consulta"]), default="administrador")
    @click.password_option()
    def _crear(nombre, rol, password):
        """Crea un usuario (para el primer administrador)."""
        db.create_all()
        crear_usuario(nombre, password, rol)
        click.echo(f"Usuario «{nombre}» creado con rol {rol}.")

    @app.cli.command("seed-demo")
    def _seed():
        """Carga datos de ejemplo (ficticios). SOLO para pruebas o demostración."""
        from .seed import cargar

        db.create_all()
        click.echo(cargar())

    @app.cli.command("backup")
    @click.option("--destino", default=None, help="Carpeta de destino (por defecto, instance/respaldos).")
    def _backup(destino):
        """Copia de seguridad de la base de datos."""
        origen_path = _ruta_sqlite()
        if not origen_path.exists():
            raise click.ClickException("Todavía no existe la base de datos.")
        carpeta = Path(destino or origen_path.parent / "respaldos")
        carpeta.mkdir(parents=True, exist_ok=True)
        archivo = carpeta / f"biblioteca_{datetime.now():%Y%m%d_%H%M%S}.sqlite3"

        origen = sqlite3.connect(origen_path)
        copia = sqlite3.connect(archivo)
        with copia:
            origen.backup(copia)  # copia consistente aunque el sistema esté en uso
        origen.close()
        copia.close()
        click.echo(f"Respaldo creado: {archivo}")
