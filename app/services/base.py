"""Base de la capa de servicios: errores de negocio y transacciones."""
from contextlib import contextmanager

from ..extensions import db


class ErrorNegocio(Exception):
    """Error controlado que se muestra a la persona usuaria."""


@contextmanager
def transaccion():
    """Confirma la unidad de trabajo o revierte todo si hay cualquier error."""
    try:
        yield
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
