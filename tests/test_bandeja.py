"""La bandeja de salida durable y su repartidor (fase 10.2b): entrega al menos una vez, reintento, tope, SQL."""
import asyncio

import pytest
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tiqsi import bandeja_sql
from tiqsi.anfitrion import Anfitrion
from tiqsi.bandeja import BandejaEnMemoria, Repartidor
from tiqsi.eventos import Bus
from tiqsi.manifiesto import Manifiesto


def correr(c):
    return asyncio.run(c)


def test_entrega_y_marca_entregado_con_id_estable():
    bus, recibidos = Bus(), []

    async def oir(e):
        recibidos.append((e.tipo, e.datos, e.id))

    bus.suscribir("foto.*", oir, "otro")
    b = BandejaEnMemoria()
    b.guardar("foto.subida", {"id": 7}, "fototeca")
    rep = Repartidor(bus, {"fototeca": b})
    assert correr(rep.ronda()) == {"entregados": 1, "fallidos": 0}
    assert recibidos == [("foto.subida", {"id": 7}, "fototeca:1")]
    # Ya entregado: la ronda siguiente no lo repite.
    assert correr(rep.ronda()) == {"entregados": 0, "fallidos": 0}


def test_sin_suscriptores_se_da_por_entregado():
    b = BandejaEnMemoria()
    b.guardar("nadie.escucha")
    assert correr(Repartidor(Bus(), {"m": b}).ronda())["entregados"] == 1


def test_un_manejador_que_falla_se_reintenta_hasta_el_tope():
    bus, veces = Bus(), {"n": 0}

    async def roto(e):
        veces["n"] += 1
        raise RuntimeError("caído")

    bus.suscribir("*", roto, "tareas")
    b = BandejaEnMemoria(max_intentos=3)
    b.guardar("x.y")
    rep = Repartidor(bus, {"m": b})
    for _ in range(5):
        correr(rep.ronda())
    assert veces["n"] == 3                            # tres intentos y queda a la vista, sin entregar
    fila = b.filas[0]
    assert not fila["entregado"] and fila["intentos"] == 3 and "tareas: RuntimeError: caído" in fila["error"]


def test_el_que_falla_no_impide_a_los_demas_y_se_recupera():
    bus, ok, estado = Bus(), [], {"caido": True}

    async def bien(e):
        ok.append(e.id)

    async def a_veces(e):
        if estado["caido"]:
            raise RuntimeError("todavía no")

    bus.suscribir("*", bien, "a")
    bus.suscribir("*", a_veces, "b")
    b = BandejaEnMemoria()
    b.guardar("x.y")
    rep = Repartidor(bus, {"m": b})
    assert correr(rep.ronda())["fallidos"] == 1
    estado["caido"] = False
    assert correr(rep.ronda())["entregados"] == 1
    # Al menos una vez: el que estaba bien lo recibió dos veces, con el mismo id para reconocerlo.
    assert ok == ["m:1", "m:1"]


def test_publicar_cuenta_los_que_recibieron():
    bus = Bus()

    async def bien(e): ...

    async def mal(e):
        raise ValueError

    bus.suscribir("a.*", bien)
    bus.suscribir("a.*", mal)
    bus.suscribir("b.*", bien)
    assert correr(bus.publicar("a.x")) == 1


def test_bandeja_sql_guarda_en_la_transaccion_y_reparte():
    async def caso():
        motor = create_async_engine("sqlite+aiosqlite:///:memory:")
        meta = MetaData()
        tabla = bandeja_sql.tabla_bandeja(meta)
        async with motor.begin() as c:
            await c.run_sync(meta.create_all)
        fabrica = async_sessionmaker(motor, expire_on_commit=False)
        # Una transacción que se deshace no deja evento (todo o nada).
        async with fabrica() as s:
            await bandeja_sql.guardar(s, tabla, "foto.borrada", {"id": 1}, "fototeca")
            await s.rollback()
        async with fabrica() as s:
            await bandeja_sql.guardar(s, tabla, "foto.subida", {"id": 2}, "fototeca")
            await s.commit()
        bus, recibidos = Bus(), []

        async def oir(e):
            recibidos.append((e.tipo, e.datos, e.id))

        bus.suscribir("foto.*", oir)
        b = bandeja_sql.BandejaSQL(fabrica, tabla)
        rep = Repartidor(bus, {"fototeca": b})
        primera, segunda = await rep.ronda(), await rep.ronda()
        quedan = await b.pendientes(10)
        await motor.dispose()
        return primera, segunda, recibidos, quedan

    primera, segunda, recibidos, quedan = correr(caso())
    assert primera["entregados"] == 1 and segunda["entregados"] == 0
    assert recibidos == [("foto.subida", {"id": 2}, "fototeca:1")]
    assert quedan == []


def test_el_anfitrion_reparte_la_bandeja_del_modulo():
    async def caso():
        b = BandejaEnMemoria()
        b.guardar("m.algo", {"k": 1}, "m")
        recibidos = []

        async def oir(e):
            recibidos.append(e.id)

        anf = Anfitrion("prueba")
        anf.intervalo_reparto = 0.01
        anf.registrar([Manifiesto(id="m", nombre="Módulo", version="0.1.0", bandeja=b,
                                  eventos={"m.*": [oir]})])
        assert anf.bandejas == {"m": b}
        await anf.arrancar()
        for _ in range(50):
            if recibidos:
                break
            await asyncio.sleep(0.01)
        await anf.detener()
        return recibidos

    assert correr(caso()) == ["m:1"]
