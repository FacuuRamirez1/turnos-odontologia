"""Tests C-03 §7.3 — rutas públicas cerradas P12 (RED primero, task 7.3).

- feliz: el registro `PUBLIC_ROUTES` es exactamente las 6 de `03 §3`;
- negocio: cualquier ruta staff sin token → 401;
- borde: ráfaga sobre pública (login) → 429; desconocida → 404 (cerrada);
- excepción infra documentada: `GET /api/health` sigue pública.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api import PUBLIC_ROUTES


def test_registro_exactamente_6_rutas_03s3_feliz() -> None:
    assert list(PUBLIC_ROUTES) == [
        "GET /disponibilidad",
        "POST /reservas",
        "POST /webhooks/mercadopago",
        "GET /mail/*",
        "GET /mis-turnos",
        "GET /precios",
    ]


def test_staff_sin_token_401_negocio(auth_client: TestClient) -> None:
    assert auth_client.get("/api/auth/me").status_code == 401
    assert auth_client.post("/api/auth/logout").status_code == 401


def test_rafaga_sobre_publica_429_borde(auth_client: TestClient, db_session: Session) -> None:
    from app.tests._auth_helpers import crear_usuario

    crear_usuario(db_session)
    malo = {"email": "recep@clinica-ficticia.example.ar", "password": "mala"}
    estados = [auth_client.post("/api/auth/login", json=malo).status_code for _ in range(6)]
    assert estados[:5] == [401] * 5
    assert estados[5] == 429


def test_ruta_desconocida_404_cerrada_por_construccion(auth_client: TestClient) -> None:
    """Sin router montado no hay ruta abierta por accidente (cierre por defecto)."""
    assert auth_client.get("/api/no-existe").status_code == 404


def test_health_sigue_publica_infra(auth_client: TestClient) -> None:
    assert auth_client.get("/api/health").status_code == 200
