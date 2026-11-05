"""Tests C-09 task 3.1 — plantillas versionadas v1 (RED primero, task 3.1).

Escenarios (U2 feliz / negocio / borde):
- feliz: render incluye texto y HTML y ambos links de acción;
- negocio: dato del paciente con `<script>`/`&` queda escapado en HTML;
- borde: aviso_devolucion usa la plantilla de aviso, porcentaje, sin confirm/cancel.
"""

from app.domain.notificaciones.plantillas import PLANTILLAS, render


def test_render_feliz_incluye_ambos_formatos_y_links_feliz() -> None:
    """Feliz: recordatorio renderiza texto+HTML con links confirmar/cancelar."""
    token = "tok-feliz-123"
    asunto, texto, html = render("v1", "recordatorio", nombre="Ana",
                                 apellido="Pérez", token=token,
                                 turno_inicio="05/11/2026 09:00")
    assert "Recordatorio" in asunto
    assert "05/11/2026 09:00" in texto
    assert "/api/mail/confirmar?token=" in texto
    assert "/api/mail/cancelar?token=" in texto
    assert "/api/mail/confirmar?token=" in html
    assert "/api/mail/cancelar?token=" in html
    assert "<strong>" in html  # parte HTML presente


def test_dato_html_escapado_negocio() -> None:
    """Negocio: `<script>` y `&` se escapan en HTML, sin markup ejecutable."""
    _, _, html = render("v1", "confirmacion", nombre="<script>alert(1)</script>",
                        apellido="Pérez & Asoc.", token="tok-x",
                        turno_inicio="05/11/2026 09:00")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "Pérez &amp; Asoc." in html


def test_aviso_devolucion_sin_links_borde() -> None:
    """Borde: aviso_devolucion muestra porcentaje y no ofrece confirm/cancel."""
    asunto, texto, html = render("v1", "aviso_devolucion", nombre="Ana",
                                 apellido="Pérez", porcentaje=60,
                                 turno_inicio="05/11/2026 09:00")
    assert "60 %" in texto or "60" in texto
    assert "/api/mail/confirmar" not in texto
    assert "/api/mail/cancelar" not in texto
    assert "/api/mail/confirmar" not in html
    assert "/api/mail/cancelar" not in html


def test_plantillas_registradas_feliz() -> None:
    """Feliz: el registro v1 tiene los tres tipos."""
    assert set(PLANTILLAS["v1"].keys()) == {
        "confirmacion", "recordatorio", "aviso_devolucion"}


def test_version_desconocida_rechazada_borde() -> None:
    """Borde: versión inexistente lanza ValueError."""
    try:
        render("v2", "confirmacion", nombre="Ana", apellido="Pérez",
               token="tok", turno_inicio="05/11/2026 09:00")
    except ValueError:
        pass
    else:
        raise AssertionError("esperaba ValueError por versión desconocida")
