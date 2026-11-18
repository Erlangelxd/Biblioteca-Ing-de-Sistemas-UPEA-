"""Servicio de solicitantes (RF08)."""
from sqlalchemy import select

from ..extensions import db
from ..models import Solicitante
from .base import ErrorNegocio, transaccion


def buscar_por_documento(documento):
    """Busca por CI o por matrícula (la matrícula vacía no participa)."""
    documento = (documento or "").strip()
    if not documento:
        return None
    return db.session.scalar(
        select(Solicitante).where(
            (Solicitante.ci == documento)
            | ((Solicitante.matricula != "") & (Solicitante.matricula == documento))
        )
    )


def guardar_solicitante(datos, id_solicitante=None):
    solicitante = db.session.get(Solicitante, id_solicitante) if id_solicitante else None
    if id_solicitante and solicitante is None:
        raise ErrorNegocio("El solicitante no existe.")

    repetido = db.session.scalar(
        select(Solicitante.id_solicitante).where(
            Solicitante.ci == datos["ci"],
            Solicitante.id_solicitante != (id_solicitante or 0),
        )
    )
    if repetido:
        raise ErrorNegocio("Ya hay un solicitante con esa CI.")

    with transaccion():
        if solicitante is None:
            solicitante = Solicitante()
            db.session.add(solicitante)
        solicitante.nombre = datos["nombre"]
        solicitante.ci = datos["ci"]
        solicitante.matricula = datos["matricula"]
        solicitante.tipo = datos["tipo"]
        solicitante.telefono = datos["telefono"]
    return solicitante
