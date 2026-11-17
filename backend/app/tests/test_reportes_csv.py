"""C-12 2.1 — exportación CSV (feliz / negocio / borde)."""

import csv
import io
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.reportes.consultas import filas_auditoria, listar_turnos, resumen_caja
from app.domain.reportes.csv_export import (
    csv_auditoria,
    csv_caja,
    csv_turnos,
    neutralizar,
)
from app.tests._reportes_seed import (
    DESDE,
    HASTA,
    sembrar_devolucion,
    sembrar_odontologo,
    sembrar_pago,
    sembrar_turno,
)


def _filas(contenido: bytes) -> list[list[str]]:
    texto = contenido.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(texto)))


def test_csv_turnos_con_bom_y_cabecera(db_session: Session) -> None:
    od = sembrar_odontologo(db_session, "g1")
    sembrar_turno(db_session, od, estado="atendido")

    contenido = csv_turnos(listar_turnos(db_session, DESDE, HASTA))

    assert contenido.startswith(b"\xef\xbb\xbf")
    filas = _filas(contenido)
    assert filas[0][:3] == ["turno_id", "odontologo_id", "inicio"]
    assert len(filas) == 2 and "atendido" in filas[1]


def test_csv_caja_neutraliza_formulas_y_marca(db_session: Session) -> None:
    od = sembrar_odontologo(db_session, "g2")
    pago = sembrar_pago(db_session, sembrar_turno(db_session, od, estado="cancelado"))
    sembrar_devolucion(db_session, pago)  # motivo "=cancelación" en la semilla

    resumen = resumen_caja(db_session, DESDE, HASTA)
    filas = _filas(csv_caja(resumen, marca="(simulado)"))

    assert filas[0][0] == "marca" and filas[0][1] == "(simulado)"
    assert not any(c.startswith("=") for fila in filas for c in fila)
    assert filas[-1][0] == "neto" and Decimal(filas[-1][1]) == Decimal("4000.00")


def test_neutralizar_prefija_solo_los_peligrosos() -> None:
    assert neutralizar("=1+1") == "'=1+1"
    assert neutralizar("+x") == "'+x"
    assert neutralizar("-x") == "'-x"
    assert neutralizar("@x") == "'@x"
    assert neutralizar("normal") == "normal"
    assert neutralizar("") == ""


def test_csv_auditoria_sin_filas_solo_cabecera(db_session: Session) -> None:
    filas = _filas(csv_auditoria(filas_auditoria(db_session, DESDE, HASTA)))
    assert filas == [["origen", "fecha", "referencia_id", "actor", "detalle"]]
