"""Datos de ejemplo (ficticios) para probar el sistema. NO usar en producción."""
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

from .db import transaccion
from .servicios import registrar_devolucion


def cargar(db):
    if db.execute("SELECT 1 FROM trabajo_grado").fetchone():
        return "Ya existen datos; no se cargó nada."
    hoy = date.today()
    with transaccion(db):
        for nombre, clave, rol in [("bibliotecaria", "biblioteca2026", "administrador"), ("consulta", "consulta2026", "consulta")]:
            db.execute("INSERT OR IGNORE INTO usuario (nombre_usuario, contrasena, rol) VALUES (?,?,?)",
                       (nombre, generate_password_hash(clave), rol))
        areas = {}
        for n in ["Programación", "Bases de datos", "Redes", "Inteligencia artificial", "Ingeniería de software"]:
            areas[n] = db.execute("INSERT INTO area_tematica (nombre) VALUES (?)", (n,)).lastrowid
        tutores = [db.execute("INSERT INTO tutor (nombre) VALUES (?)", (n,)).lastrowid
                   for n in ["Ph. D. Tutor Uno", "M. Sc. Tutor Dos", "Ing. Tutor Tres"]]
        obras = [
            ("Sistema de ejemplo para el control de inventarios", 2024, "proyecto", "Programación", ["Autor Uno"], 2),
            ("Aplicación de ejemplo para gestión académica", 2022, "tesis", "Bases de datos", ["Autor Dos", "Autor Tres"], 1),
            ("Análisis de ejemplo de una red de área local", 2021, "dirigido", "Redes", ["Autor Cuatro"], 1),
            ("Modelo de ejemplo de predicción con aprendizaje automático", 2025, "tesis", "Inteligencia artificial", ["Autor Cinco"], 2),
            ("Plataforma de ejemplo para registro de pacientes", 2023, "proyecto", "Ingeniería de software", ["Autor Seis"], 1),
            ("Sistema de ejemplo de control de almacenes", 2020, "proyecto", "Programación", ["Autor Siete"], 1)]
        ejemplares = []
        for i, (titulo, gestion, modalidad, area, autores, n) in enumerate(obras):
            idt = db.execute(
                "INSERT INTO trabajo_grado (titulo, resumen, gestion, modalidad, fecha_recepcion, cd_entregado, "
                "autoriza_publicacion, id_area, id_tutor) VALUES (?,?,?,?,?,1,1,?,?)",
                (titulo, "Resumen de ejemplo del trabajo.", gestion, modalidad,
                 (hoy - timedelta(days=30 * (i + 1))).isoformat(), areas[area], tutores[i % 3])).lastrowid
            for nombre in autores:
                ida = db.execute("INSERT INTO autor (nombre) VALUES (?)", (nombre,)).lastrowid
                db.execute("INSERT INTO trabajo_autor VALUES (?,?)", (idt, ida))
            for k in range(n):
                ejemplares.append(db.execute("INSERT INTO ejemplar (id_trabajo, codigo, ubicacion) VALUES (?,?,?)",
                                             (idt, f"TG-{idt:04d}-{k + 1}", f"Estante {i % 3 + 1} – Sección {'AB'[i % 2]}")).lastrowid)
        sol = [db.execute("INSERT INTO solicitante (nombre, ci, matricula, tipo) VALUES (?,?,?,?)", d).lastrowid for d in [
            ("Estudiante de Ejemplo Uno", "1111111", "M-001", "estudiante"), ("Estudiante de Ejemplo Dos", "2222222", "M-002", "estudiante"),
            ("Docente de Ejemplo", "3333333", "", "docente"), ("Estudiante de Ejemplo Tres", "4444444", "M-004", "estudiante")]]
        admin = db.execute("SELECT id_usuario FROM usuario WHERE nombre_usuario = 'bibliotecaria'").fetchone()[0]

        def prestar(ej, s, tipo, dias_atras, plazo, devuelto=False):
            f = hoy - timedelta(days=dias_atras)
            pid = db.execute(
                "INSERT INTO prestamo (id_ejemplar, id_solicitante, id_usuario, tipo, garantia, fecha_prestamo, fecha_devolucion_prevista) "
                "VALUES (?,?,?,?,'ci',?,?)", (ej, s, admin, tipo, f.isoformat(), (f + timedelta(days=plazo)).isoformat())).lastrowid
            db.execute("UPDATE ejemplar SET estado = ? WHERE id_ejemplar = ?",
                       ("en_consulta" if tipo == "interno" else "en_prestamo", ej))
            return pid
        prestar(ejemplares[0], sol[0], "externo", 12, 7)    # vencido
        prestar(ejemplares[2], sol[2], "externo", 2, 7)     # vigente
        prestar(ejemplares[4], sol[1], "interno", 0, 0)     # consulta en sala, hoy
        antiguo = prestar(ejemplares[5], sol[3], "externo", 20, 7)
    registrar_devolucion(db, antiguo)
    return "Datos de ejemplo cargados. Usuarios: bibliotecaria/biblioteca2026 y consulta/consulta2026"
