"""Tests C-04 §3.1 — endpoints staff disponibilidad/bloqueos con RBAC (RED primero).

- feliz: odontólogo crea la propia 201 / recepcionista crea cualquiera;
- negocio: odontólogo sobre odontologo_id ajeno → 403 sin cambios, payload
  con campo extra → 422 (P2);
- borde: recepcionista sin odontologo_id explícito → 422, nunca lectura global.
"""

import uuid
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security.jwt import create_access_token
from app.infra.db.models import Disponibilidad, Odontologo, Usuario
from app.tests.conftest import TEST_AUTH_SECRET

HASH = "$2b$04$" + "g" * 53
STAFF_DISPO = "/api/staff/disponibilidad"


def _usuario(db: Session, email: str, rol: str, od_id: uuid.UUID | None = None) -> Usuario:
    u = Usuario(email=email, password_hash=HASH, rol=rol, odontologo_id=od_id)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _perfil(db: Session, user_id: uuid.UUID) -> Odontologo:
    p = Odontologo(user_id=user_id, monto_turno=Decimal("70000"), monto_senia=Decimal("65000"))
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _sembrar(db: Session) -> tuple[uuid.UUID, uuid.UUID]:
    ua = _usuario(db, "od-a@clinica-ficticia.example.ar", "odontologo")
    pa = _perfil(db, uuid.UUID(str(ua.id)))
    ua.odontologo_id = pa.id
    ub = _usuario(db, "od-b@clinica-ficticia.example.ar", "odontologo")
    pb = _perfil(db, uuid.UUID(str(ub.id)))
    ub.odontologo_id = pb.id
    _usuario(db, "recep@clinica-ficticia.example.ar", "recepcionista")
    db.commit()
    return uuid.UUID(str(pa.id)), uuid.UUID(str(pb.id))


def _token(sub: str, rol: str, od_id: uuid.UUID | None = None) -> dict[str, str]:
    t = create_access_token(
        sub=sub, rol=rol, secret=TEST_AUTH_SECRET,
        odontologo_id=str(od_id) if od_id is not None else None,
    )
    return {"Authorization": f"Bearer {t}"}


def _payload(od_id: uuid.UUID) -> dict[str, Any]:
    return {
        "odontologo_id": str(od_id),
        "dia_semana": 0,
        "hora_inicio": "09:00:00",
        "hora_fin": "12:00:00",
        "duracion_min": 30,
        "tope_dia": 14,
    }


def _post(auth_client: TestClient, payload: dict[str, Any], headers: dict[str, str]):  # type: ignore[no-untyped-def]
    return auth_client.post(STAFF_DISPO, json=payload, headers=headers)


def test_odontologo_crea_propia_201_feliz(auth_client: TestClient, db_session: Session) -> None:
    od_a, _ = _sembrar(db_session)
    r = _post(auth_client, _payload(od_a), _token("u-a", "odontologo", od_a))
    assert r.status_code == 201, r.text
    assert r.json()["odontologo_id"] == str(od_a)


def test_recepcionista_crea_cualquiera_feliz(auth_client: TestClient, db_session: Session) -> None:
    od_a, od_b = _sembrar(db_session)
    for od in (od_a, od_b):
        r = _post(auth_client, _payload(od), _token("recep", "recepcionista"))
        assert r.status_code == 201, r.text


def test_odontologo_sobre_ajeno_403_negocio(auth_client: TestClient, db_session: Session) -> None:
    od_a, od_b = _sembrar(db_session)
    antes = db_session.query(Disponibilidad).count()
    r = _post(auth_client, _payload(od_b), _token("u-a", "odontologo", od_a))
    assert r.status_code == 403
    assert db_session.query(Disponibilidad).count() == antes


def test_campo_extra_422_P2_negocio(auth_client: TestClient, db_session: Session) -> None:
    od_a, _ = _sembrar(db_session)
    payload = {**_payload(od_a), "hack": True}
    r = _post(auth_client, payload, _token("u-a", "odontologo", od_a))
    assert r.status_code == 422


def test_recepcionista_sin_odontologo_id_422_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    _sembrar(db_session)
    payload = {k: v for k, v in _payload(uuid.uuid4()).items() if k != "odontologo_id"}
    r = _post(auth_client, payload, _token("recep", "recepcionista"))
    assert r.status_code == 422
