"""Modelo ORM de usuarios del sistema (RF01, RF02)."""
from __future__ import annotations

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db


class Usuario(db.Model):
    __tablename__ = "usuario"
    __table_args__ = (
        CheckConstraint("length(nombre_usuario) BETWEEN 3 AND 30", name="ck_usuario_nombre"),
        CheckConstraint("rol IN ('administrador','consulta')", name="ck_usuario_rol"),
        CheckConstraint("activo IN (0,1)", name="ck_usuario_activo"),
    )

    id_usuario: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre_usuario: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    contrasena: Mapped[str] = mapped_column(String(255), nullable=False)
    rol: Mapped[str] = mapped_column(String(20), nullable=False, default="consulta")
    activo: Mapped[bool] = mapped_column(nullable=False, default=True)

    prestamos: Mapped[list["Prestamo"]] = relationship(back_populates="usuario")

    def __repr__(self):
        return f"<Usuario {self.nombre_usuario}>"
