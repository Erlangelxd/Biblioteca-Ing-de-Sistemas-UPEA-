"""Servicio del agregado Trabajo de Grado y sus ejemplares (RF03–RF07)."""
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload, selectinload

from ..domain.builders import TrabajoGradoBuilder
from ..extensions import db, normalizar
from ..models import AreaTematica, Autor, Ejemplar, Prestamo, TrabajoGrado, Tutor
from ..validacion import MODALIDADES
from .base import ErrorNegocio, transaccion


def _area_por_nombre(nombre):
    area = db.session.scalar(
        select(AreaTematica).where(func.lower(AreaTematica.nombre) == nombre.lower())
    )
    return area or AreaTematica(nombre=nombre)


def _tutor_por_nombre(nombre):
    tutor = db.session.scalar(select(Tutor).where(func.lower(Tutor.nombre) == nombre.lower()))
    return tutor or Tutor(nombre=nombre)


def _resolver_autores(nombres):
    autores, vistos = [], set()
    for nombre in nombres:
        clave = nombre.lower()
        if clave in vistos:
            continue
        vistos.add(clave)
        autor = db.session.scalar(select(Autor).where(func.lower(Autor.nombre) == clave))
        autores.append(autor or Autor(nombre=nombre))
    return autores


def existe_duplicado(titulo, gestion, excepto=None):
    consulta = select(TrabajoGrado.id_trabajo).where(
        func.lower(TrabajoGrado.titulo) == titulo.lower(),
        TrabajoGrado.gestion == gestion,
    )
    if excepto:
        consulta = consulta.where(TrabajoGrado.id_trabajo != excepto)
    return db.session.scalar(consulta) is not None


def _resolver_area(datos):
    if datos.get("id_area"):
        return db.session.get(AreaTematica, datos["id_area"])
    if datos.get("area_nueva"):
        return _area_por_nombre(datos["area_nueva"])
    return None


def registrar_trabajo(datos):
    """RF03: registra trabajo, autores, área, tutor y ejemplares en una transacción."""
    if existe_duplicado(datos["titulo"], datos["gestion"]):
        raise ErrorNegocio("Ya existe un trabajo con ese título y esa gestión.")

    area = _resolver_area(datos)
    tutor = _tutor_por_nombre(datos["tutor_nombre"]) if datos.get("tutor_nombre") else None
    autores = _resolver_autores(datos["autores"])

    constructor = (
        TrabajoGradoBuilder(datos["titulo"], datos["gestion"], datos["modalidad"], datos["fecha_recepcion"])
        .con_resumen(datos["resumen"])
        .con_cd(datos["cd_entregado"])
        .con_autorizacion(datos["autoriza_publicacion"])
        .con_area(area)
        .con_tutor(tutor)
        .con_autores(autores)
        .con_ejemplares(datos["num_ejemplares"], datos["ubicacion"])
    )

    with transaccion():
        trabajo = constructor.construir()
        db.session.add(trabajo)
        db.session.flush()  # asigna id_trabajo para generar los códigos de ejemplar
        trabajo.ejemplares.extend(constructor.crear_ejemplares(trabajo.id_trabajo))
        id_trabajo = trabajo.id_trabajo
    return id_trabajo


def modificar_trabajo(id_trabajo, datos):
    """RF04: corrige los datos del trabajo y sus autores."""
    trabajo = db.session.get(TrabajoGrado, id_trabajo)
    if trabajo is None or not trabajo.activo:
        raise ErrorNegocio("El trabajo no existe o está dado de baja.")
    if existe_duplicado(datos["titulo"], datos["gestion"], excepto=id_trabajo):
        raise ErrorNegocio("Ya existe otro trabajo con ese título y esa gestión.")

    area = _resolver_area(datos)
    tutor = _tutor_por_nombre(datos["tutor_nombre"]) if datos.get("tutor_nombre") else None
    autores = _resolver_autores(datos["autores"])

    with transaccion():
        trabajo.titulo = datos["titulo"]
        trabajo.resumen = datos["resumen"]
        trabajo.gestion = datos["gestion"]
        trabajo.modalidad = datos["modalidad"]
        trabajo.fecha_recepcion = datos["fecha_recepcion"]
        trabajo.cd_entregado = datos["cd_entregado"]
        trabajo.autoriza_publicacion = datos["autoriza_publicacion"]
        trabajo.area = area
        trabajo.tutor = tutor
        trabajo.autores = autores


def dar_de_baja(id_trabajo):
    """RF04: baja lógica; conserva el historial y exige que no haya préstamos vigentes."""
    trabajo = db.session.get(TrabajoGrado, id_trabajo)
    if trabajo is None:
        raise ErrorNegocio("El trabajo no existe.")

    vigentes = db.session.scalar(
        select(func.count())
        .select_from(Prestamo)
        .join(Ejemplar, Ejemplar.id_ejemplar == Prestamo.id_ejemplar)
        .where(Ejemplar.id_trabajo == id_trabajo, Prestamo.estado == "vigente")
    )
    if vigentes:
        raise ErrorNegocio("No se puede dar de baja: tiene préstamos vigentes.")

    with transaccion():
        trabajo.activo = False
        for ejemplar in trabajo.ejemplares:
            ejemplar.estado = "baja"


def agregar_ejemplar(id_trabajo, ubicacion):
    """RF05: agrega un ejemplar a un trabajo activo."""
    ubicacion = (ubicacion or "").strip()
    if not ubicacion:
        raise ErrorNegocio("Indique la ubicación del nuevo ejemplar.")

    trabajo = db.session.get(TrabajoGrado, id_trabajo)
    if trabajo is None or not trabajo.activo:
        raise ErrorNegocio("El trabajo no existe o está dado de baja.")

    with transaccion():
        codigos = {e.codigo for e in trabajo.ejemplares}
        numero = len(trabajo.ejemplares) + 1
        while f"TG-{id_trabajo:04d}-{numero}" in codigos:
            numero += 1
        trabajo.ejemplares.append(
            Ejemplar(codigo=f"TG-{id_trabajo:04d}-{numero}", ubicacion=ubicacion[:60])
        )


def consultar_trabajos(args, solo_publicables=False):
    """RF06: consulta ORM con los filtros de la búsqueda y del catálogo público."""
    consulta = (
        select(TrabajoGrado)
        .options(
            joinedload(TrabajoGrado.area),
            selectinload(TrabajoGrado.autores),
            selectinload(TrabajoGrado.ejemplares),
        )
        .where(TrabajoGrado.activo.is_(True))
    )
    if solo_publicables:
        consulta = consulta.where(TrabajoGrado.autoriza_publicacion.is_(True))

    texto = (args.get("q") or "").strip()
    if texto:
        patron = f"%{normalizar(texto)}%"
        consulta = consulta.where(
            func.norm(TrabajoGrado.titulo).like(patron)
            | func.norm(TrabajoGrado.resumen).like(patron)
        )

    autor = (args.get("autor") or "").strip()
    if autor:
        patron = f"%{normalizar(autor)}%"
        consulta = consulta.where(
            TrabajoGrado.autores.any(func.norm(Autor.nombre).like(patron))
        )

    if (args.get("anio") or "").isdigit():
        consulta = consulta.where(TrabajoGrado.gestion == int(args["anio"]))
    if (args.get("area") or "").isdigit():
        consulta = consulta.where(TrabajoGrado.id_area == int(args["area"]))
    modalidad = args.get("modalidad")
    if modalidad in MODALIDADES:
        consulta = consulta.where(TrabajoGrado.modalidad == modalidad)

    estado = args.get("estado")
    if estado == "disponible":
        consulta = consulta.where(
            TrabajoGrado.ejemplares.any(Ejemplar.estado == "disponible")
        )
    elif estado == "prestado":
        consulta = consulta.where(
            ~TrabajoGrado.ejemplares.any(Ejemplar.estado == "disponible"),
            TrabajoGrado.ejemplares.any(Ejemplar.estado.in_(("en_prestamo", "en_consulta"))),
        )

    return consulta.order_by(TrabajoGrado.gestion.desc(), TrabajoGrado.titulo)
