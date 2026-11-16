"""Tests C-09/C-08 - plantillas versionadas."""

import pytest

from app.domain.notificaciones.plantillas import PLANTILLAS, render


def test_render_recordatorio_feliz_incluye_links(monkeypatch: pytest.MonkeyPatch) -> None:
    asunto, texto, html = render(
        "v1",
        "recordatorio",
        nombre="Ana",
        apellido="Pérez",
        token="tok-feliz-123",
        turno_inicio="05/11/2026 09:00",
    )
    assert "Recordatorio" in asunto
    assert "/api/mail/confirmar?token=" in texto
    assert "/api/mail/cancelar?token=" in html


def test_dato_html_escapado_borde() -> None:
    _, _, html = render(
        "v1",
        "confirmacion",
        nombre="<script>alert(1)</script>",
        apellido="Pérez & Asoc.",
        token="tok-x",
        turno_inicio="05/11/2026 09:00",
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "Pérez &amp; Asoc." in html


def test_aviso_devolucion_v1_sin_links_borde() -> None:
    asunto, texto, html = render(
        "v1",
        "aviso_devolucion",
        nombre="Ana",
        apellido="Pérez",
        porcentaje=60,
        turno_inicio="05/11/2026 09:00",
    )
    assert "60" in texto
    assert "/api/mail/confirmar" not in texto
    assert "/api/mail/cancelar" not in texto
    assert "/api/mail/confirmar" not in html


def test_aviso_devolucion_v2_ejecutada_simulado_feliz(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PAGO_MODO", "simulado")
    _, texto, html = render(
        "v2",
        "aviso_devolucion",
        nombre="Ana",
        apellido="Pérez",
        porcentaje=60,
        turno_inicio="05/11/2026 09:00",
        monto="6000.00",
        resultado="ejecutada",
    )
    assert "6000.00" in texto
    assert "(simulado)" in texto
    assert "No se movió dinero real" in texto
    assert "(simulado)" in html


def test_aviso_devolucion_v2_rechazada_sin_monto_devuelto_negocio() -> None:
    _, texto, _ = render(
        "v2",
        "aviso_devolucion",
        nombre="Ana",
        apellido="Pérez",
        porcentaje=60,
        turno_inicio="05/11/2026 09:00",
        monto="0.00",
        resultado="rechazada",
    )
    assert "rechazada" in texto.lower()
    assert "no se otorgó" in texto.lower() or "no se otorgo" in texto.lower()
    assert "ningún monto" in texto.lower() or "ningun monto" in texto.lower()


def test_aviso_devolucion_v2_rechaza_sin_monto_error() -> None:
    with pytest.raises(ValueError):
        render(
            "v2",
            "aviso_devolucion",
            nombre="Ana",
            apellido="Pérez",
            porcentaje=60,
            turno_inicio="05/11/2026 09:00",
            resultado="rechazada",
        )


def test_plantillas_registradas_v1_v2() -> None:
    assert set(PLANTILLAS["v1"].keys()) == {"confirmacion", "recordatorio", "aviso_devolucion"}
    assert set(PLANTILLAS["v2"].keys()) == {"confirmacion", "recordatorio", "aviso_devolucion"}
