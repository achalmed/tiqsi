"""El exportador de demos: la versión pública de un proyecto sale de su repositorio sin nada privado (fase 10.2b).

Cada proyecto guarda su RECETA en su carpeta `demo/`:

- `demo.conf`: lo público de la demo (NOMBRE, REMOTO, RAMA, RAMA_REMOTA, AUTOR, CORREO_AUTOR) y lo que el escáner acepta
  (CORREO_DOMINIOS, IP_PERMITIDAS, CELULARES_FICTICIOS, BINARIOS_PERMITIDOS, separados por comas) y lo de TERCEROS (globs de
  bibliotecas incluidas tal cual: ahí no cuentan los correos, IP ni teléfonos de sus autores, sí lo privado y los tokens);
- `excluir.txt`: lo que no sale (globs, uno por línea);
- `sustituciones.tsv`: las sustituciones genéricas (<glob> TAB <texto o re:patrón> TAB <reemplazo>);
- `vendor/`: lo propio de la demo, que se pone encima.

Y fuera del repositorio, en una carpeta PRIVADA, su mapa de sustituciones (`sustituciones.tsv`, con lo que nunca debe
salir) y lo que se permite aunque parezca privado (`permitidos.txt`). El proyecto puede sumar sus propias fuentes de
términos privados (una función) y sus ganchos sobre el árbol (cambiar logos, por ejemplo).

El árbol se arma desde lo VERSIONADO (un commit: nada sin commit) o desde la copia de trabajo (ensayo), se escanea
(términos y patrones privados, correos de dominios reales, IP públicas, celulares, nombres de Tailscale, tokens y
binarios fuera de su sitio; un hallazgo y no sale nada; los términos privados nunca se imprimen) y, con --aplicar, va a
una rama HUÉRFANA, sin historia de main. Publicar re-escanea la rama, comprueba que no comparte historia con main e
instala una guarda pre-push: solo esa rama sale hacia el remoto de la demo.

    from tiqsi.demo import Receta, principal
    sys.exit(principal(Receta(raiz=RAIZ, demo=RAIZ / "demo", privado=PRIVADO, terminos=mis_terminos,
                              ganchos=[logos_neutros], pruebas=[...]), sys.argv[1:]))
"""
from __future__ import annotations

import argparse
import fnmatch
import ipaddress
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Receta:
    """Lo que un proyecto le dice al exportador."""

    raiz: Path                                   # el repositorio
    demo: Path                                   # su receta (demo.conf, excluir.txt, sustituciones.tsv, vendor/)
    privado: Path | None = None                  # la carpeta privada (sustituciones.tsv, permitidos.txt), fuera del repo
    # Sus fuentes de términos privados: → (términos literales, patrones). Se arman en cada corrida, nada vive en el repo.
    terminos: Callable[[], tuple[list[str], list[re.Pattern]]] | None = None
    ganchos: list[Callable[[Path], list[str]]] = field(default_factory=list)   # sobre el árbol: → lo que cambiaron
    pruebas: list[str] | None = None             # una orden que corre las pruebas sobre el árbol (cwd: el árbol)
    cache: str = ""                              # nombre de su carpeta en $XDG_CACHE_HOME (por omisión, <NOMBRE>-demo)
    guion: str = "el exportador de demos (tiqsi.demo)"   # quién genera la guarda pre-push (va en su cabecera)


# --- la receta --------------------------------------------------------------------------------------------------


def lineas(p: Path | None) -> list[str]:
    if p is None or not p.exists():
        return []
    return [l.rstrip("\n") for l in p.read_text().splitlines() if l.strip() and not l.lstrip().startswith("#")]


def conf(receta: Receta) -> dict:
    c = {}
    for l in (receta.demo / "demo.conf").read_text().splitlines():
        if "=" in l and not l.lstrip().startswith("#"):
            k, v = l.split("=", 1)
            c[k.strip()] = v.split("#", 1)[0].strip()
    return c


def coincide(ruta: str, patrones: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(ruta, p) or fnmatch.fnmatchcase(ruta, p.rstrip("/") + "/*") for p in patrones)


def leer_sustituciones(p: Path | None) -> list[tuple[str, str, str]]:
    """Cada línea: <glob de archivos> TAB <texto a buscar> TAB <reemplazo>. Literal; con el prefijo `re:`, regex."""
    reglas = []
    for l in lineas(p):
        partes = l.split("\t")
        if len(partes) != 3:
            raise SystemExit(f"[error] {p.name}: línea sin tres columnas separadas por tabulador: {l[:40]!r}…")
        reglas.append((partes[0], partes[1], partes[2]))
    return reglas


# --- el árbol ---------------------------------------------------------------------------------------------------


def volcar_arbol(raiz: Path, ref: str, destino: Path) -> None:
    """Los archivos de un commit tal cual (ls-tree + cat-file), sin `git archive`: este respeta `export-ignore` de
    .gitattributes. Los enlaces simbólicos no salen."""
    lista = subprocess.run(["git", "ls-tree", "-r", "-z", ref], cwd=raiz, capture_output=True, check=True).stdout
    entradas = []
    for e in filter(None, lista.split(b"\0")):
        meta, ruta = e.split(b"\t", 1)
        modo, tipo, sha = meta.split()
        if tipo == b"blob" and modo in (b"100644", b"100755"):
            entradas.append((ruta.decode(), sha.decode(), modo == b"100755"))
    lote = subprocess.Popen(["git", "cat-file", "--batch"], cwd=raiz, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    for ruta, sha, ejecutable in entradas:
        lote.stdin.write(sha.encode() + b"\n")
        lote.stdin.flush()
        cabecera = lote.stdout.readline().split()
        datos = lote.stdout.read(int(cabecera[2]))
        lote.stdout.read(1)                                  # el salto de línea que cierra cada objeto
        p = destino / ruta
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(datos)
        if ejecutable:
            p.chmod(0o755)
    lote.stdin.close()
    lote.wait()


def extraer(raiz: Path, destino: Path, trabajo: bool, ref: str) -> None:
    if not trabajo:
        volcar_arbol(raiz, ref, destino)
        return
    archivos = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=raiz,
                              capture_output=True, check=True).stdout.decode().split("\0")
    for a in filter(None, archivos):
        o = raiz / a
        if o.is_file() and not o.is_symlink():
            (destino / a).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(o, destino / a)


def excluir(destino: Path, patrones: list[str]) -> list[str]:
    fuera = []
    for p in sorted(destino.rglob("*"), reverse=True):
        rel = p.relative_to(destino).as_posix()
        if p.is_file() and coincide(rel, patrones):
            p.unlink()
            fuera.append(rel)
        elif p.is_dir() and not any(p.iterdir()):
            p.rmdir()
    return sorted(fuera)


def superponer(origen: Path, destino: Path) -> list[str]:
    puestos = []
    for p in sorted(origen.rglob("*")) if origen.is_dir() else ():
        if p.is_file() and "__pycache__" not in p.parts:
            rel = p.relative_to(origen)
            (destino / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, destino / rel)
            puestos.append(rel.as_posix())
    return puestos


def sustituir(destino: Path, reglas: list[tuple[str, str, str]]) -> dict[int, int]:
    cuenta: dict[int, int] = {}
    for p in destino.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(destino).as_posix()
        try:
            t = p.read_text()
        except (UnicodeDecodeError, ValueError):
            continue
        nuevo = t
        for i, (glob, buscar, poner) in enumerate(reglas):
            if not (glob == "*" or coincide(rel, [glob])):
                continue
            if buscar.startswith("re:"):                   # expresión regular: re:<patrón>
                nuevo, n = re.subn(buscar[3:], poner, nuevo)
                if n:
                    cuenta[i] = cuenta.get(i, 0) + n
            elif buscar in nuevo:
                cuenta[i] = cuenta.get(i, 0) + nuevo.count(buscar)
                nuevo = nuevo.replace(buscar, poner)
        if nuevo != t:
            p.write_text(nuevo)
    return cuenta


# --- el escáner -------------------------------------------------------------------------------------------------

CORREO = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})")
IPV4 = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d{1,3}){3})(?![\d.])")
TAILNET = re.compile(r"\b([a-z0-9-]+)\.([a-z0-9-]+)\.ts\.net\b", re.I)
CELULAR = re.compile(r"(?<![\d/-])9\d{2}[ -]?\d{3}[ -]?\d{3}(?![\d/-])")
TOKEN = re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,}"
                   r"|-----BEGIN [A-Z ]*PRIVATE KEY|\b\d{8,10}:[A-Za-z0-9_-]{35}\b")
BINARIOS = (".pdf", ".docx", ".doc", ".xlsx", ".xls", ".odt", ".jpg", ".jpeg", ".heic", ".mp4", ".zip", ".sql", ".dump", ".gz")


def terminos_privados(receta: Receta) -> tuple[list[str], list[re.Pattern]]:
    """Lo que nunca puede salir: lo del proyecto (su función) y lo buscado por su mapa privado, menos lo permitido."""
    fijos, regex = (receta.terminos() if receta.terminos else ([], []))
    fijos = set(fijos)
    privado = receta.privado
    for _, buscar, _ in leer_sustituciones(privado / "sustituciones.tsv" if privado else None):
        if not buscar.startswith("re:"):
            fijos.add(buscar)
    permitidos = {l.strip().lower() for l in lineas(privado / "permitidos.txt" if privado else None)}
    return sorted((f for f in fijos if f.lower() not in permitidos), key=len, reverse=True), list(regex)


def escanear(receta: Receta, arbol: Path, mostrar: bool = False) -> list[str]:
    fijos, regex = terminos_privados(receta)
    pub = conf(receta)
    dominios = [d.strip().lower() for d in pub.get("CORREO_DOMINIOS", "").split(",") if d.strip()]
    ips_ok = {i.strip() for i in pub.get("IP_PERMITIDAS", "").split(",") if i.strip()}
    cel_ok = {c.strip() for c in pub.get("CELULARES_FICTICIOS", "").split(",") if c.strip()}
    bin_ok = [g.strip() for g in pub.get("BINARIOS_PERMITIDOS", "").split(",") if g.strip()]
    terceros = [g.strip() for g in pub.get("TERCEROS", "").split(",") if g.strip()]
    if mostrar:
        for i, t in enumerate(fijos, 1):
            print(f"  T{i}\t{t}")
        for i, r in enumerate(regex, 1):
            print(f"  R{i}\t{r.pattern}")
    bajos = [f.lower() for f in fijos]
    hallazgos = []
    for p in sorted(arbol.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(arbol).as_posix()
        nombre = rel.lower()
        for i, b in enumerate(bajos, 1):
            if b in nombre:
                hallazgos.append(f"{rel}: término privado T{i} en el NOMBRE del archivo")
        if nombre.endswith(BINARIOS) and not coincide(rel, bin_ok):
            hallazgos.append(f"{rel}: binario que no debería salir")
        try:
            texto = p.read_text()
        except (UnicodeDecodeError, ValueError):
            continue
        ajeno = coincide(rel, terceros)   # una biblioteca de terceros: los datos de contacto son de sus autores
        for n, linea in enumerate(texto.splitlines(), 1):
            bajo = linea.lower()
            for i, b in enumerate(bajos, 1):
                if b in bajo:
                    hallazgos.append(f"{rel}:{n}: término privado T{i}")
            for i, r in enumerate(regex, 1):
                if r.search(linea):
                    hallazgos.append(f"{rel}:{n}: patrón privado R{i}")
            if TOKEN.search(linea):
                hallazgos.append(f"{rel}:{n}: posible token o clave privada")
            if ajeno:
                continue
            for m in CORREO.finditer(linea):
                d = m[1].lower()
                if not any(d == x or d.endswith("." + x) for x in dominios):
                    hallazgos.append(f"{rel}:{n}: correo de un dominio real ({d})")
            for m in IPV4.finditer(linea):
                try:
                    ip = ipaddress.ip_address(m[1])
                except ValueError:
                    continue
                if ip.is_global and m[1] not in ips_ok:
                    hallazgos.append(f"{rel}:{n}: IP pública {m[1]}")
            for m in TAILNET.finditer(linea):
                if m[2].lower() not in ("ejemplo", "red", "tailnet", "example"):
                    hallazgos.append(f"{rel}:{n}: nombre de Tailscale ({m[0]})")
            for m in CELULAR.finditer(linea):
                if re.sub(r"\D", "", m[0]) not in cel_ok:
                    hallazgos.append(f"{rel}:{n}: celular que no está entre los ficticios ({m[0]})")
    return hallazgos


# --- git: la rama huérfana y la guarda ---------------------------------------------------------------------------


def _git(raiz: Path, *a, **k) -> str:
    return subprocess.run(["git", *a], cwd=raiz, capture_output=True, text=True, check=True, **k).stdout.strip()


def punta(raiz: Path, rama: str) -> str:
    r = subprocess.run(["git", "rev-parse", "-q", "--verify", f"refs/heads/{rama}"], cwd=raiz, capture_output=True, text=True)
    return r.stdout.strip()


def comprometer(raiz: Path, arbol: Path, c: dict, mensaje: str) -> str:
    """El árbol como commit de la rama de la demo (huérfana la primera vez; después, sobre su punta). → el commit."""
    rama = c["RAMA"]
    with tempfile.TemporaryDirectory() as tmp:
        entorno = {**os.environ, "GIT_INDEX_FILE": str(Path(tmp) / "indice"), "GIT_WORK_TREE": str(arbol)}
        subprocess.run(["git", "add", "-A", "-f", "."], cwd=arbol, env={**entorno, "GIT_DIR": str(raiz / ".git")}, check=True)
        arbol_git = subprocess.run(["git", "write-tree"], cwd=raiz, env=entorno, capture_output=True, text=True,
                                   check=True).stdout.strip()
    padre = punta(raiz, rama)
    if padre and _git(raiz, "rev-parse", f"{padre}^{{tree}}") == arbol_git:
        print(f"[ok] La rama {rama} ya tiene exactamente este árbol: nada que comprometer.")
        return padre
    autor = {"GIT_AUTHOR_NAME": c["AUTOR"], "GIT_AUTHOR_EMAIL": c["CORREO_AUTOR"],
             "GIT_COMMITTER_NAME": c["AUTOR"], "GIT_COMMITTER_EMAIL": c["CORREO_AUTOR"]}
    cmd = ["git", "commit-tree", arbol_git, "-m", mensaje] + (["-p", padre] if padre else [])
    nuevo = subprocess.run(cmd, cwd=raiz, env={**os.environ, **autor}, capture_output=True, text=True, check=True).stdout.strip()
    _git(raiz, "update-ref", f"refs/heads/{rama}", nuevo, *([padre] if padre else []))
    print(f"[ok] Rama {rama} → {nuevo[:10]} ({'sigue a ' + padre[:10] if padre else 'huérfana: sin historial de main'}).")
    return nuevo


GUARDA = """#!/bin/sh
# GENERADO por {guion}; no editar. Guarda de la demo pública: solo la rama `{rama}` sale hacia
# {remoto}; main y cualquier otra rama traen historia privada y no se empujan nunca a ese repositorio.
case "$2" in
  *{repo}*) while read ref_local sha_local ref_remota sha_remota; do
      [ "$ref_local" = "refs/heads/{rama}" ] || {{ echo "[guarda] $ref_local no sale a $2: solo refs/heads/{rama}." >&2; exit 1; }}
    done ;;
esac
exit 0
"""


def instalar_guarda(receta: Receta, c: dict) -> None:
    gancho = receta.raiz / ".git" / "hooks" / "pre-push"
    if gancho.exists() and receta.guion not in gancho.read_text():
        raise SystemExit(f"[error] Ya hay un pre-push propio en {gancho}: súmale la guarda a mano antes de publicar.")
    repo = c["REMOTO"].rsplit(":", 1)[-1].removesuffix(".git")
    gancho.parent.mkdir(parents=True, exist_ok=True)
    gancho.write_text(GUARDA.format(guion=receta.guion, rama=c["RAMA"], remoto=c["REMOTO"], repo=repo))
    gancho.chmod(0o755)


def comparte_historia(raiz: Path, rama: str, principal_: str = "main") -> bool | None:
    """¿La rama de la demo tiene un ancestro común con main? None si git no pudo responder."""
    r = subprocess.run(["git", "merge-base", f"refs/heads/{rama}", f"refs/heads/{principal_}"], cwd=raiz,
                       capture_output=True, text=True)
    return {0: True, 1: False}.get(r.returncode)


def publicar(receta: Receta, c: dict, mostrar: bool) -> int:
    if not punta(receta.raiz, c["RAMA"]):
        print(f"[error] No existe la rama {c['RAMA']}: primero --aplicar.")
        return 2
    with tempfile.TemporaryDirectory() as tmp:
        volcar_arbol(receta.raiz, f"refs/heads/{c['RAMA']}", Path(tmp))
        hallazgos = escanear(receta, Path(tmp), mostrar)
    if hallazgos:
        print(f"[FALLA] La rama {c['RAMA']} tiene {len(hallazgos)} hallazgos: no se publica.")
        for h in hallazgos[:200]:
            print("  " + h)
        return 1
    comparte = comparte_historia(receta.raiz, c["RAMA"])
    if comparte is not False:
        print(f"[error] La rama {c['RAMA']} {'comparte historia con main' if comparte else 'no se pudo comprobar'}: no se publica.")
        return 1
    instalar_guarda(receta, c)
    print(f"[ok] Escáner limpio y rama sin historia de main. Empujando {c['RAMA']} → {c['REMOTO']} ({c['RAMA_REMOTA']})…")
    return subprocess.run(["git", "push", c["REMOTO"], f"refs/heads/{c['RAMA']}:refs/heads/{c['RAMA_REMOTA']}"],
                          cwd=receta.raiz).returncode


# --- la orden ---------------------------------------------------------------------------------------------------


def principal(receta: Receta, argv: list[str] | None = None, descripcion: str = "") -> int:
    """La orden del exportador. Simula por omisión; salida: 0 limpio · 1 hallazgos · 2 error de uso o de entorno."""
    c = conf(receta)
    ap = argparse.ArgumentParser(description=descripcion or f"La demo pública de {c.get('NOMBRE', 'este proyecto')}.")
    ap.add_argument("--ref", default="HEAD", help="commit que se exporta (por defecto HEAD)")
    ap.add_argument("--trabajo", action="store_true", help="exporta la copia de trabajo en vez de un commit (ensayo)")
    ap.add_argument("--salida", help="carpeta del árbol (por defecto $XDG_CACHE_HOME/<nombre>-demo/arbol; se vacía)")
    ap.add_argument("--pruebas", action="store_true", help="corre las pruebas del proyecto sobre el árbol exportado")
    ap.add_argument("--aplicar", action="store_true", help="hace el commit en la rama de la demo")
    ap.add_argument("--publicar", action="store_true", help="re-escanea la rama de la demo y la empuja a su remoto")
    ap.add_argument("--mostrar-terminos", action="store_true", help="imprime los términos privados (solo en esta máquina)")
    a = ap.parse_args(argv)

    if a.publicar:
        return publicar(receta, c, a.mostrar_terminos)
    if not receta.privado or not (receta.privado / "sustituciones.tsv").exists():
        print(f"[error] Falta el mapa privado de sustituciones ({receta.privado or 'sin carpeta privada'}/sustituciones.tsv): "
              "sin él no se exporta.")
        return 2
    cache = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    arbol = Path(a.salida) if a.salida else cache / (receta.cache or f"{c.get('NOMBRE', 'proyecto').lower()}-demo") / "arbol"
    if arbol.exists():
        shutil.rmtree(arbol)
    arbol.mkdir(parents=True)

    extraer(receta.raiz, arbol, a.trabajo, a.ref)
    fuera = excluir(arbol, lineas(receta.demo / "excluir.txt"))
    puestos = superponer(receta.demo / "vendor", arbol)
    publicas = leer_sustituciones(receta.demo / "sustituciones.tsv")
    privadas = leer_sustituciones(receta.privado / "sustituciones.tsv")
    n_pub = sustituir(arbol, publicas)
    n_priv = sustituir(arbol, privadas)
    cambiados = [x for gancho in receta.ganchos for x in gancho(arbol)]
    for p in arbol.rglob("__pycache__"):
        shutil.rmtree(p, ignore_errors=True)

    archivos = [p for p in arbol.rglob("*") if p.is_file()]
    print(f"Demo {c['NOMBRE']} desde {'la copia de trabajo' if a.trabajo else a.ref} → {arbol}")
    print(f"  {len(archivos)} archivos salen · {len(fuera)} excluidos · {len(puestos)} propios de la demo · "
          f"{len(cambiados)} cambiados por sus ganchos")
    print(f"  sustituciones: {sum(n_pub.values())} genéricas ({len(n_pub)}/{len(publicas)} reglas usadas), "
          f"{sum(n_priv.values())} privadas ({len(n_priv)}/{len(privadas)} reglas usadas)")
    hallazgos = escanear(receta, arbol, a.mostrar_terminos)
    if hallazgos:
        print(f"[FALLA] {len(hallazgos)} hallazgos en el árbol de la demo:")
        for h in hallazgos[:200]:
            print("  " + h)
        return 1
    print("[ok] Escáner limpio: ningún término privado, correo real, IP pública, celular, token ni binario fuera de sitio.")

    if a.pruebas and receta.pruebas:
        if subprocess.run(receta.pruebas, cwd=arbol).returncode:
            print("[FALLA] Las pruebas no pasan sobre el árbol de la demo.")
            return 1
    if a.aplicar:
        comprometer(receta.raiz, arbol, c, f"{c['NOMBRE']}: versión de demostración\n\nExportada por {receta.guion}.")
    else:
        print(f"Simulación: nada se comprometió. --aplicar hace el commit en la rama {c['RAMA']}; "
              f"--publicar la empuja a {c['REMOTO']}.")
    return 0
