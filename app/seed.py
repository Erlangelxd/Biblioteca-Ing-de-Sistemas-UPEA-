"""Datos de ejemplo (ficticios) para probar el sistema. NO usar en producción."""
from datetime import date, timedelta

from sqlalchemy import select
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
