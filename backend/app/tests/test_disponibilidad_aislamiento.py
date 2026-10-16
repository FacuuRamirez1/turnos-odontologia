"""Tests C-04 §3.3 — aislamiento en lectura staff (P8, RN-AISLAMIENTO).

- feliz: odontólogo lista solo lo propio con 2 profesionales;
- negocio: GET por id ajeno → 404;
- borde: BaseRepository(Disponibilidad) sin scope levanta en vez de filtrar.
"""

import datetime as dt
import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security.jwt import create_access_token
from app.infra.db.models import Disponibilidad, Odontologo, Usuario
from app.infra.db.repository import BaseRepository
from app.tests.conftest import TEST_AUTH_SECRET

HASH = "$2b$04$" + "h" * 53


def _sembrar(db: Session) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    ua = Usuario(email="oa@clinica-ficticia.example.ar", password_hash=HASH, rol="odontologo")
    db.add(ua)
    db.commit()
    pa = Odontologo(user_id=ua.id, monto_turno=Decimal("1"), monto_senia=Decimal("1"))
    db.add(pa)
    db.commit()
    ua.odontologo_id = pa.id
    ub = Usuario(email="ob@clinica-ficticia.example.ar", password_hash=HASH, rol="odontologo")
    db.add(ub)
    db.commit()
    pb = Odontologo(user_id=ub.id, monto_turno=Decimal("1"), monto_senia=Decimal("1"))
    db.add(pb)
    db.commit()
    ub.odontologo_id = pb.id
    db.commit()
    od_a, od_b = uuid.UUID(str(pa.id)), uuid.UUID(str(pb.id))

    def _franja(od: uuid.UUID) -> Disponibilidad:
        return Disponibilidad(
            odontologo_id=od, dia_semana=0,
            hora_inicio=dt.time(9, 0), hora_fin=dt.time(10, 0),
            duracion_min=30, tope_dia=14,
        )

    fa, fb = _franja(od_a), _franja(od_b)
    db.add_all([fa, fb])
    db.commit()
    db.refresh(fb)
    return od_a, od_b, uuid.UUID(str(fb.id))


def _token(od: uuid.UUID) -> dict[str, str]:
    t = create_access_token(
        sub="oa", rol="odontologo", secret=TEST_AUTH_SECRET, odontologo_id=str(od)
    )
    return {"Authorization": f"Bearer {t}"}


def test_lista_solo_lo_propio_feliz(auth_client: TestClient, db_session: Session) -> None:
    od_a, _, _ = _sembrar(db_session)
    r = auth_client.get("/api/staff/disponibilidad", headers=_token(od_a))
    assert r.status_code == 200
    filas = r.json()
    assert len(filas) == 1
    assert filas[0]["odontologo_id"] == str(od_a)


def test_get_por_id_ajeno_404_negocio(auth_client: TestClient, db_session: Session) -> None:
    od_a, _, fb_id = _sembrar(db_session)
    r = auth_client.get(f"/api/staff/disponibilidad/{fb_id}", headers=_token(od_a))
    assert r.status_code == 404


def test_repo_sin_scope_levanta_borde(db_session: Session) -> None:
    with pytest.raises(ValueError):
        BaseRepository(db_session, Disponibilidad)
