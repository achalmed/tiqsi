"""Lo que todo módulo necesita saber de un PDF sin abrirlo con nada pesado: cuántas páginas tiene (fase 10.2b; nace en
Qillqa, `servicios/pdf.py`, y se mueve aquí el 2026-10-20 para que la Mesa de Partes cuente las páginas de lo que
recibe sin importar a Qillqa).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path


def contar_paginas(ruta: Path | None) -> int | None:
    """Páginas del PDF o None si no se pudo determinar.

    Primero `pdfinfo` (poppler, presente en el host donde corre la API);
    si no está, un rastreo binario de "/Type /Page" como aproximación
    (falla en PDFs con object streams comprimidos: devuelve None antes
    que un número incorrecto)."""
    if ruta is None or not ruta.is_file():
        return None
    try:
        salida = subprocess.run(
            ["pdfinfo", str(ruta)], capture_output=True, text=True, timeout=20
        )
        m = re.search(r"^Pages:\s+(\d+)", salida.stdout, re.MULTILINE)
        if m:
            return int(m.group(1))
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        crudo = ruta.read_bytes()
        # /Count del árbol de páginas raíz (si está sin comprimir).
        conteos = re.findall(rb"/Type\s*/Pages[^>]*?/Count\s+(\d+)", crudo)
        if conteos:
            return max(int(c) for c in conteos)
    except OSError:
        pass
    return None
