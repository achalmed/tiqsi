"""La bandeja de salida en SQL (SQLAlchemy asíncrono): una tabla en la base del módulo (fase 10.2b).

    TABLA = tabla_bandeja(BaseMediateca.metadata)          # «tiqsi_bandeja», la crea create_all con las demás
    await guardar(sesion, TABLA, "fototeca.foto.subida", {"id": 7}, origen="fototeca")   # sin commit: lo da quien llama
    BANDEJA = BandejaSQL(SesionMediateca, TABLA)          # la que reparte el anfitrión
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Integer, MetaData, String, Table, Text, func, insert, select, update

from .bandeja import Pendiente


def tabla_bandeja(metadata: MetaData, nombre: str = "tiqsi_bandeja") -> Table:
    return Table(
        nombre, metadata,
        Column("id", Integer, primary_key=True),
        Column("tipo", String(80), nullable=False, index=True),
        Column("datos", JSON, nullable=False, default=dict),
        Column("origen", String(60), nullable=False, default=""),
        Column("creado_en", DateTime(timezone=True), server_default=func.now()),
        Column("entregado_en", DateTime(timezone=True), nullable=True, index=True),
        Column("intentos", Integer, nullable=False, default=0),
        Column("error", Text, nullable=False, default=""),
    )


async def guardar(sesion: Any, tabla: Table, tipo: str, datos: dict | None = None, origen: str = "") -> None:
    """El evento, en la transacción de `sesion` (sin commit)."""
    await sesion.execute(insert(tabla).values(tipo=tipo, datos=dict(datos or {}), origen=origen, intentos=0, error=""))


class BandejaSQL:
    def __init__(self, fabrica: Any, tabla: Table, max_intentos: int = 8) -> None:
        self.fabrica = fabrica          # async_sessionmaker de la base del módulo
        self.tabla = tabla
        self.max_intentos = max_intentos

    async def pendientes(self, limite: int) -> list[Pendiente]:
        t = self.tabla
        async with self.fabrica() as sesion:
            filas = (await sesion.execute(
                select(t.c.id, t.c.tipo, t.c.datos, t.c.origen, t.c.intentos)
                .where(t.c.entregado_en.is_(None), t.c.intentos < self.max_intentos).order_by(t.c.id).limit(limite)
            )).all()
        return [Pendiente(f.id, f.tipo, dict(f.datos or {}), f.origen, f.intentos) for f in filas]

    async def entregado(self, ident: int) -> None:
        async with self.fabrica() as sesion:
            await sesion.execute(update(self.tabla).where(self.tabla.c.id == ident)
                                 .values(entregado_en=datetime.now(timezone.utc), error=""))
            await sesion.commit()

    async def fallo(self, ident: int, error: str) -> None:
        async with self.fabrica() as sesion:
            await sesion.execute(update(self.tabla).where(self.tabla.c.id == ident)
                                 .values(intentos=self.tabla.c.intentos + 1, error=error[:1000]))
            await sesion.commit()
