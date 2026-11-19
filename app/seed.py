"""Datos de ejemplo (ficticios) para probar el sistema. NO usar en producción."""
from datetime import date, timedelta

from sqlalchemy import func, select
from werkzeug.security import generate_password_hash

from .extensions import db
from .models import (
    AreaTematica,
    Autor,
    Ejemplar,
    Prestamo,
    Solicitante,
    TrabajoGrado,
    Tutor,
    Usuario,
)
from .services import registrar_devolucion

# Libros de referencia sobre desarrollo de software (datos de demostración).
LIBROS = [
    {
        "titulo": "Clean Code: A Handbook of Agile Software Craftsmanship",
        "gestion": 2008,
        "area": "Ingeniería de software",
        "autores": ["Robert C. Martin"],
        "cantidad": 2,
        "resumen": "Principios, patrones y buenas prácticas para escribir código limpio, legible y mantenible.",
    },
    {
        "titulo": "The Pragmatic Programmer: Your Journey to Mastery",
        "gestion": 2019,
        "area": "Ingeniería de software",
        "autores": ["Andrew Hunt", "David Thomas"],
        "cantidad": 2,
        "resumen": "Guía clásica sobre desarrollo ágil, automatización, comunicación y diseño de software.",
    },
    {
        "titulo": "Design Patterns: Elements of Reusable Object-Oriented Software",
        "gestion": 1994,
        "area": "Ingeniería de software",
        "autores": ["Erich Gamma", "Richard Helm", "Ralph Johnson", "John Vlissides"],
        "cantidad": 1,
        "resumen": "Catálogo de patrones de diseño orientado a objetos: creacionales, estructurales y de comportamiento.",
    },
    {
        "titulo": "Refactoring: Improving the Design of Existing Code",
        "gestion": 2018,
        "area": "Ingeniería de software",
        "autores": ["Martin Fowler"],
        "cantidad": 1,
        "resumen": "Técnicas para mejorar el diseño del código existente sin alterar su comportamiento.",
    },
    {
        "titulo": "The Mythical Man-Month: Essays on Software Engineering",
        "gestion": 1995,
        "area": "Ingeniería de software",
        "autores": ["Frederick P. Brooks Jr."],
        "cantidad": 1,
        "resumen": "Ensayos sobre gestión de proyectos de software, estimación, equipos y complejidad.",
    },
    {
        "titulo": "Code Complete: A Practical Handbook of Software Construction",
        "gestion": 2004,
        "area": "Ingeniería de software",
        "autores": ["Steve McConnell"],
        "cantidad": 2,
        "resumen": "Manual práctico de construcción de software: diseño, calidad, pruebas y depuración.",
    },
    {
        "titulo": "Introduction to Algorithms",
        "gestion": 2009,
        "area": "Programación",
        "autores": ["Thomas H. Cormen", "Charles E. Leiserson", "Ronald L. Rivest", "Clifford Stein"],
        "cantidad": 2,
        "resumen": "Texto de referencia sobre algoritmos, estructuras de datos y análisis de complejidad.",
    },
    {
        "titulo": "Working Effectively with Legacy Code",
        "gestion": 2004,
        "area": "Ingeniería de software",
        "autores": ["Michael C. Feathers"],
        "cantidad": 1,
        "resumen": "Estrategias para trabajar con código heredado, agregar pruebas y refactorizar con seguridad.",
    },
    {
        "titulo": "Domain-Driven Design: Tackling Complexity in the Heart of Software",
        "gestion": 2003,
        "area": "Ingeniería de software",
        "autores": ["Eric Evans"],
        "cantidad": 1,
        "resumen": "Enfoque de diseño guiado por el dominio para modelar sistemas de software complejos.",
    },
    {
        "titulo": "Peopleware: Productive Projects and Teams",
        "gestion": 2013,
        "area": "Ingeniería de software",
        "autores": ["Tom DeMarco", "Timothy Lister"],
        "cantidad": 1,
        "resumen": "Estudio sobre factores humanos, organización de equipos y productividad en proyectos.",
    },
    {
        "titulo": "Continuous Delivery: Reliable Software Releases through Build, Test, and Deployment Automation",
        "gestion": 2010,
        "area": "Ingeniería de software",
        "autores": ["Jez Humble", "David Farley"],
        "cantidad": 1,
        "resumen": "Prácticas de integración, pruebas y despliegue automatizado para entregas continuas.",
    },
    {
        "titulo": "The Clean Coder: A Code of Conduct for Professional Programmers",
        "gestion": 2011,
        "area": "Ingeniería de software",
        "autores": ["Robert C. Martin"],
        "cantidad": 1,
        "resumen": "Responsabilidad profesional, disciplina y buenas prácticas en el desarrollo de software.",
    },
]

PREFIJO_LIBRO = "LIB"


def _obtener_area(nombre):
    """Devuelve el área temática, creándola si todavía no existe."""
    area = db.session.scalar(select(AreaTematica).where(AreaTematica.nombre == nombre))
    if area is None:
        area = AreaTematica(nombre=nombre)
        db.session.add(area)
        db.session.flush()
    return area


def _insertar_libros(areas, hoy):
    """Inserta los libros que aún no estén registrados y devuelve cuántos creó."""
    creados = 0
    for posicion, libro in enumerate(LIBROS):
        existente = db.session.scalar(
            select(TrabajoGrado.id_trabajo).where(
                func.lower(TrabajoGrado.titulo) == libro["titulo"].lower(),
                TrabajoGrado.gestion == libro["gestion"],
            )
        )
        if existente:
            continue

        trabajo = TrabajoGrado(
            titulo=libro["titulo"],
            resumen=libro["resumen"],
            gestion=libro["gestion"],
            modalidad="libro",
            fecha_recepcion=(hoy - timedelta(days=120 + posicion * 9)).isoformat(),
            cd_entregado=False,
            autoriza_publicacion=True,
            area=areas[libro["area"]],
            autores=[Autor(nombre=nombre) for nombre in libro["autores"]],
        )
        db.session.add(trabajo)
        db.session.flush()
        for numero in range(1, libro["cantidad"] + 1):
            db.session.add(
                Ejemplar(
                    id_trabajo=trabajo.id_trabajo,
                    codigo=f"{PREFIJO_LIBRO}-{trabajo.id_trabajo:04d}-{numero}",
                    ubicacion=f"Estante 4 – Sección {'LM'[posicion % 2]}",
                )
            )
        creados += 1
    return creados


def cargar():
    if db.session.scalar(select(TrabajoGrado.id_trabajo).limit(1)):
        return "Ya existen datos; no se cargó nada."

    hoy = date.today()
    try:
        def usuario(nombre, clave, rol):
            """Reutiliza el usuario si ya existe (p. ej. creado con crear-usuario)."""
            existente = db.session.scalar(
                select(Usuario).where(Usuario.nombre_usuario == nombre)
            )
            if existente:
                return existente
            nuevo = Usuario(
                nombre_usuario=nombre,
                contrasena=generate_password_hash(clave),
                rol=rol,
            )
            db.session.add(nuevo)
            db.session.flush()
            return nuevo

        admin = usuario("bibliotecaria", "biblioteca2026", "administrador")
        usuario("consulta", "consulta2026", "consulta")

        areas = {
            nombre: AreaTematica(nombre=nombre)
            for nombre in ["Programación", "Bases de datos", "Redes", "Inteligencia artificial", "Ingeniería de software"]
        }
        tutores = [Tutor(nombre=nombre) for nombre in ["Ph. D. Tutor Uno", "M. Sc. Tutor Dos", "Ing. Tutor Tres"]]
        db.session.add_all(list(areas.values()) + tutores)
        db.session.flush()

        obras = [
            ("Sistema de ejemplo para el control de inventarios", 2024, "proyecto", "Programación", ["Autor Uno"], 2),
            ("Aplicación de ejemplo para gestión académica", 2022, "tesis", "Bases de datos", ["Autor Dos", "Autor Tres"], 1),
            ("Análisis de ejemplo de una red de área local", 2021, "dirigido", "Redes", ["Autor Cuatro"], 1),
            ("Modelo de ejemplo de predicción con aprendizaje automático", 2025, "tesis", "Inteligencia artificial", ["Autor Cinco"], 2),
            ("Plataforma de ejemplo para registro de pacientes", 2023, "proyecto", "Ingeniería de software", ["Autor Seis"], 1),
            ("Sistema de ejemplo de control de almacenes", 2020, "proyecto", "Programación", ["Autor Siete"], 1),
        ]
        ejemplares = []
        for i, (titulo, gestion, modalidad, area, autores, cantidad) in enumerate(obras):
            trabajo = TrabajoGrado(
                titulo=titulo,
                resumen="Resumen de ejemplo del trabajo.",
                gestion=gestion,
                modalidad=modalidad,
                fecha_recepcion=(hoy - timedelta(days=30 * (i + 1))).isoformat(),
                cd_entregado=True,
                autoriza_publicacion=True,
                area=areas[area],
                tutor=tutores[i % 3],
                autores=[Autor(nombre=nombre) for nombre in autores],
            )
            db.session.add(trabajo)
            db.session.flush()
            for numero in range(1, cantidad + 1):
                ejemplar = Ejemplar(
                    id_trabajo=trabajo.id_trabajo,
                    codigo=f"TG-{trabajo.id_trabajo:04d}-{numero}",
                    ubicacion=f"Estante {i % 3 + 1} – Sección {'AB'[i % 2]}",
                )
                db.session.add(ejemplar)
                ejemplares.append(ejemplar)

        _insertar_libros(areas, hoy)

        solicitantes = [
            Solicitante(nombre="Estudiante de Ejemplo Uno", ci="1111111", matricula="M-001", tipo="estudiante"),
            Solicitante(nombre="Estudiante de Ejemplo Dos", ci="2222222", matricula="M-002", tipo="estudiante"),
            Solicitante(nombre="Docente de Ejemplo", ci="3333333", matricula="", tipo="docente"),
            Solicitante(nombre="Estudiante de Ejemplo Tres", ci="4444444", matricula="M-004", tipo="estudiante"),
        ]
        db.session.add_all(solicitantes)
        db.session.flush()

        def prestar(ejemplar, solicitante, tipo, dias_atras, plazo):
            fecha = hoy - timedelta(days=dias_atras)
            prestamo = Prestamo(
                id_ejemplar=ejemplar.id_ejemplar,
                id_solicitante=solicitante.id_solicitante,
                id_usuario=admin.id_usuario,
                tipo=tipo,
                garantia="ci",
                fecha_prestamo=fecha.isoformat(),
                fecha_devolucion_prevista=(fecha + timedelta(days=plazo)).isoformat(),
            )
            ejemplar.estado = "en_consulta" if tipo == "interno" else "en_prestamo"
            db.session.add(prestamo)
            db.session.flush()
            return prestamo

        prestar(ejemplares[0], solicitantes[0], "externo", 12, 7)   # vencido
        prestar(ejemplares[2], solicitantes[2], "externo", 2, 7)    # vigente
        prestar(ejemplares[4], solicitantes[1], "interno", 0, 0)    # consulta en sala, hoy
        antiguo = prestar(ejemplares[5], solicitantes[3], "externo", 20, 7)
        db.session.commit()

        registrar_devolucion(antiguo.id_prestamo)
        return "Datos de ejemplo cargados. Usuarios: bibliotecaria/biblioteca2026 y consulta/consulta2026"
    except Exception:
        db.session.rollback()
        raise


def cargar_libros():
    """Carga únicamente los libros de referencia, sin borrar datos existentes."""
    hoy = date.today()
    try:
        areas = {}
        for libro in LIBROS:
            if libro["area"] not in areas:
                areas[libro["area"]] = _obtener_area(libro["area"])

        creados = _insertar_libros(areas, hoy)
        db.session.commit()
        if creados:
            return f"Libros de ejemplo cargados: {creados}. Los ejemplares quedaron disponibles."
        return "Los libros de ejemplo ya estaban registrados; no se cargó nada."
    except Exception:
        db.session.rollback()
        raise
