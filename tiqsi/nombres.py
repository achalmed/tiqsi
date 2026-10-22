"""Los nombres de archivo de la plataforma: `sanear`, `unico_en` y el largo máximo `LIMITE` (fase 10.2b; nacen en
Qillqa, `servicios/nombres.py`, y se mueven aquí el 2026-10-20 para que todo módulo use la MISMA convención sin
importar a Qillqa: `sanear` para la Mediateca y Rendición, `unico_en` y `LIMITE` para la Mesa de Partes).
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

# Largo máximo de un nombre de archivo, con su extensión (Windows y los ZIP lo aguantan holgados).
LIMITE = 100

# Palabras que no aportan nada al final de un nombre truncado: «…-de-la-» o
# «…-para» sobran y hacen que el nombre parezca cortado a la fuerza.
_VACIAS = {"de", "del", "la", "el", "los", "las", "en", "y", "a", "al", "con",
           "por", "para", "un", "una", "the", "of"}


def sanear(texto: str, maximo: int = 60) -> str:
    """Texto libre → trozo de nombre de archivo: sin tildes, sin caracteres
    problemáticos, palabras unidas por un solo guion y cortado POR PALABRAS
    (nunca a media palabra, que es lo que produce nombres ilegibles)."""
    base = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    base = re.sub(r"[^A-Za-z0-9]+", "-", base).strip("-")
    base = re.sub(r"-{2,}", "-", base)
    if len(base) <= maximo:
        return base
    corte = base[:maximo]
    if "-" in corte:
        corte = corte.rsplit("-", 1)[0]  # sin dejar media palabra
    partes = [p for p in corte.split("-") if p]
    while len(partes) > 1 and partes[-1].lower() in _VACIAS:
        partes.pop()
    return "-".join(partes) or base[:maximo].strip("-")


def unico_en(carpeta: Path, nombre: str) -> str:
    """El mismo nombre si está libre; si no, «…-2», «…-3». Sustituye al
    prefijo con el id que se usaba para garantizar unicidad."""
    destino = carpeta / nombre
    if not destino.exists():
        return nombre
    tallo, ext = Path(nombre).stem, Path(nombre).suffix
    for i in range(2, 100):
        candidato = f"{tallo}-{i}{ext}"
        if not (carpeta / candidato).exists():
            return candidato
    return nombre
