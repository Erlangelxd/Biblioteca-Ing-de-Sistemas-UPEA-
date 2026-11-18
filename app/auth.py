"""Proceso 1.0: gestionar acceso y usuarios (RF01, RF02)."""
from urllib.parse import urlparse

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for, g
from werkzeug.security import check_password_hash

from .db import get_db
from .seguridad import (admin_requerido, bloqueado, limpiar_fallos, login_requerido, registrar_fallo)
from .servicios import ErrorNegocio, cambiar_clave, crear_usuario

bp = Blueprint("auth", __name__)


def _destino_seguro(destino):
    """Solo permite rutas internas: evita redirecciones abiertas (https://, //host, /\\host)."""
    if not destino:
        return url_for("main.inicio")
    partes = urlparse(destino)
    if partes.scheme or partes.netloc or not destino.startswith("/") or destino.startswith("//") or "\\" in destino:
        return url_for("main.inicio")
    return destino


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        nombre = (request.form.get("username") or "").strip()
        clave_bloqueo = f"{nombre.lower()}|{request.remote_addr}"
        cfg = current_app.config
        espera = bloqueado(clave_bloqueo, cfg["MAX_INTENTOS"], cfg["MINUTOS_BLOQUEO"])
        if espera:
            flash(f"Demasiados intentos. Espere {espera} minuto(s) e intente de nuevo.", "error")
            return render_template("auth/login.html"), 429
        u = get_db().execute("SELECT * FROM usuario WHERE nombre_usuario = ? AND activo = 1", (nombre,)).fetchone()
        if u and check_password_hash(u["contrasena"], request.form.get("password") or ""):
            limpiar_fallos(clave_bloqueo)
            session.clear()
            session["id_usuario"] = u["id_usuario"]
            return redirect(_destino_seguro(request.form.get("next")))
        registrar_fallo(clave_bloqueo, cfg["MAX_INTENTOS"], cfg["MINUTOS_BLOQUEO"])
        flash("Usuario o contraseña incorrectos.", "error")
    return render_template("auth/login.html", siguiente=request.args.get("next", ""))


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@bp.route("/clave", methods=["GET", "POST"])
@login_requerido
def clave():
    if request.method == "POST":
        db = get_db()
        u = db.execute("SELECT * FROM usuario WHERE id_usuario = ?", (g.usuario["id_usuario"],)).fetchone()
        try:
            if not check_password_hash(u["contrasena"], request.form.get("actual") or ""):
                raise ErrorNegocio("La contraseña actual no es correcta.")
            if request.form.get("nueva") != request.form.get("repetir"):
                raise ErrorNegocio("Las contraseñas nuevas no coinciden.")
            cambiar_clave(db, u["id_usuario"], request.form.get("nueva"))
            flash("Contraseña cambiada.", "success")
            return redirect(url_for("main.inicio"))
        except ErrorNegocio as e:
            flash(str(e), "error")
    return render_template("auth/clave.html")


# ---------------------------------------------------------------- RF02: usuarios y perfiles
@bp.route("/usuarios")
@admin_requerido
def usuarios():
    filas = get_db().execute("SELECT id_usuario, nombre_usuario, rol, activo FROM usuario ORDER BY nombre_usuario").fetchall()
    return render_template("usuarios/lista.html", filas=filas)


@bp.route("/usuarios/nuevo", methods=["GET", "POST"])
@admin_requerido
def usuario_nuevo():
    if request.method == "POST":
        try:
            crear_usuario(get_db(), request.form.get("nombre_usuario"), request.form.get("clave"),
                          request.form.get("rol", "consulta"))
            flash("Usuario creado.", "success")
            return redirect(url_for("auth.usuarios"))
        except ErrorNegocio as e:
            flash(str(e), "error")
    return render_template("usuarios/form.html", u=None, f=request.form)


@bp.route("/usuarios/<int:id_usuario>/editar", methods=["GET", "POST"])
@admin_requerido
def usuario_editar(id_usuario):
    db = get_db()
    u = db.execute("SELECT * FROM usuario WHERE id_usuario = ?", (id_usuario,)).fetchone()
    if u is None:
        return redirect(url_for("auth.usuarios"))
    if request.method == "POST":
        rol = request.form.get("rol", u["rol"])
        try:
            if rol not in ("administrador", "consulta"):
                raise ErrorNegocio("Rol no válido.")
            if u["id_usuario"] == g.usuario["id_usuario"] and rol != "administrador":
                raise ErrorNegocio("No puede quitarse a sí mismo el perfil de administrador.")
            db.execute("UPDATE usuario SET rol = ? WHERE id_usuario = ?", (rol, id_usuario))
            if request.form.get("clave"):
                cambiar_clave(db, id_usuario, request.form["clave"])
            flash("Usuario actualizado.", "success")
            return redirect(url_for("auth.usuarios"))
        except ErrorNegocio as e:
            flash(str(e), "error")
    return render_template("usuarios/form.html", u=u, f=request.form)


@bp.route("/usuarios/<int:id_usuario>/estado", methods=["POST"])
@admin_requerido
def usuario_estado(id_usuario):
    """Activa o desactiva un usuario (no se borra, para conservar el historial de préstamos)."""
    db = get_db()
    u = db.execute("SELECT * FROM usuario WHERE id_usuario = ?", (id_usuario,)).fetchone()
    if u is None:
        pass
    elif u["id_usuario"] == g.usuario["id_usuario"]:
        flash("No puede desactivar su propio usuario.", "error")
    else:
        db.execute("UPDATE usuario SET activo = ? WHERE id_usuario = ?", (0 if u["activo"] else 1, id_usuario))
        flash("Usuario " + ("desactivado." if u["activo"] else "activado."), "success")
    return redirect(url_for("auth.usuarios"))
