"""Tests C-05 §4.1 + C-08 task 2.4 — cotizar/confirmar cancelación (RED primero).

Escenarios (U2 feliz / error-negocio / borde):
- feliz: en término (anticipación 24 h, turno a 30 días) → 100 %; confirmar
  cancela, libera el slot y devuelve la `devolucion` persistida con `id`,
  `porcentaje`, `monto` y `estado = pendiente` (C-08 D1);
- error: turno ya `cancelado` no se re-cancela (422, sin filas nuevas); sin
  pago aprobado → `devolucion = null`; token ajeno → 403; `no_show` no se
  puede cancelar (422, RN-ESTADOS);
- borde: fuera de término (turno en 2 h) → 60 %; cotización 0 % (post-`inicio`)
  → `devolucion = null`, turno `cancelado` (nunca `devuelto`).
"""

import uuid
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from typing import TypedDict
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security.jwt import create_access_token
from app.infra.db.models import Devolucion
from app.tests.conftest import TEST_AUTH_SECRET

CORDOBA = ZoneInfo("America/Argentina/Cordoba")
MONTO_SENIA = Decimal("65000.00")


class _Ctx(TypedDict):
    turno_id: uuid.UUID
    dni: str
    token: str
    pago_id: uuid.UUID | None


def _sembrar(
    db_session: Session, dias: float = 30.0, *,
    con_pago: bool = True, pago_estado: str = "aprobado",
    estado: str = "confirmado", inicio_pasado: bool = False,
) -> _Ctx:
    from app.core.security.action_tokens import issue_action_token
    from app.infra.db.models import (
        Disponibilidad,
        Odontologo,
        Paciente,
        Pago,
        Turno,
        Usuario,
    )

    suf = uuid.uuid4().hex[:8]
    dni = f"77{suf}"
    u = Usuario(email=f"od-c-{suf}@clinica-ficticia.example.ar",
                password_hash="$2b$04$" + "o" * 53, rol="odontologo")
    db_session.add(u)
    db_session.commit()
    od = Odontologo(user_id=u.id, monto_turno=Decimal("70000"), monto_senia=MONTO_SENIA)
    db_session.add(od)
    db_session.commit()
    pac = Paciente(dni=dni, nombre="Ana", apellido="Ficticia",
                   consentimiento_datos=True,
                   consentimiento_fecha=datetime(2026, 10, 1, 9, 0, tzinfo=UTC))
    db_session.add(pac)
    db_session.commit()
    ahora_local = datetime.now(CORDOBA)
    if inicio_pasado:
        objetivo = (ahora_local - timedelta(hours=1)).replace(
            second=0, microsecond=0)
    elif dias >= 1:
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
                  fin=ini_utc + timedelta(minutes=30), estado=estado,
                  canal="web", idempotency_key=f"key-c-{suf}")
    db_session.add(turno)
    db_session.commit()
    pago_id: uuid.UUID | None = None
    if con_pago:
        pago = Pago(
            turno_id=turno.id, odontologo_id=od.id, monto=MONTO_SENIA,
            moneda="ARS", proveedor="simulado",
            mp_payment_id=f"sim_pay_{uuid.uuid4()}", estado=pago_estado,
            idempotency_key=f"idem-c-{suf}",
        )
        db_session.add(pago)
        db_session.commit()
        pago_id = pago.id
        turno.pago_id = pago.id
        db_session.add(turno)
        db_session.commit()
    token = issue_action_token(destino=dni, proposito="mis-turnos",
                               secret=TEST_AUTH_SECRET)
    return {"turno_id": turno.id, "dni": dni, "token": token, "pago_id": pago_id}


def _staff_headers() -> dict[str, str]:
    tok = create_access_token(sub="staff-rec-1", rol="recepcionista",
                              secret=TEST_AUTH_SECRET)
    return {"Authorization": f"Bearer {tok}"}


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
    devolucion = cuerpo["devolucion"]
    assert devolucion["estado"] == "pendiente"
    assert devolucion["porcentaje"] == 100
    assert devolucion["monto"] == 65000.0
    assert uuid.UUID(devolucion["id"]) is not None

    persistida = db_session.query(Devolucion).filter(
        Devolucion.id == uuid.UUID(devolucion["id"])).one()
    assert persistida.turno_id == ctx["turno_id"]
    assert persistida.pago_id == ctx["pago_id"]

    from app.infra.db.models import Turno
    turno = db_session.query(Turno).filter(Turno.id == ctx["turno_id"]).first()
    assert turno is not None and turno.estado == "cancelado"


def test_staff_cancela_con_pago_aprobado_devuelve_devolucion_feliz(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Feliz: staff (JWT recepcionista) también obtiene la devolución real."""
    ctx = _sembrar(db_session, dias=30.0)

    r = auth_client.post(f"/api/reservas/{ctx['turno_id']}/cancelar",
                         headers=_staff_headers(), json={"motivo": "a pedido"})
    assert r.status_code == 200, r.text
    devolucion = r.json()["devolucion"]
    assert devolucion["porcentaje"] == 100
    assert devolucion["estado"] == "pendiente"
    assert db_session.query(Devolucion).count() == 1


def test_cancelar_sin_pago_aprobado_devuelve_null_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Borde: sin pago aprobado → `devolucion = null` y no se persiste fila."""
    ctx = _sembrar(db_session, dias=30.0, con_pago=False)

    r = auth_client.post(f"/api/reservas/{ctx['turno_id']}/cancelar",
                         params={"dni": ctx["dni"], "token": ctx["token"]},
                         json={})
    assert r.status_code == 200, r.text
    assert r.json()["devolucion"] is None
    assert db_session.query(Devolucion).count() == 0


def test_cancelar_con_cotizacion_cero_devuelve_null_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Borde: post-`inicio` (0 %) → turno `cancelado`, `devolucion = null`."""
    ctx = _sembrar(db_session, con_pago=True, inicio_pasado=True)

    r = auth_client.post(f"/api/reservas/{ctx['turno_id']}/cancelar",
                         params={"dni": ctx["dni"], "token": ctx["token"]},
                         json={})
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "cancelado"
    assert r.json()["devolucion"] is None
    assert db_session.query(Devolucion).count() == 0

    from app.infra.db.models import Turno
    turno = db_session.query(Turno).filter(Turno.id == ctx["turno_id"]).one()
    assert turno.estado == "cancelado"


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


def test_cancelar_no_show_422_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Borde (2.3): `no_show→cancelado` no es transición válida → 422."""
    ctx = _sembrar(db_session, estado="no_show", inicio_pasado=True)

    r = auth_client.post(f"/api/reservas/{ctx['turno_id']}/cancelar",
                         params={"dni": ctx["dni"], "token": ctx["token"]},
                         json={})
    assert r.status_code == 422, r.text
    assert db_session.query(Devolucion).count() == 0


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
