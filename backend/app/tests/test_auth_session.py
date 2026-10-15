"""Tests C-03 §5.3 — refresh con rotación + logout (RED primero, task 5.3).

Escenarios (U2 feliz / negocio / borde):
- feliz: refresh válido rota → par nuevo + cookie nueva;
- negocio: reuso del refresh rotado → 401 sin tokens;
- borde: logout invalida el access (uso posterior → 401); logout sin token → 401.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.tests._auth_helpers import TEST_PASSWORD, crear_usuario  # noqa: F401

LOGIN = "/api/auth/login"
REFRESH = "/api/auth/refresh"
LOGOUT = "/api/auth/logout"
ME = "/api/auth/me"


def _login(auth_client: TestClient, db_session: Session) -> TestClient:
    crear_usuario(db_session)
    response = auth_client.post(
        LOGIN,
        json={"email": "recep@clinica-ficticia.example.ar", "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    return auth_client


def test_refresh_rota_emite_par_nuevo_feliz(auth_client: TestClient, db_session: Session) -> None:
    _login(auth_client, db_session)
    primero = auth_client.cookies.get("refresh_token")
    assert primero

    response = auth_client.post(REFRESH)
    assert response.status_code == 200
    assert response.json()["access_token"]
    segundo = auth_client.cookies.get("refresh_token")
    assert segundo and segundo != primero


def test_reuso_de_refresh_rotado_401_negocio(auth_client: TestClient, db_session: Session) -> None:
    _login(auth_client, db_session)
    viejo = auth_client.cookies.get("refresh_token")
    assert auth_client.post(REFRESH).status_code == 200

    response = auth_client.post(REFRESH, headers={"Cookie": f"refresh_token={viejo or ''}"})
    assert response.status_code == 401
    assert "access_token" not in response.json()


def test_logout_invalida_access_borde(auth_client: TestClient, db_session: Session) -> None:
    _login(auth_client, db_session)
    login_body = auth_client.post(
        LOGIN,
        json={"email": "recep@clinica-ficticia.example.ar", "password": TEST_PASSWORD},
    ).json()
    access = str(login_body["access_token"])

    response = auth_client.post(LOGOUT, headers={"Authorization": f"Bearer {access}"})
    assert response.status_code == 200
    me = auth_client.get(ME, headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 401


def test_logout_sin_token_401(auth_client: TestClient) -> None:
    assert auth_client.post(LOGOUT).status_code == 401
