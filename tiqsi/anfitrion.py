"""El anfitrión: valida los manifiestos, conecta lo que unos ofrecen con lo que otros necesitan, monta sus
rutas EN EL ORDEN DECLARADO y arranca sus tareas.

Qillqa es un anfitrión con todos los módulos; un proyecto que funciona solo usa un anfitrión con uno. El
anfitrión NUNCA arranca a medias: si un manifiesto está mal, si falta una capacidad que alguien necesita o
si un módulo no acepta esta versión del contrato, `registrar` lanza `ErrorDeMontaje` con todas las causas.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Iterable

from . import CONTRATO
from .capacidades import Capacidades, CapacidadDuplicada
from .compat import cumple
from .eventos import Bus
from .manifiesto import EntradaMenu, Manifiesto
from .referencias import Resolutores

registro = logging.getLogger("tiqsi.anfitrion")


_ACTIVO: "Anfitrion | None" = None


def activo() -> "Anfitrion":
    """El anfitrión del proceso (el que se activó al montar). Un módulo lo usa para pedir capacidades sin
    importar a quien las ofrece: `tiqsi.capacidad("medios.v1")`."""
    if _ACTIVO is None:
        raise RuntimeError("No hay un anfitrión activo: el módulo se usa fuera de un anfitrión (¿falta activar()?).")
    return _ACTIVO


class ErrorDeMontaje(RuntimeError):
    def __init__(self, causas: list[str]):
        self.causas = causas
        super().__init__("No se pueden montar los módulos:\n- " + "\n- ".join(causas))


class Anfitrion:
    def __init__(self, nombre: str, puertos: dict[str, Any] | None = None,
                 dependencias: dict[Any, Any] | None = None) -> None:
        """`puertos`: lo que el anfitrión ofrece a todos («identidad.v1», «archivos.v1», «avisos.v1»…).
        `dependencias`: marcador de `tiqsi.puertos` → la dependencia real de FastAPI que lo atiende."""
        self.nombre = nombre
        self.dependencias = dict(dependencias or {})
        self.capacidades = Capacidades()
        self.bus = Bus()
        self.referencias = Resolutores()
        self.modulos: list[Manifiesto] = []
        self._tareas: list[asyncio.Task] = []
        # Las bandejas de salida durables: la de cada módulo que la declara y las del propio anfitrión.
        self.bandejas: dict[str, Any] = {}
        self.intervalo_reparto = 2.0
        for capacidad, impl in (puertos or {}).items():
            self.capacidades.ofrecer(capacidad, impl, nombre)

    # --- registrar ----------------------------------------------------------------------------------
    def registrar(self, modulos: Iterable[Manifiesto]) -> None:
        nuevos = list(modulos)
        causas: list[str] = []
        ids = [m.id for m in self.modulos]
        prefijos = {p: m.id for m in self.modulos for p in m.prefijos}
        for m in nuevos:
            causas += m.errores()
            if m.id in ids:
                causas.append(f"el id «{m.id}» está repetido")
            ids.append(m.id)
            try:
                if not cumple(CONTRATO, m.contrato):
                    causas.append(f"{m.id}: acepta el contrato «{m.contrato}» y este anfitrión es {CONTRATO}")
            except ValueError as e:
                causas.append(f"{m.id}: {e}")
            for p in m.prefijos:
                if p in prefijos:
                    causas.append(f"{m.id}: el prefijo «{p}» ya es de «{prefijos[p]}»")
                prefijos[p] = m.id
        if causas:
            raise ErrorDeMontaje(causas)

        for m in nuevos:
            for nombre, impl in m.ofrece.items():
                try:
                    self.capacidades.ofrecer(nombre, impl, m.id)
                except CapacidadDuplicada as e:
                    causas.append(str(e))
        for m in nuevos:
            for nombre in m.necesita:
                if not self.capacidades.hay(nombre):
                    causas.append(f"{m.id}: necesita «{nombre}» y nadie la ofrece")
        if causas:
            raise ErrorDeMontaje(causas)

        for m in nuevos:
            for patron, manejadores in m.eventos.items():
                for manejador in manejadores:
                    self.bus.suscribir(patron, manejador, m.id)
            for tipo, resolutor in m.resolutores.items():
                self.referencias.registrar(m.id, tipo, resolutor)
            if m.bandeja is not None:
                self.bandejas[m.id] = m.bandeja
            ausentes = [c for c in m.aprovecha if not self.capacidades.hay(c)]
            if ausentes:
                registro.info("%s funciona sin %s (nadie la ofrece aquí).", m.id, ", ".join(ausentes))
            self.modulos.append(m)

    def activar(self) -> "Anfitrion":
        """Este anfitrión pasa a ser el del proceso (lo usan `tiqsi.capacidad` y compañía). Devuelve self."""
        global _ACTIVO
        _ACTIVO = self
        return self

    # --- montar ---------------------------------------------------------------------------------------
    def montar(self, app: Any) -> None:
        """Incluye los routers de cada módulo en una aplicación FastAPI, en el orden registrado, y conecta
        los marcadores de `tiqsi.puertos` con las dependencias reales del anfitrión."""
        app.dependency_overrides.update(self.dependencias)
        for m in self.modulos:
            for router in m.routers:
                app.include_router(router)

    def menu(self, rol: str = "") -> list[EntradaMenu]:
        """Las entradas del menú de todos los módulos, en orden; con `rol`, solo las que ese rol ve."""
        salida = []
        for m in self.modulos:
            for e in m.menu:
                if rol and ((e.roles and rol not in e.roles) or (e.solo_admin and rol != "administrador")):
                    continue
                salida.append(e)
        return salida

    def prefijos(self) -> dict[str, str]:
        """Prefijo de API → módulo (para apagar un módulo sin tocar a los demás)."""
        return {p: m.id for m in self.modulos for p in m.prefijos}

    def informe(self) -> list[dict]:
        """Módulo, nombre y versión de cada uno (para «Acerca de»)."""
        return [{"id": m.id, "nombre": m.nombre, "version": m.version} for m in self.modulos]

    # --- arrancar y detener ---------------------------------------------------------------------------
    async def arrancar(self) -> None:
        """Corre los ganchos de arranque en orden y lanza las tareas en segundo plano de cada módulo."""
        for m in self.modulos:
            for gancho in m.al_arrancar:
                await gancho(self)
        for m in self.modulos:
            for tarea in m.tareas:
                self._tareas.append(asyncio.create_task(tarea(self), name=f"{m.id}:{getattr(tarea, '__name__', 'tarea')}"))
        if self.bandejas:
            self._tareas.append(asyncio.create_task(self.repartidor().bucle(self.intervalo_reparto), name="repartidor"))

    def repartidor(self):
        """El repartidor de todas las bandejas de salida durables (lo lanza `arrancar`)."""
        from .bandeja import Repartidor

        return Repartidor(self.bus, self.bandejas)

    async def detener(self) -> None:
        for t in self._tareas:
            t.cancel()
        for t in self._tareas:
            try:
                await t
            except asyncio.CancelledError:
                pass
            except Exception:  # noqa: BLE001
                registro.exception("La tarea %s terminó con error.", t.get_name())
        self._tareas.clear()
