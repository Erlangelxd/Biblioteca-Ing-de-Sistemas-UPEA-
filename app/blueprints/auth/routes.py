"""Proceso 1.0: acceso, usuarios y perfiles (RF01, RF02)."""
from urllib.parse import urlparse

from flask import Blueprint, current_app, flash, g, redirect, render_template, request, session, url_for
from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash

from ...extensions import db
from ...models import Usuario
from ...seguridad import (
    admin_requerido,
    bloqueado,
    limpiar_fallos,
    login_requerido,
    registrar_fallo,
)
from ...services import ErrorNegocio, crear_usuario, transaccion, validar_clave

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
        config = current_app.config
        espera = bloqueado(clave_bloqueo, config["MAX_INTENTOS"], config["MINUTOS_BLOQUEO"])
        if espera:
            flash(f"Demasiados intentos. Espere {espera} minuto(s) e intente de nuevo.", "error")
            return render_template("auth/login.html"), 429

        usuario = db.session.scalar(
            select(Usuario).where(
                Usuario.nombre_usuario == nombre,
                Usuario.activo.is_(True),
            )
        )
        if usuario and check_password_hash(usuario.contrasena, request.form.get("password") or ""):
            limpiar_fallos(clave_bloqueo)
            session.clear()
            session["id_usuario"] = usuario.id_usuario
            return redirect(_destino_seguro(request.form.get("next")))

        registrar_fallo(clave_bloqueo, config["MAX_INTENTOS"], config["MINUTOS_BLOQUEO"])
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
        usuario = db.session.get(Usuario, g.usuario.id_usuario)
        try:
            if not check_password_hash(usuario.contrasena, request.form.get("actual") or ""):
                raise ErrorNegocio("La contraseña actual no es correcta.")
            if request.form.get("nueva") != request.form.get("repetir"):
                raise ErrorNegocio("Las contraseñas nuevas no coinciden.")
            validar_clave(request.form.get("nueva"))
            with transaccion():
                usuario.contrasena = generate_password_hash(request.form["nueva"])
            flash("Contraseña cambiada.", "success")
            return redirect(url_for("main.inicio"))
        except ErrorNegocio as error:
            flash(str(error), "error")
    return render_template("auth/clave.html")


# ---------------------------------------------------------------- RF02: usuarios y perfiles
@bp.route("/usuarios")
@admin_requerido
def usuarios():
    filas = db.session.scalars(select(Usuario).order_by(Usuario.nombre_usuario)).all()
    return render_template("usuarios/lista.html", filas=filas)


@bp.route("/usuarios/nuevo", methods=["GET", "POST"])
@admin_requerido
def usuario_nuevo():
    if request.method == "POST":
        try:
            crear_usuario(
                request.form.get("nombre_usuario"),
                request.form.get("clave"),
                request.form.get("rol", "consulta"),
            )
            flash("Usuario creado.", "success")
            return redirect(url_for("auth.usuarios"))
        except ErrorNegocio as error:
            flash(str(error), "error")
    return render_template("usuarios/form.html", u=None, f=request.form)


@bp.route("/usuarios/<int:id_usuario>/editar", methods=["GET", "POST"])
@admin_requerido
def usuario_editar(id_usuario):
    usuario = db.session.get(Usuario, id_usuario)
    if usuario is None:
        return redirect(url_for("auth.usuarios"))
    if request.method == "POST":
        rol = request.form.get("rol", usuario.rol)
        try:
            if rol not in ("administrador", "consulta"):
                raise ErrorNegocio("Rol no válido.")
            if usuario.id_usuario == g.usuario.id_usuario and rol != "administrador":
                raise ErrorNegocio("No puede quitarse a sí mismo el perfil de administrador.")
            clave = request.form.get("clave") or ""
            if clave:
                validar_clave(clave)
            with transaccion():
                usuario.rol = rol
                if clave:
                    usuario.contrasena = generate_password_hash(clave)
            flash("Usuario actualizado.", "success")
            return redirect(url_for("auth.usuarios"))
        except ErrorNegocio as error:
            flash(str(error), "error")
    return render_template("usuarios/form.html", u=usuario, f=request.form)


@bp.route("/usuarios/<int:id_usuario>/estado", methods=["POST"])
@admin_requerido
def usuario_estado(id_usuario):
    """Activa o desactiva un usuario (no se borra, para conservar el historial)."""
    usuario = db.session.get(Usuario, id_usuario)
    if usuario is None:
        pass
    elif usuario.id_usuario == g.usuario.id_usuario:
        flash("No puede desactivar su propio usuario.", "error")
    else:
        with transaccion():
            usuario.activo = not usuario.activo
        flash("Usuario " + ("activado." if usuario.activo else "desactivado."), "success")
    return redirect(url_for("auth.usuarios"))
