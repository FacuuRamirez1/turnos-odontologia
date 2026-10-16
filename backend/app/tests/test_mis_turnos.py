"""Tests C-05 §5.2 — GET /mis-turnos con token (RED primero, task 5.2).

Escenarios (U2 feliz / error-negocio / borde):
- feliz: token propio → 200 solo con sus turnos;
- error: DNI solo sin token → 401, sin exponer nada;
- borde: token de otro paciente → 403.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.tests.conftest import TEST_AUTH_SECRET


def _sembrar(db_session: Session) -> dict[str, object]:
    from app.core.security.action_tokens import issue_action_token
    from app.infra.db.models import Odontologo, Paciente, Turno, Usuario

    suf = uuid.uuid4().hex[:8]
    u = Usuario(email=f"od-mt-{suf}@clinica-ficticia.example.ar",
                password_hash="$2b$04$" + "r" * 53, rol="odontologo")
    db_session.add(u)
    db_session.commit()
    od = Odontologo(user_id=u.id, monto_turno=Decimal("70000"), monto_senia=Decimal("65000"))
    db_session.add(od)
    db_session.commit()
    fecha = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
    base = uuid.uuid4().int % 900000 + 100000
    dni_p1, dni_p2 = f"44{base:06d}", f"45{base:06d}"
    p1 = Paciente(dni=dni_p1, nombre="Ana", apellido="Ficticia",
                  consentimiento_datos=True, consentimiento_fecha=fecha)
    p2 = Paciente(dni=dni_p2, nombre="Otro", apellido="Ficticio",
                  consentimiento_datos=True, consentimiento_fecha=fecha)
    db_session.add_all([p1, p2])
    db_session.commit()
    ini = datetime.now(UTC).replace(microsecond=0) + timedelta(days=30)
    for n, (pac, key) in enumerate(((p1, "mt-p1"), (p2, "mt-p2"))):
        ini_n = ini + timedelta(minutes=60 * n)
        db_session.add(Turno(
            paciente_id=pac.id, odontologo_id=od.id, inicio=ini_n,
            fin=ini_n + timedelta(minutes=30), estado="confirmado",
            canal="web", idempotency_key=f"key-{key}-{suf}"))
    db_session.commit()
    t1 = issue_action_token(destino=dni_p1, proposito="mis-turnos",
                            secret=TEST_AUTH_SECRET)
    return {"dni_p1": dni_p1, "token_p1": t1}


def test_token_propio_devuelve_solo_sus_turnos_feliz(
    auth_client: TestClient, db_session: Session,
) -> None:
    ctx = _sembrar(db_session)
    r = auth_client.get("/api/mis-turnos",
                        params={"dni": ctx["dni_p1"], "token": ctx["token_p1"]})
    assert r.status_code == 200, r.text
    turnos = r.json()
    assert len(turnos) == 1


def test_dni_solo_sin_token_401_negocio(
    auth_client: TestClient, db_session: Session,
) -> None:
    ctx = _sembrar(db_session)
    r = auth_client.get("/api/mis-turnos", params={"dni": ctx["dni_p1"]})
    assert r.status_code == 401, r.text


def test_token_ajeno_403_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    from app.core.security.action_tokens import issue_action_token

    ctx = _sembrar(db_session)
    ajeno = issue_action_token(destino="99999999", proposito="mis-turnos",
                               secret=TEST_AUTH_SECRET)
    r = auth_client.get("/api/mis-turnos",
                        params={"dni": ctx["dni_p1"], "token": ajeno})
    assert r.status_code == 403, r.text
