"""tests/test_minimo.py — el anfitrión mínimo: un módulo funciona solo, con cuentas locales y su sesión."""
import json
import os
import stat

import pytest

from tiqsi import Manifiesto
from tiqsi.minimo import Cuentas, _principal, crear_app, firmar, leer

SECRETO = "s" * 40


def test_fichas_firmadas():
    f = firmar({"sub": "1"}, SECRETO)
    assert leer(f, SECRETO)["sub"] == "1"
    assert leer(f, "otro" * 10) is None
    carga, firma = f.split(".")
    assert leer(carga[:-2] + "xx." + firma, SECRETO) is None
    assert leer(firmar({"sub": "1"}, SECRETO, minutos=-1), SECRETO) is None
    assert leer("basura", SECRETO) is None and leer("", SECRETO) is None


def test_cuentas_sin_clave_en_claro(tmp_path):
    archivo = tmp_path / "cuentas.json"
    c = Cuentas(archivo)
    ana = c.crear("Ana", "clave-larga-1", "administrador", "Ana Pérez")
    assert ana["usuario"] == "ana" and "hash" not in ana
    assert stat.S_IMODE(os.stat(archivo).st_mode) == 0o600
    assert "clave-larga-1" not in archivo.read_text()
    assert c.verificar("ANA", "clave-larga-1")["id"] == 1 and c.verificar("ana", "otra-clave-9") is None
    for malo in (("ana", "clave-larga-1", "asesor"), ("beto", "corta", "asesor"), ("beto", "clave-larga-2", "jefe")):
        with pytest.raises(ValueError):
            c.crear(*malo)
    assert c.crear("beto", "clave-larga-2")["id"] == 2 and c.por_id(2)["rol"] == "asesor"


def test_un_modulo_solo_con_su_sesion(tmp_path):
    from fastapi import APIRouter, Depends
    from fastapi.testclient import TestClient

    from tiqsi import puertos
    from tiqsi.modulo import capacidad, opcional

    arranques = []
    router = APIRouter(prefix="/api/fotos")

    @router.get("")
    async def lista(u=Depends(puertos.usuario_actual)):
        quien = await capacidad("identidad.v1").persona(u.id)
        return {"quien": quien["nombre"], "semanas": opcional("semanas.v1") is not None}

    @router.delete("")
    async def vaciar(u=Depends(puertos.solo_administrador)):
        return {"ok": True}

    async def al_arrancar(anfitrion):
        arranques.append(anfitrion.nombre)

    cuentas = tmp_path / "cuentas.json"
    Cuentas(cuentas).crear("ana", "clave-larga-1", "administrador", "Ana Pérez")
    Cuentas(cuentas).crear("beto", "clave-larga-2", "asesor", "Beto Ríos")
    m = Manifiesto(id="rikchay", nombre="Mediateca", version="0.3.0", routers=[router], necesita=("identidad.v1",),
                   aprovecha=("semanas.v1",), al_arrancar=[al_arrancar])
    app = crear_app([m], nombre="Mediateca", secreto=SECRETO, cuentas=cuentas)
    with TestClient(app) as c:
        assert arranques == ["Mediateca"]
        assert c.get("/api/health").json() == {"api": "ok", "anfitrion": "Mediateca"}
        assert c.get("/api/anfitrion").json()["modulos"] == [{"id": "rikchay", "nombre": "Mediateca", "version": "0.3.0"}]
        assert c.get("/api/fotos").status_code == 401
        assert c.post("/api/auth/login", json={"usuario": "ana", "clave": "mala-clave-9"}).status_code == 401
        ana = c.post("/api/auth/login", json={"usuario": "ana", "clave": "clave-larga-1"}).json()
        beto = c.post("/api/auth/login", json={"usuario": "beto", "clave": "clave-larga-2"}).json()
        cab = {"Authorization": f"Bearer {ana['token']}"}
        assert c.get("/api/fotos", headers=cab).json() == {"quien": "Ana Pérez", "semanas": False}
        assert c.delete("/api/fotos", headers=cab).json() == {"ok": True}
        assert c.delete("/api/fotos", headers={"Authorization": f"Bearer {beto['token']}"}).status_code == 403
        assert c.get("/api/fotos", headers={"Authorization": "Bearer " + firmar({"sub": "9"}, SECRETO)}).status_code == 401
    with pytest.raises(ValueError, match="32 caracteres"):
        crear_app([m], nombre="x", secreto="corto", cuentas=cuentas)


def test_orden_para_crear_cuentas(tmp_path, monkeypatch, capsys):
    archivo = tmp_path / "c.json"
    monkeypatch.setenv("TIQSI_CLAVE", "clave-larga-3")
    assert _principal(["cuenta", str(archivo), "carla", "--rol", "administrador", "--nombre", "Carla"]) == 0
    assert json.loads(archivo.read_text())["cuentas"][0]["usuario"] == "carla"
    assert _principal(["cuenta", str(archivo), "carla"]) == 1
    assert "ya existe" in capsys.readouterr().out


def test_sirve_la_pagina_del_modulo_sin_tapar_la_api(tmp_path):
    from fastapi.testclient import TestClient

    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<!doctype html><title>Mediateca</title>", encoding="utf-8")
    m = Manifiesto(id="rikchay", nombre="Mediateca", version="0.1.0")
    c = TestClient(crear_app([m], nombre="Mediateca", secreto=SECRETO, cuentas=tmp_path / "c.json", web=web))
    assert "<title>Mediateca</title>" in c.get("/").text
    assert c.get("/api/health").json()["api"] == "ok"
    assert c.post("/api/auth/login", json={"usuario": "x", "clave": "y"}).status_code == 401


def test_identidad_da_las_cuentas_completas(tmp_path):
    """«identidad.v1».cuenta y .cuentas: la misma ficha que en Qillqa (Rendición la usa para el comisionado)."""
    import asyncio

    archivo = tmp_path / "cuentas.json"
    Cuentas(archivo).crear("ana", "clave-larga-1", "administrador", "Ana Pérez Soto", "Asesora", "Ana", "12345678")
    app = crear_app([Manifiesto(id="m", nombre="Módulo", version="0.1.0", necesita=("identidad.v1",))],
                    nombre="Prueba", secreto=SECRETO, cuentas=archivo)
    identidad = app.state.anfitrion.capacidades.obtener("identidad.v1")
    ana = {"id": 1, "usuario": "ana", "nombre_completo": "Ana Pérez Soto", "nombres": "Ana", "cargo": "Asesora",
           "dni": "12345678", "rol": "administrador", "activo": True}
    assert asyncio.run(identidad.cuenta(1)) == ana
    assert asyncio.run(identidad.cuentas()) == [ana]
    assert asyncio.run(identidad.cuenta(7)) is None


def test_la_pagina_abre_en_un_enlace_directo(tmp_path):
    """Un enlace a una pantalla del módulo («/rendiciones/3») devuelve la página; la API y los archivos que faltan,
    no (404)."""
    from fastapi.testclient import TestClient

    web = tmp_path / "web"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text("<html>pagina</html>", encoding="utf-8")
    (web / "assets" / "a.js").write_text("1", encoding="utf-8")
    c = TestClient(crear_app([Manifiesto(id="m", nombre="Módulo", version="0.1.0")], nombre="P", secreto=SECRETO,
                             cuentas=tmp_path / "c.json", web=web))
    assert c.get("/").text == "<html>pagina</html>"
    assert c.get("/rendiciones/3").text == "<html>pagina</html>"
    assert c.get("/assets/a.js").text == "1"
    assert c.get("/assets/falta.js").status_code == 404
    assert c.get("/api/no-existe").status_code == 404
