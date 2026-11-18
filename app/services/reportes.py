"""Servicios de reportes (RF11–RF19). Cada reporte devuelve un diccionario."""
from datetime import date, timedelta

from sqlalchemy import case, desc, func, select
from sqlalchemy.orm import joinedload, selectinload

from ..extensions import db, normalizar
from ..models import AreaTematica, Ejemplar, Prestamo, Solicitante, TrabajoGrado
from ..validacion import MODALIDADES, TIPOS_PRESTAMO
from .prestamos import dias_retraso, estado_prestamo

TXT_ESTADO = {"vigente": "Vigente", "vencido": "Vencido", "devuelto": "Devuelto"}


def _fecha(valor, defecto):
    try:
        return date.fromisoformat(valor) if valor else defecto
    except ValueError:
        return defecto


def _fmt(valor):
    """Fecha ISO -> dd/mm/aaaa para mostrar y exportar."""
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    if isinstance(valor, str) and len(valor) == 10 and valor[4] == "-":
        try:
            return date.fromisoformat(valor).strftime("%d/%m/%Y")
        except ValueError:
            return valor
    return valor


def _consulta_prestamos():
    return (
        select(Prestamo)
        .join(Prestamo.ejemplar)
        .join(Ejemplar.trabajo)
        .join(Prestamo.solicitante)
        .options(
            joinedload(Prestamo.ejemplar).joinedload(Ejemplar.trabajo),
            joinedload(Prestamo.solicitante),
        )
    )


def prestamos_activos(args):
    prestamos = db.session.scalars(
        _consulta_prestamos()
        .where(Prestamo.estado == "vigente")
        .order_by(Prestamo.fecha_devolucion_prevista)
    ).all()
    filas = [
        [
            i,
            p.ejemplar.codigo,
            p.ejemplar.trabajo.titulo,
            p.solicitante.nombre,
            TIPOS_PRESTAMO[p.tipo],
            p.fecha_prestamo,
            p.fecha_devolucion_prevista,
            TXT_ESTADO[estado_prestamo(p)],
        ]
        for i, p in enumerate(prestamos, 1)
    ]
    return {
        "titulo": "Reporte de préstamos activos",
        "columnas": ["N.º", "Código", "Título del trabajo", "Solicitante", "Tipo", "Préstamo", "Devolución prevista", "Estado"],
        "filas": filas,
        "total": f"Total de préstamos activos: {len(filas)}",
    }


def historial_usuario(args):
    q = (args.get("q") or "").strip()
    consulta = _consulta_prestamos()
    if q:
        patron = f"%{normalizar(q)}%"
        consulta = consulta.where(
            func.norm(Solicitante.nombre).like(patron)
            | (Solicitante.ci == q)
            | (Solicitante.matricula == q)
        )
    prestamos = db.session.scalars(
        consulta.order_by(Prestamo.fecha_prestamo.desc(), Prestamo.id_prestamo.desc())
    ).all()
    filas = [
        [
            i,
            p.solicitante.nombre,
            p.ejemplar.trabajo.titulo,
            p.fecha_prestamo,
            p.fecha_devolucion_real or "—",
            TXT_ESTADO[estado_prestamo(p)],
        ]
        for i, p in enumerate(prestamos, 1)
    ]
    return {
        "titulo": "Reporte de historial por usuario",
        "columnas": ["N.º", "Solicitante", "Trabajo", "Préstamo", "Devolución real", "Estado"],
        "filas": filas,
        "total": f"Total de préstamos: {len(filas)}",
        "filtro_q": True,
        "q": q,
    }


def mas_prestados(args):
    hasta = _fecha(args.get("hasta"), date.today())
    desde = _fecha(args.get("desde"), hasta - timedelta(days=365))
    veces = func.count(Prestamo.id_prestamo).label("n")
    filas_orm = db.session.execute(
        select(TrabajoGrado.titulo, TrabajoGrado.gestion, veces)
        .join(Ejemplar, Ejemplar.id_trabajo == TrabajoGrado.id_trabajo)
        .join(Prestamo, Prestamo.id_ejemplar == Ejemplar.id_ejemplar)
        .where(Prestamo.fecha_prestamo.between(desde.isoformat(), hasta.isoformat()))
        .group_by(TrabajoGrado.id_trabajo)
        .order_by(veces.desc(), TrabajoGrado.titulo)
        .limit(10)
    ).all()
    return {
        "titulo": "Reporte de trabajos más prestados",
        "columnas": ["N.º", "Título", "Gestión", "Veces prestado"],
        "filas": [[i, r.titulo, r.gestion, r.n] for i, r in enumerate(filas_orm, 1)],
        "total": f"Período: {desde:%d/%m/%Y} al {hasta:%d/%m/%Y}",
        "filtro_fechas": True,
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "barras": [(r.titulo[:40], r.n) for r in filas_orm],
    }


def disponibilidad(args):
    total = func.sum(case((Ejemplar.estado != "baja", 1), else_=0))
    disponibles = func.sum(case((Ejemplar.estado == "disponible", 1), else_=0))
    filas_orm = db.session.execute(
        select(TrabajoGrado.titulo, total.label("total"), disponibles.label("disp"))
        .outerjoin(Ejemplar, Ejemplar.id_trabajo == TrabajoGrado.id_trabajo)
        .where(TrabajoGrado.activo.is_(True))
        .group_by(TrabajoGrado.id_trabajo)
        .order_by(TrabajoGrado.titulo)
    ).all()
    filas = [
        [i, r.titulo, r.total or 0, r.disp or 0, (r.total or 0) - (r.disp or 0)]
        for i, r in enumerate(filas_orm, 1)
    ]
    return {
        "titulo": "Reporte de disponibilidad de ejemplares",
        "columnas": ["N.º", "Trabajo", "Ejemplares", "Disponibles", "Prestados o en consulta"],
        "filas": filas,
        "total": f"Total de trabajos: {len(filas)}",
    }


def por_area(args):
    cantidad = func.count(TrabajoGrado.id_trabajo)
    filas_orm = db.session.execute(
        select(func.coalesce(AreaTematica.nombre, "Sin área asignada"), cantidad.label("n"))
        .select_from(TrabajoGrado)
        .outerjoin(AreaTematica, AreaTematica.id_area == TrabajoGrado.id_area)
        .where(TrabajoGrado.activo.is_(True))
        .group_by(AreaTematica.id_area)
        .order_by(cantidad.desc(), AreaTematica.nombre)
    ).all()
    filas = [[i, r[0], r.n] for i, r in enumerate(filas_orm, 1)]
    return {
        "titulo": "Reporte de trabajos por área temática",
        "columnas": ["N.º", "Área temática", "Trabajos"],
        "filas": filas,
        "total": f"Total de trabajos activos: {sum(f[2] for f in filas)}",
        "barras": [(f[1], f[2]) for f in filas],
    }


def estadisticas(args):
    pre = dict(
        db.session.execute(
            select(func.substr(Prestamo.fecha_prestamo, 1, 7), func.count())
            .group_by(func.substr(Prestamo.fecha_prestamo, 1, 7))
        ).all()
    )
    dev = dict(
        db.session.execute(
            select(func.substr(Prestamo.fecha_devolucion_real, 1, 7), func.count())
            .where(Prestamo.fecha_devolucion_real.is_not(None))
            .group_by(func.substr(Prestamo.fecha_devolucion_real, 1, 7))
        ).all()
    )
    meses = sorted(set(pre) | set(dev))
    filas = [[f"{m[5:]}/{m[:4]}", pre.get(m, 0), dev.get(m, 0)] for m in meses]
    return {
        "titulo": "Reporte de estadísticas de uso",
        "columnas": ["Mes", "Préstamos y consultas", "Devoluciones"],
        "filas": filas,
        "total": f"Total de préstamos registrados: {sum(pre.values())}",
        "barras": [(f[0], f[1]) for f in filas],
    }


def alertas_retraso(args):
    prestamos = db.session.scalars(
        _consulta_prestamos()
        .where(
            Prestamo.estado == "vigente",
            Prestamo.fecha_devolucion_prevista < date.today().isoformat(),
        )
        .order_by(Prestamo.fecha_devolucion_prevista)
    ).all()
    filas = [
        [
            i,
            p.solicitante.nombre,
            p.solicitante.ci,
            p.solicitante.telefono or "—",
            p.ejemplar.trabajo.titulo,
            p.fecha_devolucion_prevista,
            dias_retraso(p),
        ]
        for i, p in enumerate(prestamos, 1)
    ]
    return {
        "titulo": "Alertas de retraso en devoluciones",
        "columnas": ["N.º", "Solicitante", "CI", "Teléfono", "Trabajo", "Devolución prevista", "Días de retraso"],
        "filas": filas,
        "total": f"Fecha de corte: {date.today():%d/%m/%Y} — Total con retraso: {len(filas)}",
    }


def nuevas_adquisiciones(args):
    hasta = _fecha(args.get("hasta"), date.today())
    desde = _fecha(args.get("desde"), hasta - timedelta(days=90))
    trabajos = db.session.scalars(
        select(TrabajoGrado)
        .options(selectinload(TrabajoGrado.autores))
        .where(TrabajoGrado.fecha_recepcion.between(desde.isoformat(), hasta.isoformat()))
        .order_by(desc(TrabajoGrado.fecha_recepcion))
    ).all()
    filas = [
        [
            i,
            t.titulo,
            t.autores_texto,
            t.gestion,
            MODALIDADES[t.modalidad],
            t.fecha_recepcion,
        ]
        for i, t in enumerate(trabajos, 1)
    ]
    return {
        "titulo": "Reporte de nuevas adquisiciones",
        "columnas": ["N.º", "Título", "Autor(es)", "Gestión", "Modalidad", "Recepción"],
        "filas": filas,
        "total": f"Período: {desde:%d/%m/%Y} al {hasta:%d/%m/%Y} — Total: {len(filas)}",
        "filtro_fechas": True,
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
    }


def comparativo_anual(args):
    def por_anio(columna, filtro=None):
        consulta = select(func.substr(columna, 1, 4), func.count())
        if filtro is not None:
            consulta = consulta.where(filtro)
        consulta = consulta.group_by(func.substr(columna, 1, 4))
        return dict(db.session.execute(consulta).all())

    prestamos = por_anio(Prestamo.fecha_prestamo)
    devoluciones = por_anio(Prestamo.fecha_devolucion_real, Prestamo.fecha_devolucion_real.is_not(None))
    recibidos = por_anio(TrabajoGrado.fecha_recepcion)
    filas = [
        [int(anio), prestamos.get(anio, 0), devoluciones.get(anio, 0), recibidos.get(anio, 0)]
        for anio in sorted(set(prestamos) | set(devoluciones) | set(recibidos))
    ]
    return {
        "titulo": "Reporte comparativo anual",
        "columnas": ["Año", "Préstamos y consultas", "Devoluciones", "Trabajos recibidos"],
        "filas": filas,
        "total": f"Años con movimiento: {len(filas)}",
        "barras": [(str(f[0]), f[1]) for f in filas],
    }


REPORTES = {
    "prestamos-activos": ("Préstamos activos", "RF11", prestamos_activos),
    "historial-usuario": ("Historial por usuario", "RF12", historial_usuario),
    "mas-prestados": ("Trabajos más prestados", "RF13", mas_prestados),
    "disponibilidad": ("Disponibilidad de ejemplares", "RF14", disponibilidad),
    "por-area": ("Trabajos por área temática", "RF15", por_area),
    "estadisticas": ("Estadísticas de uso", "RF16", estadisticas),
    "alertas-retraso": ("Alertas de retraso", "RF17", alertas_retraso),
    "nuevas-adquisiciones": ("Nuevas adquisiciones", "RF18", nuevas_adquisiciones),
    "comparativo-anual": ("Comparativo anual", "RF19", comparativo_anual),
}
