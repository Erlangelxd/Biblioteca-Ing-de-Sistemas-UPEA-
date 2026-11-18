"""Acceso a la base de datos SQLite (módulo estándar sqlite3)."""
import sqlite3
import unicodedata
from datetime import date
from pathlib import Path

import click
from flask import current_app, g


def _norm(texto):
    """Minúsculas y sin tildes, para que 'programacion' encuentre 'Programación'."""
    texto = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def get_db():
    if "db" not in g:
        Path(current_app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(current_app.config["DATABASE"], isolation_level=None)  # transacciones manuales
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.create_function("norm", 1, _norm, deterministic=True)
    return g.db


def cerrar_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def hoy():
    return date.today().isoformat()


class transaccion:
    """with transaccion(db): ...  -> BEGIN IMMEDIATE / COMMIT, y ROLLBACK si hay error."""

    def __init__(self, db):
        self.db = db

    def __enter__(self):
        self.db.execute("BEGIN IMMEDIATE")

    def __exit__(self, tipo, valor, tb):
        self.db.execute("ROLLBACK" if tipo else "COMMIT")
        return False


def init_db():
    db = get_db()
    db.executescript((Path(__file__).parent / "schema.sql").read_text(encoding="utf-8"))


def registrar_comandos(app):
    app.teardown_appcontext(cerrar_db)

    @app.cli.command("init-db")
    def _init():
        """Crea las tablas (no borra datos existentes)."""
        init_db()
        click.echo("Base de datos lista: " + app.config["DATABASE"])

    @app.cli.command("crear-usuario")
    @click.argument("nombre")
    @click.option("--rol", type=click.Choice(["administrador", "consulta"]), default="administrador")
    @click.password_option()
    def _crear(nombre, rol, password):
        """Crea un usuario (para el primer administrador)."""
        from .servicios import crear_usuario
        init_db()
        crear_usuario(get_db(), nombre, password, rol)
        click.echo(f"Usuario «{nombre}» creado con rol {rol}.")

    @app.cli.command("seed-demo")
    def _seed():
        """Carga datos de ejemplo (ficticios). SOLO para pruebas o demostración."""
        from .seed import cargar
        init_db()
        click.echo(cargar(get_db()))

    @app.cli.command("backup")
    @click.option("--destino", default=None, help="Carpeta de destino (por defecto, instance/respaldos).")
    def _backup(destino):
        """Copia de seguridad de la base de datos (RNF14)."""
        from datetime import datetime
        carpeta = Path(destino or Path(app.config["DATABASE"]).parent / "respaldos")
        carpeta.mkdir(parents=True, exist_ok=True)
        archivo = carpeta / f"biblioteca_{datetime.now():%Y%m%d_%H%M%S}.sqlite3"
        origen = sqlite3.connect(app.config["DATABASE"])
        copia = sqlite3.connect(archivo)
        with copia:
            origen.backup(copia)  # copia consistente aunque el sistema esté en uso
        origen.close(); copia.close()
        click.echo(f"Respaldo creado: {archivo}")
