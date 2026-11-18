"""Modelos ORM del sistema. Se importan todos para que create_all los registre."""
from .catalogo import AreaTematica, Autor, Tutor
from .prestamo import Prestamo
from .solicitante import Solicitante
from .trabajo import Ejemplar, TrabajoGrado, trabajo_autor
from .usuario import Usuario

__all__ = [
    "AreaTematica",
    "Autor",
    "Tutor",
    "TrabajoGrado",
    "Ejemplar",
    "trabajo_autor",
    "Solicitante",
    "Prestamo",
    "Usuario",
]
