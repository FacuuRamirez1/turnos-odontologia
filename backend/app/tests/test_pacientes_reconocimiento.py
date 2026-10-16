"""Tests C-06 slice 2 — reconocimiento A2 `GET /pacientes?dni=` (RED primero).

- feliz: match exacto devuelve ficha para precarga;
- negocio: DNI no registrado → 200 vacío uniforme (no 404);
- borde: sin JWT → 401; DNI malformado → 422; normalizado con puntos matchea.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security.jwt import create_access_token
from app.tests.conftest import TEST_AUTH_SECRET


def _staff_headers(rol: str = "recepcionista") -> dict[str, str]:
    token = create_access_token(sub="staff-1", rol=rol, secret=TEST_AUTH_SECRET)
    return {"Authorization": f"Bearer {token}"}


def _alta(auth_client: TestClient, dni: str = "99.999.921") -> dict[str, object]:
    r = auth_client.post(
        "/api/pacientes",
        json={
            "dni": dni,
            "nombre": "Ana",
            "apellido": "Ficticia",
            "consentimiento_datos": True,
            "consentimiento_fecha": "2026-10-01T09:00:00+00:00",
        },
        headers=_staff_headers(),
    )
    assert r.status_code == 201, r.text
    body: dict[str, object] = r.json()
    return body


def test_match_exacto_devuelve_ficha_feliz(
    auth_client: TestClient, db_session: Session
) -> None:
    """Feliz A2: DNI registrado → 200 con ficha para precarga."""
    _ = db_session
    creada = _alta(auth_client)
    r = auth_client.get(
        "/api/pacientes", params={"dni": "99.999.921"}, headers=_staff_headers()
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["found"] is True
    assert body["paciente"]["dni"] == "99999921"
    assert body["paciente"]["id"] == creada["id"]


def test_dni_no_registrado_200_vacio_uniforme(
    auth_client: TestClient, db_session: Session
) -> None:
    """Negocio: DNI bien formado sin match → 200 vacío (nunca 404)."""
    _ = db_session
    r = auth_client.get(
        "/api/pacientes", params={"dni": "99.999.929"}, headers=_staff_headers()
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"found": False, "paciente": None}


def test_sin_jwt_401_borde(auth_client: TestClient) -> None:
    """Borde: sin JWT staff → 401."""
    r = auth_client.get("/api/pacientes", params={"dni": "99.999.921"})
    assert r.status_code == 401, r.text


def test_dni_normalizado_con_puntos_matchea_borde(
    auth_client: TestClient, db_session: Session
) -> None:
    """Borde: alta `99.999.922`, búsqueda `99999922` (y viceversa) matchean."""
    _ = db_session
    _alta(auth_client, "99.999.922")
    for forma in ("99999922", "99.999.922", " 99.999.922 "):
        r = auth_client.get(
            "/api/pacientes", params={"dni": forma}, headers=_staff_headers()
        )
        assert r.status_code == 200, (forma, r.text)
        assert r.json()["found"] is True


def test_dni_malformado_422_borde(auth_client: TestClient) -> None:
    """Borde: DNI con letras → 422 (no 200 vacío)."""
    r = auth_client.get(
        "/api/pacientes", params={"dni": "ABC"}, headers=_staff_headers()
    )
    assert r.status_code == 422, r.text


def test_odontologo_tambien_reconoce_triangulacion(
    auth_client: TestClient, db_session: Session
) -> None:
    """Triangulación: odontólogo (con perfil) también ve fichas (matriz 03 §2)."""
    _ = db_session
    _alta(auth_client)
    od_id = "11111111-1111-4111-8111-111111111111"
    token = create_access_token(
        sub="od-1", rol="odontologo", secret=TEST_AUTH_SECRET, odontologo_id=od_id
    )
    r = auth_client.get(
        "/api/pacientes",
        params={"dni": "99.999.921"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["found"] is True


def test_openapi_expone_reconocimiento_cerrado(auth_client: TestClient) -> None:
    """2.3: OpenAPI expone `ReconocimientoOut`/`PacienteRead` cerrados (P2)."""
    r = auth_client.get("/openapi.json")
    assert r.status_code == 200, r.text
    schemas = r.json()["components"]["schemas"]
    for nombre in ("ReconocimientoOut", "PacienteRead", "PacienteCreate", "TurnoAcotado"):
        assert nombre in schemas, nombre
        assert schemas[nombre].get("additionalProperties") is False, nombre


def test_rafaga_staff_429_borde(auth_client: TestClient) -> None:
    """Req 8/P12: ráfaga sobre endpoints staff → 429 (seam de límite bajo)."""
    from app.api import pacientes as pacientes_router

    pacientes_router.reset_pacientes_limiter(limit=2, window_seconds=60)
    try:
        h = _staff_headers()
        params = {"dni": "99.999.929"}
        assert auth_client.get("/api/pacientes", params=params, headers=h).status_code == 200
        assert auth_client.get("/api/pacientes", params=params, headers=h).status_code == 200
        assert (
            auth_client.get("/api/pacientes", params=params, headers=h).status_code
            == 429
        )
    finally:
        pacientes_router.reset_pacientes_limiter()
