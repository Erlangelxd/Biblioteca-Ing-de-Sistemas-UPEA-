"""Servicio de préstamos, devoluciones y renovaciones (RF09, RF10)."""
from datetime import date, timedelta

from flask import current_app
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Ejemplar, Prestamo, Solicitante
from .base import ErrorNegocio, transaccion
from .solicitantes import buscar_por_documento


def calcular_fecha_prevista(tipo, desde=None):
    desde = desde or date.today()
    if tipo == "interno":
        return desde.isoformat()  # consulta en sala: se devuelve el mismo día
    return (desde + timedelta(days=current_app.config["DIAS_PRESTAMO_EXTERNO"])).isoformat()


def estado_prestamo(prestamo):
    """'devuelto', 'vencido' o 'vigente' (RF10)."""
    if prestamo.estado == "devuelto":
        return "devuelto"
    return "vencido" if prestamo.fecha_devolucion_prevista < date.today().isoformat() else "vigente"


def dias_retraso(prestamo):
    if estado_prestamo(prestamo) != "vencido":
        return 0
    return (date.today() - date.fromisoformat(prestamo.fecha_devolucion_prevista)).days


def puede_renovar(prestamo):
    return (
        prestamo.estado == "vigente"
        and prestamo.tipo == "externo"
        and prestamo.renovaciones < current_app.config["MAX_RENOVACIONES"]
        and estado_prestamo(prestamo) == "vigente"
    )


def registrar_prestamo(id_ejemplar, documento, tipo, garantia, fecha_prevista, id_usuario):
    """RF09: registra el préstamo y cambia el estado del ejemplar en una transacción."""
    if tipo not in ("interno", "externo") or garantia not in ("ci", "matricula", "ninguna"):
        raise ErrorNegocio("Tipo o garantía no válidos.")

    solicitante = buscar_por_documento(documento)
    if solicitante is None:
        raise ErrorNegocio("No hay un solicitante con esa CI o matrícula. Regístrelo primero.")

    if tipo == "interno":
        # La consulta en sala se devuelve el mismo día, sin importar la fecha enviada.
        fecha_prevista = calcular_fecha_prevista("interno")
    elif fecha_prevista:
        try:
            date.fromisoformat(fecha_prevista)
        except ValueError:
            raise ErrorNegocio("La fecha de devolución prevista no es válida.")
        if fecha_prevista < date.today().isoformat():
            raise ErrorNegocio("La fecha de devolución prevista no puede ser anterior a hoy.")
    else:
        fecha_prevista = calcular_fecha_prevista(tipo)

    try:
        with transaccion():
            if tipo == "externo":
                vigentes = db.session.scalar(
                    select(func.count())
                    .select_from(Prestamo)
                    .where(
                        Prestamo.id_solicitante == solicitante.id_solicitante,
                        Prestamo.estado == "vigente",
                        Prestamo.tipo == "externo",
                    )
                )
                maximo = current_app.config["MAX_PRESTAMOS_EXTERNOS"]
                if vigentes >= maximo:
                    raise ErrorNegocio(
                        f"El solicitante ya tiene {vigentes} préstamos a domicilio vigentes (máximo {maximo})."
                    )

            ejemplar = db.session.get(Ejemplar, id_ejemplar)
            if ejemplar is None or ejemplar.estado != "disponible" or not ejemplar.trabajo.activo:
                raise ErrorNegocio("Ese ejemplar no está disponible.")

            ejemplar.estado = "en_consulta" if tipo == "interno" else "en_prestamo"
            prestamo = Prestamo(
                id_ejemplar=ejemplar.id_ejemplar,
                id_solicitante=solicitante.id_solicitante,
                id_usuario=id_usuario,
                tipo=tipo,
                garantia=garantia,
                fecha_prestamo=date.today().isoformat(),
                fecha_devolucion_prevista=fecha_prevista,
            )
            db.session.add(prestamo)
            db.session.flush()
            id_prestamo = prestamo.id_prestamo
        return id_prestamo
    except IntegrityError:
        # El índice único parcial impide dos préstamos vigentes del mismo ejemplar.
        raise ErrorNegocio("Ese ejemplar no está disponible.")


def registrar_devolucion(id_prestamo):
    """RF10: marca el préstamo como devuelto y libera el ejemplar."""
    prestamo = db.session.get(Prestamo, id_prestamo)
    if prestamo is None or prestamo.estado != "vigente":
        raise ErrorNegocio("El préstamo no existe o ya fue devuelto.")

    with transaccion():
        prestamo.estado = "devuelto"
        prestamo.fecha_devolucion_real = date.today().isoformat()
        if prestamo.ejemplar.estado != "baja":
            prestamo.ejemplar.estado = "disponible"


def renovar_prestamo(id_prestamo):
    prestamo = db.session.get(Prestamo, id_prestamo)
    if prestamo is None or not puede_renovar(prestamo):
        raise ErrorNegocio("Este préstamo no se puede renovar.")

    with transaccion():
        prestamo.renovaciones += 1
        prestamo.fecha_devolucion_prevista = (
            date.fromisoformat(prestamo.fecha_devolucion_prevista)
            + timedelta(days=current_app.config["DIAS_PRESTAMO_EXTERNO"])
        ).isoformat()
