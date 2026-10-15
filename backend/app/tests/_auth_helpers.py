"""Ayudas para tests de endpoints auth C-03 (alta de usuarios con hash real).

El fixture `auth_client` vive en `conftest.py` (auto-registro pytest).
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.security.passwords import hash_password
from app.infra.db.models import Usuario

TEST_SECRET = "secreto-de-test-ficticio"
TEST_PASSWORD = "Clave-Ficticia-123"


def crear_usuario(
    db_session: Session,
    *,
    email: str = "recep@clinica-ficticia.example.ar",
    rol: str = "recepcionista",
    password: str = TEST_PASSWORD,
    odontologo_id: UUID | None = None,
    activo: bool = True,
) -> Usuario:
    """Usuario persistido con hash bcrypt real (cost 12)."""
    usuario = Usuario(
        email=email,
        password_hash=hash_password(password),
        rol=rol,
        odontologo_id=odontologo_id,
        activo=activo,
    )
    db_session.add(usuario)
    db_session.commit()
    db_session.refresh(usuario)
    return usuario
