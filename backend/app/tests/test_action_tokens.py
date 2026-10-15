"""Tests C-03 §6.1+6.3 — tokens de acción por mail (RED primero, tasks 6.1/6.3).

Escenarios (U2 feliz / negocio / borde):
- feliz: emisión + validación de un uso OK;
- negocio: segundo uso rechazado por hash consumido;
- borde: access presentado como mail-token rechazado por `type` (6.1) y
  mail-token expirado rechazado con error explícito (6.3).
Triangulación: el store guarda hashes, nunca el token crudo.
"""

from datetime import timedelta

import pytest

from app.core.security.action_tokens import (
    ActionTokenStore,
    issue_action_token,
    validate_action_token,
)
from app.core.security.jwt import AuthError, ExpiredAuthError, create_access_token

SECRET = "secreto-de-test-ficticio"


def _store() -> ActionTokenStore:
    return ActionTokenStore(client=None)


def test_emision_y_validacion_un_uso_feliz() -> None:
    token = issue_action_token("turno-123", "confirmar", secret=SECRET)
    claims = validate_action_token(token, _store(), secret=SECRET)
    assert claims["type"] == "action"
    assert claims["sub"] == "turno-123"
    assert claims["proposito"] == "confirmar"


def test_segundo_uso_rechazado_negocio() -> None:
    store = _store()
    token = issue_action_token("turno-123", "cancelar", secret=SECRET)
    validate_action_token(token, store, secret=SECRET)
    with pytest.raises(AuthError):
        validate_action_token(token, store, secret=SECRET)


def test_access_no_sirve_como_mail_token_borde() -> None:
    access = create_access_token(sub="user-1", rol="admin", secret=SECRET)
    with pytest.raises(AuthError):
        validate_action_token(access, _store(), secret=SECRET)


def test_mail_token_expirado_error_explicito_63() -> None:
    vencido = issue_action_token(
        "turno-9", "confirmar", secret=SECRET, ttl_override=timedelta(seconds=-120)
    )
    with pytest.raises(ExpiredAuthError):
        validate_action_token(vencido, _store(), secret=SECRET)


def test_store_guarda_hashes_nunca_raw_triangulacion() -> None:
    store = _store()
    token = issue_action_token("turno-7", "confirmar", secret=SECRET)
    validate_action_token(token, store, secret=SECRET)
    assert token not in store.debug_keys()
    hashes = [k.removeprefix("auth:action_consumed:") for k in store.debug_keys()]
    assert any(len(h) == 64 and all(c in "0123456789abcdef" for c in h) for h in hashes)
