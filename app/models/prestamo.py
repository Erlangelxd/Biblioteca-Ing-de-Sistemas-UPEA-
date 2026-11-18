"""Modelo ORM de préstamos y devoluciones (RF09, RF10)."""
from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db


class Prestamo(db.Model):
    __tablename__ = "prestamo"
    __table_args__ = (
        CheckConstraint("tipo IN ('interno','externo')", name="ck_prestamo_tipo"),
        CheckConstraint("garantia IN ('ci','matricula','ninguna')", name="ck_prestamo_garantia"),
        CheckConstraint("renovaciones >= 0", name="ck_prestamo_renovaciones"),
        CheckConstraint("estado IN ('vigente','devuelto')", name="ck_prestamo_estado"),
    )

    id_prestamo: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_ejemplar: Mapped[int] = mapped_column(ForeignKey("ejemplar.id_ejemplar"), nullable=False)
    id_solicitante: Mapped[int] = mapped_column(ForeignKey("solicitante.id_solicitante"), nullable=False)
    id_usuario: Mapped[int] = mapped_column(ForeignKey("usuario.id_usuario"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(10), nullable=False, default="interno")
    garantia: Mapped[str] = mapped_column(String(10), nullable=False, default="ci")
    fecha_prestamo: Mapped[str] = mapped_column(String(10), nullable=False)
    fecha_devolucion_prevista: Mapped[str] = mapped_column(String(10), nullable=False)
    fecha_devolucion_real: Mapped[str | None] = mapped_column(String(10), nullable=True)
    renovaciones: Mapped[int] = mapped_column(nullable=False, default=0)
    estado: Mapped[str] = mapped_column(String(10), nullable=False, default="vigente")

    ejemplar: Mapped["Ejemplar"] = relationship(back_populates="prestamos")
    solicitante: Mapped["Solicitante"] = relationship(back_populates="prestamos")
    usuario: Mapped["Usuario"] = relationship(back_populates="prestamos")

    def __repr__(self):
        return f"<Prestamo {self.id_prestamo} {self.estado}>"


Index("ix_prestamo_estado", Prestamo.estado, Prestamo.fecha_devolucion_prevista)
Index("ix_prestamo_solicitante", Prestamo.id_solicitante)
Index("ix_prestamo_ejemplar", Prestamo.id_ejemplar)
# Un ejemplar no puede tener dos préstamos vigentes a la vez (RNF05).
Index(
    "ux_prestamo_ejemplar_vigente",
    Prestamo.id_ejemplar,
    unique=True,
    sqlite_where=text("estado = 'vigente'"),
)
