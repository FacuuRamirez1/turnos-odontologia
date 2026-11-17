"""C-12 3.2 — aislamiento por profesional en reportes y exportaciones (P8)."""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.tests._reportes_seed import (
    sembrar_odontologo,
    sembrar_pago,
    sembrar_turno,
)
from app.tests.test_reportes_api import PERIODO, headers


def test_odontologo_ignora_odontologo_id_ajeno(
    auth_client: TestClient, db_session: Session
) -> None:
    a = sembrar_odontologo(db_session, "s1")
    b = sembrar_odontologo(db_session, "s2")
    sembrar_turno(db_session, a, estado="atendido")
    sembrar_turno(db_session, b, estado="atendido")
    sembrar_turno(db_session, b, estado="atendido")

    r = auth_client.get(
        "/api/reportes/asistencia",
        params={**PERIODO, "odontologo_id": str(b)},
        headers=headers("odontologo", a),
    )

    assert r.json()["conteos"]["atendido"] == 1
    assert r.json()["odontologo_id"] == str(a)


def test_odontologo_caja_y_csv_solo_lo_propio(
    auth_client: TestClient, db_session: Session
) -> None:
    a = sembrar_odontologo(db_session, "s3")
    b = sembrar_odontologo(db_session, "s4")
    sembrar_pago(db_session, sembrar_turno(db_session, a), monto="100.00")
    sembrar_pago(db_session, sembrar_turno(db_session, b), monto="900.00")
    h = headers("odontologo", a)

    caja = auth_client.get("/api/reportes/caja", params=PERIODO, headers=h).json()
    turnos = auth_client.get("/api/reportes/turnos.csv", params=PERIODO, headers=h)

    assert float(caja["total_aprobado"]) == 100.0
    assert str(b) not in turnos.text


def test_odontologo_sin_vinculo_403(auth_client: TestClient) -> None:
    r = auth_client.get(
        "/api/reportes/asistencia", params=PERIODO, headers=headers("odontologo")
    )
    assert r.status_code == 403


def test_recepcion_filtra_por_profesional(
    auth_client: TestClient, db_session: Session
) -> None:
    a = sembrar_odontologo(db_session, "s5")
    b = sembrar_odontologo(db_session, "s6")
    sembrar_turno(db_session, a, estado="atendido")
    sembrar_turno(db_session, b, estado="atendido")

    r = auth_client.get(
        "/api/reportes/asistencia",
        params={**PERIODO, "odontologo_id": str(b)},
        headers=headers("recepcionista"),
    )

    assert r.json()["conteos"]["atendido"] == 1
    assert r.json()["odontologo_id"] == str(b)
    otro = auth_client.get(
        "/api/reportes/asistencia",
        params={**PERIODO, "odontologo_id": str(uuid.uuid4())},
        headers=headers("recepcionista"),
    )
    assert otro.json()["conteos"]["atendido"] == 0
