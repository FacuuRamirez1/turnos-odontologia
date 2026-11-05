"""Tests C-09 task 3.2 — adaptador SMTP stdlib (RED primero, task 3.2).

Escenarios (U2 feliz / negocio / borde):
- feliz: envío contra MailHog sin auth → mensaje aceptado;
- negocio: SMTP caído propaga error reintentable;
- borde: From siempre alineado a MAIL_FROM.
No se agregan dependencias de terceros (smtplib + EmailMessage solo).
"""

import smtplib
from email.message import EmailMessage
from typing import Any, Literal

import pytest

from app.infra.smtp.client import SmtpMailer


class _FakeSMTP:
    """Doble de smtplib.SMTP: captura el mensaje enviado, puede fallar."""

    def __init__(
        self, host: str, port: int, timeout: int | None = None, fail: bool = False,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.fail = fail
        self.logueado: Any = False
        self.enviado: EmailMessage | None = None

    def __enter__(self) -> "_FakeSMTP":
        return self

    def __exit__(self, *exc: Any) -> Literal[False]:
        return False

    def login(self, user: str, password: str) -> None:
        if self.fail:
            raise ConnectionError("SMTP caído")
        self.logueado = (user, password)

    def send_message(self, msg: EmailMessage) -> None:
        if self.fail:
            raise smtplib.SMTPException("servidor no disponible")
        self.enviado = msg


def _mailer(fail: bool = False) -> SmtpMailer:
    return SmtpMailer(host="mailhog", port=1025, user="", password="",
                      mail_from="turnos@clinica-ficticia.example.ar")


def test_envio_mailhog_sin_auth_feliz(monkeypatch: pytest.MonkeyPatch) -> None:
    """Feliz: MailHog sin credenciales, mensaje aceptado."""
    fake: Any = _FakeSMTP(host="mailhog", port=1025, fail=False)
    monkeypatch.setattr("smtplib.SMTP", lambda *a, **k: fake)
    m = _mailer()
    m.enviar("paciente@ficticia.example.ar", "Asunto", "texto", "<b>html</b>")
    assert fake.logueado is False  # sin auth
    assert fake.enviado is not None
    assert str(fake.enviado["From"]) == "turnos@clinica-ficticia.example.ar"
    assert str(fake.enviado["To"]) == "paciente@ficticia.example.ar"


def test_smtp_caido_propaga_error_negocio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Negocio: SMTP inalcanzable lanza SMTPException (reintentable)."""
    fake: Any = _FakeSMTP(host="mailhog", port=1025, fail=True)
    monkeypatch.setattr("smtplib.SMTP", lambda *a, **k: fake)
    m = _mailer()
    with pytest.raises(smtplib.SMTPException):
        m.enviar("paciente@ficticia.example.ar", "A", "t", "<b>h</b>")


def test_from_siempre_alineado_borde(monkeypatch: pytest.MonkeyPatch) -> None:
    """Borde: From = MAIL_FROM en todo mensaje, independiente del destinatario."""
    fake: Any = _FakeSMTP(host="mailhog", port=1025, fail=False)
    monkeypatch.setattr("smtplib.SMTP", lambda *a, **k: fake)
    m = SmtpMailer(host="mailhog", port=1025, user="u", password="p",
                   mail_from="turnos@clinica-ficticia.example.ar")
    m.enviar("otra@ficticia.example.ar", "A", "t", "<b>h</b>")
    assert fake.enviado is not None
    assert str(fake.enviado["From"]) == "turnos@clinica-ficticia.example.ar"


def test_login_solo_con_usuario(monkeypatch: pytest.MonkeyPatch) -> None:
    """Feliz/borde: login solo cuando SMTP_USER no está vacío."""
    fake: Any = _FakeSMTP(host="mailhog", port=1025, fail=False)
    monkeypatch.setattr("smtplib.SMTP", lambda *a, **k: fake)
    m = _mailer()  # user="" → sin login
    m.enviar("a@b.c", "A", "t", "<b>h</b>")
    assert fake.logueado is False
