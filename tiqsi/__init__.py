"""Tiqsi («cimiento» en quechua): el contrato con que los proyectos se conectan a un anfitrión.

Qillqa es el anfitrión que reúne a todos; cada proyecto (el chat, la mesa de partes, la Mediateca…) es un
módulo que declara un `Manifiesto` y puede funcionar solo con un anfitrión mínimo o junto a los demás.
"""
VERSION = "0.1.0"
CONTRATO = "0.1.0"

from .anfitrion import Anfitrion, ErrorDeMontaje, activo  # noqa: E402
from .capacidades import CapacidadAusente, CapacidadDuplicada, Capacidades, Superficie  # noqa: E402
from .compat import cumple, version  # noqa: E402
from .eventos import Bus, Evento  # noqa: E402
from .manifiesto import EntradaMenu, Manifiesto  # noqa: E402
from .referencias import Referencia, Resolutores  # noqa: E402

__all__ = [
    "VERSION", "CONTRATO", "Anfitrion", "ErrorDeMontaje", "activo", "Capacidades", "CapacidadAusente", "CapacidadDuplicada",
    "cumple", "version", "Bus", "Evento", "EntradaMenu", "Manifiesto", "Referencia", "Resolutores", "Superficie",
]
