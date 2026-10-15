"""Tests C-03 §7.1 — aislamiento `odontologo_id` E2E (RED primero, task 7.1).

Escenarios (U2 feliz-aislado / borde fail-closed):
- feliz-aislado: odontólogo A no recibe filas de B aunque el endpoint no
  filtre (el scope viaja por constructor vía `scoped_repository`, C-02);
- borde: identidad sin vínculo → 403 (nunca datos sin filtrar);
- pin C-02: repositorio scopeado sin `odontologo_id` levanta `ValueError`.
"""

import uuid

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import dependencies
from app.core.security.dependencies import Identity, require_role, scoped_repository
from app.core.security.jwt import create_access_token
from app.infra.db.models import Usuario
from app.infra.db.repository import BaseRepository
from app.infra.db.session import get_db
from app.infra.redis.blacklist import TokenBlacklist

SECRET = "secreto-de-test-ficticio"
HASH = "$2b$12$" + "K" * 53

A = uuid.uuid4()
B = uuid.uuid4()


def _sembrar(db: Session) -> None:
    db.add_all(
        [
            Usuario(email="a@x.example.ar", password_hash=HASH, rol="odontologo", odontologo_id=A),
            Usuario(email="b@x.example.ar", password_hash=HASH, rol="odontologo", odontologo_id=B),
        ]
    )
    db.commit()


def _app(db: Session) -> FastAPI:
    dependencies.configure_security(SECRET, TokenBlacklist(client=None))
    app = FastAPI()

    @app.get("/agenda")
    def agenda(
        ident: Identity = Depends(require_role("odontologo")),
        session: Session = Depends(get_db),
    ) -> list[str]:
        # Sin filtro explícito del endpoint: el scope lo fuerza el constructor.
        repo = scoped_repository(session, Usuario, ident)
        return sorted(u.email for u in repo.list())

    app.dependency_overrides[get_db] = lambda: db
    return app


def _token_a() -> dict[str, str]:
    token = create_access_token(sub="u-a", rol="odontologo", odontologo_id=str(A), secret=SECRET)
    return {"Authorization": f"Bearer {token}"}


def test_a_no_recibe_filas_de_b_feliz(db_session: Session) -> None:
    _sembrar(db_session)
    response = TestClient(_app(db_session)).get("/agenda", headers=_token_a())
    assert response.status_code == 200
    assert response.json() == ["a@x.example.ar"]


def test_sin_vinculo_403_nunca_sin_filtrar_borde(db_session: Session) -> None:
    _sembrar(db_session)
    suelto = create_access_token(sub="u-x", rol="odontologo", secret=SECRET)
    response = TestClient(_app(db_session)).get(
        "/agenda", headers={"Authorization": f"Bearer {suelto}"}
    )
    assert response.status_code == 403


def test_repo_scopeado_sin_scope_ValueError_pin(db_session: Session) -> None:
    """Pin C-02 fail-closed: sin `odontologo_id` en constructor → ValueError."""
    with pytest.raises(ValueError):
        BaseRepository(db_session, Usuario)
