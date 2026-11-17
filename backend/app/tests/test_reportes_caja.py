"""C-12 1.2 — resumen de caja (feliz / negocio / borde)."""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.reportes.consultas import resumen_caja
from app.tests._reportes_seed import (
    DESDE,
    HASTA,
    sembrar_devolucion,
    sembrar_odontologo,
    sembrar_pago,
    sembrar_turno,
)


def test_neto_de_caja_y_trazabilidad(db_session: Session) -> None:
    od = sembrar_odontologo(db_session, "c1")
    turno = sembrar_turno(db_session, od, estado="cancelado")
    pago = sembrar_pago(db_session, turno, monto="10000.00")
    dev = sembrar_devolucion(db_session, pago, monto="6000.00")

    res = resumen_caja(db_session, DESDE, HASTA)

    assert res.total_aprobado == Decimal("10000.00")
    assert res.total_devuelto == Decimal("6000.00")
    assert res.neto == Decimal("4000.00")
    tipos = {f.concepto: f for f in res.filas}
    assert tipos["pago"].pago_id == pago.id and tipos["pago"].turno_id == turno.id
    assert tipos["devolucion"].devolucion_id == dev.id


def test_no_aprobados_ni_pendientes_no_suman(db_session: Session) -> None:
    od = sembrar_odontologo(db_session, "c2")
    turno = sembrar_turno(db_session, od)
    sembrar_pago(db_session, turno, estado="pendiente")
    sembrar_pago(db_session, turno, estado="rechazado")
    pago = sembrar_pago(db_session, turno, monto="500.00")
    sembrar_devolucion(db_session, pago, estado="pendiente", monto="300.00")

    res = resumen_caja(db_session, DESDE, HASTA)

    assert res.total_aprobado == Decimal("500.00")
    assert res.total_devuelto == Decimal("0")
    assert len(res.filas) == 1


def test_caja_vacia_y_aislamiento(db_session: Session) -> None:
    a = sembrar_odontologo(db_session, "c3")
    b = sembrar_odontologo(db_session, "d3")
    sembrar_pago(db_session, sembrar_turno(db_session, b), monto="900.00")

    vacia = resumen_caja(db_session, DESDE, HASTA, odontologo_id=a)

    assert vacia.neto == Decimal("0")
    assert vacia.filas == []
