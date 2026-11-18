"""Modelos de catálogos: áreas temáticas, tutores y autores."""
from __future__ import annotations

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db


class AreaTematica(db.Model):
    __tablename__ = "area_tematica"
    __table_args__ = (
        CheckConstraint("length(nombre) <= 60", name="ck_area_nombre"),
    )

    id_area: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)

    trabajos: Mapped[list["TrabajoGrado"]] = relationship(back_populates="area")

    def __repr__(self):
        return f"<AreaTematica {self.nombre}>"


class Tutor(db.Model):
    __tablename__ = "tutor"
    __table_args__ = (
        CheckConstraint("length(nombre) <= 80", name="ck_tutor_nombre"),
    )

    id_tutor: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)

    trabajos: Mapped[list["TrabajoGrado"]] = relationship(back_populates="tutor")

    def __repr__(self):
        return f"<Tutor {self.nombre}>"


class Autor(db.Model):
    __tablename__ = "autor"
    __table_args__ = (
        CheckConstraint("length(nombre) <= 80", name="ck_autor_nombre"),
        CheckConstraint("length(ci) <= 15", name="ck_autor_ci"),
    )

    id_autor: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    ci: Mapped[str] = mapped_column(String(15), nullable=False, default="")

    trabajos: Mapped[list["TrabajoGrado"]] = relationship(
        secondary="trabajo_autor", back_populates="autores"
    )

    def __repr__(self):
        return f"<Autor {self.nombre}>"
