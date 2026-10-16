"""Tests C-04 §5.1 — GET público /api/disponibilidad (P12, 03 §3.1) (RED primero).

- feliz: día con 3 huecos → 200 con 3 pares inicio/fin y cero campos paciente;
- negocio: odontologo_id desconocido → 404, fecha pasada/malformada o params
  ausentes → 422;
- borde: día totalmente bloqueado → 200 lista vacía; slot dentro de
  anticipación ausente.
"""

import datetime as dt
import uuid
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.infra.db.models import Bloqueo, Disponibilidad, Odontologo, Usuario

HASH = "$2b$04$" + "j" * 53
CORDOBA = ZoneInfo("America/Argentina/Cordoba")
# Lunes futuro fijo (dia_semana 0): 2026-12-07.
FECHA_LUNES = "2026-12-07"


def _sembrar(db: Session) -> uuid.UUID:
    u = Usuario(email="od-pub@clinica-ficticia.example.ar", password_hash=HASH, rol="odontologo")
    db.add(u)
    db.commit()
    p = Odontologo(user_id=u.id, monto_turno=Decimal("1"), monto_senia=Decimal("1"))
    db.add(p)
    db.commit()
    od = uuid.UUID(str(p.id))
    db.add(
        Disponibilidad(
            odontologo_id=od, dia_semana=0,
            hora_inicio=dt.time(9, 0), hora_fin=dt.time(10, 30),
            duracion_min=30, tope_dia=14,
        )
    )
    db.commit()
    return od


def _get(auth_client: TestClient, od: uuid.UUID, fecha: str):  # type: ignore[no-untyped-def]
    return auth_client.get("/api/disponibilidad", params={"odontologo_id": str(od), "fecha": fecha})


def test_dia_con_3_huecos_feliz(auth_client: TestClient, db_session: Session) -> None:
    od = _sembrar(db_session)
    r = _get(auth_client, od, FECHA_LUNES)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert len(cuerpo["slots"]) == 3
    for slot in cuerpo["slots"]:
        assert set(slot.keys()) == {"inicio", "fin"}
        assert "paciente" not in r.text.lower()


def test_odontologo_desconocido_404_negocio(auth_client: TestClient, db_session: Session) -> None:
    _sembrar(db_session)
    r = _get(auth_client, uuid.uuid4(), FECHA_LUNES)
    assert r.status_code == 404


def test_fecha_pasada_422_negocio(auth_client: TestClient, db_session: Session) -> None:
    od = _sembrar(db_session)
    r = _get(auth_client, od, "2020-01-01")
    assert r.status_code == 422


def test_fecha_malformada_422_negocio(auth_client: TestClient, db_session: Session) -> None:
    od = _sembrar(db_session)
    r = _get(auth_client, od, "no-fecha")
    assert r.status_code == 422


def test_params_ausentes_422_negocio(auth_client: TestClient) -> None:
    assert auth_client.get("/api/disponibilidad").status_code == 422
    params = {"fecha": FECHA_LUNES}
    assert auth_client.get("/api/disponibilidad", params=params).status_code == 422


def test_dia_bloqueado_lista_vacia_borde(auth_client: TestClient, db_session: Session) -> None:
    od = _sembrar(db_session)
    base = dt.datetime(2026, 12, 7, 0, 0, tzinfo=CORDOBA)
    db_session.add(
        Bloqueo(
            odontologo_id=od, desde=base,
            hasta=base.replace(hour=23, minute=59), motivo="feriado",
        )
    )
    db_session.commit()
    r = _get(auth_client, od, FECHA_LUNES)
    assert r.status_code == 200
    assert r.json()["slots"] == []


def test_anticipacion_ausente_borde(auth_client: TestClient, db_session: Session) -> None:
    od = _sembrar(db_session)
    hoy_local = dt.datetime.now(CORDOBA)
    db_session.add(
        Disponibilidad(
            odontologo_id=od, dia_semana=hoy_local.weekday(),
            hora_inicio=dt.time(0, 0), hora_fin=dt.time(1, 0),
            duracion_min=30, tope_dia=14,
        )
    )
    db_session.commit()
    r = _get(auth_client, od, hoy_local.date().isoformat())
    assert r.status_code == 200
    assert r.json()["slots"] == []
