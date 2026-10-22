"""Los nombres de archivo y el conteo de páginas que comparten los módulos (tiqsi.nombres, tiqsi.pdf; 2026-10-20)."""
from tiqsi.nombres import LIMITE, sanear, unico_en
from tiqsi.pdf import contar_paginas


def test_unico_en_numera_lo_que_ya_existe(tmp_path):
    assert unico_en(tmp_path, "ENT-SN_MEF.pdf") == "ENT-SN_MEF.pdf"
    (tmp_path / "ENT-SN_MEF.pdf").write_bytes(b"x")
    assert unico_en(tmp_path, "ENT-SN_MEF.pdf") == "ENT-SN_MEF-2.pdf"
    (tmp_path / "ENT-SN_MEF-2.pdf").write_bytes(b"x")
    assert unico_en(tmp_path, "ENT-SN_MEF.pdf") == "ENT-SN_MEF-3.pdf"


def test_sanear_cabe_en_el_limite():
    assert len(sanear("Oficio múltiple de la Dirección General " * 10, LIMITE)) <= LIMITE


def _pdf(paginas: int) -> bytes:
    kids = " ".join(f"{3 + i} 0 R" for i in range(paginas))
    objetos = [b"<< /Type /Catalog /Pages 2 0 R >>", f"<< /Type /Pages /Kids [{kids}] /Count {paginas} >>".encode()]
    objetos += [b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>"] * paginas
    cuerpo, desplazamientos = b"%PDF-1.4\n", []
    for i, o in enumerate(objetos, 1):
        desplazamientos.append(len(cuerpo))
        cuerpo += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(cuerpo)
    cuerpo += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    cuerpo += b"".join(f"{d:010d} 00000 n \n".encode() for d in desplazamientos)
    cuerpo += f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return cuerpo


def test_cuenta_las_paginas(tmp_path):
    ruta = tmp_path / "tres.pdf"
    ruta.write_bytes(_pdf(3))
    assert contar_paginas(ruta) == 3


def test_sin_archivo_no_hay_paginas(tmp_path):
    assert contar_paginas(None) is None
    assert contar_paginas(tmp_path / "no-esta.pdf") is None
