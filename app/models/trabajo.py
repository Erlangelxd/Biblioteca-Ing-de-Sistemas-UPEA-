"""Modelos del agregado Trabajo de Grado y sus ejemplares (RF03–RF07)."""
from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db

# Tabla intermedia N:M entre trabajos y autores.
trabajo_autor = db.Table(
    "trabajo_autor",
    db.Column("id_trabajo", db.Integer, db.ForeignKey("trabajo_grado.id_trabajo", ondelete="CASCADE"), primary_key=True),
    db.Column("id_autor", db.Integer, db.ForeignKey("autor.id_autor", ondelete="CASCADE"), primary_key=True),
)


class TrabajoGrado(db.Model):
    __tablename__ = "trabajo_grado"
    __table_args__ = (
        CheckConstraint("length(titulo) <= 250", name="ck_trabajo_titulo"),
        CheckConstraint("gestion BETWEEN 1980 AND 2100", name="ck_trabajo_gestion"),
        CheckConstraint("modalidad IN ('tesis','proyecto','dirigido','libro')", name="ck_trabajo_modalidad"),
        CheckConstraint("cd_entregado IN (0,1)", name="ck_trabajo_cd"),
        CheckConstraint("autoriza_publicacion IN (0,1)", name="ck_trabajo_publicacion"),
        CheckConstraint("activo IN (0,1)", name="ck_trabajo_activo"),
    )

    id_trabajo: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    titulo: Mapped[str] = mapped_column(String(250), nullable=False)
    resumen: Mapped[str] = mapped_column(Text, nullable=False, default="")
    gestion: Mapped[int] = mapped_column(nullable=False)
    modalidad: Mapped[str] = mapped_column(String(20), nullable=False)
    fecha_recepcion: Mapped[str] = mapped_column(String(10), nullable=False)
    cd_entregado: Mapped[bool] = mapped_column(nullable=False, default=False)
    autoriza_publicacion: Mapped[bool] = mapped_column(nullable=False, default=False)
    activo: Mapped[bool] = mapped_column(nullable=False, default=True)

    id_area: Mapped[int | None] = mapped_column(
        ForeignKey("area_tematica.id_area", ondelete="SET NULL"), nullable=True
    )
    id_tutor: Mapped[int | None] = mapped_column(
        ForeignKey("tutor.id_tutor", ondelete="SET NULL"), nullable=True
    )

    area: Mapped["AreaTematica | None"] = relationship(back_populates="trabajos")
    tutor: Mapped["Tutor | None"] = relationship(back_populates="trabajos")
    autores: Mapped[list["Autor"]] = relationship(
        secondary=trabajo_autor, back_populates="trabajos", order_by="Autor.nombre"
    )
    ejemplares: Mapped[list["Ejemplar"]] = relationship(
        back_populates="trabajo", cascade="all, delete-orphan", order_by="Ejemplar.id_ejemplar"
    )

    @property
    def autores_texto(self) -> str:
        return "; ".join(a.nombre for a in self.autores)

    @property
    def total_ejemplares(self) -> int:
        return sum(1 for e in self.ejemplares if e.estado != "baja")

    @property
    def disponibles(self) -> int:
        return sum(1 for e in self.ejemplares if e.estado == "disponible")

    @property
    def ubicacion_principal(self) -> str | None:
        return self.ejemplares[0].ubicacion if self.ejemplares else None

    def __repr__(self):
        return f"<TrabajoGrado {self.titulo}>"


class Ejemplar(db.Model):
    __tablename__ = "ejemplar"
    __table_args__ = (
        CheckConstraint("length(codigo) <= 20", name="ck_ejemplar_codigo"),
        CheckConstraint("length(ubicacion) <= 60", name="ck_ejemplar_ubicacion"),
        CheckConstraint(
            "estado IN ('disponible','en_consulta','en_prestamo','baja')",
            name="ck_ejemplar_estado",
        ),
    )

    id_ejemplar: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_trabajo: Mapped[int] = mapped_column(
        ForeignKey("trabajo_grado.id_trabajo", ondelete="CASCADE"), nullable=False
    )
    codigo: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    ubicacion: Mapped[str] = mapped_column(String(60), nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="disponible")

    trabajo: Mapped[TrabajoGrado] = relationship(back_populates="ejemplares")
    prestamos: Mapped[list["Prestamo"]] = relationship(back_populates="ejemplar")

    def __repr__(self):
        return f"<Ejemplar {self.codigo}>"


# Índices declarados fuera de la clase para poder usar expresiones.
Index("ux_trabajo_titulo_gestion", func.lower(TrabajoGrado.titulo), TrabajoGrado.gestion, unique=True)
Index("ix_trabajo_area", TrabajoGrado.id_area)
Index("ix_trabajo_gestion", TrabajoGrado.gestion)
Index("ix_ejemplar_trabajo", Ejemplar.id_trabajo)
