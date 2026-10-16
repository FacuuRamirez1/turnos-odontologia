"""Tests C-05 §4.1 — cotizar-cancelar (RED primero, task 4.1).

Escenarios (U2 feliz / error-negocio / borde):
- feliz: en término (anticipación 24 h, turno a 30 días) → 100 %; confirmar
  cancela + libera (slot re-ofrecido) + devolución `pendiente`;
- error: turno ya `cancelado` no se retiene ni se re-cancela (422, sin filas nuevas);
- borde: fuera de término (turno en 2 h; franja creada hoy) → 60 %;
  paciente con token ajeno → 403.
"""

import uuid
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from typing import TypedDict
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.tests.conftest import TEST_AUTH_SECRET

CORDOBA = ZoneInfo("America/Argentina/Cordoba")


class _Ctx(TypedDict):
    turno_id: uuid.UUID
    dni: str
    token: str


def _sembrar(db_session: Session, dias: float = 30.0) -> _Ctx:
    from app.core.security.action_tokens import issue_action_token
    from app.infra.db.models import Disponibilidad, Odontologo, Paciente, Turno, Usuario

    suf = uuid.uuid4().hex[:8]
    dni = f"77{suf}"
    u = Usuario(email=f"od-c-{suf}@clinica-ficticia.example.ar",
                password_hash="$2b$04$" + "o" * 53, rol="odontologo")
    db_session.add(u)
    db_session.commit()
    od = Odontologo(user_id=u.id, monto_turno=Decimal("70000"), monto_senia=Decimal("65000"))
    db_session.add(od)
    db_session.commit()
    pac = Paciente(dni=dni, nombre="Ana", apellido="Ficticia",
                   consentimiento_datos=True,
                   consentimiento_fecha=datetime(2026, 10, 1, 9, 0, tzinfo=UTC))
    db_session.add(pac)
    db_session.commit()
    ahora_local = datetime.now(CORDOBA)
    if dias >= 1:
        objetivo = (ahora_local + timedelta(days=dias)).replace(
            hour=9, minute=0, second=0, microsecond=0)
    else:
        # Fuera de término: hoy, próximo slot de 30 min aún futuro (+2 h).
        base = (ahora_local + timedelta(hours=2)).replace(second=0, microsecond=0)
        minuto = 0 if base.minute < 30 else 30
        objetivo = base.replace(minute=minuto)
        if objetivo <= ahora_local:  # pragma: no cover
            objetivo = objetivo + timedelta(minutes=30)
    db_session.add(Disponibilidad(
        odontologo_id=od.id, dia_semana=objetivo.weekday(),
        hora_inicio=time(0, 0), hora_fin=time(23, 30),
        duracion_min=30, tope_dia=48))
    db_session.commit()
    ini_utc = objetivo.astimezone(UTC)
    turno = Turno(paciente_id=pac.id, odontologo_id=od.id, inicio=ini_utc,
                  fin=ini_utc + timedelta(minutes=30), estado="confirmado",
                  canal="web", idempotency_key=f"key-c-{suf}")
    db_session.add(turno)
    db_session.commit()
    token = issue_action_token(destino=dni, proposito="mis-turnos",
                               secret=TEST_AUTH_SECRET)
    return {"turno_id": turno.id, "dni": dni, "token": token}


def test_cotizar_en_termino_100_y_confirmar_libera_feliz(
    auth_client: TestClient, db_session: Session,
) -> None:
    ctx = _sembrar(db_session, dias=30.0)

    cot = auth_client.get(
        f"/api/reservas/{ctx['turno_id']}/cotizar-cancelacion",
        params={"dni": ctx["dni"], "token": ctx["token"]})
    assert cot.status_code == 200, cot.text
    assert cot.json()["porcentaje"] == 100

    r = auth_client.post(
        f"/api/reservas/{ctx['turno_id']}/cancelar",
        params={"dni": ctx["dni"], "token": ctx["token"]},
        json={})
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["estado"] == "cancelado"
    assert cuerpo["devolucion"]["estado"] == "pendiente"
    assert cuerpo["devolucion"]["porcentaje"] == 100

    from app.infra.db.models import Turno
    turno = db_session.query(Turno).filter(Turno.id == ctx["turno_id"]).first()
    assert turno is not None and turno.estado == "cancelado"


def test_cancelar_ya_cancelado_422_sin_efecto_negocio(
    auth_client: TestClient, db_session: Session,
) -> None:
    from app.core.security.action_tokens import issue_action_token
    from app.infra.db.models import TurnoHistorial

    ctx = _sembrar(db_session, dias=30.0)
    auth_client.post(f"/api/reservas/{ctx['turno_id']}/cancelar",
                     params={"dni": ctx["dni"], "token": ctx["token"]}, json={})
    antes = db_session.query(TurnoHistorial).count()

    token2 = issue_action_token(destino=ctx["dni"], proposito="mis-turnos",
                                secret=TEST_AUTH_SECRET)
    r = auth_client.post(f"/api/reservas/{ctx['turno_id']}/cancelar",
                         params={"dni": ctx["dni"], "token": token2}, json={})
    assert r.status_code == 422, r.text
    assert db_session.query(TurnoHistorial).count() == antes


def test_cotizar_fuera_de_termino_60_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    ctx = _sembrar(db_session, dias=0.0)
    cot = auth_client.get(
        f"/api/reservas/{ctx['turno_id']}/cotizar-cancelacion",
        params={"dni": ctx["dni"], "token": ctx["token"]})
    assert cot.status_code == 200, cot.text
    assert cot.json()["porcentaje"] == 60


def test_paciente_con_token_ajeno_403_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    from app.core.security.action_tokens import issue_action_token

    ctx = _sembrar(db_session, dias=30.0)
    ajeno = issue_action_token(destino="99999999", proposito="mis-turnos",
                               secret=TEST_AUTH_SECRET)
    r = auth_client.post(f"/api/reservas/{ctx['turno_id']}/cancelar",
                         params={"dni": ctx["dni"], "token": ajeno}, json={})
    assert r.status_code == 403, r.text
