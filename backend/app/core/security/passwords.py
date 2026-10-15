"""Hashing de passwords C-03 (design D2) — bcrypt cost 12, verify constant-time.

`dummy_verify()` existe para igualar timing ante email inexistente: el login
la invoca antes del 401 genérico para no distinguir causa (spec § passwords).
"""

import bcrypt

_COST = 12

# Hash descartable solo para igualar timing (nunca representa un usuario real).
_DUMMY_HASH = bcrypt.hashpw(b"email-inexistente-dummy-ficticio", bcrypt.gensalt(rounds=_COST))


def hash_password(plain: str) -> str:
    """Hashea con bcrypt cost 12 + salt aleatorio (60 chars, formato `$2b$12$`)."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=_COST)).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    """Verifica en tiempo constante; hash malformado → False (nunca excepción)."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("ascii"))
    except ValueError:
        return False


def dummy_verify() -> bool:
    """Cuesta un verify real contra hash descartable; siempre retorna False."""
    bcrypt.checkpw(b"email-inexistente-dummy-ficticio", _DUMMY_HASH)
    return False
