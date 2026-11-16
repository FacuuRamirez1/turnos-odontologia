"""Generador de PDF de comprobante C-08 (design D6)."""

from app.domain.pagos.service import LEYENDA_COMPROBANTE_SIMULADO
from app.infra.db.models import Comprobante

_ANCHOR_X = 50
_ANCHOR_Y = 760
_SIZE_TITULO = 16
_SIZE_CABECERA = 12
_SIZE_DATO = 10


def _escape(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _operacion(texto: str, *, y: float, size: int) -> bytes:
    return (
        f"BT /F1 {size} Tf {_ANCHOR_X:.0f} {y:.0f} Td ({_escape(texto)}) Tj ET"
    ).encode("cp1252")


def _contenido(comprobante: Comprobante) -> bytes:
    monto = f"{comprobante.monto:.2f} {comprobante.moneda}"
    snapshot: dict[str, object] = (
        comprobante.payload_json if isinstance(comprobante.payload_json, dict) else {}
    )
    paciente = " ".join(
        str(valor)
        for valor in (snapshot.get("paciente_nombre"), snapshot.get("paciente_apellido"))
        if valor
    ).strip()
    operaciones: list[tuple[str, float, int]] = [
        (f"RECIBO {comprobante.numero}", _ANCHOR_Y, _SIZE_TITULO),
        (f"Concepto: {comprobante.concepto}", _ANCHOR_Y - 22, _SIZE_CABECERA),
        (f"Monto: {monto}", _ANCHOR_Y - 44, _SIZE_CABECERA),
    ]
    if paciente:
        operaciones.append((f"Paciente: {paciente}", _ANCHOR_Y - 66, _SIZE_DATO))
    odontologo = str(snapshot.get("odontologo") or "")
    if odontologo:
        operaciones.append((f"Odontologo: {odontologo}", _ANCHOR_Y - 88, _SIZE_DATO))
    fecha = str(snapshot.get("fecha_turno") or "")
    if fecha:
        operaciones.append((f"Fecha: {fecha}", _ANCHOR_Y - 110, _SIZE_DATO))
    if comprobante.simulado:
        operaciones.append((LEYENDA_COMPROBANTE_SIMULADO, _ANCHOR_Y - 132, _SIZE_DATO))
    return b"\n".join(_operacion(texto, y=y, size=size) for texto, y, size in operaciones)


def _objetos(contenido: bytes) -> list[bytes]:
    datos = contenido + b"\n"
    longitud = str(len(datos)).encode("ascii")
    return [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Length " + longitud + b" >>\nstream\n" + datos + b"\nendstream",
    ]


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


def generar_pdf(comprobante: Comprobante) -> bytes:
    """Renderiza el PDF del comprobante desde su snapshot (D6)."""
    return _ensamblar(_objetos(_contenido(comprobante)))
