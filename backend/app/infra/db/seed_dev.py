"""Seed dev idempotente C-02 (KB `04 §5` acotado al scope: sin turnos/pagos).

Contenido: 2 odontólogos (montos distintos), 1 recepcionista + 1 admin con
hash bcrypt demo FIJO (60 chars, nunca plaintext; solo dev — C-03 hashea de
verdad), 5 pacientes DNI ficticios `99.999.9xx` con consentimiento (P11).
Idempotencia por natural-key vía `ON CONFLICT DO NOTHING` (PG y SQLite).
Feriado + bloqueo de ejemplo: fixture JSON en `seed_data/` (tabla `bloqueo`
= C-04 por Non-Goals). Sin escrituras v2 (P13). Secretos solo por env (P5).
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.security.passwords import hash_password
from app.infra.db.models import Odontologo, Paciente, Usuario

# Password dev documentada (SOLO dev, nunca producción): C-03 hashea de verdad
# y el spec § passwords exige que todo seed staff autentique con ella (P11: ficticia).
DEV_PASSWORD = "dev-ficticio-123"
DEMO_HASH = hash_password(DEV_PASSWORD)
assert len(DEMO_HASH) == 60

DOMINIO = "clinica-ficticia.example.ar"
CONSENT_AT = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)

ID_ODONTO_1 = uuid.UUID("11111111-1111-4111-8111-111111111111")
ID_USER_ODONTO_1 = uuid.UUID("11111111-1111-4111-8111-111111111112")
ID_ODONTO_2 = uuid.UUID("22222222-2222-4222-8222-222222222222")
ID_USER_ODONTO_2 = uuid.UUID("22222222-2222-4222-8222-222222222223")
ID_RECEP = uuid.UUID("33333333-3333-4333-8333-333333333333")
ID_ADMIN = uuid.UUID("44444444-4444-4434-8444-444444444444")

USUARIOS: list[dict[str, Any]] = [
    {
        "id": ID_USER_ODONTO_1,
        "email": f"odonto1@{DOMINIO}",
        "password_hash": DEMO_HASH,
        "rol": "odontologo",
        "odontologo_id": ID_ODONTO_1,
        "activo": True,
        "is_active": True,
    },
    {
        "id": ID_USER_ODONTO_2,
        "email": f"odonto2@{DOMINIO}",
        "password_hash": DEMO_HASH,
        "rol": "odontologo",
        "odontologo_id": ID_ODONTO_2,
        "activo": True,
        "is_active": True,
    },
    {
        "id": ID_RECEP,
        "email": f"recep@{DOMINIO}",
        "password_hash": DEMO_HASH,
        "rol": "recepcionista",
        "odontologo_id": None,
        "activo": True,
        "is_active": True,
    },
    {
        "id": ID_ADMIN,
        "email": f"admin@{DOMINIO}",
        "password_hash": DEMO_HASH,
        "rol": "admin",
        "odontologo_id": None,
        "activo": True,
        "is_active": True,
    },
]

# Montos demo distintos por profesional (default comercial se cierra en C-07/Q1).
PERFILES: list[dict[str, Any]] = [
    {
        "id": ID_ODONTO_1,
        "user_id": ID_USER_ODONTO_1,
        "monto_turno": Decimal("70000.00"),
        "monto_senia": Decimal("65000.00"),
        "activo": True,
        "is_active": True,
    },
    {
        "id": ID_ODONTO_2,
        "user_id": ID_USER_ODONTO_2,
        "monto_turno": Decimal("80000.00"),
        "monto_senia": Decimal("70000.00"),
        "activo": True,
        "is_active": True,
    },
]

PACIENTES: list[dict[str, Any]] = [
    {
        "id": uuid.UUID(f"90000000-0000-4000-8000-00000000000{i}"),
        "dni": f"99.999.90{i}",
        "nombre": nombre,
        "apellido": "Ficticio/a",
        "email": None,
        "telefono": None,
        "consentimiento_datos": True,
        "consentimiento_fecha": CONSENT_AT,
        "is_active": True,
    }
    for i, nombre in enumerate(
        ("Ana", "Bruno", "Carla", "Diego", "Elena"), start=1
    )
]


def _insert_do_nothing(
    session: Session, model: type[Usuario] | type[Odontologo] | type[Paciente],
    rows: list[dict[str, Any]],
) -> None:
    """`INSERT … ON CONFLICT DO NOTHING` portable (PG prod, SQLite tests)."""
    bind = session.get_bind()
    dialecto = bind.dialect.name if bind is not None else "postgresql"
    if dialecto == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        session.execute(pg_insert(model).values(rows).on_conflict_do_nothing())
    else:
        from sqlalchemy.dialects.sqlite import insert as lite_insert

        session.execute(lite_insert(model).values(rows).on_conflict_do_nothing())


def seed(session: Session) -> None:
    """Aplica el seed dev; re-corridas no duplican (natural keys email/DNI)."""
    _insert_do_nothing(session, Usuario, USUARIOS)
    _insert_do_nothing(session, Odontologo, PERFILES)
    _insert_do_nothing(session, Paciente, PACIENTES)
    session.commit()


def main() -> None:
    """Punto de entrada manual: `python -m app.infra.db.seed_dev` (asume 001 aplicada)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.settings import get_settings

    engine = create_engine(get_settings().database_url, future=True)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    with factory() as session:
        seed(session)
    print("seed dev C-02 aplicado (idempotente, ON CONFLICT DO NOTHING).")


if __name__ == "__main__":
    main()
