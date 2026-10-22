"""El anfitrión MÍNIMO: para que un módulo funcione solo, sin Qillqa ni ningún otro anfitrión.

Da lo que todo módulo necesita y nada más: cuentas locales (un archivo JSON con claves derivadas por scrypt),
inicio de sesión con fichas firmadas (HMAC-SHA256, sin dependencias), la identidad conectada a los marcadores
de `tiqsi.puertos`, el puerto «identidad.v1» y el arranque y la parada de los módulos. Lo que el módulo solo
APROVECHA (otros módulos) no está, y el módulo funciona sin eso.

    from tiqsi.minimo import crear_app
    app = crear_app([MANIFIESTO], nombre="Mediateca", secreto=..., cuentas="…/cuentas.json")

    python -m tiqsi.minimo cuenta …/cuentas.json ana --rol administrador --nombre "Ana Pérez"   # pide la clave

Las rutas del anfitrión son las de Qillqa donde coinciden (`POST /api/auth/login`, `GET /api/health`), para que la
misma web pueda hablar con uno u otro.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from . import CONTRATO, VERSION
from . import puertos as marcadores
from .anfitrion import Anfitrion
from .manifiesto import Manifiesto

ROLES = ("administrador", "asesor", "secretaria", "invitado")


class Credenciales(BaseModel):
    usuario: str
    clave: str
MINUTOS_SESION = 12 * 60


# --- fichas firmadas --------------------------------------------------------------------------------------
def _b64(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).decode().rstrip("=")


def _desb64(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def firmar(datos: dict, secreto: str, minutos: int = MINUTOS_SESION) -> str:
    carga = _b64(json.dumps({**datos, "exp": int(time.time()) + 60 * minutos}, separators=(",", ":")).encode())
    return f"{carga}.{_b64(hmac.new(secreto.encode(), carga.encode(), hashlib.sha256).digest())}"


def leer(ficha: str, secreto: str) -> dict | None:
    """Los datos de una ficha válida y vigente, o None (falta, alterada o vencida)."""
    try:
        carga, firma = ficha.split(".")
        esperada = _b64(hmac.new(secreto.encode(), carga.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(firma, esperada):
            return None
        datos = json.loads(_desb64(carga))
        return datos if datos.get("exp", 0) > time.time() else None
    except (ValueError, json.JSONDecodeError):
        return None


# --- cuentas locales ---------------------------------------------------------------------------------------
def _derivar(clave: str, sal: bytes) -> str:
    return hashlib.scrypt(clave.encode(), salt=sal, n=2**14, r=8, p=1).hex()


class Cuentas:
    """Cuentas en un archivo JSON (permiso 600). Nunca guarda claves: sal y derivación scrypt."""

    def __init__(self, archivo: str | Path) -> None:
        self.archivo = Path(archivo)

    def _leer(self) -> list[dict]:
        if not self.archivo.is_file():
            return []
        return json.loads(self.archivo.read_text(encoding="utf-8")).get("cuentas", [])

    def _escribir(self, cuentas: list[dict]) -> None:
        self.archivo.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.archivo.with_suffix(".tmp")
        tmp.write_text(json.dumps({"cuentas": cuentas}, ensure_ascii=False, indent=1), encoding="utf-8")
        os.chmod(tmp, 0o600)
        tmp.replace(self.archivo)

    def crear(self, usuario: str, clave: str, rol: str = "asesor", nombre: str = "", cargo: str = "",
              nombres: str = "", dni: str = "") -> dict:
        usuario = usuario.strip().lower()
        if not usuario or len(clave) < 8:
            raise ValueError("Usuario obligatorio y clave de 8 caracteres o más.")
        if rol not in ROLES:
            raise ValueError(f"Rol «{rol}»: uno de {', '.join(ROLES)}.")
        cuentas = self._leer()
        if any(c["usuario"] == usuario for c in cuentas):
            raise ValueError(f"La cuenta «{usuario}» ya existe.")
        sal = secrets.token_bytes(16)
        cuenta = {"id": max((c["id"] for c in cuentas), default=0) + 1, "usuario": usuario, "nombre": nombre or usuario,
                  "cargo": cargo, "nombres": nombres, "dni": dni, "rol": rol, "activo": True, "sal": sal.hex(),
                  "hash": _derivar(clave, sal)}
        self._escribir(cuentas + [cuenta])
        return {k: v for k, v in cuenta.items() if k not in ("sal", "hash")}

    def verificar(self, usuario: str, clave: str) -> dict | None:
        for c in self._leer():
            if c["usuario"] == usuario.strip().lower() and c.get("activo", True):
                if hmac.compare_digest(c["hash"], _derivar(clave, bytes.fromhex(c["sal"]))):
                    return c
        return None

    def por_id(self, ident: int) -> dict | None:
        return next((c for c in self._leer() if c["id"] == ident and c.get("activo", True)), None)

    def todas(self) -> list[dict]:
        """Todas las cuentas (también las inactivas), sin sal ni derivación."""
        return [{k: v for k, v in c.items() if k not in ("sal", "hash")} for c in self._leer()]


def ficha_cuenta(c: dict) -> dict:
    """La cuenta como la da «identidad.v1».cuenta en todo anfitrión: {id, usuario, nombre_completo, nombres, cargo,
    dni, rol, activo}."""
    return {"id": c["id"], "usuario": c["usuario"], "nombre_completo": c.get("nombre") or c["usuario"],
            "nombres": c.get("nombres", ""), "cargo": c.get("cargo", ""), "dni": c.get("dni", ""), "rol": c["rol"],
            "activo": bool(c.get("activo", True))}


def _persona(c: dict) -> SimpleNamespace:
    return SimpleNamespace(id=c["id"], rol=c["rol"], nombre_usuario=c["usuario"], nombre_completo=c["nombre"],
                           cargo=c.get("cargo", ""))


# --- la aplicación ------------------------------------------------------------------------------------------
def crear_app(modulos: list[Manifiesto], *, nombre: str, secreto: str, cuentas: str | Path,
              puertos: dict[str, Any] | None = None, web: str | Path | None = None) -> FastAPI:
    """Una aplicación FastAPI con estos módulos y nada más. `secreto` firma las sesiones (mínimo 32 caracteres).
    `web`: la carpeta de la página del módulo (la cáscara mínima de Tiqsi web, construida), servida en la raíz."""
    if len(secreto) < 32:
        raise ValueError("El secreto de sesión debe tener al menos 32 caracteres.")
    registro = Cuentas(cuentas)

    async def usuario_actual(authorization: str = Header(default="")) -> SimpleNamespace:
        datos = leer(authorization.removeprefix("Bearer ").strip(), secreto)
        cuenta = registro.por_id(int(datos["sub"])) if datos and str(datos.get("sub", "")).isdigit() else None
        if cuenta is None:
            raise HTTPException(401, "Inicie sesión.")
        return _persona(cuenta)

    async def de_ficha(token: str) -> SimpleNamespace | None:
        """La cuenta de una ficha de sesión, sin cabeceras (un WebSocket la manda en la dirección); None si no vale."""
        datos = leer((token or "").strip(), secreto)
        cuenta = registro.por_id(int(datos["sub"])) if datos and str(datos.get("sub", "")).isdigit() else None
        return _persona(cuenta) if cuenta else None

    async def solo_administrador(u: SimpleNamespace = Depends(usuario_actual)) -> SimpleNamespace:
        if u.rol != "administrador":
            raise HTTPException(403, "Solo administración.")
        return u

    async def persona(ident: int) -> dict | None:
        c = registro.por_id(int(ident))
        return {"nombre": c["nombre"], "cargo": c.get("cargo", "")} if c else None

    async def cuenta(ident: int) -> dict | None:
        c = next((x for x in registro.todas() if x["id"] == int(ident)), None)
        return ficha_cuenta(c) if c else None

    async def cuentas() -> list[dict]:
        return [ficha_cuenta(c) for c in registro.todas()]

    anfitrion = Anfitrion(nombre, puertos={
        "identidad.v1": SimpleNamespace(usuario_actual=usuario_actual, solo_administrador=solo_administrador, persona=persona,
                                        cuenta=cuenta, cuentas=cuentas, de_ficha=de_ficha),
        **(puertos or {}),
    }, dependencias={marcadores.usuario_actual: usuario_actual, marcadores.solo_administrador: solo_administrador})
    anfitrion.registrar(modulos)
    anfitrion.activar()

    @asynccontextmanager
    async def ciclo(_app):
        await anfitrion.arrancar()
        yield
        await anfitrion.detener()

    app = FastAPI(title=nombre, version=modulos[0].version if len(modulos) == 1 else VERSION, lifespan=ciclo)

    propio = APIRouter(prefix="/api")

    @propio.post("/auth/login")
    async def iniciar_sesion(credenciales: Credenciales) -> dict:
        c = registro.verificar(credenciales.usuario, credenciales.clave)
        if c is None:
            raise HTTPException(401, "Usuario o clave incorrectos.")
        return {"token": firmar({"sub": str(c["id"])}, secreto), "rol": c["rol"], "nombre": c["nombre"]}

    @propio.get("/health")
    async def salud() -> dict:
        return {"api": "ok", "anfitrion": nombre}

    @propio.get("/anfitrion")
    async def acerca() -> dict:
        return {"anfitrion": nombre, "contrato": CONTRATO, "tiqsi": VERSION, "modulos": anfitrion.informe(),
                "capacidades": anfitrion.capacidades.ofrecidas()}

    app.include_router(propio)
    anfitrion.montar(app)
    if web is not None and Path(web).is_dir():
        from fastapi.staticfiles import StaticFiles
        from starlette.exceptions import HTTPException as HTTPExceptionStarlette

        class Pagina(StaticFiles):
            """Los archivos de la página y, para cualquier otra dirección que no sea de la API, su index.html: un
            enlace directo a una pantalla del módulo («/rendiciones/3») abre la página y su enrutador la muestra."""

            async def get_response(self, ruta: str, scope):
                try:
                    return await super().get_response(ruta, scope)
                except HTTPExceptionStarlette as e:
                    if e.status_code != 404 or ruta.startswith("api/") or Path(ruta).suffix:
                        raise
                    return await super().get_response("index.html", scope)

        app.mount("/", Pagina(directory=Path(web), html=True), name="web")   # después de la API: no la tapa
    app.state.anfitrion = anfitrion
    return app


def _principal(argv: list[str]) -> int:
    import argparse
    import getpass

    p = argparse.ArgumentParser(prog="python -m tiqsi.minimo", description="Cuentas del anfitrión mínimo.")
    sub = p.add_subparsers(dest="orden", required=True)
    c = sub.add_parser("cuenta", help="crea una cuenta (la clave se pide sin mostrarla, o por TIQSI_CLAVE)")
    c.add_argument("archivo")
    c.add_argument("usuario")
    c.add_argument("--rol", default="asesor", choices=ROLES)
    c.add_argument("--nombre", default="")
    c.add_argument("--cargo", default="")
    c.add_argument("--nombres", default="", help="los nombres de pila (cómo se la nombra en una línea breve)")
    c.add_argument("--dni", default="")
    a = p.parse_args(argv)
    clave = os.environ.get("TIQSI_CLAVE") or getpass.getpass("Clave (8 o más caracteres): ")
    try:
        cuenta = Cuentas(a.archivo).crear(a.usuario, clave, a.rol, a.nombre, a.cargo, a.nombres, a.dni)
    except ValueError as e:
        print(f"[error] {e}")
        return 1
    print(f"Cuenta «{cuenta['usuario']}» ({cuenta['rol']}) creada en {a.archivo}.")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_principal(sys.argv[1:]))
