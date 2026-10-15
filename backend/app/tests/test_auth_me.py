"""Tests C-03 §5.5 — `GET /api/auth/me` (RED primero, task 5.5).

Escenarios (U2 feliz / negocio / borde):
- feliz: token válido → 200 con sub/rol/email/odontologo_id?;
- negocio: token expirado → 401 con envelope estándar;
- borde: token blacklisteado → 401.
"""

from datetime import timedelta
from uuid import uuid4

import jwt as pyjwt
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security.jwt import create_access_token
from app.tests._auth_helpers import TEST_PASSWORD, TEST_SECRET, crear_usuario  # noqa: F401

LOGIN = "/api/auth/login"
ME = "/api/auth/me"


def test_me_devuelve_identidad_feliz(auth_client: TestClient, db_session: Session) -> None:
    odonto_id = uuid4()
    usuario = crear_usuario(
        db_session,
        email="od@clinica-ficticia.example.ar",
        rol="odontologo",
        odontologo_id=odonto_id,
    )
    access = auth_client.post(
        LOGIN, json={"email": "od@clinica-ficticia.example.ar", "password": TEST_PASSWORD}
    ).json()["access_token"]

    response = auth_client.get(ME, headers={"Authorization": f"Bearer {access}"})
    assert response.status_code == 200
    assert response.json() == {
        "sub": str(usuario.id),
        "rol": "odontologo",
        "email": "od@clinica-ficticia.example.ar",
        "odontologo_id": str(odonto_id),
    }


def test_me_token_expirado_401_envelope_negocio(
    auth_client: TestClient, db_session: Session
) -> None:
    usuario = crear_usuario(db_session)
    vencido = create_access_token(
        sub=str(usuario.id), rol="recepcionista", secret=TEST_SECRET,
        ttl_override=timedelta(seconds=-120),
    )
    response = auth_client.get(ME, headers={"Authorization": f"Bearer {vencido}"})
    assert response.status_code == 401
    assert set(response.json()) == {"error", "detail", "path"}


def test_me_token_blacklisteado_401_borde(auth_client: TestClient, db_session: Session) -> None:
    crear_usuario(db_session)
    access = auth_client.post(
        LOGIN, json={"email": "recep@clinica-ficticia.example.ar", "password": TEST_PASSWORD}
    ).json()["access_token"]
    jti = str(pyjwt.decode(access, options={"verify_signature": False})["jti"])

    from app.core.security.dependencies import get_blacklist

    get_blacklist().add(jti, ttl_seconds=900)
    assert auth_client.get(ME, headers={"Authorization": f"Bearer {access}"}).status_code == 401


def test_me_sin_token_401(auth_client: TestClient) -> None:
    assert auth_client.get(ME).status_code == 401
