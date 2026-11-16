"""Tests C-09/C-08 - adaptador SMTP stdlib (TDD 6.1)."""

import smtplib
from email.message import EmailMessage
from typing import Any, Literal

import pytest

from app.infra.smtp.client import SmtpMailer


class _FakeSMTP:
    def __init__(
        self, host: str, port: int, timeout: int | None = None, fail: bool = False
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
            raise ConnectionError("SMTP caido")
        self.logueado = (user, password)

    def send_message(self, msg: EmailMessage) -> None:
        if self.fail:
            raise smtplib.SMTPException("servidor no disponible")
        self.enviado = msg


def _mailer(mail_from: str = "turnos@clinica-ficticia.example.ar") -> SmtpMailer:
    return SmtpMailer(host="mailhog", port=1025, user="", password="", mail_from=mail_from)


def test_adjunto_pdf_viaja_como_application_pdf_feliz(monkeypatch: pytest.MonkeyPatch) -> None:
    fake: Any = _FakeSMTP(host="mailhog", port=1025)
    monkeypatch.setattr("smtplib.SMTP", lambda *a, **k: fake)
    pdf = b"%PDF-1.4 recibo"
    _mailer().enviar(
        "paciente@ficticia.example.ar",
        "Aviso",
        "texto",
        "<b>html</b>",
        adjuntos=[("recibo-RI-000001.pdf", pdf, "application/pdf")],
    )
    assert fake.enviado is not None
    adjuntos = list(fake.enviado.iter_attachments())
    assert len(adjuntos) == 1
    assert adjuntos[0].get_content_type() == "application/pdf"
    assert adjuntos[0].get_filename() == "recibo-RI-000001.pdf"
    assert adjuntos[0].get_payload(decode=True) == pdf
    assert str(fake.enviado["From"]) == "turnos@clinica-ficticia.example.ar"


def test_sin_adjuntos_mensaje_no_cambia_borde(monkeypatch: pytest.MonkeyPatch) -> None:
    fake: Any = _FakeSMTP(host="mailhog", port=1025)
    monkeypatch.setattr("smtplib.SMTP", lambda *a, **k: fake)
    _mailer().enviar("otra@ficticia.example.ar", "A", "texto-plano", "<b>html</b>")
    assert fake.enviado is not None
    assert list(fake.enviado.iter_attachments()) == []
    assert fake.enviado.get_body(preferencelist=("plain")) is not None
    assert fake.enviado.get_body(preferencelist=("html")) is not None


def test_from_siempre_alineado_a_mail_from_borde(monkeypatch: pytest.MonkeyPatch) -> None:
    fake: Any = _FakeSMTP(host="mailhog", port=1025)
    monkeypatch.setattr("smtplib.SMTP", lambda *a, **k: fake)
    mail_from = "turnos@clinica-ficticia.example.ar"
    _mailer(mail_from).enviar("otra@ficticia.example.ar", "A", "t", "<b>h</b>")
    assert fake.enviado is not None
    assert str(fake.enviado["From"]) == mail_from
