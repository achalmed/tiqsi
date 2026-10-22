"""La base propia de un módulo (fase 10.2b): separar sus tablas de la base del anfitrión, simulando y verificando."""
import asyncio

import pytest
from sqlalchemy import JSON, Column, ForeignKey, Integer, MetaData, String, Table
from sqlalchemy.ext.asyncio import create_async_engine

from tiqsi.sql import ErrorDeSeparacion, crear_base_si_falta, separar, sin_separar


def _modelo():
    meta = MetaData()
    padre = Table("m_padre", meta, Column("id", Integer, primary_key=True), Column("nombre", String(20)))
    hija = Table("m_hija", meta, Column("id", Integer, primary_key=True),
                 Column("padre_id", ForeignKey("m_padre.id")), Column("datos", JSON))
    nueva = Table("m_nueva", meta, Column("clave", String(10), primary_key=True), Column("valor", JSON))
    return meta, padre, hija, nueva


async def _origen(url):
    """La base del anfitrión con las tablas del módulo (sin la nueva) y una tabla ajena."""
    meta, padre, hija, _ = _modelo()
    ajena = MetaData()
    Table("ajena", ajena, Column("id", Integer, primary_key=True))
    motor = create_async_engine(url)
    async with motor.begin() as c:
        await c.run_sync(lambda s: padre.create(s))
        await c.run_sync(lambda s: hija.create(s))
        await c.run_sync(ajena.create_all)
        await c.execute(padre.insert(), [{"id": 3, "nombre": "uno"}, {"id": 9, "nombre": "dos"}])
        await c.execute(hija.insert(), [{"id": 5, "padre_id": 9, "datos": {"a": [1, 2]}}])
    await motor.dispose()


def test_simula_copia_y_verifica(tmp_path):
    origen, destino = f"sqlite+aiosqlite:///{tmp_path}/o.db", f"sqlite+aiosqlite:///{tmp_path}/d.db"

    async def caso():
        await _origen(origen)
        meta, padre, hija, nueva = _modelo()
        plan = await separar(origen, destino, meta)
        assert {k: v["filas"] for k, v in plan.items()} == {"m_padre": 2, "m_hija": 1, "m_nueva": 0}
        assert not (tmp_path / "d.db").exists() or (tmp_path / "d.db").stat().st_size == 0   # simular no escribe
        hecho = await separar(origen, destino, meta, aplicar=True)
        assert hecho == plan
        motor = create_async_engine(destino)
        async with motor.connect() as c:
            filas = (await c.execute(hija.select())).mappings().all()
            tablas = await c.run_sync(lambda s: __import__("sqlalchemy").inspect(s).get_table_names())
        await motor.dispose()
        assert [dict(f) for f in filas] == [{"id": 5, "padre_id": 9, "datos": {"a": [1, 2]}}]   # con su id
        assert "ajena" not in tablas                                                          # solo lo del módulo
        with pytest.raises(ErrorDeSeparacion, match="ya tiene datos"):
            await separar(origen, destino, meta, aplicar=True)                                # nunca mezcla

    asyncio.run(caso())


def test_no_separa_una_base_en_si_misma(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path}/o.db"
    with pytest.raises(ErrorDeSeparacion, match="misma base"):
        asyncio.run(separar(url, url, _modelo()[0]))


def test_crear_base_en_sqlite_no_hace_nada(tmp_path):
    assert asyncio.run(crear_base_si_falta(f"sqlite+aiosqlite:///{tmp_path}/x.db")) is False


def test_una_tabla_que_se_apunta_a_si_misma_se_copia_entera(tmp_path):
    """Rimay R3: `canales.padre_id` y `mensajes.padre_id` apuntan a su propia tabla. Las filas entran en orden de clave y
    lo que apunta a la misma tabla se pone al final: da igual que el padre tenga un id mayor que su hijo."""
    origen, destino = f"sqlite+aiosqlite:///{tmp_path}/o.db", f"sqlite+aiosqlite:///{tmp_path}/d.db"
    meta = MetaData()
    canal = Table("t_canal", meta, Column("id", Integer, primary_key=True), Column("padre_id", ForeignKey("t_canal.id"), nullable=True),
                  Column("nombre", String(20)))
    filas = [{"id": 2, "padre_id": 7, "nombre": "hija"}, {"id": 7, "padre_id": None, "nombre": "madre"},
             {"id": 4, "padre_id": 2, "nombre": "nieta"}]

    async def caso():
        motor = create_async_engine(origen)
        async with motor.begin() as c:
            await c.run_sync(meta.create_all)
            await c.execute(canal.insert(), filas)
        await motor.dispose()
        await separar(origen, destino, meta, aplicar=True)
        motor = create_async_engine(destino)
        async with motor.connect() as c:
            copia = [dict(f) for f in (await c.execute(canal.select().order_by(canal.c.id))).mappings()]
        await motor.dispose()
        assert copia == sorted(filas, key=lambda f: f["id"])

    asyncio.run(caso())



def test_el_seguro_de_arranque(tmp_path):
    """Propia vacía y origen con filas: no arranca. Propia con filas, origen vacío, misma base o sin origen: arranca."""
    origen, propia = f"sqlite+aiosqlite:///{tmp_path / 'o.db'}", f"sqlite+aiosqlite:///{tmp_path / 'p.db'}"
    asyncio.run(_origen(origen))
    assert asyncio.run(sin_separar(propia, origen, ("m_padre", "m_hija"))) is True
    assert asyncio.run(sin_separar(propia, origen, ("m_nueva",))) is False          # el origen no la tiene
    assert asyncio.run(sin_separar(origen, origen, ("m_padre",))) is False          # la misma base
    assert asyncio.run(sin_separar(propia, "", ("m_padre",))) is False
    meta, *_ = _modelo()
    asyncio.run(separar(origen, propia, meta, aplicar=True))
    assert asyncio.run(sin_separar(propia, origen, ("m_padre", "m_hija"))) is False  # ya separada
    with pytest.raises(ValueError):
        asyncio.run(sin_separar(propia, origen, ("m_padre; DROP",)))
