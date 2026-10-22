"""El registro de capacidades: quién ofrece cada «nombre.vN» y cómo se pide.

El anfitrión ofrece los puertos («identidad.v1», «archivos.v1», «avisos.v1», «ajustes.v1»); cada módulo
ofrece las suyas. Pedir una que nadie ofrece es un error si se NECESITA (`obtener`) y un `None` si solo se
APROVECHA (`opcional`): así un módulo funciona solo y, junto a otros, hace más.
"""
from __future__ import annotations

from typing import Any


class CapacidadAusente(LookupError):
    """Nadie ofrece esa capacidad en este anfitrión."""


class CapacidadDuplicada(ValueError):
    """Dos módulos ofrecen la misma capacidad: el anfitrión no puede elegir por ellos."""


class Capacidades:
    def __init__(self) -> None:
        self._impl: dict[str, Any] = {}
        self._de: dict[str, str] = {}

    def ofrecer(self, nombre: str, implementacion: Any, modulo: str) -> None:
        if nombre in self._impl:
            raise CapacidadDuplicada(f"«{nombre}» ya la ofrece «{self._de[nombre]}»; «{modulo}» no puede ofrecerla también.")
        self._impl[nombre] = implementacion
        self._de[nombre] = modulo

    def hay(self, nombre: str) -> bool:
        return nombre in self._impl

    def obtener(self, nombre: str) -> Any:
        try:
            return self._impl[nombre]
        except KeyError:
            raise CapacidadAusente(f"Nadie ofrece «{nombre}» en este anfitrión.") from None

    def opcional(self, nombre: str) -> Any | None:
        return self._impl.get(nombre)

    def quien(self, nombre: str) -> str | None:
        return self._de.get(nombre)

    def ofrecidas(self) -> dict[str, str]:
        """Capacidad → módulo que la ofrece (para «Acerca de» y para depurar)."""
        return dict(sorted(self._de.items()))


class Superficie:
    """Lo que un módulo ofrece como capacidad, con una lista EXPLÍCITA de funciones: cada nombre se resuelve al usarlo
    (una prueba con monkeypatch ve la función de hoy) y lo que no está en la lista no existe para quien la pide.

        DOCUMENTOS_V1 = Superficie("documentos.v1", {"documento": lambda: documento, "recientes": lambda: recientes})
        Manifiesto(..., ofrece={"documentos.v1": DOCUMENTOS_V1})
    """

    def __init__(self, nombre: str, funciones: dict, donde: str = "") -> None:
        self._nombre, self._funciones, self._donde = nombre, funciones, donde

    def __getattr__(self, nombre: str) -> Any:
        if nombre.startswith("_") or nombre not in self._funciones:
            donde = f" ({self._donde})" if self._donde else ""
            raise AttributeError(f"«{nombre}» no es parte de «{self._nombre}»{donde}")
        return self._funciones[nombre]()

    def __dir__(self):
        return sorted(self._funciones)
