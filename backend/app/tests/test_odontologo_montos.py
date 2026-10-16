"""Tests C-04 §4.1 — PATCH /api/odontologos/montos (D-MONTOS, D1).

- feliz: odontólogo actualiza los propios 200 (claim odontologo_id, nunca body);
- negocio: recepcionista/admin → 403 sin cambios;
- borde: monto negativo → 422; monto_senia > monto_turno permitido (sin regla
  de proporción en v1).
"""

import uuid
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security.jwt import create_access_token
from app.infra.db.models import Odontologo, Usuario
from app.tests.conftest import TEST_AUTH_SECRET

HASH = "$2b$04$" + "i" * 53


def _sembrar(db: Session) -> uuid.UUID:
    u = Usuario(email="od-m@clinica-ficticia.example.ar", password_hash=HASH, rol="odontologo")
    db.add(u)
    db.commit()
    p = Odontologo(user_id=u.id, monto_turno=Decimal("70000"), monto_senia=Decimal("65000"))
    db.add(p)
    db.commit()
    u.odontologo_id = p.id
    db.commit()
    return uuid.UUID(str(p.id))


def _token(rol: str, od: uuid.UUID | None = None) -> dict[str, str]:
    t = create_access_token(
        sub=f"s-{rol}", rol=rol, secret=TEST_AUTH_SECRET,
        odontologo_id=str(od) if od else None,
    )
    return {"Authorization": f"Bearer {t}"}


MONTOS = "/api/odontologos/montos"


def _patch(auth_client: TestClient, payload: object, headers: dict[str, str]):  # type: ignore[no-untyped-def]
    return auth_client.patch(MONTOS, json=payload, headers=headers)


def test_actualiza_propios_200_feliz(auth_client: TestClient, db_session: Session) -> None:
    od = _sembrar(db_session)
    r = _patch(
        auth_client,
        {"monto_turno": "75000.00", "monto_senia": "70000.00"},
        _token("odontologo", od),
    )
    assert r.status_code == 200, r.text
    assert r.json()["monto_turno"] == "75000.00"


def test_recepcionista_403_sin_cambios_negocio(
    auth_client: TestClient, db_session: Session,
) -> None:
    od = _sembrar(db_session)
    r = _patch(auth_client, {"monto_turno": "1.00"}, _token("recepcionista"))
    assert r.status_code == 403
    db_session.expire_all()
    fila = db_session.query(Odontologo).filter(Odontologo.id == od).first()
    assert fila is not None and fila.monto_turno == Decimal("70000")


def test_admin_403_sin_cambios_negocio(auth_client: TestClient, db_session: Session) -> None:
    _sembrar(db_session)
    r = _patch(auth_client, {"monto_turno": "1.00"}, _token("admin"))
    assert r.status_code == 403


def test_monto_negativo_422_borde(auth_client: TestClient, db_session: Session) -> None:
    od = _sembrar(db_session)
    r = _patch(auth_client, {"monto_turno": "-5.00"}, _token("odontologo", od))
    assert r.status_code == 422


def test_senia_mayor_que_turno_permitida_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    od = _sembrar(db_session)
    r = _patch(
        auth_client,
        {"monto_turno": "50000.00", "monto_senia": "60000.00"},
        _token("odontologo", od),
    )
    assert r.status_code == 200, r.text
