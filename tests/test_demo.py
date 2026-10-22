"""tests/test_demo.py — el exportador de demos (tiqsi.demo): el árbol sale de lo versionado, sin lo excluido, con lo
propio de la demo y las sustituciones; el escáner no deja salir nada privado; la rama de la demo es huérfana y publicar
no empuja una rama con historia de main. Con un repositorio de git temporal (sin red: el remoto es una carpeta).
"""
import re
import subprocess
from pathlib import Path

import pytest

from tiqsi import demo


def _git(raiz, *a):
    return subprocess.run(["git", *a], cwd=raiz, capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def proyecto(tmp_path):
    raiz = tmp_path / "proyecto"
    (raiz / "app").mkdir(parents=True)
    _git(raiz, "init", "-q", "-b", "main")
    _git(raiz, "config", "user.email", "prueba@example.com")
    _git(raiz, "config", "user.name", "Prueba")
    (raiz / "app" / "hola.py").write_text('NOMBRE = "Despacho Secreto"\nCORREO = "ana@example.com"\n')
    (raiz / "app" / "privado.txt").write_text("no sale\n")
    (raiz / "README.md").write_text("Proyecto de PRUEBA\n")
    d = raiz / "demo"
    (d / "vendor").mkdir(parents=True)
    (d / "vendor" / "LEEME-DEMO.md").write_text("Esta es la demo.\n")
    (d / "demo.conf").write_text("NOMBRE=Prueba\nREMOTO=" + str(tmp_path / "remoto.git") + "\nRAMA=demo\nRAMA_REMOTA=main\n"
                                 "AUTOR=Autor Demo\nCORREO_AUTOR=demo@example.com\nCORREO_DOMINIOS=example.com\n")
    (d / "excluir.txt").write_text("app/privado.txt\ndemo/\n")
    (d / "sustituciones.tsv").write_text("README.md\tPRUEBA\tdemostración\n")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", "inicio")
    privado = tmp_path / "privado"
    privado.mkdir()
    (privado / "sustituciones.tsv").write_text("*\tDespacho Secreto\tDespacho de ejemplo\n")
    subprocess.run(["git", "init", "-q", "--bare", str(tmp_path / "remoto.git")], check=True)
    return demo.Receta(raiz=raiz, demo=d, privado=privado, cache="prueba-demo")


def test_el_arbol_sale_limpio_y_la_rama_es_huerfana(proyecto, tmp_path, capsys):
    arbol = tmp_path / "arbol"
    assert demo.principal(proyecto, ["--salida", str(arbol)]) == 0
    assert not (arbol / "app" / "privado.txt").exists() and not (arbol / "demo").exists()
    assert (arbol / "LEEME-DEMO.md").exists()
    assert (arbol / "README.md").read_text() == "Proyecto de demostración\n"
    assert "Despacho de ejemplo" in (arbol / "app" / "hola.py").read_text()
    assert "Simulación" in capsys.readouterr().out and not demo.punta(proyecto.raiz, "demo")
    assert demo.principal(proyecto, ["--salida", str(arbol), "--aplicar"]) == 0
    assert demo.punta(proyecto.raiz, "demo") and demo.comparte_historia(proyecto.raiz, "demo") is False
    # Sin cambios, otra vez: nada que comprometer (la misma punta).
    antes = demo.punta(proyecto.raiz, "demo")
    assert demo.principal(proyecto, ["--salida", str(arbol), "--aplicar"]) == 0
    assert demo.punta(proyecto.raiz, "demo") == antes


# Lo que el escáner debe atrapar se arma aquí, por trozos: así este archivo no lo trae escrito y su propia demo sale limpia.
CORREO_REAL, IP_PUBLICA, CELULAR = "jefe" + "@" + "gobierno.pe", "190.12" + ".34.56", "987" + "123456"
CORREO_GMAIL = "alguien" + "@" + "gmail.com"


def test_el_escaner_no_deja_salir_nada_privado(proyecto, tmp_path, capsys):
    (proyecto.raiz / "app" / "fuga.py").write_text(
        f'a = "{CORREO_REAL}"\nb = "{IP_PUBLICA}"\nc = "{CELULAR}"\nd = "ghp_' + "x" * 30 + '"\ne = "Clave Interna"\n')
    proyecto.terminos = lambda: (["Clave Interna"], [re.compile(r"secreto-\d+")])
    (proyecto.raiz / "app" / "otro.txt").write_text("secreto-42\n")
    arbol = tmp_path / "arbol"
    assert demo.principal(proyecto, ["--trabajo", "--salida", str(arbol)]) == 1
    salida = capsys.readouterr().out
    for falta in ("correo de un dominio real (gobierno.pe)", f"IP pública {IP_PUBLICA}", "celular", "posible token",
                  "término privado T", "patrón privado R1"):
        assert falta in salida, falta
    assert "Clave Interna" not in salida   # los términos privados nunca se imprimen
    assert not demo.punta(proyecto.raiz, "demo")


def test_sin_mapa_privado_no_se_exporta(proyecto, tmp_path):
    proyecto.privado = tmp_path / "no-existe"
    assert demo.principal(proyecto, ["--salida", str(tmp_path / "arbol")]) == 2


def test_publicar_exige_rama_huerfana_y_deja_la_guarda(proyecto, tmp_path):
    assert demo.principal(proyecto, ["--publicar"]) == 2          # sin rama todavía
    assert demo.principal(proyecto, ["--salida", str(tmp_path / "arbol"), "--aplicar"]) == 0
    assert demo.principal(proyecto, ["--publicar"]) == 0
    guarda = (proyecto.raiz / ".git" / "hooks" / "pre-push").read_text()
    assert "refs/heads/demo" in guarda and "tiqsi.demo" in guarda
    assert _git(tmp_path / "remoto.git", "rev-parse", "main") == demo.punta(proyecto.raiz, "demo")
    # Una rama de demo que comparte historia con main no se publica.
    _git(proyecto.raiz, "branch", "-f", "demo", "main")
    assert demo.principal(proyecto, ["--publicar"]) == 1


def test_lo_de_terceros_conserva_a_sus_autores_pero_no_lo_privado(proyecto, tmp_path, capsys):
    """Una biblioteca incluida tal cual (TERCEROS) trae el correo y la versión de sus autores: no son hallazgos; un
    término privado o un token dentro de ella, sí."""
    conf = proyecto.demo / "demo.conf"
    conf.write_text(conf.read_text() + "TERCEROS=app/vendor/*\n")
    (proyecto.raiz / "app" / "vendor").mkdir()
    (proyecto.raiz / "app" / "vendor" / "lib.js").write_text(f'// autor: {CORREO_GMAIL} · v2.28' + '.5.5\n')
    arbol = tmp_path / "arbol"
    assert demo.principal(proyecto, ["--trabajo", "--salida", str(arbol)]) == 0
    (proyecto.raiz / "app" / "vendor" / "lib.js").write_text(f'// autor: {CORREO_GMAIL}\nconst k = "ghp_' + "y" * 30 + '"\n')
    assert demo.principal(proyecto, ["--trabajo", "--salida", str(arbol)]) == 1
    salida = capsys.readouterr().out
    assert "posible token" in salida and "gmail.com" not in salida.split("hallazgos")[-1]
