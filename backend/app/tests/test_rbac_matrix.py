"""Tests C-03 §4.3 — matriz RBAC `03 §2` exigible en backend (RED primero, task 4.3).

Recepcionista, 6 permisos sí (feliz ×6) y 4 prohibiciones no (negocio ×4);
borde: header de UI (`X-Role: admin`) no otorga nada — el backend decide.
Las rutas son representativas de cada capacidad (endpoints reales en C-04+).
"""

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.security import dependencies
from app.core.security.dependencies import require_role
from app.core.security.jwt import create_access_token
from app.infra.redis.blacklist import TokenBlacklist

SECRET = "secreto-de-test-ficticio"

# Las 6 capacidades permitidas a recepcionista (03 §2.1–2.6) + roles que las sirven.
PERMITIDAS = [
    ("GET", "/agendas", ("odontologo", "recepcionista", "admin")),
    ("POST", "/disponibilidad", ("odontologo", "recepcionista", "admin")),
    ("POST", "/turnos/reprogramar", ("odontologo", "recepcionista", "admin")),
    ("POST", "/devoluciones/operar", ("recepcionista", "admin")),
    ("GET", "/reportes", ("odontologo", "recepcionista", "admin")),
    ("GET", "/pacientes", ("odontologo", "recepcionista", "admin")),
]

# Las 4 prohibiciones de recepcionista (03 §2 prohibido explícito).
PROHIBIDAS = [
    ("POST", "/admin/usuarios", ("admin",)),
    ("POST", "/pagos/config", ("admin",)),
    ("DELETE", "/audit", ("admin",)),
    ("GET", "/arca/comprobantes", ("admin",)),
]


def _app() -> FastAPI:
    dependencies.configure_security(SECRET, TokenBlacklist(client=None))
    app = FastAPI()

    def _ok() -> dict[str, str]:
        return {"ok": "si"}

    for method, path, roles in PERMITIDAS + PROHIBIDAS:
        app.add_api_route(
            path,
            _ok,
            methods=[method],
            dependencies=[Depends(require_role(*roles))],
            response_model=None,
        )
    return app


def _recep() -> dict[str, str]:
    token = create_access_token(sub="recep-1", rol="recepcionista", secret=SECRET)
    return {"Authorization": f"Bearer {token}"}


def test_recepcionista_6_permisos_si_feliz() -> None:
    client = TestClient(_app())
    for method, path, _ in PERMITIDAS:
        response = client.request(method, path, headers=_recep())
        assert response.status_code == 200, f"{method} {path} → {response.status_code}"


def test_recepcionista_4_prohibiciones_403_negocio() -> None:
    client = TestClient(_app())
    for method, path, _ in PROHIBIDAS:
        response = client.request(method, path, headers=_recep())
        assert response.status_code == 403, f"{method} {path} → {response.status_code}"


def test_ui_no_confiada_borde() -> None:
    """Borde P8: aunque la UI simule rol admin por header, el backend niega."""
    client = TestClient(_app())
    headers = {**_recep(), "X-Role": "admin"}
    response = client.post("/admin/usuarios", headers=headers)
    assert response.status_code == 403


def test_admin_si_autoriza_prohibidas_recepcionista() -> None:
    """Triangulación: el 403 es por rol, no por ruta rota (admin pasa)."""
    token = create_access_token(sub="admin-1", rol="admin", secret=SECRET)
    client = TestClient(_app())
    for method, path, _ in PROHIBIDAS:
        response = client.request(method, path, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200, f"{method} {path} → {response.status_code}"
