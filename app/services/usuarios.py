"""Servicio de usuarios y contraseñas (RF01, RF02)."""
from sqlalchemy import select
from werkzeug.security import generate_password_hash

from ..extensions import db
from ..models import Usuario
from .base import ErrorNegocio, transaccion

ROLES = ("administrador", "consulta")


def validar_clave(clave):
    if len(clave or "") < 8:
        raise ErrorNegocio("La contraseña debe tener al menos 8 caracteres.")


def crear_usuario(nombre, clave, rol="consulta"):
    nombre = (nombre or "").strip()
    if not 3 <= len(nombre) <= 30:
        raise ErrorNegocio("El nombre de usuario debe tener entre 3 y 30 caracteres.")
    if rol not in ROLES:
        raise ErrorNegocio("Rol no válido.")
    validar_clave(clave)
    if db.session.scalar(select(Usuario.id_usuario).where(Usuario.nombre_usuario == nombre)):
        raise ErrorNegocio("Ya existe un usuario con ese nombre.")

    usuario = Usuario(nombre_usuario=nombre, contrasena=generate_password_hash(clave), rol=rol)
    with transaccion():
        db.session.add(usuario)
    return usuario


def cambiar_clave(usuario, clave):
    validar_clave(clave)
    with transaccion():
        usuario.contrasena = generate_password_hash(clave)
