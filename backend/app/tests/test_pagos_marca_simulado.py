"""Tests C-07 task 9 — Marca '(simulado)' en pagos y mails (RED primero)."""

import uuid
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security.jwt import create_access_token
from app.domain.notificaciones.plantillas import render
from app.domain.pagos.service import LEYENDA_COMPROBANTE_SIMULADO
from app.infra.db.models import Disponibilidad, Odontologo, Paciente, Pago, Usuario
from app.tests.conftest import TEST_AUTH_SECRET

CORDOBA = ZoneInfo("America/Argentina/Cordoba")


def _sembrar_recep_y_odonto(db_session: Session) -> tuple[uuid.UUID, dict[str, str]]:
    h = "$2b$04$" + "s" * 53
    suf = uuid.uuid4().hex[:8]
    u_od = Usuario(
        email=f"od-ms-{suf}@clinica-ficticia.example.ar",
        password_hash=h,
        rol="odontologo",
    )
    u_rec = Usuario(
        email=f"rec-ms-{suf}@clinica-ficticia.example.ar",
        password_hash=h,
        rol="recepcionista",
    )
    db_session.add_all([u_od, u_rec])
    db_session.commit()

    od = Odontologo(
        user_id=u_od.id,
        monto_turno=Decimal("70000"),
        monto_senia=Decimal("65000"),
    )
    db_session.add(od)
    db_session.commit()

    objetivo = (datetime.now(CORDOBA) + timedelta(days=35)).replace(
        hour=9, minute=0, second=0, microsecond=0
    )
    db_session.add(
        Disponibilidad(
            odontologo_id=od.id,
            dia_semana=objetivo.weekday(),
            hora_inicio=time(9, 0),
            hora_fin=time(12, 0),
            duracion_min=30,
            tope_dia=14,
        )
    )
    db_session.add(
        Paciente(
            dni=f"98{uuid.uuid4().int % 90000000 + 10000000:08d}",
            nombre="Ana",
            apellido="Ficticia",
            consentimiento_datos=True,
            consentimiento_fecha=datetime(2026, 10, 1, 9, 0, tzinfo=UTC),
        )
    )
    db_session.commit()
    token = create_access_token(
        sub=str(u_rec.id),
        rol="recepcionista",
        secret=TEST_AUTH_SECRET,
    )
    return uuid.UUID(str(od.id)), {"Authorization": f"Bearer {token}"}


def test_respuestas_pago_incluyen_marca_simulado_feliz(
    auth_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Feliz: GET /pagos/{id} y sandbox en PAGO_MODO=simulado incluyen marca."""
    monkeypatch.setenv("PAGO_MODO", "simulado")
    od_id, headers = _sembrar_recep_y_odonto(db_session)
    objetivo = (datetime.now(CORDOBA) + timedelta(days=35)).replace(
        hour=9, minute=0, second=0, microsecond=0
    )
    r_res = auth_client.post(
        "/api/reservas",
        json={
            "odontologo_id": str(od_id),
            "inicio": objetivo.isoformat(),
            "dni": "98111222",
            "nombre": "Ana",
            "apellido": "Ficticia",
            "consentimiento_datos": True,
            "consentimiento_fecha": "2026-01-01T09:00:00+00:00",
        },
        headers={"Idempotency-Key": f"rk-ms-{uuid.uuid4().hex[:10]}"},
    )
    assert r_res.status_code == 201, r_res.text
    cuerpo = r_res.json()
    pago = db_session.query(Pago).filter_by(turno_id=uuid.UUID(cuerpo["id"])).first()
    assert pago is not None

    r_sim = auth_client.post(
        f"/api/pagos/{pago.id}/simular",
        json={"accion": "aprobar"},
        headers={"checkout_token": cuerpo["checkout_token"]},
    )
    assert r_sim.status_code == 200, r_sim.text
    assert r_sim.json().get("marca") == "(simulado)"

    r_get = auth_client.get(f"/api/pagos/{pago.id}", headers=headers)
    assert r_get.status_code == 200, r_get.text
    detalle = r_get.json()
    assert detalle["marca"] == "(simulado)"
    assert detalle["leyenda_comprobante"] == LEYENDA_COMPROBANTE_SIMULADO
    assert "SIMULADO" in LEYENDA_COMPROBANTE_SIMULADO
    assert "sin valor fiscal" in LEYENDA_COMPROBANTE_SIMULADO


def test_get_pago_inexistente_404_negocio(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Negocio: consultar un pago_id inexistente devuelve 404."""
    _, headers = _sembrar_recep_y_odonto(db_session)
    r = auth_client.get(f"/api/pagos/{uuid.uuid4()}", headers=headers)
    assert r.status_code == 404


def test_mails_incluyen_marca_simulado_borde(monkeypatch: pytest.MonkeyPatch) -> None:
    """Borde: plantillas confirmacion y aviso_devolucion llevan '(simulado)' en modo simulado."""
    monkeypatch.setenv("PAGO_MODO", "simulado")
    _, texto_conf, html_conf = render(
        "v1",
        "confirmacion",
        nombre="Ana",
        apellido="Pérez",
        token="tok-sim",
        turno_inicio="05/11/2026 09:00",
    )
    assert "(simulado)" in texto_conf
    assert "(simulado)" in html_conf

    _, texto_dev, html_dev = render(
        "v1",
        "aviso_devolucion",
        nombre="Ana",
        apellido="Pérez",
        porcentaje=60,
        turno_inicio="05/11/2026 09:00",
    )
    assert "(simulado)" in texto_dev
    assert "(simulado)" in html_dev
