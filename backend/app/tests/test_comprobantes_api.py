"""Tests C-08 task 5.3 - comprobantes staff: detalle y descarga PDF (RED primero)."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security.jwt import create_access_token
from app.infra.db.models import (
    Comprobante,
    Odontologo,
    Paciente,
    Pago,
    Turno,
    Usuario,
)
from app.tests.conftest import TEST_AUTH_SECRET


def _sembrar_odontologo(db_session: Session, sufijo: str) -> uuid.UUID:
    u = Usuario(
        email=f"od-cmp-{sufijo}@clinica-ficticia.example.ar",
        password_hash="$2b$04$" + "b" * 53,
        rol="odontologo",
    )
    db_session.add(u)
    db_session.commit()
    od = Odontologo(
        user_id=u.id, monto_turno=Decimal("70000"), monto_senia=Decimal("10000"),
    )
    db_session.add(od)
    db_session.commit()
    return uuid.UUID(str(od.id))


def _sembrar_comprobante(db_session: Session, od_id: uuid.UUID) -> Comprobante:
    suf = uuid.uuid4().hex[:8]
    pac = Paciente(
        dni=f"76{uuid.uuid4().int % 90000000 + 10000000:08d}",
        nombre="Ana",
        apellido="Ficticia",
        consentimiento_datos=True,
        consentimiento_fecha=datetime(2026, 10, 1, 9, 0, tzinfo=UTC),
    )
    db_session.add(pac)
    db_session.commit()
    inicio = datetime(2026, 12, 1, 9, 0, tzinfo=UTC) + timedelta(
        minutes=(uuid.uuid4().int % 2000) * 30
    )
    turno = Turno(
        paciente_id=pac.id,
        odontologo_id=od_id,
        inicio=inicio,
        fin=inicio + timedelta(minutes=30),
        estado="cancelado",
        canal="web",
        idempotency_key=f"key-cmp-{suf}",
    )
    db_session.add(turno)
    db_session.commit()
    pago = Pago(
        turno_id=turno.id,
        odontologo_id=od_id,
        monto=Decimal("10000.00"),
        moneda="ARS",
        proveedor="simulado",
        mp_payment_id=f"sim_pay_{uuid.uuid4()}",
        estado="aprobado",
        idempotency_key=f"idem-cmp-{suf}",
    )
    db_session.add(pago)
    db_session.commit()
    comprobante = Comprobante(
        pago_id=pago.id,
        turno_id=turno.id,
        devolucion_id=None,
        tipo="recibo_interno",
        concepto="pago",
        numero="RI-000001",
        monto=Decimal("10000.00"),
        moneda="ARS",
        cae=None,
        simulado=True,
        payload_json={
            "concepto": "pago",
            "paciente_nombre": "Ana",
            "paciente_apellido": "Ficticia",
            "odontologo": "od-cmp-x@clinica-ficticia.example.ar",
            "fecha_turno": "2026-12-01T09:00:00",
            "porcentaje": None,
            "monto": "10000.00",
        },
    )
    db_session.add(comprobante)
    db_session.commit()
    db_session.refresh(comprobante)
    return comprobante


def _headers(rol: str, odontologo_id: uuid.UUID | None = None) -> dict[str, str]:
    token = create_access_token(
        sub=f"user-{uuid.uuid4().hex[:8]}",
        rol=rol,
        secret=TEST_AUTH_SECRET,
        odontologo_id=str(odontologo_id) if odontologo_id else None,
    )
    return {"Authorization": f"Bearer {token}"}


def test_recepcionista_descarga_comprobante_pdf_feliz(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Feliz (D6/D8): recepcionista descarga el PDF del comprobante (200, %PDF-1.4)."""
    od = _sembrar_odontologo(db_session, "a")
    comprobante = _sembrar_comprobante(db_session, od)

    r_pdf = auth_client.get(
        f"/api/comprobantes/{comprobante.id}/pdf", headers=_headers("recepcionista"),
    )
    assert r_pdf.status_code == 200, r_pdf.text
    assert r_pdf.headers["content-type"].startswith("application/pdf")
    assert r_pdf.content.startswith(b"%PDF-1.4")

    r_det = auth_client.get(
        f"/api/comprobantes/{comprobante.id}", headers=_headers("recepcionista"),
    )
    assert r_det.status_code == 200, r_det.text
    assert r_det.json()["id"] == str(comprobante.id)
    assert r_det.json()["numero"] == "RI-000001"
    assert r_det.json()["marca"] == "(simulado)"


def test_odontologo_ajeno_comprobante_403_negocio(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Negocio (P8): odontologo A no descarga el PDF del comprobante de B."""
    od_a = _sembrar_odontologo(db_session, "b1")
    od_b = _sembrar_odontologo(db_session, "b2")
    comprobante_b = _sembrar_comprobante(db_session, od_b)

    r_ajena = auth_client.get(
        f"/api/comprobantes/{comprobante_b.id}/pdf",
        headers=_headers("odontologo", od_a),
    )
    assert r_ajena.status_code == 403

    r_det_ajena = auth_client.get(
        f"/api/comprobantes/{comprobante_b.id}",
        headers=_headers("odontologo", od_a),
    )
    assert r_det_ajena.status_code == 403

    r_propio = auth_client.get(
        f"/api/comprobantes/{comprobante_b.id}/pdf",
        headers=_headers("odontologo", od_b),
    )
    assert r_propio.status_code == 200, r_propio.text


def test_sin_jwt_o_id_inexistente_401_404_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Borde (P8/P12): 401 sin JWT y 404 con id inexistente."""
    r_sin_jwt_pdf = auth_client.get(
        "/api/comprobantes/00000000-0000-0000-0000-000000000000/pdf"
    )
    assert r_sin_jwt_pdf.status_code == 401
    r_sin_jwt = auth_client.get(
        "/api/comprobantes/00000000-0000-0000-0000-000000000000"
    )
    assert r_sin_jwt.status_code == 401

    r = auth_client.get(
        f"/api/comprobantes/{uuid.uuid4()}/pdf",
        headers=_headers("recepcionista"),
    )
    assert r.status_code == 404
