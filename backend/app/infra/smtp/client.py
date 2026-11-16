"""Adaptador SMTP stdlib C-09/C-08 - sin dependencias nuevas.

Configurado solo por SMTP_HOST/PORT/USER/PASS y MAIL_FROM. `From` siempre
alineado a `MAIL_FROM` (P14). Soporta adjuntos PDF opcionales.
"""

import smtplib
from email.message import EmailMessage


class SmtpMailer:
    """Envia un correo por SMTP. Login solo si SMTP_USER no esta vacio."""

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        mail_from: str,
        timeout: int = 10,
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.mail_from = mail_from
        self.timeout = timeout

    def enviar(
        self,
        destinatario: str,
        asunto: str,
        texto: str,
        html: str,
        adjuntos: list[tuple[str, bytes, str]] | None = None,
    ) -> None:
        """Envia texto + HTML con adjuntos opcionales."""
        msg = EmailMessage()
        msg["From"] = self.mail_from
        msg["To"] = destinatario
        msg["Subject"] = asunto
        msg.set_content(texto)
        msg.add_alternative(html, subtype="html")
        for nombre, datos, mimetype in adjuntos or []:
            maintype, _, subtype = mimetype.partition("/")
            msg.add_attachment(
                datos,
                maintype=maintype or "application",
                subtype=subtype or "octet-stream",
                filename=nombre,
            )
        with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as smtp:
            if self.user:
                smtp.login(self.user, self.password)
            smtp.send_message(msg)


def build_mailer_from_settings() -> SmtpMailer:
    """Fabrica desde `get_settings()` (api/worker)."""
    from app.core.settings import get_settings

    settings = get_settings()
    return SmtpMailer(
        host=settings.smtp_host,
        port=settings.smtp_port,
        user=settings.smtp_user,
        password=settings.smtp_pass,
        mail_from=settings.mail_from,
    )
