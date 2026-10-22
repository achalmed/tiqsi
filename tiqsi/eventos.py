"""El bus de eventos dentro del proceso: un módulo cuenta lo que pasó y no sabe quién escucha.

«recibido.registrado» lo publica la Mesa de Partes; las Tareas crean la tarea, el Chat avisa en su canal. Si
el que escucha no está (funciona solo), no pasa nada. Un manejador que falla no detiene a los demás ni al
que publicó: se anota y sigue. Los tipos admiten comodín al final o en medio («recibido.*», «*»).

La entrega DURABLE (el evento se guarda en la misma transacción que el cambio y se entrega aunque la API se
reinicie) la hacen la bandeja de salida y su repartidor (`tiqsi.bandeja`): este bus entrega lo que le dan.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from fnmatch import fnmatchcase
from typing import Any, Awaitable, Callable

registro = logging.getLogger("tiqsi.eventos")

Manejador = Callable[["Evento"], Awaitable[None]]


@dataclass(frozen=True)
class Evento:
    tipo: str
    datos: dict[str, Any]
    origen: str
    cuando: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # Id estable cuando viene de una bandeja durable («fototeca:12»): un manejador lo usa para no hacer dos veces
    # lo mismo si el evento le llega otra vez (la entrega durable es «al menos una vez»).
    id: str = ""


class Bus:
    def __init__(self) -> None:
        self._suscritos: list[tuple[str, str, Manejador]] = []

    def suscribir(self, patron: str, manejador: Manejador, modulo: str = "") -> None:
        self._suscritos.append((patron, modulo, manejador))

    def suscripciones(self) -> list[tuple[str, str]]:
        return [(p, m) for p, m, _ in self._suscritos]

    async def publicar(self, tipo: str, datos: dict[str, Any] | None = None, origen: str = "") -> int:
        """Entrega el evento a cada suscripción que coincide; devuelve a cuántas llegó bien."""
        evento = Evento(tipo, dict(datos or {}), origen)
        return len(self._coinciden(tipo)) - len(await self.entregar(evento))

    def _coinciden(self, tipo: str) -> list[tuple[str, str, Manejador]]:
        return [s for s in list(self._suscritos) if fnmatchcase(tipo, s[0])]

    async def entregar(self, evento: Evento) -> list[str]:
        """Entrega un evento ya armado; devuelve los fallos («modulo: error»), vacío si todos lo recibieron.
        Un manejador que falla no impide a los demás."""
        fallos = []
        for patron, modulo, manejador in self._coinciden(evento.tipo):
            try:
                await manejador(evento)
            except Exception as e:  # noqa: BLE001  (un manejador roto no rompe al que publica)
                registro.exception("El manejador de «%s» en «%s» falló con «%s».", patron, modulo or "?", evento.tipo)
                fallos.append(f"{modulo or patron}: {type(e).__name__}: {e}"[:300])
        return fallos
