"""Tests C-03 §4.1 — guard `require_role` (RED primero, task 4.1).

Escenarios (U2 feliz / negocio / borde) sobre app local con ruta staff:
- feliz: rol permitido autoriza y devuelve identidad sub/rol/odontologo_id;
- negocio: rol no permitido → 403;
- borde: odontólogo sin vínculo no autoriza scope → 403.
"""

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.security import dependencies
from app.core.security.dependencies import Identity, require_role
from app.core.security.jwt import create_access_token
from app.infra.redis.blacklist import TokenBlacklist

SECRET = "secreto-de-test-ficticio"
ODONTO_ID = "11111111-1111-4111-8111-111111111111"


def _app() -> FastAPI:
    dependencies.configure_security(SECRET, TokenBlacklist(client=None))
    app = FastAPI()

    @app.get("/mi-agenda")
    def mi_agenda(ident: Identity = Depends(require_role("odontologo"))) -> dict[str, str | None]:
        return {"sub": ident.sub, "rol": ident.rol, "odontologo_id": ident.odontologo_id}

    return app


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_rol_permitido_autoriza_con_identidad_feliz() -> None:
    token = create_access_token(
        sub="user-1", rol="odontologo", odontologo_id=ODONTO_ID, secret=SECRET
    )
    response = TestClient(_app()).get("/mi-agenda", headers=_bearer(token))
    assert response.status_code == 200
    assert response.json() == {"sub": "user-1", "rol": "odontologo", "odontologo_id": ODONTO_ID}


def test_rol_no_permitido_403_negocio() -> None:
    token = create_access_token(sub="user-2", rol="recepcionista", secret=SECRET)
    response = TestClient(_app()).get("/mi-agenda", headers=_bearer(token))
    assert response.status_code == 403


def test_odontologo_sin_vinculo_no_autoriza_scope_borde() -> None:
    token = create_access_token(sub="user-3", rol="odontologo", secret=SECRET)
    response = TestClient(_app()).get("/mi-agenda", headers=_bearer(token))
    assert response.status_code == 403


def test_sin_token_401() -> None:
    response = TestClient(_app()).get("/mi-agenda")
    assert response.status_code == 401
