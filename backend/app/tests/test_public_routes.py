"""Tests C-03 §7.3 — rutas públicas cerradas P12 (RED primero, task 7.3).

- feliz: el registro `PUBLIC_ROUTES` es exactamente las 6 de `03 §3`;
- negocio: cualquier ruta staff sin token → 401;
- borde: ráfaga sobre pública (login) → 429; desconocida → 404 (cerrada);
- excepción infra documentada: `GET /api/health` sigue pública.
"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api import PUBLIC_ROUTES
from app.core.security.jwt import create_access_token
from app.tests.conftest import TEST_AUTH_SECRET


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


def test_devoluciones_no_publicas_p12(auth_client: TestClient) -> None:
    """C-08 3.5: las rutas nuevas exigen JWT staff y no entran en PUBLIC_ROUTES."""
    dev_id = uuid.uuid4()
    rutas = [
        ("GET", "/api/devoluciones", None),
        ("GET", f"/api/devoluciones/{dev_id}", None),
        ("POST", f"/api/devoluciones/{dev_id}/aprobar", {"monto_confirmado": "1.00"}),
        ("POST", f"/api/devoluciones/{dev_id}/rechazar", {"motivo": "x"}),
        ("POST", f"/api/devoluciones/{dev_id}/ejecutar", None),
    ]
    for metodo, path, cuerpo in rutas:
        r = auth_client.request(metodo, path, json=cuerpo)
        assert r.status_code == 401, (metodo, path, r.status_code)

    token = create_access_token(
        sub=str(uuid.uuid4()), rol="paciente", secret=TEST_AUTH_SECRET
    )
    r = auth_client.get(
        "/api/devoluciones", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 403

    assert not any("devolucion" in ruta.lower() for ruta in PUBLIC_ROUTES)
