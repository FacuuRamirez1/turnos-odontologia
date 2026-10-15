"""TRIANGULATE C-01 — P2 extra='forbid' y envelope de errores (U2: 3 escenarios c/u)."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.health import HealthResponse
from app.core.errors import ErrorEnvelope
from app.main import app


def test_healthresponse_valido_feliz() -> None:
    model = HealthResponse(status="ok", service="turnos-odontologia")
    assert model.status == "ok"


def test_healthresponse_campo_extra_rechazado() -> None:
    """Error de negocio P2: campo no declarado debe rechazarse."""
    with pytest.raises(ValidationError):
        HealthResponse(status="ok", service="x", intruso="y")  # type: ignore[call-arg]


def test_healthresponse_faltante_borde() -> None:
    """Borde: sin status no se puede construir."""
    with pytest.raises(ValidationError):
        HealthResponse(service="x")  # type: ignore[call-arg]


def test_envelope_404_estable_feliz() -> None:
    response = TestClient(app).get("/api/no-existe")
    assert response.status_code == 404
    body = response.json()
    assert set(body.keys()) == {"error", "detail", "path"}
    assert body["error"] == "not_found"


def test_envelope_404_path_coincide() -> None:
    """Error: el path del envelope refleja la ruta pedida."""
    response = TestClient(app).get("/api/otra-ruta-inexistente?x=1")
    body = response.json()
    assert body["path"] == "/api/otra-ruta-inexistente"


def test_envelope_modelo_rechaza_extra_borde() -> None:
    """Borde: el envelope tambien es estricto (P2)."""
    with pytest.raises(ValidationError):
        ErrorEnvelope(error="a", detail="b", path="c", extra="d")  # type: ignore[call-arg]
