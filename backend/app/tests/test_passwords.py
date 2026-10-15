"""Tests C-03 §2.1 — hashing bcrypt (RED primero, task 2.1).

Escenarios (U2 feliz / negocio / borde):
- feliz: hash verifica con la password original;
- negocio: wrong-password falla (retorna False, no excepción distinguishable);
- borde: dummy-verify para email inexistente no hace early-return (no excepción).
Triangulación: dos passwords distintas producen hashes distintos y cruzados fallan.
"""

from app.core.security.passwords import dummy_verify, hash_password, verify_password


def test_hash_verifica_feliz() -> None:
    assert verify_password("Secreta-Ficticia-123", hash_password("Secreta-Ficticia-123")) is True


def test_wrong_password_falla_negocio() -> None:
    assert verify_password("otra-clave", hash_password("Secreta-Ficticia-123")) is False


def test_dummy_verify_sin_early_return_borde() -> None:
    """Borde: email inexistente igual cuesta un verify (timing) y retorna False."""
    assert dummy_verify() is False


def test_hashes_distintos_triangulacion() -> None:
    """Triangulación: sales aleatorias — misma password da hashes distintos, ambos válidos."""
    hash_a = hash_password("misma-clave")
    hash_b = hash_password("misma-clave")
    assert hash_a != hash_b
    assert verify_password("misma-clave", hash_a) is True
    assert verify_password("misma-clave", hash_b) is True
    assert verify_password("clave-cruzada", hash_a) is False


def test_hash_formato_bcrypt_cost12() -> None:
    """Estructura: prefijo bcrypt $2b$12$ (cost 12, design D2) y largo 60."""
    hashed = hash_password("x")
    assert hashed.startswith("$2b$12$")
    assert len(hashed) == 60
