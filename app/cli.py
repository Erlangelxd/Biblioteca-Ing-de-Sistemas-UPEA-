"""Comandos de consola: init-db, crear-usuario, seed-demo y backup."""
import sqlite3
from datetime import datetime
from pathlib import Path

import click
from flask import current_app
from sqlalchemy.engine import make_url

from .extensions import db
from .migraciones import migrar_modalidad_libro
from .services import crear_usuario


def _ruta_sqlite():
    url = make_url(current_app.config["SQLALCHEMY_DATABASE_URI"])
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        raise click.ClickException("Esta operación solo está implementada para archivos SQLite.")
    return Path(url.database)


def _actualizar_esquema():
    """Crea las tablas y aplica migraciones ligeras sobre bases existentes."""
    ruta = _ruta_sqlite()
    db.session.remove()
    if ruta.exists():
        migrar_modalidad_libro(ruta)
    db.create_all()


def registrar_comandos(app):
    @app.cli.command("init-db")
    def _init():
        """Crea las tablas definidas por los modelos ORM (no borra datos)."""
        _actualizar_esquema()
        click.echo("Base de datos lista: " + current_app.config["SQLALCHEMY_DATABASE_URI"])

    @app.cli.command("migrar-db")
    def _migrar():
        """Actualiza el esquema SQLite para admitir la modalidad «Libro»."""
        ruta = _ruta_sqlite()
        db.session.remove()
        cambiado = migrar_modalidad_libro(ruta) if ruta.exists() else False
        db.create_all()
        if cambiado:
            click.echo("Esquema actualizado: modalidad «Libro» habilitada.")
        else:
            click.echo("El esquema ya está actualizado.")

    @app.cli.command("crear-usuario")
    @click.argument("nombre")
    @click.option("--rol", type=click.Choice(["administrador", "consulta"]), default="administrador")
    @click.password_option()
    def _crear(nombre, rol, password):
        """Crea un usuario (para el primer administrador)."""
        _actualizar_esquema()
        crear_usuario(nombre, password, rol)
        click.echo(f"Usuario «{nombre}» creado con rol {rol}.")

    @app.cli.command("seed-demo")
    def _seed():
        """Carga datos de ejemplo (ficticios). SOLO para pruebas o demostración."""
        from .seed import cargar

        _actualizar_esquema()
        click.echo(cargar())

    @app.cli.command("seed-libros")
    def _seed_libros():
        """Carga libros famosos de desarrollo de software sin borrar datos."""
        from .seed import cargar_libros

        _actualizar_esquema()
        click.echo(cargar_libros())

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
