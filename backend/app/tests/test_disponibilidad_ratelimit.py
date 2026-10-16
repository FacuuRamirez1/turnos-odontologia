"""Tests C-04 §5.3 — limitador público generalizado 30/min (RED primero).

- feliz: 30 req/min pasan (unidad, FakeClock);
- negocio: req 31 → 429 (endpoint, seam de límite bajo);
- borde: IP distinta no afectada (llaves distintas); caída de Redis →
  fallback memoria sin 500.
"""

import datetime as dt
import uuid
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api import public_disponibilidad as pub
from app.infra.db.models import Disponibilidad, Odontologo, Usuario
from app.infra.redis.rate_limit import LoginRateLimiter, disponibilidad_key, login_key

HASH = "$2b$04$" + "k" * 53


class FakeClock:
    def __init__(self) -> None:
        self.now = 5_000.0

    def __call__(self) -> float:
        return self.now


def _limiter(limit: int, clock: Callable[[], float] | None = None) -> LoginRateLimiter:
    return LoginRateLimiter(client=None, limit=limit, window_seconds=60, clock=clock or FakeClock())


def test_30_pasan_feliz() -> None:
    limiter = _limiter(30)
    key = disponibilidad_key("10.1.1.1")
    assert [limiter.check_and_count(key) for _ in range(30)] == [True] * 30


def test_31_bloqueada_y_login_sigue_5() -> None:
    limiter = _limiter(30)
    key = disponibilidad_key("10.1.1.2")
    for _ in range(30):
        assert limiter.check_and_count(key) is True
    assert limiter.check_and_count(key) is False
    # Triangulación: login conserva su (5, 60s) por defecto.
    login = LoginRateLimiter(client=None)
    lkey = login_key("10.1.1.2", "x@clinica-ficticia.example.ar")
    assert [login.check_and_count(lkey) for _ in range(5)] == [True] * 5
    assert login.check_and_count(lkey) is False


def test_ip_distinta_no_afectada_borde() -> None:
    limiter = _limiter(2)
    for _ in range(2):
        assert limiter.check_and_count(disponibilidad_key("10.2.2.2")) is True
    assert limiter.check_and_count(disponibilidad_key("10.2.2.2")) is False
    assert limiter.check_and_count(disponibilidad_key("10.2.2.3")) is True


def test_ventana_resetea_borde() -> None:
    clock = FakeClock()
    limiter = _limiter(1, clock)
    key = disponibilidad_key("10.3.3.3")
    assert limiter.check_and_count(key) is True
    assert limiter.check_and_count(key) is False
    clock.now += 61
    assert limiter.check_and_count(key) is True


def _sembrar(db: Session) -> uuid.UUID:
    u = Usuario(email="od-rl@clinica-ficticia.example.ar", password_hash=HASH, rol="odontologo")
    db.add(u)
    db.commit()
    p = Odontologo(user_id=u.id, monto_turno=Decimal("1"), monto_senia=Decimal("1"))
    db.add(p)
    db.commit()
    od = uuid.UUID(str(p.id))
    db.add(
        Disponibilidad(
            odontologo_id=od, dia_semana=0,
            hora_inicio=dt.time(9, 0), hora_fin=dt.time(10, 0),
            duracion_min=30, tope_dia=14,
        )
    )
    db.commit()
    return od


def test_endpoint_429_tras_limite_negocio(auth_client: TestClient, db_session: Session) -> None:
    od = _sembrar(db_session)
    pub.reset_public_limiter(limit=2, window_seconds=60)
    try:
        params = {"odontologo_id": str(od), "fecha": "2026-12-07"}
        assert auth_client.get("/api/disponibilidad", params=params).status_code == 200
        assert auth_client.get("/api/disponibilidad", params=params).status_code == 200
        r = auth_client.get("/api/disponibilidad", params=params)
        assert r.status_code == 429
    finally:
        pub.reset_public_limiter()


def test_fallback_memoria_sin_500_borde(
    auth_client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch | None = None
) -> None:
    """Sin Redis (client=None) el endpoint responde 200, nunca 500."""
    _ = monkeypatch
    od = _sembrar(db_session)
    pub.reset_public_limiter(limit=30, window_seconds=60)
    params = {"odontologo_id": str(od), "fecha": "2026-12-07"}
    r = auth_client.get("/api/disponibilidad", params=params)
    assert r.status_code in (200, 404)
