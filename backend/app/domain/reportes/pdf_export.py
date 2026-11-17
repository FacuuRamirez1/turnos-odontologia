"""PDF tabular mínimo C-12 (sin dependencias, mismo enfoque que comprobantes).

Helvetica 10 pt, una línea por fila, paginado fijo; la marca "(simulado)"
(D14/P15) se imprime en cada página cuando se recibe no vacía.
"""

from collections.abc import Sequence

_X = 40
_Y_INICIO = 750
_Y_MIN = 50
_INTERLINEADO = 14
_FILAS_POR_PAGINA = (_Y_INICIO - _Y_MIN - 3 * _INTERLINEADO) // _INTERLINEADO
_MAX_CARACTERES = 110


def _escape(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _linea(texto: str, y: int, size: int = 10) -> bytes:
    recortado = texto[:_MAX_CARACTERES]
    return f"BT /F1 {size} Tf {_X} {y} Td ({_escape(recortado)}) Tj ET".encode(
        "cp1252", errors="replace"
    )


def _contenido_pagina(
    titulo: str, cabeceras: Sequence[str], filas: Sequence[Sequence[str]], marca: str
) -> bytes:
    lineas = [_linea(f"{titulo} {marca}".strip(), _Y_INICIO, 14)]
    y = _Y_INICIO - 2 * _INTERLINEADO
    lineas.append(_linea(" | ".join(cabeceras), y))
    for fila in filas:
        y -= _INTERLINEADO
        lineas.append(_linea(" | ".join(fila), y))
    return b"\n".join(lineas) + b"\n"


def generar_pdf_tabla(
    titulo: str,
    cabeceras: Sequence[str],
    filas: Sequence[Sequence[str]],
    *,
    marca: str,
) -> bytes:
    """PDF con tabla paginada; `marca` vacía no se imprime."""
    if filas:
        grupos = [
            filas[i : i + _FILAS_POR_PAGINA]
            for i in range(0, len(filas), _FILAS_POR_PAGINA)
        ]
    else:
        grupos = [[["Sin datos"]]]
    contenidos = [_contenido_pagina(titulo, cabeceras, g, marca) for g in grupos]

    # Objetos: 1 catálogo, 2 páginas, 3 fuente, luego (página, contenido) por hoja.
    primer = 4
    kids = " ".join(f"{primer + 2 * i} 0 R" for i in range(len(contenidos)))
    objetos: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {len(contenidos)} >>".encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    for i, datos in enumerate(contenidos):
        contenido_ref = primer + 2 * i + 1
        objetos.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 3 0 R >> >> /Contents {contenido_ref} 0 R >>"
            ).encode("ascii")
        )
        objetos.append(
            f"<< /Length {len(datos)} >>\nstream\n".encode("ascii")
            + datos
            + b"endstream"
        )
    return _ensamblar(objetos)


def _ensamblar(objetos: list[bytes]) -> bytes:
    salida = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for numero, cuerpo in enumerate(objetos, start=1):
        offsets.append(len(salida))
        salida += f"{numero} 0 obj\n".encode("ascii") + cuerpo + b"\nendobj\n"
    xref = len(salida)
    salida += f"xref\n0 {len(objetos) + 1}\n".encode("ascii")
    salida += b"0000000000 65535 f \n"
    for offset in offsets:
        salida += f"{offset:010d} 00000 n \n".encode("ascii")
    salida += (
        f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n"
    ).encode("ascii")
    return bytes(salida)
