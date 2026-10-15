"""Tests C-03 §3.3 — rate-limit login 5/60 s por IP+email (RED primero, task 3.3).

Escenarios (U2 límite / borde / negocio):
- feliz/límite: 5 intentos OK + 6to bloqueado;
- borde: par IP+email distinto no afectado;
- negocio: ventana 60 s resetea contador.
Triangulación: mismo contrato sobre backend Redis (doble mínimo).
"""

from collections.abc import Callable

from app.infra.redis.client import RateLimitRedis
from app.infra.redis.rate_limit import LoginRateLimiter, login_key


class FakeClock:
    def __init__(self) -> None:
        self.now = 2_000.0

    def __call__(self) -> float:
        return self.now


class FakeRedis(RateLimitRedis):
    """Doble mínimo: solo los comandos que usa `LoginRateLimiter`."""

    def __init__(self) -> None:
        self.counters: dict[str, int] = {}

    def incr(self, key: str) -> int:
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    def expire(self, key: str, ttl: int) -> bool:
        return True


def _memory(clock: Callable[[], float] | None = None) -> LoginRateLimiter:
    return LoginRateLimiter(client=None, clock=clock or FakeClock())


def test_5_ok_y_6to_bloqueado_limite() -> None:
    limiter = _memory()
    key = login_key("10.0.0.1", "recep@clinica-ficticia.example.ar")
    assert [limiter.check_and_count(key) for _ in range(5)] == [True] * 5
    assert limiter.check_and_count(key) is False
    assert limiter.check_and_count(key) is False


def test_par_distinto_no_afectado_borde() -> None:
    limiter = _memory()
    bloqueada = login_key("10.0.0.1", "a@clinica-ficticia.example.ar")
    for _ in range(6):
        limiter.check_and_count(bloqueada)
    assert limiter.check_and_count(bloqueada) is False
    libre = login_key("10.0.0.1", "b@clinica-ficticia.example.ar")
    assert limiter.check_and_count(libre) is True
    otra_ip = login_key("10.0.0.2", "a@clinica-ficticia.example.ar")
    assert limiter.check_and_count(otra_ip) is True


def test_ventana_60s_resetea_negocio() -> None:
    clock = FakeClock()
    limiter = _memory(clock)
    key = login_key("10.0.0.9", "x@clinica-ficticia.example.ar")
    for _ in range(5):
        assert limiter.check_and_count(key) is True
    assert limiter.check_and_count(key) is False
    clock.now += 61
    assert limiter.check_and_count(key) is True


def test_mismo_contrato_sobre_redis_triangulacion() -> None:
    limiter = LoginRateLimiter(client=FakeRedis())
    key = login_key("10.0.0.7", "r@clinica-ficticia.example.ar")
    assert [limiter.check_and_count(key) for _ in range(5)] == [True] * 5
    assert limiter.check_and_count(key) is False


def test_email_case_insensitive_misma_llave() -> None:
    """`Admin@x` y `admin@x` comparten ventana (login es case-insensitive)."""
    assert login_key("1.1.1.1", "Admin@X") == login_key("1.1.1.1", "admin@x")
