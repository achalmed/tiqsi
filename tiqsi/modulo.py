"""Lo que un módulo usa de su anfitrión SIN importarlo: capacidades, eventos y referencias.

Dentro de un módulo no se importa a otro módulo ni al anfitrión: se pide al anfitrión activo lo que se
necesita, cuando se necesita (en el momento de atender, no al importar):

    from tiqsi.modulo import capacidad, opcional, publicar

    medios = capacidad("medios.v1")          # la necesita: si falta, CapacidadAusente
    tareas = opcional("tareas.v1")           # la aprovecha: si falta, None y esa parte no se ofrece
    await publicar("recibido.registrado", {"id": 7}, origen="punku")
"""
from __future__ import annotations

from typing import Any

from .anfitrion import activo
from .referencias import Referencia


def capacidad(nombre: str) -> Any:
    return activo().capacidades.obtener(nombre)


def opcional(nombre: str) -> Any | None:
    return activo().capacidades.opcional(nombre)


def hay(nombre: str) -> bool:
    return activo().capacidades.hay(nombre)


class Perezosa:
    """Una capacidad que se resuelve al USARLA, no al importar: `medios = Perezosa("medios.v1")` en lo alto
    del archivo y `medios.registrar(...)` dentro de una función. Sirve también en un `except medios.Error:`,
    que se evalúa recién cuando hay una excepción. Fuera de un anfitrión activo, falla al usarse."""

    def __init__(self, nombre: str) -> None:
        object.__setattr__(self, "_nombre", nombre)

    def __getattr__(self, atributo: str) -> Any:
        return getattr(capacidad(object.__getattribute__(self, "_nombre")), atributo)

    def __repr__(self) -> str:
        return f"<capacidad perezosa «{object.__getattribute__(self, '_nombre')}»>"


async def publicar(tipo: str, datos: dict | None = None, origen: str = "") -> int:
    return await activo().bus.publicar(tipo, datos, origen)


async def resolver(ref: Referencia | str) -> dict | None:
    return await activo().referencias.resolver(ref)
