"""C-12 3.1 — endpoints /api/reportes (feliz / negocio / borde) + RBAC."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security.jwt import create_access_token
from app.tests._reportes_seed import (
    sembrar_devolucion,
    sembrar_odontologo,
    sembrar_pago,
    sembrar_turno,
)
from app.tests.conftest import TEST_AUTH_SECRET

PERIODO = {"desde": "2026-12-01", "hasta": "2026-12-31"}


def headers(rol: str, odontologo_id: uuid.UUID | None = None) -> dict[str, str]:
    token = create_access_token(
        sub=f"user-{uuid.uuid4().hex[:8]}",
        rol=rol,
        secret=TEST_AUTH_SECRET,
        odontologo_id=str(odontologo_id) if odontologo_id else None,
    )
    return {"Authorization": f"Bearer {token}"}


def test_asistencia_recepcionista_ve_todo(
    auth_client: TestClient, db_session: Session
) -> None:
    a = sembrar_odontologo(db_session, "h1")
    b = sembrar_odontologo(db_session, "h2")
    sembrar_turno(db_session, a, estado="atendido")
    sembrar_turno(db_session, b, estado="no_show")

    r = auth_client.get(
        "/api/reportes/asistencia", params=PERIODO, headers=headers("recepcionista")
    )

    assert r.status_code == 200
    conteos = r.json()["conteos"]
    assert conteos["atendido"] == 1 and conteos["no_show"] == 1
    assert conteos["creado"] == 0 and len(conteos) == 7


def test_caja_con_marca_simulada_y_neto(
    auth_client: TestClient, db_session: Session
) -> None:
    od = sembrar_odontologo(db_session, "h3")
    pago = sembrar_pago(db_session, sembrar_turno(db_session, od, estado="cancelado"))
    sembrar_devolucion(db_session, pago)

    r = auth_client.get(
        "/api/reportes/caja", params=PERIODO, headers=headers("admin")
    )

    cuerpo = r.json()
    assert r.status_code == 200 and cuerpo["marca"] == "(simulado)"
    assert float(cuerpo["neto"]) == 4000.0
    assert float(cuerpo["total_aprobado"]) == sum(
        float(f["monto"]) for f in cuerpo["filas"] if f["concepto"] == "pago"
    )


def test_caja_sin_marca_fuera_de_modo_simulado(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.api.reportes as reportes_api

    monkeypatch.setattr(reportes_api, "marca_pago_actual", lambda: "")
    r = auth_client.get("/api/reportes/caja", params=PERIODO, headers=headers("admin"))
    assert r.json()["marca"] == ""


def test_periodo_invalido_422(auth_client: TestClient) -> None:
    r = auth_client.get(
        "/api/reportes/asistencia",
        params={"desde": "2026-12-31", "hasta": "2026-12-01"},
        headers=headers("admin"),
    )
    assert r.status_code == 422


@pytest.mark.parametrize(
    "ruta",
    [
        "/api/reportes/asistencia",
        "/api/reportes/caja",
        "/api/reportes/mail",
        "/api/reportes/turnos.csv",
        "/api/reportes/turnos.pdf",
        "/api/reportes/caja.csv",
        "/api/reportes/caja.pdf",
        "/api/reportes/auditoria.csv",
    ],
)
def test_sin_jwt_401_y_paciente_403(auth_client: TestClient, ruta: str) -> None:
    assert auth_client.get(ruta, params=PERIODO).status_code == 401
    r = auth_client.get(ruta, params=PERIODO, headers=headers("paciente"))
    assert r.status_code == 403


def test_exportaciones_content_type_y_marca(
    auth_client: TestClient, db_session: Session
) -> None:
    od = sembrar_odontologo(db_session, "h4")
    sembrar_pago(db_session, sembrar_turno(db_session, od))
    h = headers("recepcionista")

    csv_t = auth_client.get("/api/reportes/turnos.csv", params=PERIODO, headers=h)
    pdf_c = auth_client.get("/api/reportes/caja.pdf", params=PERIODO, headers=h)
    csv_c = auth_client.get("/api/reportes/caja.csv", params=PERIODO, headers=h)
    csv_a = auth_client.get("/api/reportes/auditoria.csv", params=PERIODO, headers=h)

    assert csv_t.headers["content-type"].startswith("text/csv")
    assert "attachment" in csv_t.headers["content-disposition"]
    assert pdf_c.headers["content-type"] == "application/pdf"
    assert rb"\(simulado\)" in pdf_c.content
    assert b"(simulado)" in csv_c.content
    assert csv_a.status_code == 200


def test_mail_devuelve_seis_claves_con_ceros(auth_client: TestClient) -> None:
    r = auth_client.get("/api/reportes/mail", params=PERIODO, headers=headers("admin"))
    assert r.status_code == 200
    assert set(r.json()["conteos"]) == {
        "encolado", "enviado", "reintentando", "fallido",
        "confirmado_desde_mail", "cancelado_desde_mail",
    }


def test_rutas_no_son_publicas() -> None:
    from app.api import PUBLIC_ROUTES

    assert not any("reportes" in str(ruta) for ruta in PUBLIC_ROUTES)
