"""La bandeja de salida DURABLE: un evento que se guarda en la misma transacción que el cambio que lo origina y
que el repartidor entrega al bus aunque la API se reinicie entre medio (fase 10.2b de la plataforma Qillqa).

    async with sesion.begin():                    # el cambio y su evento, todo o nada
        sesion.add(foto)
        await bandeja_sql.guardar(sesion, TABLA, "fototeca.foto.subida", {"id": foto.id}, origen="fototeca")

El repartidor lee lo pendiente de cada bandeja, lo entrega al bus y lo marca entregado; si un manejador falla,
lo reintenta en la ronda siguiente (hasta `max_intentos`; después queda en la bandeja con su error, a la vista).
Es entrega «al menos una vez»: cada evento lleva un id estable (`Evento.id`) para que un manejador no haga dos
veces lo mismo. Cada módulo tiene su bandeja en SU base (una transacción no cruza bases); el anfitrión las
reparte todas.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from .eventos import Bus, Evento

registro = logging.getLogger("tiqsi.bandeja")


@dataclass
class Pendiente:
    id: int
    tipo: str
    datos: dict[str, Any]
    origen: str
    intentos: int = 0


class Bandeja(Protocol):
    async def pendientes(self, limite: int) -> list[Pendiente]: ...
    async def entregado(self, ident: int) -> None: ...
    async def fallo(self, ident: int, error: str) -> None: ...


@dataclass
class BandejaEnMemoria:
    """Para pruebas y para un anfitrión sin base: lo mismo que una bandeja SQL, sin durabilidad."""

    max_intentos: int = 8
    filas: list[dict] = field(default_factory=list)

    def guardar(self, tipo: str, datos: dict | None = None, origen: str = "") -> int:
        ident = len(self.filas) + 1
        self.filas.append({"id": ident, "tipo": tipo, "datos": dict(datos or {}), "origen": origen,
                           "entregado": False, "intentos": 0, "error": ""})
        return ident

    async def pendientes(self, limite: int) -> list[Pendiente]:
        return [Pendiente(f["id"], f["tipo"], f["datos"], f["origen"], f["intentos"]) for f in self.filas
                if not f["entregado"] and f["intentos"] < self.max_intentos][:limite]

    async def entregado(self, ident: int) -> None:
        self.filas[ident - 1]["entregado"] = True

    async def fallo(self, ident: int, error: str) -> None:
        self.filas[ident - 1]["intentos"] += 1
        self.filas[ident - 1]["error"] = error


class Repartidor:
    """Entrega al bus lo pendiente de cada bandeja («módulo» → bandeja), en orden, una ronda tras otra."""

    def __init__(self, bus: Bus, bandejas: dict[str, Bandeja]) -> None:
        self.bus = bus
        self.bandejas = bandejas

    async def ronda(self, limite: int = 100) -> dict[str, int]:
        cuenta = {"entregados": 0, "fallidos": 0}
        for nombre, bandeja in self.bandejas.items():
            for p in await bandeja.pendientes(limite):
                fallos = await self.bus.entregar(Evento(p.tipo, p.datos, p.origen, id=f"{nombre}:{p.id}"))
                if fallos:
                    await bandeja.fallo(p.id, "; ".join(fallos)[:1000])
                    cuenta["fallidos"] += 1
                else:
                    await bandeja.entregado(p.id)
                    cuenta["entregados"] += 1
        return cuenta

    async def bucle(self, intervalo: float = 2.0) -> None:
        while True:
            try:
                await self.ronda()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001  (una bandeja caída no detiene a las demás en la próxima ronda)
                registro.exception("La ronda del repartidor falló; se reintenta.")
            await asyncio.sleep(intervalo)
