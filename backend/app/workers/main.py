"""Worker esqueleto C-01 — loop/cola sin logica de dominio (08 §1: fuera del request path).

La logica real de mails/scheduler llega en C-09. Aqui solo: conecta a Redis,
hace BLPOP en la cola de prueba y registra. Nunca toca el request path.
"""

import logging
import os
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("turnos-worker")

QUEUE = os.getenv("WORKER_QUEUE", "mail:pendientes")
IDLE_SLEEP_S = float(os.getenv("WORKER_IDLE_SLEEP_S", "5"))
HEARTBEAT_FILE = os.getenv("WORKER_HEARTBEAT_FILE", "/tmp/worker.heartbeat")


def _beat() -> None:
    try:
        with open(HEARTBEAT_FILE, "w", encoding="utf-8") as fh:
            fh.write(str(time.time()))
    except OSError as exc:
        logger.warning("no se pudo escribir heartbeat (%s)", exc)


def run_once() -> str:
    """Un ciclo: intenta leer de Redis, tolera Redis caido (dev sin redis)."""
    try:
        from typing import Any

        import redis  # import diferido: el esqueleto arranca aun sin lib instalada

        client: Any = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
        item: Any = client.blpop(QUEUE, timeout=1)
        if item is None:
            return "idle"
        _key, payload = item
        logger.info("job recibido: %s", bytes(payload)[:80])
        return "job"
    except Exception as exc:  # Redis caido o lib ausente: visible, no silencioso
        logger.warning("worker sin redis (%s); idle", exc)
        time.sleep(IDLE_SLEEP_S)
        return "no-redis"


def main() -> None:
    logger.info("worker esqueleto C-01 — cola=%s (logica real en C-09)", QUEUE)
    while True:
        _beat()
        run_once()


if __name__ == "__main__":
    main()
