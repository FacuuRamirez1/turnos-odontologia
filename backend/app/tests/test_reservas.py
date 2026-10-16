"""Tests C-05 §3.1 — POST /reservas público (RED primero, task 3.1).

Escenarios (U2 feliz / error-negocio / borde):
- feliz: DNI reconocido → 201 `creado` reutilizando paciente;
- error: paciente nuevo sin consentimiento → 422 CONSENTIMIENTO_REQUERIDO
  sin filas (ni paciente ni turno); campo extra → 422 (P2);
- borde: DNI `30.123.456` normaliza; replay misma Idempotency-Key no
  duplica (mismo id); keys distintas mismo slot → exactamente 1 turno + 409.
"""

import uuid
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

CORDOBA = ZoneInfo("America/Argentina/Cordoba")
RUTA = "/api/reservas"
CONSENT_AT = "2030-01-01T09:00:00+00:00"


def _sembrar_odonto(db_session: Session) -> uuid.UUID:
    from app.infra.db.models import Disponibilidad, Odontologo, Usuario

    h = "$2b$04$" + "m" * 53
    suf = uuid.uuid4().hex[:8]
    u = Usuario(email=f"od-r-{suf}@clinica-ficticia.example.ar",
                password_hash=h, rol="odontologo")
    db_session.add(u)
    db_session.commit()
    od = Odontologo(user_id=u.id, monto_turno=Decimal("70000"), monto_senia=Decimal("65000"))
    db_session.add(od)
    db_session.commit()
    od_id = uuid.UUID(str(od.id))
    objetivo = datetime.now(CORDOBA) + timedelta(days=35)
    objetivo = objetivo.replace(hour=9, minute=0, second=0, microsecond=0)
    db_session.add(Disponibilidad(
        odontologo_id=od_id, dia_semana=objetivo.weekday(),
        hora_inicio=time(9, 0), hora_fin=time(12, 0),
        duracion_min=30, tope_dia=14))
    db_session.commit()
    return od_id


def _sembrar_paciente(db_session: Session, dni: str) -> None:
    from app.infra.db.models import Paciente

    db_session.add(Paciente(dni=dni, nombre="Ana", apellido="Ficticia",
                            consentimiento_datos=True,
                            consentimiento_fecha=datetime(2026, 10, 1, 9, 0, tzinfo=UTC)))
    db_session.commit()


def _inicio_iso() -> str:
    objetivo = datetime.now(CORDOBA) + timedelta(days=35)
    return objetivo.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()


def _payload(od_id: uuid.UUID, dni: str = "99999601") -> dict[str, object]:
    return {
        "odontologo_id": str(od_id),
        "inicio": _inicio_iso(),
        "dni": dni,
        "nombre": "Ana",
        "apellido": "Ficticia",
        "consentimiento_datos": True,
        "consentimiento_fecha": CONSENT_AT,
    }


def test_reserva_dni_reconocido_201_creado_feliz(
    auth_client: TestClient, db_session: Session,
) -> None:
    od_id = _sembrar_odonto(db_session)
    _sembrar_paciente(db_session, "99999601")

    r = auth_client.post(RUTA, json=_payload(od_id),
                         headers={"Idempotency-Key": f"rk-{uuid.uuid4().hex[:12]}"})
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["estado"] == "creado"
    assert cuerpo["odontologo_id"] == str(od_id)

    from app.infra.db.models import Paciente, Turno
    assert db_session.query(Paciente).count() == 1  # reutiliza, no duplica
    assert db_session.query(Turno).count() == 1


def test_reserva_sin_consentimiento_422_sin_filas_negocio(
    auth_client: TestClient, db_session: Session,
) -> None:
    od_id = _sembrar_odonto(db_session)
    cuerpo = _payload(od_id, dni="99999602")
    cuerpo["consentimiento_datos"] = False
    cuerpo["consentimiento_fecha"] = None

    r = auth_client.post(RUTA, json=cuerpo,
                         headers={"Idempotency-Key": f"rk-{uuid.uuid4().hex[:12]}"})
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "CONSENTIMIENTO_REQUERIDO"

    from app.infra.db.models import Paciente, Turno
    assert db_session.query(Paciente).count() == 0
    assert db_session.query(Turno).count() == 0


def test_reserva_campo_extra_422_P2_negocio(
    auth_client: TestClient, db_session: Session,
) -> None:
    od_id = _sembrar_odonto(db_session)
    cuerpo = {**_payload(od_id), "hack": True}

    r = auth_client.post(RUTA, json=cuerpo,
                         headers={"Idempotency-Key": f"rk-{uuid.uuid4().hex[:12]}"})
    assert r.status_code == 422, r.text


def test_reserva_dni_con_puntos_normaliza_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    od_id = _sembrar_odonto(db_session)
    _sembrar_paciente(db_session, "30123456")

    r = auth_client.post(RUTA, json=_payload(od_id, dni="30.123.456"),
                         headers={"Idempotency-Key": f"rk-{uuid.uuid4().hex[:12]}"})
    assert r.status_code == 201, r.text

    from app.infra.db.models import Paciente, Turno
    assert db_session.query(Paciente).count() == 1
    assert db_session.query(Turno).count() == 1


def test_replay_misma_key_no_duplica_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    od_id = _sembrar_odonto(db_session)
    _sembrar_paciente(db_session, "99999601")
    key = f"rk-{uuid.uuid4().hex[:12]}"

    r1 = auth_client.post(RUTA, json=_payload(od_id), headers={"Idempotency-Key": key})
    r2 = auth_client.post(RUTA, json=_payload(od_id), headers={"Idempotency-Key": key})
    assert r1.status_code == 201, r1.text
    assert r2.status_code in (200, 201), r2.text
    assert r2.json()["id"] == r1.json()["id"]

    from app.infra.db.models import Turno
    assert db_session.query(Turno).count() == 1


def test_keys_distintas_mismo_slot_solo_uno_409_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    od_id = _sembrar_odonto(db_session)
    _sembrar_paciente(db_session, "99999601")

    r1 = auth_client.post(RUTA, json=_payload(od_id),
                          headers={"Idempotency-Key": f"rk-{uuid.uuid4().hex[:12]}"})
    r2 = auth_client.post(RUTA, json=_payload(od_id),
                          headers={"Idempotency-Key": f"rk-{uuid.uuid4().hex[:12]}"})
    assert r1.status_code == 201, r1.text
    assert r2.status_code == 409, r2.text

    from app.infra.db.models import Turno
    assert db_session.query(Turno).count() == 1
