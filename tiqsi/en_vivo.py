"""tiqsi.en_vivo — difusión en vivo dentro del proceso del anfitrión (venía de Qillqa, `servicios/difusor.py`; fase 10.2b
de la plataforma, 2026-10-20: el chat —Rimay— lo usa también cuando corre solo).

Cada pestaña conectada a un WebSocket se suscribe con su `usuario_id` y recibe una cola; `publicar(usuario_ids,
carga)` deja el mismo dict en la cola de cada pestaña de esas personas. Sin Redis ni colas externas: el anfitrión corre
en un solo proceso; si un día hay varios, aquí entra LISTEN/NOTIFY de PostgreSQL sin tocar a los que publican. Una
cola llena (una pestaña colgada) descarta el mensaje más viejo: la API es la verdad y el socket, la aceleración.

Qué mira cada pestaña: la web cuenta por el socket si está a la vista y qué conversación tiene abierta
(`{"tipo": "viendo", "canal_id": N|null, "visible": bool}`); con eso `a_la_vista` y `viendo` deciden si algo merece un
aviso push (nadie lo está mirando) o basta el sonido dentro de la aplicación. Todos los módulos del proceso comparten
este estado (es un módulo de Python: una sola copia).
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

log = logging.getLogger("tiqsi.en_vivo")
TAM_COLA = 200

_suscripciones: dict[int, set[asyncio.Queue]] = defaultdict(set)
# Por pestaña: (canal abierto o None, ¿la pestaña está a la vista?). La web lo dice apenas se
# conecta; una que nunca lo dice (una versión vieja de la web) cuenta como NO a la vista: mejor un
# aviso de más que uno que nunca llega.
_mirando: dict[asyncio.Queue, tuple[int | None, bool]] = {}


def suscribir(usuario_id: int) -> asyncio.Queue:
    cola: asyncio.Queue = asyncio.Queue(maxsize=TAM_COLA)
    _suscripciones[usuario_id].add(cola)
    _mirando[cola] = (None, False)
    return cola


def cancelar(usuario_id: int, cola: asyncio.Queue) -> None:
    _suscripciones[usuario_id].discard(cola)
    _mirando.pop(cola, None)
    if not _suscripciones[usuario_id]:
        _suscripciones.pop(usuario_id, None)


def conectados() -> set[int]:
    return {uid for uid, colas in _suscripciones.items() if colas}


def publicar(usuario_ids: set[int] | list[int], carga: dict) -> int:
    """Entrega `carga` a cada pestaña de cada usuario; devuelve cuántas pestañas la recibieron."""
    n = 0
    for uid in set(usuario_ids):
        for cola in list(_suscripciones.get(uid, ())):
            if cola.full():
                try:
                    cola.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                cola.put_nowait(carga)
                n += 1
            except asyncio.QueueFull:
                log.warning("Cola llena para el usuario %s: se descarta", uid)
    return n


def poner_mirando(cola: asyncio.Queue, canal_id: int | None, visible: bool) -> None:
    """Lo que la pestaña dice que mira (`{"tipo": "viendo"}` del socket)."""
    if cola in _mirando:
        _mirando[cola] = (canal_id, bool(visible))


def a_la_vista(usuario_id: int) -> bool:
    """¿Tiene alguna pestaña de Qillqa a la vista? Entonces no hace falta un aviso push: el
    sonido y el contador de la aplicación bastan."""
    return any(_mirando.get(c, (None, False))[1] for c in _suscripciones.get(usuario_id, ()))


def viendo(usuario_id: int, canal_id: int) -> bool:
    """¿Tiene ESA conversación abierta y a la vista? (ni sonido ni aviso)."""
    return any(_mirando.get(c) == (canal_id, True) for c in _suscripciones.get(usuario_id, ()))
