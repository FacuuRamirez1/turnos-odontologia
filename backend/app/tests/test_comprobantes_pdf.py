"""Tests C-08 task 5.2 - generador de PDF de comprobante (RED primero)."""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.domain.comprobantes.pdf import generar_pdf
from app.domain.pagos.service import LEYENDA_COMPROBANTE_SIMULADO
from app.infra.db.models import Comprobante


def _comprobante(db_session: Session, *, simulado: bool) -> Comprobante:
    comprobante = Comprobante(
        pago_id=uuid.uuid4(),
        devolucion_id=None,
        turno_id=uuid.uuid4(),
        tipo="recibo_interno",
        concepto="pago",
        numero="RI-000001",
        monto=Decimal("65000.00"),
        moneda="ARS",
        cae=None,
        simulado=simulado,
        payload_json={
            "concepto": "pago",
            "paciente_nombre": "Juan",
            "paciente_apellido": "Perez",
            "odontologo": "od-em-test@clinica-ficticia.example.ar",
            "fecha_turno": "2026-11-16T09:00:00",
            "porcentaje": None,
            "monto": "65000.00",
        },
    )
    db_session.add(comprobante)
    db_session.commit()
    db_session.refresh(comprobante)
    return comprobante


def test_generar_pdf_estructura_valida_y_datos_del_recibo(db_session: Session) -> None:
    comprobante = _comprobante(db_session, simulado=True)
    pdf = generar_pdf(comprobante)
    assert pdf.startswith(b"%PDF-1.4")
    assert b"xref" in pdf
    assert b"trailer" in pdf
    assert b"startxref" in pdf
    assert b"%%EOF" in pdf
    assert comprobante.numero.encode("ascii") in pdf
    assert b"65000.00" in pdf
    assert LEYENDA_COMPROBANTE_SIMULADO.encode("cp1252") in pdf


def test_generar_pdf_leyenda_presente_si_simulado_borde(
    monkeypatch: pytest.MonkeyPatch, db_session: Session,
) -> None:
    monkeypatch.setenv("PAGO_MODO", "mercadopago")
    comprobante = _comprobante(db_session, simulado=True)
    pdf = generar_pdf(comprobante)
    assert LEYENDA_COMPROBANTE_SIMULADO.encode("cp1252") in pdf


def test_generar_pdf_sin_leyenda_si_no_simulado_error(db_session: Session) -> None:
    comprobante = _comprobante(db_session, simulado=False)
    pdf = generar_pdf(comprobante)
    assert LEYENDA_COMPROBANTE_SIMULADO.encode("cp1252") not in pdf
