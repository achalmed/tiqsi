"""tests/test_en_vivo.py — la difusión en vivo dentro del proceso (tiqsi.en_vivo; venía de Qillqa, Rimay R2)."""
from tiqsi import en_vivo


def test_publica_a_cada_pestaña_y_sabe_que_mira():
    a, b = en_vivo.suscribir(1), en_vivo.suscribir(1)
    c = en_vivo.suscribir(2)
    try:
        assert en_vivo.conectados() >= {1, 2}
        assert en_vivo.publicar({1}, {"tipo": "mensaje"}) == 2 and c.empty()
        assert a.get_nowait() == b.get_nowait() == {"tipo": "mensaje"}
        assert not en_vivo.a_la_vista(1)          # hasta que la pestaña diga qué mira, no cuenta como a la vista
        en_vivo.poner_mirando(a, 5, True)
        assert en_vivo.a_la_vista(1) and en_vivo.viendo(1, 5) and not en_vivo.viendo(1, 6)
    finally:
        en_vivo.cancelar(1, a), en_vivo.cancelar(1, b), en_vivo.cancelar(2, c)
    assert 1 not in en_vivo.conectados() and 2 not in en_vivo.conectados()


def test_una_cola_llena_descarta_lo_mas_viejo():
    cola = en_vivo.suscribir(9)
    try:
        for i in range(en_vivo.TAM_COLA + 3):
            en_vivo.publicar({9}, {"n": i})
        assert cola.qsize() == en_vivo.TAM_COLA and cola.get_nowait() == {"n": 3}
    finally:
        en_vivo.cancelar(9, cola)
