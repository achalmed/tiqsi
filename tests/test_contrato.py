"""tests/test_contrato.py — el contrato de Tiqsi: versiones, manifiestos, capacidades, eventos, referencias
y el anfitrión que los monta. Uso: python -m pytest -q tests
"""
import asyncio

import pytest

from tiqsi import (
    CONTRATO, Anfitrion, CapacidadAusente, CapacidadDuplicada, Capacidades, EntradaMenu, ErrorDeMontaje,
    Manifiesto, Referencia, Resolutores, cumple, version,
)
from tiqsi.eventos import Bus


def correr(c):
    return asyncio.run(c)


# --- versiones ------------------------------------------------------------------------------------
def test_version_y_rangos():
    assert version("0.1") == (0, 1, 0) and version("1.2.3") == (1, 2, 3)
    with pytest.raises(ValueError):
        version("uno")
    assert cumple("0.1.4", "^0.1") and not cumple("0.2.0", "^0.1")
    assert cumple("1.9.0", "^1.2") and not cumple("2.0.0", "^1.2")
    assert cumple("0.1.0", ">=0.1,<0.2") and not cumple("0.2.0", ">=0.1,<0.2")
    assert cumple("3.0.0", "") and cumple(CONTRATO, "^0.1")
    with pytest.raises(ValueError):
        cumple("0.1.0", "~0.1")


# --- manifiesto -----------------------------------------------------------------------------------
def test_manifiesto_bien_y_mal_declarado():
    assert Manifiesto(id="chat", nombre="Chat", version="0.1.0", ofrece={"mensajes.v1": object()}).errores() == []
    malo = Manifiesto(id="Chat-1", nombre=" ", version="uno", ofrece={"mensajes": 1}, prefijos=("api/x",),
                      eventos={"Recibido": []}, menu=(EntradaMenu("x", "X", "sin-barra"),))
    errores = " | ".join(malo.errores())
    for pista in ("id «Chat-1»", "falta el nombre", "Versión no válida", "capacidad «mensajes»", "evento «Recibido»",
                  "prefijo «api/x»", "ruta que empiece por /"):
        assert pista in errores


# --- capacidades ----------------------------------------------------------------------------------
def test_capacidades_necesitar_y_aprovechar():
    c = Capacidades()
    c.ofrecer("documentos.v1", "impl", "qillqasqa")
    assert c.obtener("documentos.v1") == "impl" and c.quien("documentos.v1") == "qillqasqa"
    assert c.opcional("tareas.v1") is None
    with pytest.raises(CapacidadAusente):
        c.obtener("tareas.v1")
    with pytest.raises(CapacidadDuplicada):
        c.ofrecer("documentos.v1", "otra", "intruso")


# --- eventos --------------------------------------------------------------------------------------
def test_bus_entrega_por_patron_y_aisla_al_que_falla():
    bus, recibidos = Bus(), []

    async def tareas(e):
        recibidos.append(("tareas", e.tipo, e.datos["id"]))

    async def roto(e):
        raise RuntimeError("falla a propósito")

    async def todo(e):
        recibidos.append(("todo", e.tipo))

    bus.suscribir("recibido.*", tareas, "minka")
    bus.suscribir("recibido.registrado", roto, "roto")
    bus.suscribir("*", todo, "auditoria")
    assert correr(bus.publicar("recibido.registrado", {"id": 7}, "punku")) == 2
    assert correr(bus.publicar("documento.firmado", {"id": 1}, "qillqasqa")) == 1
    assert recibidos == [("tareas", "recibido.registrado", 7), ("todo", "recibido.registrado"), ("todo", "documento.firmado")]


# --- referencias ----------------------------------------------------------------------------------
def test_referencias_se_leen_y_se_resuelven_con_su_dueno():
    r = Referencia.leer("qillqasqa:documento:123")
    assert (r.modulo, r.tipo, r.id) == ("qillqasqa", "documento", "123") and str(r) == "qillqasqa:documento:123"
    for malo in ("qillqasqa:documento", "Qillqasqa:documento:1", "a:b:c d"):
        with pytest.raises(ValueError):
            Referencia.leer(malo)

    async def doc(ident):
        return {"titulo": f"Oficio {ident}", "estado": "FIRMADO"} if ident == "123" else None

    res = Resolutores()
    res.registrar("qillqasqa", "documento", doc)
    assert correr(res.resolver("qillqasqa:documento:123"))["estado"] == "FIRMADO"
    assert correr(res.resolver("qillqasqa:documento:9")) is None
    assert correr(res.resolver("punku:recibido:1")) is None          # el dueño no está: no es un error
    with pytest.raises(ValueError):
        res.registrar("qillqasqa", "documento", doc)


# --- el anfitrión ---------------------------------------------------------------------------------
def _app_con(*modulos, puertos=None):
    from fastapi import FastAPI

    anfitrion = Anfitrion("prueba", puertos or {"identidad.v1": object()})
    anfitrion.registrar(modulos)
    app = FastAPI()
    anfitrion.montar(app)
    return anfitrion, app


def _router(prefijo, *rutas):
    from fastapi import APIRouter

    r = APIRouter(prefix=prefijo)
    for ruta, respuesta in rutas:
        r.add_api_route(ruta, (lambda v=respuesta: v), methods=["GET"])
    return r


def test_monta_en_el_orden_declarado_y_conecta_capacidades():
    from fastapi.testclient import TestClient

    documentos = Manifiesto(id="documentos", nombre="Gestión documental", version="0.1.0", prefijos=("/api/documentos",),
                            routers=[_router("/api/documentos", ("/buscar", "buscar"), ("/{ident}", "uno"))],
                            ofrece={"documentos.v1": "servicio"}, necesita=("identidad.v1",),
                            menu=(EntradaMenu("documentos", "Gestión documental", "/documentos"),))
    mesa = Manifiesto(id="mesa", nombre="Mesa de Partes", version="0.1.0", prefijos=("/api/entradas",),
                      routers=[_router("/api/entradas", ("", "lista"))], aprovecha=("documentos.v1", "tareas.v1"),
                      menu=(EntradaMenu("recibidos", "Mesa de Partes", "/recibidos", roles=("secretaria",)),))
    anfitrion, app = _app_con(documentos, mesa)
    c = TestClient(app)
    assert c.get("/api/documentos/buscar").json() == "buscar"      # la concreta antes que la genérica, como se declaró
    assert c.get("/api/documentos/5").json() == "uno"
    assert c.get("/api/entradas").json() == "lista"
    assert anfitrion.capacidades.opcional("documentos.v1") == "servicio" and anfitrion.capacidades.opcional("tareas.v1") is None
    assert [e.nombre for e in anfitrion.menu()] == ["Gestión documental", "Mesa de Partes"]
    assert [e.nombre for e in anfitrion.menu("asesor")] == ["Gestión documental"]
    assert anfitrion.prefijos() == {"/api/documentos": "documentos", "/api/entradas": "mesa"}
    assert anfitrion.informe()[1] == {"id": "mesa", "nombre": "Mesa de Partes", "version": "0.1.0"}


def test_no_arranca_a_medias():
    sin_puerto = Manifiesto(id="chat", nombre="Chat", version="0.1.0", necesita=("avisos.v1",))
    viejo = Manifiesto(id="viejo", nombre="Viejo", version="1.0.0", contrato="^1.0")
    a = Manifiesto(id="a", nombre="A", version="0.1.0", prefijos=("/api/x",), ofrece={"x.v1": 1})
    b = Manifiesto(id="b", nombre="B", version="0.1.0", prefijos=("/api/x",))
    for modulos, pista in [((sin_puerto,), "necesita «avisos.v1»"), ((viejo,), "acepta el contrato «^1.0»"),
                           ((a, b), "el prefijo «/api/x» ya es de «a»"), ((a, Manifiesto(id="a", nombre="A2", version="0.1.0")), "repetido")]:
        anfitrion = Anfitrion("prueba", {"identidad.v1": 1})
        with pytest.raises(ErrorDeMontaje) as e:
            anfitrion.registrar(modulos)
        assert pista in str(e.value)
        assert anfitrion.modulos == []                                 # nada quedó montado a medias
    dos = Anfitrion("prueba")
    with pytest.raises(ErrorDeMontaje, match="ya la ofrece"):
        dos.registrar([a, Manifiesto(id="c", nombre="C", version="0.1.0", ofrece={"x.v1": 2})])


def test_eventos_y_tareas_entre_modulos():
    visto = []

    async def al_registrar(evento):
        visto.append(("minka", evento.datos["id"], evento.origen))

    async def arranque(anfitrion):
        visto.append(("arranque", len(anfitrion.modulos)))

    async def bucle(anfitrion):
        visto.append(("tarea", "corriendo"))
        await asyncio.sleep(3600)

    minka = Manifiesto(id="minka", nombre="Tareas y Agenda", version="0.1.0", eventos={"recibido.*": [al_registrar]},
                       al_arrancar=[arranque], tareas=[bucle])
    punku = Manifiesto(id="punku", nombre="Mesa de Partes", version="0.1.0")
    anfitrion = Anfitrion("prueba")
    anfitrion.registrar([punku, minka])

    async def todo():
        await anfitrion.arrancar()
        await asyncio.sleep(0)
        entregados = await anfitrion.bus.publicar("recibido.registrado", {"id": 3}, "punku")
        await anfitrion.detener()
        return entregados

    assert correr(todo()) == 1
    assert visto == [("arranque", 2), ("tarea", "corriendo"), ("minka", 3, "punku")]


def test_el_modulo_pide_al_anfitrion_activo_sin_importarlo():
    from tiqsi import activo
    from tiqsi.modulo import capacidad, hay, opcional, publicar, resolver
    from tiqsi.capacidades import CapacidadAusente

    vistos = []

    async def escuchar(e):
        vistos.append(e.tipo)

    async def doc(ident):
        return {"titulo": f"Documento {ident}"}

    mediateca = Manifiesto(id="rikchay", nombre="Mediateca", version="0.1.0", ofrece={"medios.v1": "servicio de medios"},
                           eventos={"foto.*": [escuchar]}, resolutores={"foto": doc})
    a = Anfitrion("prueba")
    a.registrar([mediateca])
    assert a.activar() is a and activo() is a
    assert capacidad("medios.v1") == "servicio de medios" and hay("medios.v1")
    assert opcional("tareas.v1") is None and not hay("tareas.v1")
    with pytest.raises(CapacidadAusente):
        capacidad("tareas.v1")
    assert correr(publicar("foto.subida", {"id": 1}, origen="prensa")) == 1 and vistos == ["foto.subida"]
    assert correr(resolver("rikchay:foto:5")) == {"titulo": "Documento 5"}


def test_capacidad_perezosa_se_resuelve_al_usarla():
    from tiqsi.modulo import Perezosa

    class Error(Exception):
        pass

    medios = Perezosa("medios_perezosos.v1")          # se declara sin anfitrión: aún no se resuelve
    a = Anfitrion("perezoso")
    a.registrar([Manifiesto(id="rikchay", nombre="Mediateca", version="0.1.0",
                            ofrece={"medios_perezosos.v1": type("M", (), {"Error": Error, "doble": staticmethod(lambda x: 2 * x)})})])
    a.activar()
    assert medios.doble(4) == 8
    try:
        raise Error("x")
    except medios.Error:
        pass
    assert "medios_perezosos.v1" in repr(medios)


def test_los_puertos_de_identidad_los_conecta_el_anfitrion():
    from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
    from fastapi.testclient import TestClient

    from tiqsi import puertos

    router = APIRouter(prefix="/api/fotos")

    @router.get("")
    async def lista(usuario=Depends(puertos.usuario_actual)):
        return {"quien": usuario["nombre"]}

    @router.delete("")
    async def vaciar(usuario=Depends(puertos.solo_administrador)):
        return {"ok": True}

    async def real_usuario(authorization: str = Header(default="")):
        if authorization != "Bearer bueno":
            raise HTTPException(401, "sin sesión")
        return {"nombre": "Ana", "rol": "asesor"}

    async def real_admin(u=Depends(real_usuario)):
        if u["rol"] != "administrador":
            raise HTTPException(403, "solo administración")
        return u

    m = Manifiesto(id="rikchay", nombre="Mediateca", version="0.1.0", routers=[router])
    a = Anfitrion("prueba", dependencias={puertos.usuario_actual: real_usuario, puertos.solo_administrador: real_admin})
    a.registrar([m])
    app = FastAPI()
    a.montar(app)
    c = TestClient(app)
    assert c.get("/api/fotos").status_code == 401
    assert c.get("/api/fotos", headers={"Authorization": "Bearer bueno"}).json() == {"quien": "Ana"}
    assert c.delete("/api/fotos", headers={"Authorization": "Bearer bueno"}).status_code == 403
    sola = FastAPI()                     # el mismo módulo sin anfitrión que conecte los puertos
    sola.include_router(router)
    assert TestClient(sola).get("/api/fotos").status_code == 503


def test_enviar_archivo_revalida_y_sirve_tramos(tmp_path):
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient

    from tiqsi.web import enviar_archivo, rango_pedido

    archivo = tmp_path / "v.bin"
    archivo.write_bytes(bytes(range(256)) * 4)
    app = FastAPI()

    @app.get("/a")
    async def a(peticion: Request):
        return enviar_archivo(archivo, "v.bin", "application/octet-stream", peticion, rangos=True)

    c = TestClient(app)
    r = c.get("/a")
    assert r.status_code == 200 and r.headers["cache-control"] == "private, no-cache, must-revalidate"
    assert c.get("/a", headers={"If-None-Match": r.headers["etag"]}).status_code == 304
    t = c.get("/a", headers={"Range": "bytes=10-19"})
    assert t.status_code == 206 and t.content == bytes(range(10, 20))
    assert rango_pedido("bytes=-500", 1024) == (524, 1023) and rango_pedido("x", 10) is None


# --- superficies ----------------------------------------------------------------------------------
def test_una_superficie_solo_ofrece_lo_que_declara():
    from tiqsi import Superficie

    def hoy(x):
        return x + 1

    s = Superficie("cosas.v1", {"hoy": lambda: hoy}, donde="servicios/cosas.py")
    assert s.hoy(1) == 2 and dir(s) == ["hoy"]
    for ausente in ("manana", "_privada", "__dict__x"):
        with pytest.raises(AttributeError, match="no es parte de «cosas.v1» \\(servicios/cosas.py\\)"):
            getattr(s, ausente)
    # Se resuelve al usarla: un cambio posterior (una prueba con monkeypatch) se ve.
    funciones = {"hoy": lambda: (lambda x: x * 10)}
    assert Superficie("cosas.v1", funciones).hoy(2) == 20
