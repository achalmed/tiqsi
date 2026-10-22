"""El manifiesto: lo que un módulo declara de sí mismo para que un anfitrión (Qillqa u otro) lo monte.

Un módulo nunca importa el código de otro módulo. Dice lo que OFRECE (capacidades con nombre y versión,
«documentos.v1»), lo que NECESITA (sin eso no arranca: «identidad.v1», que da cualquier anfitrión) y lo que
APROVECHA si está («tareas.v1»: sin ella, esa parte se apaga con elegancia). El anfitrión los conecta.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from .compat import version

ID = re.compile(r"^[a-z][a-z0-9_]*$")
CAPACIDAD = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*\.v\d+$")
TIPO_EVENTO = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_*]+)+$|^\*$")

Gancho = Callable[[Any], Awaitable[None]]          # async def gancho(anfitrion) -> None
Manejador = Callable[[Any], Awaitable[None]]       # async def manejador(evento) -> None
Resolutor = Callable[[str], Awaitable["dict | None"]]  # async def resolver(id) -> {titulo, estado, enlace} | None


@dataclass(frozen=True)
class EntradaMenu:
    """Una entrada del menú de la plataforma. El nombre va en castellano y por su función."""

    id: str
    nombre: str
    ruta: str
    descripcion: str = ""
    roles: tuple[str, ...] = ()
    solo_admin: bool = False


@dataclass
class Manifiesto:
    id: str
    nombre: str
    version: str
    contrato: str = "^0.1"
    routers: list = field(default_factory=list)
    prefijos: tuple[str, ...] = ()
    ofrece: dict[str, Any] = field(default_factory=dict)
    necesita: tuple[str, ...] = ()
    aprovecha: tuple[str, ...] = ()
    eventos: dict[str, list[Manejador]] = field(default_factory=dict)
    resolutores: dict[str, Resolutor] = field(default_factory=dict)
    al_arrancar: list[Gancho] = field(default_factory=list)
    tareas: list[Gancho] = field(default_factory=list)
    menu: tuple[EntradaMenu, ...] = ()
    publico: bool = False
    # Su bandeja de salida durable (tiqsi.bandeja: una tabla en SU base); el anfitrión la reparte al bus.
    bandeja: Any = None

    def errores(self) -> list[str]:
        """Lo que está mal declarado (vacío = válido). El anfitrión no monta un manifiesto con errores."""
        e: list[str] = []
        if not ID.match(self.id):
            e.append(f"id «{self.id}»: minúsculas, dígitos y guion bajo, empezando por letra")
        if not self.nombre.strip():
            e.append(f"{self.id}: falta el nombre (en castellano, por su función)")
        try:
            version(self.version)
        except ValueError as x:
            e.append(f"{self.id}: {x}")
        for c in (*self.ofrece, *self.necesita, *self.aprovecha):
            if not CAPACIDAD.match(c):
                e.append(f"{self.id}: capacidad «{c}» (se escribe «nombre.vN», p. ej. «documentos.v1»)")
        for t in self.eventos:
            if not TIPO_EVENTO.match(t):
                e.append(f"{self.id}: evento «{t}» (se escribe «modulo.algo», con * como comodín)")
        for p in self.prefijos:
            if not p.startswith("/"):
                e.append(f"{self.id}: prefijo «{p}» debe empezar por /")
        for m in self.menu:
            if not m.ruta.startswith("/"):
                e.append(f"{self.id}: la entrada de menú «{m.nombre}» debe tener una ruta que empiece por /")
        return e
