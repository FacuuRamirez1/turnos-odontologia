"""Plantillas versionadas v1 C-09 — confirmacion, recordatorio, aviso_devolucion.

Cada render devuelve `(asunto, texto, html)`. Todo valor interpolado se escapa
con `html.escape` (HTML); el texto plano interpola sin HTML. Los links de
acción usan `API_PUBLIC_URL` y `urllib.parse.quote` del token.
"""

from collections.abc import Callable
from html import escape
from typing import Any
from urllib.parse import quote

from app.core.settings import get_settings

PLANTILLAS: dict[str, dict[str, Callable[..., tuple[str, str, str]]]] = {
    "v1": {}
}

_BASE_URL = get_settings().api_public_url.rstrip("/")


def _url(path: str, token: str) -> str:
    return f"{_BASE_URL}{path}?token={quote(token)}"


def _render_confirmacion(
    nombre: str, apellido: str, token: str, turno_inicio: str,
) -> tuple[str, str, str]:
    asunto = f"Confirmá tu turno, {escape(nombre)}"
    link_confirmar = _url("/api/mail/confirmar", token)
    link_cancelar = _url("/api/mail/cancelar", token)
    texto = (
        f"Hola {escape(nombre)} {escape(apellido)}.\n"
        f"Tu turno está confirmado para el {escape(turno_inicio)}.\n"
        f"Confirmar: {link_confirmar}\n"
        f"Cancelar: {link_cancelar}\n"
    )
    html = (
        f"<p>Hola {escape(nombre)} {escape(apellido)},</p>"
        f"<p>Tu turno está confirmado para el <strong>{escape(turno_inicio)}</strong>.</p>"
        f'<p><a href="{escape(link_confirmar, quote=True)}">Confirmar turno</a> | '
        f'<a href="{escape(link_cancelar, quote=True)}">Cancelar turno</a></p>'
    )
    return asunto, texto, html


def _render_recordatorio(
    nombre: str, apellido: str, token: str, turno_inicio: str,
) -> tuple[str, str, str]:
    asunto = f"Recordatorio: tu turno es el {escape(turno_inicio)}"
    link_confirmar = _url("/api/mail/confirmar", token)
    link_cancelar = _url("/api/mail/cancelar", token)
    texto = (
        f"Hola {escape(nombre)} {escape(apellido)}.\n"
        f"Te recordamos tu turno para el {escape(turno_inicio)}.\n"
        f"Confirmar: {link_confirmar}\n"
        f"Cancelar: {link_cancelar}\n"
    )
    html = (
        f"<p>Hola {escape(nombre)} {escape(apellido)},</p>"
        f"<p>Te recordamos tu turno para el <strong>{escape(turno_inicio)}</strong>.</p>"
        f'<p><a href="{escape(link_confirmar, quote=True)}">Confirmar turno</a> | '
        f'<a href="{escape(link_cancelar, quote=True)}">Cancelar turno</a></p>'
    )
    return asunto, texto, html


def _render_aviso_devolucion(
    nombre: str, apellido: str, porcentaje: int, turno_inicio: str,
) -> tuple[str, str, str]:
    asunto = f"Aviso de devolución — turno del {escape(turno_inicio)}"
    texto = (
        f"Hola {escape(nombre)} {escape(apellido)}.\n"
        f"Se canceló tu turno del {escape(turno_inicio)}.\n"
        f"Porcentaje de devolución de la seña: {porcentaje} %.\n"
        f"(La devolución se gestiona por la administración; este mail es solo aviso.)\n"
    )
    html = (
        f"<p>Hola {escape(nombre)} {escape(apellido)},</p>"
        f"<p>Se canceló tu turno del <strong>{escape(turno_inicio)}</strong>.</p>"
        f"<p>Porcentaje de devolución de la seña: <strong>{porcentaje} %</strong>.</p>"
        f"<p>La devolución se gestiona por la administración; este mail es solo aviso.</p>"
    )
    return asunto, texto, html


PLANTILLAS["v1"] = {
    "confirmacion": _render_confirmacion,
    "recordatorio": _render_recordatorio,
    "aviso_devolucion": _render_aviso_devolucion,
}


def render(version: str, tipo: str, **datos: Any) -> tuple[str, str, str]:
    """Renderiza `(asunto, texto, html)` para `(version, tipo)`."""
    try:
        variantes = PLANTILLAS[version]
    except KeyError as exc:
        raise ValueError(f"versión de plantilla desconocida: {version}") from exc
    try:
        fn = variantes[tipo]
    except KeyError as exc:
        raise ValueError(f"tipo de plantilla desconocido: {tipo}") from exc
    return fn(**datos)
