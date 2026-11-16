"""Plantillas versionadas - confirmacion, recordatorio, aviso_devolucion.

`aviso_devolucion` v2 (C-08): monto, resultado, "(simulado)" y
"no se movio dinero real" en modo simulado. v1 se mantiene para filas viejas.
"""

from collections.abc import Callable
from html import escape
from typing import Any
from urllib.parse import quote

from app.core.settings import get_settings

PLANTILLAS: dict[str, dict[str, Callable[..., tuple[str, str, str]]]] = {"v1": {}, "v2": {}}

_BASE_URL = get_settings().api_public_url.rstrip("/")


def _url(path: str, token: str) -> str:
    return f"{_BASE_URL}{path}?token={quote(token)}"


def _marca_simulado() -> str:
    return " (simulado)" if get_settings().pago_modo == "simulado" else ""


def _render_confirmacion(
    nombre: str, apellido: str, token: str, turno_inicio: str,
) -> tuple[str, str, str]:
    marca = _marca_simulado()
    asunto = f"Confirmá tu turno, {escape(nombre)}"
    link_confirmar = _url("/api/mail/confirmar", token)
    link_cancelar = _url("/api/mail/cancelar", token)
    texto = (
        f"Hola {escape(nombre)} {escape(apellido)}.\n"
        f"Tu turno está confirmado para el {escape(turno_inicio)}{marca}.\n"
        f"Confirmar: {link_confirmar}\n"
        f"Cancelar: {link_cancelar}\n"
    )
    html = (
        f"<p>Hola {escape(nombre)} {escape(apellido)},</p>"
        f"<p>Tu turno está confirmado para el "
        f"<strong>{escape(turno_inicio)}</strong>{escape(marca)}.</p>"
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


def _render_aviso_devolucion_v1(
    nombre: str, apellido: str, porcentaje: int, turno_inicio: str,
) -> tuple[str, str, str]:
    marca = _marca_simulado()
    asunto = f"Aviso de devolución - turno del {escape(turno_inicio)}"
    texto = (
        f"Hola {escape(nombre)} {escape(apellido)}.\n"
        f"Se canceló tu turno del {escape(turno_inicio)}.\n"
        f"Porcentaje de devolución de la seña{marca}: {porcentaje} %.\n"
        f"(La devolución se gestiona por la administración; este mail es solo aviso.)\n"
    )
    html = (
        f"<p>Hola {escape(nombre)} {escape(apellido)},</p>"
        f"<p>Se canceló tu turno del <strong>{escape(turno_inicio)}</strong>.</p>"
        f"<p>Porcentaje de devolución de la seña{escape(marca)}: "
        f"<strong>{porcentaje} %</strong>.</p>"
        f"<p>La devolución se gestiona por la administración; este mail es solo aviso.</p>"
    )
    return asunto, texto, html


def _render_aviso_devolucion_v2(
    nombre: str,
    apellido: str,
    porcentaje: int,
    turno_inicio: str,
    monto: Any = None,
    resultado: str = "",
) -> tuple[str, str, str]:
    if monto is None or str(monto).strip() == "":
        raise ValueError("aviso_devolucion v2 requiere monto devuelto")
    monto_txt = str(monto)
    resultado_txt = str(resultado)
    marca = _marca_simulado()
    simulado_linea = "No se movió dinero real." if marca else ""
    asunto = f"Aviso de devolución{marca} - turno del {escape(turno_inicio)}"
    if resultado_txt == "ejecutada":
        cuerpo_txt = f"Monto devuelto{marca}: {monto_txt}."
        cuerpo_html = f"<p>Monto devuelto{escape(marca)}: <strong>{escape(monto_txt)}</strong>.</p>"
    else:
        cuerpo_txt = "No se otorgó la devolución y no se devolvió ningún monto."
        cuerpo_html = "<p>No se otorgó la devolución y no se devolvió ningún monto.</p>"
    texto = (
        f"Hola {escape(nombre)} {escape(apellido)}.\n"
        f"Resultado de la devolución: {resultado_txt}.\n"
        f"Porcentaje: {porcentaje} %.\n"
        f"{cuerpo_txt}\n"
        f"{simulado_linea}\n"
    )
    html = (
        f"<p>Hola {escape(nombre)} {escape(apellido)},</p>"
        f"<p>Resultado de la devolución: <strong>{escape(resultado_txt)}</strong>.</p>"
        f"<p>Porcentaje: <strong>{porcentaje} %</strong>.</p>"
        f"{cuerpo_html}"
        + (f"<p>{escape(simulado_linea)}</p>" if simulado_linea else "")
    )
    return asunto, texto, html


PLANTILLAS["v1"] = {
    "confirmacion": _render_confirmacion,
    "recordatorio": _render_recordatorio,
    "aviso_devolucion": _render_aviso_devolucion_v1,
}
PLANTILLAS["v2"] = {
    "confirmacion": _render_confirmacion,
    "recordatorio": _render_recordatorio,
    "aviso_devolucion": _render_aviso_devolucion_v2,
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
