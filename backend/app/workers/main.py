"""Worker real C-09/C-08 - consumo mail:pendientes + scheduler de ventana."""

import json
import logging
import os
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from redis import Redis
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.domain.notificaciones.metricas import ESTADOS  # noqa: F401
from app.domain.notificaciones.outbox import (
    encolar_recordatorios_ventana,
    publicar_pendientes,
    republicar_reintentando,
)
from app.domain.notificaciones.plantillas import render
from app.domain.notificaciones.tokens import emitir_token_para_recordatorio
from app.infra.db.models import Comprobante, Paciente, RecordatorioMail, Turno
from app.infra.db.session import SessionLocal
from app.infra.smtp import SmtpMailer, build_mailer_from_settings

logger = logging.getLogger("turnos-worker")

QUEUE = os.getenv("WORKER_QUEUE", "mail:pendientes")
IDLE_SLEEP_S = float(os.getenv("WORKER_IDLE_SLEEP_S", "5"))
HEARTBEAT_FILE = os.getenv("WORKER_HEARTBEAT_FILE", "/tmp/worker.heartbeat")
MAX_INTENTOS = 3
BACKOFF_MINUTOS = [1, 5]


def _beat() -> None:
    try:
        with open(HEARTBEAT_FILE, "w", encoding="utf-8") as fh:
            fh.write(str(time.time()))
    except OSError as exc:
        logger.warning("no se pudo escribir heartbeat (%s)", exc)


def _ahora_utc() -> datetime:
    return datetime.now(UTC)


def _proximo_intento(intentos: int, ahora: datetime) -> datetime:
    idx = min(intentos - 1, len(BACKOFF_MINUTOS) - 1)
    return ahora + timedelta(minutes=BACKOFF_MINUTOS[idx])


def _datos_para_render(session: Session, fila: RecordatorioMail) -> dict[str, str]:
    turno = session.query(Turno).filter(Turno.id == fila.turno_id).first()
    if turno is None:
        raise ValueError(f"turno inexistente para recordatorio {fila.id}")
    paciente = session.query(Paciente).filter(Paciente.id == turno.paciente_id).first()
    if paciente is None:
        raise ValueError(f"paciente inexistente para turno {turno.id}")
    inicio = turno.inicio
    if inicio.tzinfo is None:
        inicio = inicio.replace(tzinfo=UTC)
    turno_inicio = inicio.astimezone(UTC).strftime("%d/%m/%Y %H:%M")
    return {
        "nombre": paciente.nombre or "",
        "apellido": paciente.apellido or "",
        "turno_inicio": turno_inicio,
    }


def _adjuntos_aviso_devolucion(
    session: Session, fila: RecordatorioMail,
) -> list[tuple[str, bytes, str]]:
    ctx = fila.contexto_json or {}
    comprobante_id = ctx.get("comprobante_id")
    if not comprobante_id:
        return []
    comprobante = session.get(Comprobante, UUID(str(comprobante_id)))
    if comprobante is None:
        return []
    from app.domain.comprobantes.pdf import generar_pdf

    nombre = f"recibo-{comprobante.numero}.pdf"
    return [(nombre, generar_pdf(comprobante), "application/pdf")]


def _render_fila(
    session: Session, fila: RecordatorioMail, token: str,
) -> tuple[str, str, str]:
    datos = _datos_para_render(session, fila)
    version = str(fila.plantilla_version or "v1")
    if fila.tipo == "aviso_devolucion":
        pct = fila.contexto_json or {}
        porcentaje = pct.get("porcentaje", 0)
        if version == "v2":
            return render(
                "v2",
                "aviso_devolucion",
                nombre=datos["nombre"],
                apellido=datos["apellido"],
                porcentaje=porcentaje,
                turno_inicio=datos["turno_inicio"],
                monto=pct.get("monto"),
                resultado=str(pct.get("resultado", "")),
            )
        return render(
            "v1",
            "aviso_devolucion",
            nombre=datos["nombre"],
            apellido=datos["apellido"],
            porcentaje=porcentaje,
            turno_inicio=datos["turno_inicio"],
        )
    return render(
        version,
        fila.tipo,
        nombre=datos["nombre"],
        apellido=datos["apellido"],
        token=token,
        turno_inicio=datos["turno_inicio"],
    )


def procesar_job(session: Session, mailer: SmtpMailer, recordatorio_id: str) -> str:
    try:
        rid = UUID(recordatorio_id)
    except (ValueError, AttributeError):
        logger.warning("payload inválido: %s", recordatorio_id)
        return "descartado-payload-invalido"

    fila = (
        session.query(RecordatorioMail)
        .filter(RecordatorioMail.id == rid, RecordatorioMail.is_active.is_(True))
        .first()
    )
    if fila is None:
        return "descartado-inexistente"

    ahora = _ahora_utc()
    estado = str(fila.estado)
    if estado == "reintentando":
        pim = fila.proximo_intento_at
        if pim is not None and pim.tzinfo is None:
            pim = pim.replace(tzinfo=UTC)
        if pim is None or pim > ahora:
            return "descartado-no-vencido"
    elif estado != "encolado":
        return f"descartado-no-sendable:{estado}"

    token = emitir_token_para_recordatorio(session, fila)
    asunto, texto, html = _render_fila(session, fila, token)
    adjuntos = _adjuntos_aviso_devolucion(session, fila) if fila.tipo == "aviso_devolucion" else []

    try:
        mailer.enviar(fila.destinatario, asunto, texto, html, adjuntos=adjuntos or None)
    except Exception as exc:
        fila.intentos = int(fila.intentos or 0) + 1
        fila.ultimo_error = str(exc)
        if fila.intentos >= MAX_INTENTOS:
            fila.estado = "fallido"
            fila.proximo_intento_at = None
        else:
            fila.estado = "reintentando"
            fila.proximo_intento_at = _proximo_intento(fila.intentos, ahora)
        session.add(fila)
        session.flush()
        logger.warning("envío falló (intento %s): %s", fila.intentos, exc)
        return "fallo"

    fila.estado = "enviado"
    fila.enviado_at = ahora
    session.add(fila)
    session.flush()
    return "enviado"


def ejecutar_tick_scheduler(
    session_factory: Callable[[], Session], ventana_hs: int,
) -> dict[str, int]:
    resultado = {"publicados": 0, "republicados": 0, "recordatorios_encolados": 0}
    with session_factory() as session:
        publicados = publicar_pendientes(session)
        session.commit()
        resultado["publicados"] = len(publicados)
    with session_factory() as session:
        republicados = republicar_reintentando(session)
        session.commit()
        resultado["republicados"] = len(republicados)
    with session_factory() as session:
        creados = encolar_recordatorios_ventana(session, ventana_hs)
        session.commit()
        resultado["recordatorios_encolados"] = len(creados)
    return resultado


def _leer_job(redis_client: Any) -> Any:
    try:
        item = redis_client.blpop(QUEUE, timeout=1)
    except Exception as exc:
        logger.warning("worker sin redis (%s); idle", exc)
        time.sleep(IDLE_SLEEP_S)
        return None
    if item is None:
        return None
    _, payload = item
    try:
        return json.loads(payload if isinstance(payload, str) else payload.decode("utf-8"))
    except (ValueError, AttributeError) as exc:
        logger.warning("payload no JSON: %s", exc)
        return {"_raw": payload}


def run_once(
    session_factory: Callable[[], Session],
    mailer: SmtpMailer,
    redis_client: Any,
    ventana_hs: int,
    scheduler_due: float,
    ahora_monotonic: float,
) -> float:
    job = _leer_job(redis_client)
    if job is not None and "_raw" not in job:
        rid = str(job.get("recordatorio_id", ""))
        with session_factory() as session:
            estado = procesar_job(session, mailer, rid)
            session.commit()
        logger.info("job procesado recordatorio=%s estado=%s", rid, estado)

    if ahora_monotonic >= scheduler_due:
        try:
            res = ejecutar_tick_scheduler(session_factory, ventana_hs)
            logger.info("tick scheduler: %s", res)
        except Exception as exc:
            logger.exception("falló tick scheduler: %s", exc)
        return ahora_monotonic + float(os.getenv("WORKER_SCHEDULER_TICK_S", "60"))
    return scheduler_due


def main() -> None:
    settings = get_settings()
    mailer = build_mailer_from_settings()
    redis_client = Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
    scheduler_due = time.monotonic()
    logger.info("worker C-09 - cola=%s tick_s=%s", QUEUE, settings.worker_scheduler_tick_s)
    while True:
        _beat()
        ahora = time.monotonic()
        scheduler_due = run_once(
            SessionLocal, mailer, redis_client,
            settings.recordatorio_ventana_hs, scheduler_due, ahora,
        )
        time.sleep(IDLE_SLEEP_S)


if __name__ == "__main__":
    main()
