"""La base PROPIA de un módulo (SQLAlchemy asíncrono; extra `[sql]`; fase 10.2b de la plataforma Qillqa, 2026-10-20).

- `crear_base_si_falta(url)`: crea la base de PostgreSQL desde la base de mantenimiento «postgres» del mismo
  servidor (con el mismo usuario). Idempotente. En SQLite no hace nada (el archivo nace solo).
- `separar(origen, destino, metadata)`: lleva las tablas de un módulo de la base donde vivían (la documental del
  anfitrión) a la suya. SIMULA por omisión (dice qué copiaría); con `aplicar=True` copia cada fila con su id, en
  orden de dependencias, sigue cada secuencia desde donde iba la del origen (un id que se usó y se borró no se
  vuelve a dar: una referencia vieja «rend:15» no puede pasar a nombrar otra cosa) y VERIFICA que cada tabla tenga en el destino las mismas filas
  con la misma huella. Nunca borra ni cambia el origen; se niega si el destino ya tiene datos.

    await separar(URL_DOCUMENTAL, URL_PROPIA, BaseRendicion.metadata, aplicar=True)

- `sin_separar(propia, origen, tablas)`: el seguro de arranque. True si la base propia es otra, sus tablas clave están
  vacías y en el origen alguna tiene filas: arrancar así empezaría un módulo vacío y lo de antes quedaría a la vista de
  nadie (separe primero). Sin el origen a la vista, False: no hay nada que proteger.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from sqlalchemy import MetaData, func, insert, inspect, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine


async def crear_base_si_falta(url: Any) -> bool:
    """True si la creó."""
    u = make_url(url) if isinstance(url, str) else url   # nunca str(URL): oculta la clave
    if not u.drivername.startswith("postgresql"):
        return False
    nombre = u.database or ""
    if not re.fullmatch(r"[a-z0-9_]+", nombre):
        raise RuntimeError(f"Nombre de base no válido: {nombre!r}")
    mantenimiento = create_async_engine(u.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        async with mantenimiento.connect() as conexion:
            if (await conexion.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": nombre})).scalar():
                return False
            await conexion.execute(text(f'CREATE DATABASE "{nombre}"'))
            return True
    finally:
        await mantenimiento.dispose()


class ErrorDeSeparacion(RuntimeError):
    pass


def _huella(filas: list[dict]) -> str:
    """La huella de una tabla: cada fila con sus columnas en orden alfabético, como texto, ordenadas."""
    lineas = sorted(json.dumps({k: f[k] for k in sorted(f)}, default=str, ensure_ascii=False) for f in filas)
    return hashlib.md5("\n".join(lineas).encode()).hexdigest()


async def _filas(conexion, tabla) -> list[dict]:
    return [dict(f) for f in (await conexion.execute(select(tabla))).mappings().all()]


async def _existe(conexion, nombre: str) -> bool:
    return await conexion.run_sync(lambda c: inspect(c).has_table(nombre))


def _serial(t):
    """La columna de la clave primaria con secuencia (id entero único), o None."""
    cols = list(t.primary_key.columns)
    if len(cols) == 1 and cols[0].autoincrement in (True, "auto") and cols[0].type.python_type is int:
        return cols[0]
    return None


async def _siguientes(conexion, tablas) -> dict[str, int]:
    """El próximo valor de la secuencia de cada tabla en el ORIGEN (PostgreSQL); 0 si no tiene o no se sabe."""
    salida = {}
    if conexion.dialect.name != "postgresql":
        return salida
    for t in tablas:
        col = _serial(t)
        if col is None or not await _existe(conexion, t.name):
            continue
        sec = (await conexion.execute(text("SELECT pg_get_serial_sequence(:t, :c)"), {"t": t.name, "c": col.name})).scalar()
        if sec:
            ultimo, llamado = (await conexion.execute(text(f"SELECT last_value, is_called FROM {sec}"))).one()
            salida[t.name] = ultimo + 1 if llamado else ultimo
    return salida


async def _copiar(d, t, filas: list[dict], lote: int) -> None:
    """Las filas de `t`, en orden de clave primaria. Si la tabla se apunta a sí misma (un tema que cuelga de otro, la
    respuesta a un mensaje), esas columnas entran vacías y se ponen cuando ya están todas las filas: el orden de los ids
    no importa y la clave foránea se cumple en todo momento (las columnas deben admitir NULL)."""
    pk = list(t.primary_key.columns)
    if pk:
        filas = sorted(filas, key=lambda f: tuple((f[c.name] is None, f[c.name]) for c in pk))
    propias = sorted({fk.parent.name for fk in t.foreign_keys if fk.column.table is t})
    entran = [{**f, **{c: None for c in propias}} for f in filas] if propias else filas
    for i in range(0, len(entran), lote):
        await d.execute(insert(t), entran[i:i + lote])
    if propias and pk:
        for f in filas:
            valores = {c: f[c] for c in propias if f[c] is not None}
            if valores:
                await d.execute(update(t).where(*[c == f[c.name] for c in pk]).values(**valores))


async def separar(origen: str, destino: str, metadata: MetaData, *, aplicar: bool = False,
                  lote: int = 500) -> dict[str, dict]:
    """{tabla: {filas, huella}}. Lo que falta en el origen cuenta como vacío (una tabla nueva del módulo)."""
    if make_url(origen) == make_url(destino):
        raise ErrorDeSeparacion("El origen y el destino son la misma base.")
    m_origen, m_destino = create_async_engine(origen), create_async_engine(destino)
    tablas = metadata.sorted_tables
    try:
        async with m_origen.connect() as o:
            leidas = {t.name: (await _filas(o, t) if await _existe(o, t.name) else []) for t in tablas}
            siguientes = await _siguientes(o, tablas)
        plan = {n: {"filas": len(f), "huella": _huella(f)} for n, f in leidas.items()}
        if not aplicar:
            return plan
        async with m_destino.begin() as d:
            await d.run_sync(metadata.create_all)
            ocupadas = [t.name for t in tablas if (await d.execute(select(func.count()).select_from(t))).scalar()]
            if ocupadas:
                raise ErrorDeSeparacion(f"El destino ya tiene datos en {', '.join(ocupadas)}: no se mezcla.")
            for t in tablas:
                filas = leidas[t.name]
                await _copiar(d, t, filas, lote)
                col = _serial(t)
                if d.dialect.name == "postgresql" and col is not None:
                    maximo = max((f[col.name] for f in filas), default=0)
                    await d.execute(text(f"SELECT setval(pg_get_serial_sequence('{t.name}', '{col.name}'), :n, false)"),
                                    {"n": max(maximo + 1, siguientes.get(t.name, 0), 1)})
        async with m_destino.connect() as d:
            for t in tablas:
                copia = await _filas(d, t)
                if len(copia) != plan[t.name]["filas"] or _huella(copia) != plan[t.name]["huella"]:
                    raise ErrorDeSeparacion(f"{t.name}: la copia no coincide con el origen (filas o huella).")
        return plan
    finally:
        await m_origen.dispose()
        await m_destino.dispose()


async def _filas_de(conexion, tabla: str) -> int:
    if not re.fullmatch(r"[a-z0-9_]+", tabla):
        raise ValueError(f"Nombre de tabla no válido: {tabla!r}")
    if not await _existe(conexion, tabla):
        return 0
    return (await conexion.execute(text(f'SELECT count(*) FROM "{tabla}"'))).scalar() or 0


async def sin_separar(propia: str, origen: str, tablas: tuple[str, ...] | list[str]) -> bool:
    """¿La base propia (otra que el origen) tiene vacías sus `tablas` y el origen aún las tiene con filas?"""
    if not propia or not origen or make_url(propia) == make_url(origen):
        return False
    m_propia, m_origen = create_async_engine(propia), create_async_engine(origen)
    try:
        async with m_propia.connect() as c:
            for tabla in tablas:
                if await _filas_de(c, tabla):
                    return False
        async with m_origen.connect() as c:
            for tabla in tablas:
                if await _filas_de(c, tabla):
                    return True
        return False
    except ValueError:
        raise
    except Exception:  # noqa: BLE001 — sin el origen (o la propia) a la vista no hay nada que proteger
        return False
    finally:
        await m_propia.dispose()
        await m_origen.dispose()
