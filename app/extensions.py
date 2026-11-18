"""Extensiones compartidas de Flask y utilidades de base de datos.

Aquí se concentra la instancia de SQLAlchemy (ORM) para evitar importaciones
circulares entre la fábrica de la aplicación, los modelos y los blueprints.
"""
import sqlite3
import unicodedata

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base declarativa de todos los modelos."""


db = SQLAlchemy(model_class=Base)


def normalizar(texto):
    """Minúsculas y sin tildes, para búsquedas tolerantes a acentos."""
    texto = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


@event.listens_for(Engine, "connect")
def _registrar_funciones_sqlite(dbapi_connection, connection_record):
    """Expone norm() en SQLite para filtrar sin tildes desde el ORM."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        dbapi_connection.create_function("norm", 1, normalizar, deterministic=True)
