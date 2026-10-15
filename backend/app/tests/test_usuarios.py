"""Tests C-02 §1.1 — `Usuario`: feliz / negocio / borde (U2: RED primero).

Escenarios aprobados en tasks.md 1.1:
- feliz: crea con email/rol valido;
- negocio: email duplicado case-insensitive rechazado;
- borde: `password_hash` < 60 chars rechazado.
"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infra.db.models import Usuario

# Hashes demo de 60 chars (nunca plaintext, P5): prefijo bcrypt + relleno.
HASH_A = "$2b$04$" + "a" * 53
HASH_B = "$2b$04$" + "b" * 53
assert len(HASH_A) == 60 and len(HASH_B) == 60


def test_crea_usuario_valido_feliz(db_session: Session) -> None:
    usuario = Usuario(
        email="recepcion@clinica-ficticia.example.ar",
        password_hash=HASH_A,
        rol="recepcionista",
    )
    db_session.add(usuario)
    db_session.commit()

    assert usuario.id is not None
    assert usuario.is_active is True
    assert usuario.activo is True
    assert usuario.odontologo_id is None


def test_email_duplicado_case_insensitive_rechazado(db_session: Session) -> None:
    """Negocio: `Admin@x` + `admin@x` violan la unicidad sobre `lower(email)`."""
    db_session.add(
        Usuario(
            email="Admin@clinica-ficticia.example.ar",
            password_hash=HASH_A,
            rol="admin",
        )
    )
    db_session.commit()
    db_session.add(
        Usuario(
            email="admin@clinica-ficticia.example.ar",
            password_hash=HASH_B,
            rol="admin",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    assert db_session.query(Usuario).count() == 1


def test_password_hash_corto_rechazado_borde(db_session: Session) -> None:
    """Borde: hash de 9 chars viola el CHECK `length(password_hash) >= 60`."""
    db_session.add(
        Usuario(
            email="corto@clinica-ficticia.example.ar",
            password_hash="no-es-hash",
            rol="recepcionista",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    assert db_session.query(Usuario).count() == 0


def test_rol_fuera_de_lista_rechazado(db_session: Session) -> None:
    """Spec: rol fuera de `odontologo|recepcionista|admin` viola el CHECK."""
    db_session.add(
        Usuario(
            email="super@clinica-ficticia.example.ar",
            password_hash=HASH_A,
            rol="superadmin",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    assert db_session.query(Usuario).count() == 0
