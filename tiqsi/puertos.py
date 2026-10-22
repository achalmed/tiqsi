"""Los puertos del anfitrión como dependencias de FastAPI: un módulo declara `Depends(usuario_actual)` con
estos marcadores, sin importar el sistema de cuentas de nadie, y el anfitrión los conecta con los suyos.

    from tiqsi.puertos import Usuario, usuario_actual

    @router.get("/algo")
    async def algo(usuario: Usuario = Depends(usuario_actual)): ...

El anfitrión (Qillqa u otro) los conecta al crearse:

    Anfitrion("qillqa", dependencias={puertos.usuario_actual: mi_usuario_actual, ...})

`Anfitrion.montar(app)` los pone en `app.dependency_overrides`: FastAPI llama a la dependencia real, con
sus propias dependencias (la cabecera de la sesión, la base). Sin anfitrión que los conecte, responden 503.
"""
from __future__ import annotations

from typing import Protocol

from fastapi import HTTPException


class Usuario(Protocol):
    """Lo que un módulo puede esperar de la persona que llama, sea cual sea el anfitrión."""

    id: int
    rol: str


def _sin_anfitrion(puerto: str):
    raise HTTPException(503, f"El puerto «{puerto}» no está conectado: el módulo corre sin anfitrión.")


async def usuario_actual() -> Usuario:
    """La persona con sesión que hace la petición (el anfitrión decide cómo se inicia sesión)."""
    _sin_anfitrion("usuario_actual")


async def solo_administrador() -> Usuario:
    """Igual, pero solo si administra (el anfitrión decide qué es administrar)."""
    _sin_anfitrion("solo_administrador")


MARCADORES = (usuario_actual, solo_administrador)
