"""Referencias entre módulos sin claves foráneas: «modulo:tipo:id».

Un recibido de la Mesa de Partes guarda «qillqasqa:documento:123» en vez de una clave foránea a la tabla de
documentos. Para mostrarlo vigente (título, estado, enlace) se pregunta al dueño. Si el dueño no está (el
módulo funciona solo), la referencia sigue guardada y se muestra tal cual.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Awaitable, Callable

_PARTE = re.compile(r"^[a-z][a-z0-9_]*$")
_ID = re.compile(r"^[A-Za-z0-9_.-]+$")

Resolutor = Callable[[str], Awaitable["dict | None"]]


@dataclass(frozen=True)
class Referencia:
    modulo: str
    tipo: str
    id: str

    def __post_init__(self) -> None:
        if not (_PARTE.match(self.modulo) and _PARTE.match(self.tipo) and _ID.match(self.id)):
            raise ValueError(f"Referencia no válida: «{self.modulo}:{self.tipo}:{self.id}».")

    def __str__(self) -> str:
        return f"{self.modulo}:{self.tipo}:{self.id}"

    @classmethod
    def leer(cls, texto: str) -> "Referencia":
        partes = texto.strip().split(":")
        if len(partes) != 3:
            raise ValueError(f"Referencia no válida: «{texto}» (se espera «modulo:tipo:id»).")
        return cls(*partes)


class Resolutores:
    def __init__(self) -> None:
        self._r: dict[tuple[str, str], Resolutor] = {}

    def registrar(self, modulo: str, tipo: str, resolutor: Resolutor) -> None:
        if (modulo, tipo) in self._r:
            raise ValueError(f"Ya hay quien resuelva «{modulo}:{tipo}».")
        self._r[(modulo, tipo)] = resolutor

    def sabe(self, ref: Referencia) -> bool:
        return (ref.modulo, ref.tipo) in self._r

    async def resolver(self, ref: Referencia | str) -> dict | None:
        """{titulo, estado, enlace, …} vigentes, o None si el dueño no está o el objeto ya no existe."""
        r = Referencia.leer(ref) if isinstance(ref, str) else ref
        resolutor = self._r.get((r.modulo, r.tipo))
        return await resolutor(r.id) if resolutor else None
