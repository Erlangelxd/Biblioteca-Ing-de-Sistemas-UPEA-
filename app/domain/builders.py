"""Patrón Builder para construir el agregado TrabajoGrado.

Separa la construcción paso a paso de un objeto complejo (trabajo + autores +
área + tutor + ejemplares) de su representación final y de la persistencia.
"""
from __future__ import annotations

from ..models import AreaTematica, Autor, Ejemplar, TrabajoGrado, Tutor


class TrabajoGradoBuilder:
    def __init__(self, titulo: str, gestion: int, modalidad: str, fecha_recepcion: str):
        self._titulo = titulo
        self._gestion = gestion
        self._modalidad = modalidad
        self._fecha_recepcion = fecha_recepcion
        self._resumen = ""
        self._cd_entregado = False
        self._autoriza_publicacion = False
        self._area: AreaTematica | None = None
        self._tutor: Tutor | None = None
        self._autores: list[Autor] = []
        self._num_ejemplares = 1
        self._ubicacion = ""

    def con_resumen(self, resumen: str) -> "TrabajoGradoBuilder":
        self._resumen = resumen
        return self

    def con_cd(self, entregado: bool) -> "TrabajoGradoBuilder":
        self._cd_entregado = bool(entregado)
        return self

    def con_autorizacion(self, autoriza: bool) -> "TrabajoGradoBuilder":
        self._autoriza_publicacion = bool(autoriza)
        return self

    def con_area(self, area: AreaTematica | None) -> "TrabajoGradoBuilder":
        self._area = area
        return self

    def con_tutor(self, tutor: Tutor | None) -> "TrabajoGradoBuilder":
        self._tutor = tutor
        return self

    def con_autores(self, autores: list[Autor]) -> "TrabajoGradoBuilder":
        self._autores = list(autores)
        return self

    def con_ejemplares(self, cantidad: int, ubicacion: str) -> "TrabajoGradoBuilder":
        self._num_ejemplares = max(1, min(int(cantidad), 20))
        self._ubicacion = ubicacion
        return self

    def construir(self) -> TrabajoGrado:
        """Crea el trabajo con sus relaciones, sin persistirlo todavía."""
        return TrabajoGrado(
            titulo=self._titulo,
            resumen=self._resumen,
            gestion=self._gestion,
            modalidad=self._modalidad,
            fecha_recepcion=self._fecha_recepcion,
            cd_entregado=self._cd_entregado,
            autoriza_publicacion=self._autoriza_publicacion,
            area=self._area,
            tutor=self._tutor,
            autores=list(self._autores),
        )

    def crear_ejemplares(self, id_trabajo: int) -> list[Ejemplar]:
        """Genera los ejemplares una vez que el trabajo tiene identificador."""
        prefijo = "LIB" if self._modalidad == "libro" else "TG"
        return [
            Ejemplar(
                id_trabajo=id_trabajo,
                codigo=f"{prefijo}-{id_trabajo:04d}-{numero}",
                ubicacion=self._ubicacion[:60],
            )
            for numero in range(1, self._num_ejemplares + 1)
        ]
