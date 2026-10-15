"""Tests C-02 §2.1 — aislamiento `odontologo_id` + atomicidad UoW (RED primero).

Escenarios aprobados en tasks.md 2.1 / spec § repository-level isolation:
- feliz: query con `odontologo_id=A` devuelve solo filas de A;
- negocio: query sin filtro explícito del caller sigue filtrada;
- borde: `Paciente` (sin scope profesional) lista sin filtro de odontólogo.

Y § atomic units of work:
- rollback: escritura parcial con fallo revierte todo.
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.infra.db.models import Paciente, Usuario
from app.infra.db.repository import BaseRepository, UnitOfWork

HASH = "$2b$04$" + "d" * 53
assert len(HASH) == 60

ODONTO_A = uuid.uuid4()
ODONTO_B = uuid.uuid4()


def _sembrar_usuarios(db_session: Session) -> None:
    db_session.add_all(
        [
            Usuario(
                email="a1@clinica-ficticia.example.ar",
                password_hash=HASH,
                rol="odontologo",
                odontologo_id=ODONTO_A,
            ),
            Usuario(
                email="a2@clinica-ficticia.example.ar",
                password_hash=HASH,
                rol="odontologo",
                odontologo_id=ODONTO_A,
            ),
            Usuario(
                email="b1@clinica-ficticia.example.ar",
                password_hash=HASH,
                rol="odontologo",
                odontologo_id=ODONTO_B,
            ),
        ]
    )
    db_session.commit()


def test_scope_a_devuelve_solo_filas_de_a_feliz(db_session: Session) -> None:
    _sembrar_usuarios(db_session)
    repo = BaseRepository(db_session, Usuario, odontologo_id=ODONTO_A)

    filas = repo.list()

    assert {u.email for u in filas} == {
        "a1@clinica-ficticia.example.ar",
        "a2@clinica-ficticia.example.ar",
    }


def test_sin_filtro_explicito_sigue_filtrada_negocio(db_session: Session) -> None:
    """Negocio P8: el caller no pasa filtro; el repositorio igual aísla por constructor."""
    _sembrar_usuarios(db_session)
    repo = BaseRepository(db_session, Usuario, odontologo_id=ODONTO_B)

    filas = repo.list()  # sin ningún argumento de filtrado

    assert [u.email for u in filas] == ["b1@clinica-ficticia.example.ar"]


def test_paciente_sin_scope_lista_sin_filtro_borde(db_session: Session) -> None:
    """Borde: `Paciente` no tiene `odontologo_id` → lista global, sin exigir scope."""

    db_session.add_all(
        [
            Paciente(
                dni="99.999.911",
                nombre="Ana",
                apellido="Ficticia",
                consentimiento_datos=True,
                consentimiento_fecha=datetime(2026, 10, 1, 9, tzinfo=UTC),
            ),
            Paciente(
                dni="99.999.912",
                nombre="Bruno",
                apellido="Ficticio",
                consentimiento_datos=True,
                consentimiento_fecha=datetime(2026, 10, 1, 9, tzinfo=UTC),
            ),
        ]
    )
    db_session.commit()

    repo = BaseRepository(db_session, Paciente)
    assert len(repo.list()) == 2


def test_scope_faltante_en_entidad_scopeada_falla() -> None:
    """Fail-closed P8: entidad con `odontologo_id` sin scope en constructor → error."""
    with pytest.raises(ValueError):
        BaseRepository(session=None, model=Usuario)  # type: ignore[arg-type]


def test_lectura_estandar_oculta_inactivos(db_session: Session) -> None:
    """Spec soft-delete: `list()` excluye inactivos salvo `include_inactive=True`."""
    _sembrar_usuarios(db_session)
    repo = BaseRepository(db_session, Usuario, odontologo_id=ODONTO_A)
    a1 = next(u for u in repo.list(include_inactive=True) if u.email.startswith("a1@"))
    a1.soft_delete()
    db_session.commit()

    assert {u.email for u in repo.list()} == {"a2@clinica-ficticia.example.ar"}
    assert len(repo.list(include_inactive=True)) == 2
    assert repo.get(a1.id) is None
    assert repo.get(a1.id, include_inactive=True) is not None


def test_uow_rollback_revierte_escritura_parcial(db_engine: Engine) -> None:
    """UoW: dos escrituras, falla la segunda → ninguna visible después."""
    factory = sessionmaker(bind=db_engine, class_=Session, expire_on_commit=False)
    with pytest.raises(RuntimeError, match="falla la segunda"):
        with UnitOfWork(factory) as uow:
            repo = BaseRepository(uow.session, Usuario, odontologo_id=ODONTO_A)
            repo.add(
                Usuario(
                    email="ok@clinica-ficticia.example.ar",
                    password_hash=HASH,
                    rol="odontologo",
                    odontologo_id=ODONTO_A,
                )
            )
            repo.add(
                Usuario(
                    email="ok@clinica-ficticia.example.ar",  # duplicado → revierte todo
                    password_hash=HASH,
                    rol="odontologo",
                    odontologo_id=ODONTO_A,
                )
            )
            raise RuntimeError("falla la segunda")

    verificadora = factory()
    try:
        assert verificadora.query(Usuario).count() == 0
    finally:
        verificadora.close()


def test_uow_commit_atomico_feliz(db_engine: Engine) -> None:
    """Feliz UoW: salida limpia del contexto commitea ambas escrituras juntas."""
    factory = sessionmaker(bind=db_engine, class_=Session, expire_on_commit=False)
    with UnitOfWork(factory) as uow:
        repo = BaseRepository(uow.session, Usuario, odontologo_id=ODONTO_A)
        repo.add(
            Usuario(
                email="uow1@clinica-ficticia.example.ar",
                password_hash=HASH,
                rol="odontologo",
                odontologo_id=ODONTO_A,
            )
        )
        repo.add(
            Usuario(
                email="uow2@clinica-ficticia.example.ar",
                password_hash=HASH,
                rol="odontologo",
                odontologo_id=ODONTO_A,
            )
        )

    verificadora = factory()
    try:
        assert verificadora.query(Usuario).count() == 2
    finally:
        verificadora.close()
