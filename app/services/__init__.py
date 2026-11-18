"""Capa de servicios: reglas de negocio y consultas de la aplicación."""
from .base import ErrorNegocio, transaccion
from .prestamos import (
    calcular_fecha_prevista,
    dias_retraso,
    estado_prestamo,
    puede_renovar,
    registrar_devolucion,
    registrar_prestamo,
    renovar_prestamo,
)
from .solicitantes import buscar_por_documento, guardar_solicitante
from .trabajos import (
    agregar_ejemplar,
    consultar_trabajos,
    dar_de_baja,
    modificar_trabajo,
    registrar_trabajo,
)
from .usuarios import cambiar_clave, crear_usuario, validar_clave

__all__ = [
    "ErrorNegocio",
    "transaccion",
    "calcular_fecha_prevista",
    "dias_retraso",
    "estado_prestamo",
    "puede_renovar",
    "registrar_devolucion",
    "registrar_prestamo",
    "renovar_prestamo",
    "buscar_por_documento",
    "guardar_solicitante",
    "agregar_ejemplar",
    "consultar_trabajos",
    "dar_de_baja",
    "modificar_trabajo",
    "registrar_trabajo",
    "cambiar_clave",
    "crear_usuario",
    "validar_clave",
]
