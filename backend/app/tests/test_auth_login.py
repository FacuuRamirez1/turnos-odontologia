"""Tests C-03 §5.1 — `POST /api/auth/login` (RED primero, task 5.1).

Escenarios (U2 feliz / negocio / borde):
- feliz: credenciales seed OK → 200 + cookie `refresh_token` HttpOnly/Secure/SameSite=Lax;
- negocio: credencial mala → 401 sin distinguir causa (mismo cuerpo email-x vs clave-x);
- borde P2: campo extra → 422 (`extra='forbid'`), sin tokens.
Más: inactivo → 401; email case-insensitive; 6to intento → 429.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.tests._auth_helpers import TEST_PASSWORD, crear_usuario  # noqa: F401

LOGIN = "/api/auth/login"


def test_login_ok_con_cookie_segura_feliz(auth_client: TestClient, db_session: Session) -> None:
    crear_usuario(db_session)
    response = auth_client.post(
        LOGIN,
        json={"email": "recep@clinica-ficticia.example.ar", "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"] and body["token_type"] == "bearer"
    assert "refresh_token" not in body
    set_cookie = response.headers.get("set-cookie", "")
    assert "refresh_token=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "SameSite=Lax" in set_cookie or "samesite=lax" in set_cookie.lower()


def test_credencial_mala_no_distingue_causa_negocio(
    auth_client: TestClient, db_session: Session
) -> None:
    crear_usuario(db_session)
    email_x = auth_client.post(
        LOGIN, json={"email": "nadie@x.example.ar", "password": TEST_PASSWORD}
    )
    clave_x = auth_client.post(
        LOGIN, json={"email": "recep@clinica-ficticia.example.ar", "password": "clave-otra"}
    )
    assert email_x.status_code == 401
    assert clave_x.status_code == 401
    assert email_x.json() == clave_x.json()
    assert "refresh_token" not in (email_x.headers.get("set-cookie", ""))


def test_campo_extra_422_borde(auth_client: TestClient, db_session: Session) -> None:
    crear_usuario(db_session)
    response = auth_client.post(
        LOGIN,
        json={
            "email": "recep@clinica-ficticia.example.ar",
            "password": TEST_PASSWORD,
            "rol": "admin",
        },
    )
    assert response.status_code == 422


def test_usuario_inactivo_401(auth_client: TestClient, db_session: Session) -> None:
    crear_usuario(db_session, email="off@clinica-ficticia.example.ar", activo=False)
    response = auth_client.post(
        LOGIN, json={"email": "off@clinica-ficticia.example.ar", "password": TEST_PASSWORD}
    )
    assert response.status_code == 401
    assert "access_token" not in response.json()


def test_email_case_insensitive(auth_client: TestClient, db_session: Session) -> None:
    crear_usuario(db_session)
    response = auth_client.post(
        LOGIN, json={"email": "RECEP@clinica-ficticia.example.ar", "password": TEST_PASSWORD}
    )
    assert response.status_code == 200


def test_sexto_intento_429_aun_con_clave_buena(
    auth_client: TestClient, db_session: Session
) -> None:
    crear_usuario(db_session)
    malo = {"email": "recep@clinica-ficticia.example.ar", "password": "clave-mala"}
    for _ in range(5):
        assert auth_client.post(LOGIN, json=malo).status_code == 401
    buena = {"email": "recep@clinica-ficticia.example.ar", "password": TEST_PASSWORD}
    response = auth_client.post(LOGIN, json=buena)
    assert response.status_code == 429
