"""Tests C-05 §3.2 — rate-limit POST /reservas + ruta sin JWT (RED primero).

- feliz: reserva sin Authorization llega al handler (no 401);
- borde: ráfaga sobre el umbral → 429 (y sigue sin exigir JWT).
"""

import uuid
from datetime import timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.reservas import reset_reservas_limiter

CORDOBA = ZoneInfo("America/Argentina/Cordoba")
RUTA = "/api/reservas"


def _payload(od_id: object, inicio_iso: str) -> dict[str, object]:
    return {
        "odontologo_id": str(od_id),
        "inicio": inicio_iso,
        "dni": "99999701",
        "nombre": "Ana",
        "apellido": "Ficticia",
        "consentimiento_datos": True,
        "consentimiento_fecha": "2030-01-01T09:00:00+00:00",
    }


def _contexto(db_session: Session) -> tuple[object, str]:
    import datetime as dt
    from datetime import time
    from decimal import Decimal

    from app.infra.db.models import Disponibilidad, Odontologo, Paciente, Usuario

    u = Usuario(email=f"od-rl-{uuid.uuid4().hex[:8]}@clinica-ficticia.example.ar",
                password_hash="$2b$04$" + "n" * 53, rol="odontologo")
    db_session.add(u)
    db_session.commit()
    od = Odontologo(user_id=u.id, monto_turno=Decimal("70000"), monto_senia=Decimal("65000"))
    db_session.add(od)
    db_session.commit()
    objetivo = dt.datetime.now(CORDOBA) + timedelta(days=35)
    objetivo = objetivo.replace(hour=9, minute=0, second=0, microsecond=0)
    db_session.add(Disponibilidad(
        odontologo_id=od.id, dia_semana=objetivo.weekday(),
        hora_inicio=time(9, 0), hora_fin=time(12, 0),
        duracion_min=30, tope_dia=14))
    db_session.add(Paciente(dni="99999701", nombre="Ana", apellido="Ficticia",
                            consentimiento_datos=True,
                            consentimiento_fecha=dt.datetime(2026, 10, 1, 9, 0,
                                                             tzinfo=dt.UTC)))
    db_session.commit()
    return od.id, objetivo.isoformat()


def test_reserva_sin_jwt_no_401_feliz(
    auth_client: TestClient, db_session: Session,
) -> None:
    od_id, inicio = _contexto(db_session)
    r = auth_client.post(RUTA, json=_payload(od_id, inicio),
                         headers={"Idempotency-Key": f"rk-{uuid.uuid4().hex[:12]}"})
    assert r.status_code != 401, r.text
    assert r.status_code == 201, r.text


def test_rafaga_reservas_429_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    reset_reservas_limiter(limit=3, window_seconds=60)
    od_id, inicio = _contexto(db_session)
    estados = []
    for _ in range(4):
        r = auth_client.post(
            RUTA, json=_payload(od_id, inicio),
            headers={"Idempotency-Key": f"rk-{uuid.uuid4().hex[:12]}"})
        estados.append(r.status_code)
    assert estados[:3] != [401] * 3  # nunca exige JWT, ni bajo ráfaga
    assert estados[3] == 429
