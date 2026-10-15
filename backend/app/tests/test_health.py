"""Tests TDD C-01 — contrato GET /api/health (3 escenarios U2)."""

from fastapi.testclient import TestClient

from app.main import app


def _client() -> TestClient:
    return TestClient(app)


def test_health_200_sin_auth() -> None:
    """Escenario feliz: GET /api/health sin credenciales responde 200."""
    response = _client().get("/api/health")
    assert response.status_code == 200


def test_health_cuerpo_con_status() -> None:
    """Escenario borde: el cuerpo contiene status deserializable sin headers extra."""
    response = _client().get("/api/health")
    body = response.json()
    assert body["status"] == "ok"
    assert "service" in body


def test_ruta_inexistente_404() -> None:
    """Escenario error de negocio: ruta inexistente responde 404 (envelope estable)."""
    response = _client().get("/api/ruta-que-no-existe")
    assert response.status_code == 404
    body = response.json()
    assert "error" in body
