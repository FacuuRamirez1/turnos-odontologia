"""Tests C-03 §3.1 — blacklist de jti (RED primero, task 3.1).

Escenarios (U2 feliz-negado / borde / negocio):
- feliz-negado: jti listado es rechazado (`is_listed` True, `claim` False);
- borde: TTL expira y deja de listar (reloj inyectado, determinístico);
- negocio: Redis caído usa fallback en memoria con warning (sigue funcional).
Triangulación: mismo contrato sobre backend Redis (doble `FakeRedis` mínimo).
"""

import logging
from collections.abc import Callable

import pytest

from app.infra.redis.blacklist import TokenBlacklist, build_blacklist
from app.infra.redis.client import BlacklistRedis


class FakeClock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


class FakeRedis(BlacklistRedis):
    """Doble mínimo: solo los comandos que usa `TokenBlacklist`."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def exists(self, key: str) -> int:
        return 1 if key in self.store else 0

    def setex(self, key: str, ttl: int, value: str) -> bool:
        self.store[key] = value
        return True

    def set(self, key: str, value: str, ex: int | None = None, nx: bool = False) -> bool | None:
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True


def _memory(clock: Callable[[], float] | None = None) -> TokenBlacklist:
    return TokenBlacklist(client=None, clock=clock or FakeClock())


def test_jti_listado_es_rechazado_feliz() -> None:
    blacklist = _memory()
    assert blacklist.is_listed("jti-1") is False
    blacklist.add("jti-1", ttl_seconds=3600)
    assert blacklist.is_listed("jti-1") is True
    assert blacklist.claim("jti-1", ttl_seconds=3600) is False


def test_ttl_expira_y_deja_de_listar_borde() -> None:
    clock = FakeClock()
    blacklist = _memory(clock)
    blacklist.add("jti-ttl", ttl_seconds=100)
    assert blacklist.is_listed("jti-ttl") is True
    clock.now += 101
    assert blacklist.is_listed("jti-ttl") is False
    assert blacklist.claim("jti-ttl", ttl_seconds=100) is True


def test_redis_caido_fallback_en_memoria_con_warning_negocio(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="turnos-odontologia"):
        blacklist = build_blacklist("redis://127.0.0.1:6399/0")
    assert any("fallback" in r.message for r in caplog.records)
    blacklist.add("jti-fb", ttl_seconds=60)
    assert blacklist.is_listed("jti-fb") is True


def test_mismo_contrato_sobre_redis_triangulacion() -> None:
    blacklist = TokenBlacklist(client=FakeRedis())
    assert blacklist.claim("jti-r", ttl_seconds=60) is True
    assert blacklist.is_listed("jti-r") is True
    assert blacklist.claim("jti-r", ttl_seconds=60) is False
