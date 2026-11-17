"""Exportación CSV C-12: UTF-8 con BOM (Excel) y neutralización de fórmulas.

Una celda de texto que empieza con `=`, `+`, `-` o `@` se prefija con `'` para
que una planilla no la ejecute como fórmula (CSV injection).
"""

import csv
import io
from collections.abc import Sequence

from app.domain.reportes.consultas import FilaAuditoria, ResumenCaja
from app.infra.db.models import Turno

_PELIGROSOS = ("=", "+", "-", "@")
_BOM = b"\xef\xbb\xbf"


def neutralizar(valor: str) -> str:
    """Prefija con `'` las celdas que una planilla interpretaría como fórmula."""
    return f"'{valor}" if valor.startswith(_PELIGROSOS) else valor


def _serializar(filas: Sequence[Sequence[str]]) -> bytes:
    salida = io.StringIO(newline="")
    writer = csv.writer(salida, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    for fila in filas:
        writer.writerow([neutralizar(celda) for celda in fila])
    return _BOM + salida.getvalue().encode("utf-8")


def csv_turnos(turnos: Sequence[Turno]) -> bytes:
    filas: list[list[str]] = [
        ["turno_id", "odontologo_id", "inicio", "fin", "estado", "canal"]
    ]
    for t in turnos:
        filas.append(
            [str(t.id), str(t.odontologo_id), t.inicio.isoformat(),
             t.fin.isoformat(), t.estado, t.canal]
        )
    return _serializar(filas)


def csv_caja(resumen: ResumenCaja, *, marca: str) -> bytes:
    filas: list[list[str]] = [["marca", marca]]
    filas.append(
        ["concepto", "fecha", "monto", "turno_id", "pago_id", "devolucion_id", "odontologo_id"]
    )
    for f in resumen.filas:
        filas.append(
            [f.concepto, f.fecha.isoformat(), str(f.monto), str(f.turno_id),
             str(f.pago_id), str(f.devolucion_id or ""), str(f.odontologo_id)]
        )
    filas.append(["total_aprobado", str(resumen.total_aprobado)])
    filas.append(["total_devuelto", str(resumen.total_devuelto)])
    filas.append(["neto", str(resumen.neto)])
    return _serializar(filas)


def csv_auditoria(filas_aud: Sequence[FilaAuditoria]) -> bytes:
    filas: list[list[str]] = [["origen", "fecha", "referencia_id", "actor", "detalle"]]
    for f in filas_aud:
        filas.append(
            [f.origen, f.fecha.isoformat(), str(f.referencia_id), f.actor, f.detalle]
        )
    return _serializar(filas)
