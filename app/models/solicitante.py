"""Modelo ORM de solicitantes (RF08)."""
from __future__ import annotations

from sqlalchemy import CheckConstraint, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db


class Solicitante(db.Model):
    __tablename__ = "solicitante"
    __table_args__ = (
        CheckConstraint("length(nombre) <= 80", name="ck_solicitante_nombre"),
        CheckConstraint("length(ci) <= 15", name="ck_solicitante_ci"),
        CheckConstraint("length(matricula) <= 15", name="ck_solicitante_matricula"),
        CheckConstraint("tipo IN ('estudiante','docente')", name="ck_solicitante_tipo"),
        CheckConstraint("length(telefono) <= 15", name="ck_solicitante_telefono"),
    )

    id_solicitante: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    ci: Mapped[str] = mapped_column(String(15), unique=True, nullable=False)
    matricula: Mapped[str] = mapped_column(String(15), nullable=False, default="")
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, default="estudiante")
    telefono: Mapped[str] = mapped_column(String(15), nullable=False, default="")

    prestamos: Mapped[list["Prestamo"]] = relationship(back_populates="solicitante")

    def __repr__(self):
        return f"<Solicitante {self.nombre}>"


Index("ix_solicitante_matricula", Solicitante.matricula)
