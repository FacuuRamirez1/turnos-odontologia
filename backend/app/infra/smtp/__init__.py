"""Adaptador SMTP C-09 — reexporta `SmtpMailer` y `build_mailer_from_settings`."""

from app.infra.smtp.client import SmtpMailer, build_mailer_from_settings

__all__ = ["SmtpMailer", "build_mailer_from_settings"]
