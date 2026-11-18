"""Autenticación, roles (RF01, RF02), protección CSRF y bloqueo por intentos fallidos (RNF02, RNF12)."""
import secrets
import time
from functools import wraps

from flask import abort, flash, g, redirect, request, session, url_for

from .db import get_db

_intentos = {}   # {clave: [fallos, hasta_cuando]}  (en memoria; suficiente para un solo servidor)


def cargar_usuario():
    g.usuario = None
    id_usuario = session.get("id_usuario")
    if id_usuario:
        fila = get_db().execute("SELECT id_usuario, nombre_usuario, rol FROM usuario WHERE id_usuario = ? AND activo = 1",
                                (id_usuario,)).fetchone()
        if fila is None:
            session.clear()
        g.usuario = fila


def token_csrf():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


def verificar_csrf():
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        enviado = request.form.get("csrf_token", "")
        if not enviado or not secrets.compare_digest(enviado, session.get("csrf", "")):
            abort(400, "Formulario no válido o vencido. Vuelva a cargar la página.")


def login_requerido(vista):
    @wraps(vista)
    def envoltura(*a, **k):
        if g.usuario is None:
            flash("Inicie sesión para continuar.", "error")
            return redirect(url_for("auth.login", next=request.full_path if request.method == "GET" else None))
        return vista(*a, **k)
    return envoltura


def admin_requerido(vista):
    @wraps(vista)
    def envoltura(*a, **k):
        if g.usuario is None:
            flash("Inicie sesión para continuar.", "error")
            return redirect(url_for("auth.login"))
        if g.usuario["rol"] != "administrador":
            flash("No tiene permiso para realizar esta acción.", "error")
            return redirect(url_for("main.inicio"))
        return vista(*a, **k)
    return envoltura


def bloqueado(clave, maximo, minutos):
    fallos, hasta = _intentos.get(clave, [0, 0])
    if fallos >= maximo and time.time() < hasta:
        return int((hasta - time.time()) // 60) + 1
    return 0


def registrar_fallo(clave, maximo, minutos):
    fallos, hasta = _intentos.get(clave, [0, 0])
    if time.time() >= hasta and fallos >= maximo:
        fallos = 0
    fallos += 1
    _intentos[clave] = [fallos, time.time() + minutos * 60]


def limpiar_fallos(clave):
    _intentos.pop(clave, None)
