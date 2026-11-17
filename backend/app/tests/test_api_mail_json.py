"""Tests C-10 task 1.3 — JSON en `/api/mail/*` vía `Accept` (RED primero).

Escenarios (U2 feliz / negocio / borde):
- feliz: token válido + `Accept: application/json` → JSON estructurado
  (confirmar y cancelar), con la DB reflejando la acción;
- negocio: token usado/expirado → 400 JSON; turno incompatible → 409 JSON;
- borde: petición HTML estándar sigue devolviendo `text/html` (C-09 intacto).
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.mail import reset_mail_limiter
from app.core.security import dependencies
from app.core.security.action_tokens import issue_action_token
from app.core.settings import get_settings
from app.domain.notificaciones.tokens import token_hash_raw
from app.infra.db.models import (
    Odontologo,
    Paciente,
    RecordatorioMail,
    Turno,
    Usuario,
)
from app.infra.redis.blacklist import TokenBlacklist

SECRET = "secreto-de-test-ficticio"
JSON = {"Accept": "application/json"}


def _sembrar(db_session: Session, estado: str = "confirmado") -> Turno:
    h = "$2b$04$" + "r" * 53
    fecha = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
    u = Usuario(email=f"od-mail-json-{uuid.uuid4().hex[:8]}@clinica-ficticia.example.ar",
                password_hash=h, rol="odontologo")
    db_session.add(u)
    db_session.commit()
    od = Odontologo(user_id=u.id, monto_turno=70000, monto_senia=65000)
    db_session.add(od)
    db_session.commit()
    pac = Paciente(dni=f"97{uuid.uuid4().int % 90000000 + 10000000:08d}",
                   nombre="Ana", apellido="Ficticia",
                   consentimiento_datos=True, consentimiento_fecha=fecha)
    db_session.add(pac)
    db_session.commit()
    turno = Turno(paciente_id=pac.id, odontologo_id=od.id,
                  inicio=datetime.now(UTC) + timedelta(days=30),
                  fin=datetime.now(UTC) + timedelta(days=30, minutes=30),
                  estado=estado, canal="web",
                  idempotency_key=f"key-mail-json-{uuid.uuid4().hex[:12]}")
    db_session.add(turno)
    db_session.commit()
    return turno


def _fila_con_token(db_session: Session, turno: Turno) -> tuple[RecordatorioMail, str]:
    fila = RecordatorioMail(turno_id=turno.id, tipo="confirmacion",
                            destinatario="ana@ficticia.example.ar",
                            estado="encolado")
    db_session.add(fila)
    db_session.commit()
    token = issue_action_token(str(fila.id), "mail_accion", secret=SECRET,
                               action_min=get_settings().mail_action_ttl_min)
    fila.token_accion_hash = token_hash_raw(token)
    fila.token_expira_at = datetime.now(UTC) + timedelta(hours=1)
    db_session.add(fila)
    db_session.commit()
    return fila, token


def _client(db_session: Session) -> TestClient:
    app = __import__("app.main", fromlist=["app"]).app
    dependencies.configure_security(SECRET, TokenBlacklist(client=None))
    app.dependency_overrides[__import__("app.infra.db.session", fromlist=["get_db"]).get_db] = (
        lambda: db_session)
    reset_mail_limiter()
    return TestClient(app, base_url="https://testserver")


def test_confirmar_json_feliz(db_session: Session) -> None:
    """Feliz: confirmar acepta JSON y refleja `confirmado_desde_mail`."""
    turno = _sembrar(db_session, "confirmado")
    fila, token = _fila_con_token(db_session, turno)

    resp = _client(db_session).get(f"/api/mail/confirmar?token={token}", headers=JSON)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("application/json")
    cuerpo = resp.json()
    assert cuerpo["ok"] is True
    assert cuerpo["accion"] == "confirmar"
    assert cuerpo["estado"] == "confirmado_desde_mail"
    assert cuerpo["turno_id"] == str(turno.id)

    db_session.refresh(fila)
    assert fila.estado == "confirmado_desde_mail"


def test_cancelar_json_feliz(db_session: Session) -> None:
    """Feliz: cancelar acepta JSON y devuelve estado + cotización."""
    turno = _sembrar(db_session, "confirmado")
    fila, token = _fila_con_token(db_session, turno)

    resp = _client(db_session).get(f"/api/mail/cancelar?token={token}", headers=JSON)
    assert resp.status_code == 200, resp.text
    cuerpo = resp.json()
    assert cuerpo["ok"] is True
    assert cuerpo["accion"] == "cancelar"
    assert cuerpo["estado"] == "cancelado"
    assert cuerpo["porcentaje"] == 100
    assert cuerpo["devolucion"] is None

    db_session.refresh(turno)
    assert str(turno.estado) == "cancelado"


def test_token_usado_json_400_negocio(db_session: Session) -> None:
    """Negocio: token ya consumido sin acción reflejada → 400 JSON."""
    turno = _sembrar(db_session, "confirmado")
    fila, token = _fila_con_token(db_session, turno)
    fila.token_usado_at = datetime.now(UTC)
    db_session.add(fila)
    db_session.commit()

    resp = _client(db_session).get(f"/api/mail/confirmar?token={token}", headers=JSON)
    assert resp.status_code == 400, resp.text
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json()["ok"] is False
    assert resp.json()["code"] == "TOKEN_INVALIDO"


def test_turno_incompatible_json_409_negocio(db_session: Session) -> None:
    """Negocio: turno `creado` → 409 JSON (no confirma)."""
    turno = _sembrar(db_session, "creado")
    fila, token = _fila_con_token(db_session, turno)

    resp = _client(db_session).get(f"/api/mail/confirmar?token={token}", headers=JSON)
    assert resp.status_code == 409, resp.text
    assert resp.json()["ok"] is False
    assert resp.json()["code"] == "ESTADO_INCOMPATIBLE"

    db_session.refresh(fila)
    assert fila.estado == "encolado"


def test_peticion_html_estandar_sigue_funcionando_borde(db_session: Session) -> None:
    """Borde: sin `Accept: application/json` → HTML como en C-09."""
    turno = _sembrar(db_session, "confirmado")
    _fila, token = _fila_con_token(db_session, turno)

    resp = _client(db_session).get(
        f"/api/mail/confirmar?token={token}", headers={"Accept": "text/html"})
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/html")
    assert "Turno confirmado" in resp.text
