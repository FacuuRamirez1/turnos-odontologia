"""Tests C-03 §2.3 — JWT core (RED primero, task 2.3).

Escenarios (U2 feliz / negocio / borde):
- feliz: access válido decodifica claims sub/rol/jti/type;
- negocio: token manipulado es rechazado (firma inválida);
- borde: exp en frontera — 20 s vencido acepta (leeway 30 s), 120 s vencido rechaza.
Triangulación: refresh usa type distinto; cross-type reuse rechazado.
"""

from datetime import timedelta

import pytest

from app.core.security.jwt import (
    AuthError,
    create_access_token,
    create_refresh_token,
    decode_and_validate,
)

SECRET = "secreto-de-test-ficticio"
SUB = "11111111-1111-4111-8111-111111111112"


def test_access_valido_decodifica_claims_feliz() -> None:
    token = create_access_token(
        sub=SUB, rol="odontologo", odontologo_id="11111111-1111-4111-8111-111111111111",
        secret=SECRET,
    )
    claims = decode_and_validate(token, expected_type="access", secret=SECRET)
    assert claims["sub"] == SUB
    assert claims["rol"] == "odontologo"
    assert claims["type"] == "access"
    assert claims["odontologo_id"] == "11111111-1111-4111-8111-111111111111"
    assert "jti" in claims and "exp" in claims


def test_token_manipulado_rechazado_negocio() -> None:
    token = create_access_token(sub=SUB, rol="admin", secret=SECRET)
    manipulado = token[:-2] + ("AA" if not token.endswith("AA") else "BB")
    with pytest.raises(AuthError):
        decode_and_validate(manipulado, expected_type="access", secret=SECRET)


def test_exp_frontera_leeway_borde() -> None:
    """Borde: vencido hace 20 s acepta (leeway 30 s); vencido hace 120 s rechaza."""
    casi = create_access_token(
        sub=SUB, rol="admin", secret=SECRET, ttl_override=timedelta(seconds=-20)
    )
    assert decode_and_validate(casi, expected_type="access", secret=SECRET)["sub"] == SUB

    vencido = create_access_token(
        sub=SUB, rol="admin", secret=SECRET, ttl_override=timedelta(seconds=-120)
    )
    with pytest.raises(AuthError):
        decode_and_validate(vencido, expected_type="access", secret=SECRET)


def test_cross_type_rechazado_triangulacion() -> None:
    """Triangulación: refresh no pasa como access (choke point type, design D3)."""
    refresh = create_refresh_token(sub=SUB, rol="recepcionista", secret=SECRET)
    with pytest.raises(AuthError):
        decode_and_validate(refresh, expected_type="access", secret=SECRET)
    claims = decode_and_validate(refresh, expected_type="refresh", secret=SECRET)
    assert claims["type"] == "refresh"
    assert "jti" in claims


def test_secreto_distinto_rechaza() -> None:
    token = create_access_token(sub=SUB, rol="admin", secret=SECRET)
    with pytest.raises(AuthError):
        decode_and_validate(token, expected_type="access", secret="otro-secreto")
