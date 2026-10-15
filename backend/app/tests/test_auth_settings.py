"""Tests C-03 §1 — deps + settings JWT (RED primero, tasks 1.1–1.3).

Escenarios (U2 feliz / negocio / borde):
- feliz: defaults JWT_ACCESS_MIN=15, JWT_REFRESH_DIAS=7, JWT_ACTION_MIN=15;
- feliz: PyJWT + bcrypt importables (task 1.1);
- borde: COOKIE_SECURE derivado del esquema de FRONTEND_URL;
- negocio P5: JWT_SECRET vacío o placeholder en producción falla al arrancar.
"""

import pytest

from app.core.settings import Settings


def test_dependencias_jwt_y_bcrypt_disponibles() -> None:
    """Task 1.1 feliz: PyJWT + bcrypt resolubles (requirements.txt los declara)."""
    import bcrypt  # noqa: F401
    import jwt  # noqa: F401


def test_jwt_defaults_presentes_feliz() -> None:
    """Task 1.2 feliz: TTLs con defaults 15 min / 7 días / 15 min."""
    settings = Settings()
    assert settings.jwt_access_min == 15
    assert settings.jwt_refresh_dias == 7
    assert settings.jwt_action_min == 15


def test_cookie_secure_derivado_borde(monkeypatch: pytest.MonkeyPatch) -> None:
    """Task 1.2 borde: http local → False; https → True (design Riesgo Secure)."""
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:5173")
    assert Settings().cookie_secure is False

    monkeypatch.setenv("FRONTEND_URL", "https://turnos.clinica-ficticia.example.ar")
    assert Settings().cookie_secure is True


def test_produccion_sin_secreto_falla_negocio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Task 1.2 negocio P5: producción sin secreto válido no arranca."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "")
    with pytest.raises(ValueError):
        Settings()

    monkeypatch.setenv("JWT_SECRET", "cambiar-en-produccion")
    with pytest.raises(ValueError):
        Settings()


def test_produccion_con_secreto_real_arranca(monkeypatch: pytest.MonkeyPatch) -> None:
    """Triangulación: producción CON secreto real sí construye Settings."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "secreto-real-de-produccion-ficticio")
    assert Settings().jwt_secret == "secreto-real-de-produccion-ficticio"
