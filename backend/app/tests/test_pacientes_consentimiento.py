"""Tests C-06 slice 1 — gate RN-CONSENTIMIENTO en POST /pacientes (RED primero).

- negocio: sin consentimiento → 422 CONSENTIMIENTO_REQUERIDO y cero filas.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security.jwt import create_access_token
from app.infra.db.models import Paciente
from app.tests.conftest import TEST_AUTH_SECRET


def _staff_headers(rol: str = "recepcionista") -> dict[str, str]:
    token = create_access_token(sub="staff-1", rol=rol, secret=TEST_AUTH_SECRET)
    return {"Authorization": f"Bearer {token}"}


def _payload_sin_consentimiento() -> dict[str, object]:
    return {
        "dni": "99.999.911",
        "nombre": "Ana",
        "apellido": "Ficticia",
        "consentimiento_datos": False,
    }


def test_post_sin_consentimiento_422_sin_filas(
    auth_client: TestClient, db_session: Session
) -> None:
    """Negocio RN-CONSENTIMIENTO: sin consentimiento no hay fila (P11)."""
    antes = db_session.query(Paciente).count()
    r = auth_client.post(
        "/api/pacientes", json=_payload_sin_consentimiento(), headers=_staff_headers()
    )
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "CONSENTIMIENTO_REQUERIDO"
    db_session.expire_all()
    assert db_session.query(Paciente).count() == antes


def _payload_con_consentimiento(dni: str = "99.999.912") -> dict[str, object]:
    return {
        "dni": dni,
        "nombre": "Bruno",
        "apellido": "Ficticio",
        "consentimiento_datos": True,
        "consentimiento_fecha": "2026-10-01T09:00:00+00:00",
    }


def test_alta_con_consentimiento_201_feliz(
    auth_client: TestClient, db_session: Session
) -> None:
    """Feliz: con consentimiento + fecha persiste y devuelve id."""
    r = auth_client.post(
        "/api/pacientes", json=_payload_con_consentimiento(), headers=_staff_headers()
    )
    assert r.status_code == 201, r.text
    assert r.json()["dni"] == "99999912"
    db_session.expire_all()
    assert db_session.query(Paciente).count() == 1


def test_dni_con_puntos_y_espacios_normaliza_borde(
    auth_client: TestClient, db_session: Session
) -> None:
    """Borde: `30.123.456` / con espacios se normaliza a `30123456`."""
    r = auth_client.post(
        "/api/pacientes",
        json=_payload_con_consentimiento(" 30.123.456 "),
        headers=_staff_headers(),
    )
    assert r.status_code == 201, r.text
    assert r.json()["dni"] == "30123456"
    db_session.expire_all()
    fila = db_session.query(Paciente).first()
    assert fila is not None and fila.dni == "30123456"


def test_dni_duplicado_409_sin_segunda_fila(
    auth_client: TestClient, db_session: Session
) -> None:
    """Negocio: duplicado (tras normalizar) → 409 sin segunda fila."""
    r1 = auth_client.post(
        "/api/pacientes", json=_payload_con_consentimiento("99.999.913"), headers=_staff_headers()
    )
    assert r1.status_code == 201, r1.text
    r2 = auth_client.post(
        "/api/pacientes",
        json=_payload_con_consentimiento("99.999.913"),
        headers=_staff_headers(),
    )
    assert r2.status_code == 409, r2.text
    db_session.expire_all()
    assert db_session.query(Paciente).count() == 1


def test_campo_extra_password_422_P2_borde(
    auth_client: TestClient, db_session: Session
) -> None:
    """Borde P2: campo no declarado (`password`) → 422 sin persistir."""
    payload = {**_payload_con_consentimiento("99.999.914"), "password": "x"}
    r = auth_client.post("/api/pacientes", json=payload, headers=_staff_headers())
    assert r.status_code == 422, r.text
    db_session.expire_all()
    assert db_session.query(Paciente).count() == 0


def test_dni_invalido_422_borde(
    auth_client: TestClient, db_session: Session
) -> None:
    """Borde: DNI con letras o longitud errónea → 422 sin fila."""
    for malo in ("ABC1234", "12345", "123456789"):
        r = auth_client.post(
            "/api/pacientes",
            json=_payload_con_consentimiento(malo),
            headers=_staff_headers(),
        )
        assert r.status_code == 422, (malo, r.text)
    db_session.expire_all()
    assert db_session.query(Paciente).count() == 0


def test_sin_jwt_401_borde(auth_client: TestClient) -> None:
    """Borde: sin JWT staff → 401 (nunca expone nada)."""
    r = auth_client.post("/api/pacientes", json=_payload_con_consentimiento())
    assert r.status_code == 401, r.text
