"""Versiones y rangos (SemVer reducido): con qué versión del contrato trabaja cada módulo.

Una versión es «MAYOR.MENOR.PARCHE» (el parche es opcional: «0.1» = «0.1.0»). Un rango es una lista de
condiciones separadas por coma, todas obligatorias: «>=0.1,<0.2», «==0.1.3», o la forma corta «^0.1»
(compatible: mismo MAYOR, o mismo MENOR si el MAYOR es 0, como en npm y Cargo).
"""
from __future__ import annotations

import re

_VERSION = re.compile(r"^(\d+)\.(\d+)(?:\.(\d+))?$")
_CONDICION = re.compile(r"^(>=|<=|==|>|<|\^)\s*(\d+\.\d+(?:\.\d+)?)$")


def version(texto: str) -> tuple[int, int, int]:
    """«0.1» → (0, 1, 0). Un texto que no es versión es un error, no un cero."""
    m = _VERSION.match(texto.strip())
    if not m:
        raise ValueError(f"Versión no válida: «{texto}» (se espera MAYOR.MENOR[.PARCHE]).")
    return int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)


def _techo_compatible(v: tuple[int, int, int]) -> tuple[int, int, int]:
    mayor, menor, _ = v
    return (mayor + 1, 0, 0) if mayor > 0 else (0, menor + 1, 0)


def cumple(texto_version: str, rango: str) -> bool:
    """¿La versión cae dentro del rango? Rango vacío = cualquiera."""
    v = version(texto_version)
    for parte in (p.strip() for p in rango.split(",") if p.strip()):
        m = _CONDICION.match(parte)
        if not m:
            raise ValueError(f"Rango no válido: «{rango}» (p. ej. «>=0.1,<0.2» o «^0.1»).")
        op, otra = m.group(1), version(m.group(2))
        ok = {
            ">=": v >= otra, "<=": v <= otra, "==": v == otra, ">": v > otra, "<": v < otra,
            "^": otra <= v < _techo_compatible(otra),
        }[op]
        if not ok:
            return False
    return True
