"""Outbox transaccional C-09/C-08 - servicios de encolado y publicacion."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security.action_tokens import issue_action_token
from app.core.settings import get_settings
from app.domain.notificaciones.tokens import token_hash_raw
from app.infra.db.models import Paciente, RecordatorioMail, Turno


def _paciente_email(session: Session, paciente_id: uuid.UUID) -> str | None:
    fila = session.query(Paciente).filter(Paciente.id == paciente_id).first()
    if fila is None:
        return None
    email = fila.email
    if not email or not str(email).strip():
        return None
    return str(email).strip()


def _obtener_existente(
    session: Session, turno_id: uuid.UUID, tipo: str,
) -> RecordatorioMail | None:
    return (
        session.query(RecordatorioMail)
        .filter(
            RecordatorioMail.turno_id == turno_id,
            RecordatorioMail.tipo == tipo,
            RecordatorioMail.is_active.is_(True),
        )
        .first()
    )


def _flush_o_requery(
    session: Session, fila: RecordatorioMail, turno_id: uuid.UUID, tipo: str,
) -> RecordatorioMail:
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        existente = _obtener_existente(session, turno_id, tipo)
        if existente is not None:
            return existente
        raise
    return fila


def _crear_fila(
    session: Session,
    turno_id: uuid.UUID,
    tipo: str,
    email: str | None,
    emitir_token: bool,
    plantilla_version: str = "v1",
) -> RecordatorioMail:
    ahora = datetime.now(UTC)
    if email is None:
        fila = RecordatorioMail(
            turno_id=turno_id,
            tipo=tipo,
            destinatario="",
            estado="fallido",
            intentos=0,
            ultimo_error="paciente sin email",
            plantilla_version=plantilla_version,
        )
    else:
        fila = RecordatorioMail(
            turno_id=turno_id,
            tipo=tipo,
            destinatario=email,
            estado="encolado",
            intentos=0,
            plantilla_version=plantilla_version,
        )
        if emitir_token:
            token = issue_action_token(
                str(fila.id), "mail_accion", action_min=get_settings().mail_action_ttl_min,
            )
            fila.token_accion_hash = token_hash_raw(token)
            fila.token_expira_at = ahora + timedelta(minutes=get_settings().mail_action_ttl_min)
    session.add(fila)
    return _flush_o_requery(session, fila, turno_id, tipo)


def _encolar(
    session: Session,
    turno: Turno,
    tipo: str,
    emitir_token: bool,
    contexto: dict[str, object] | None = None,
    plantilla_version: str = "v1",
) -> RecordatorioMail | None:
    existente = _obtener_existente(session, turno.id, tipo)
    if existente is not None:
        return existente
    email = _paciente_email(session, turno.paciente_id)
    fila = _crear_fila(session, turno.id, tipo, email, emitir_token, plantilla_version)
    if contexto is not None and email is not None:
        fila.contexto_json = contexto
        session.add(fila)
        session.flush()
    return fila


def encolar_confirmacion(session: Session, turno: Turno) -> RecordatorioMail | None:
    return _encolar(session, turno, "confirmacion", emitir_token=True)


def encolar_recordatorio(session: Session, turno: Turno) -> RecordatorioMail | None:
    return _encolar(session, turno, "recordatorio", emitir_token=True)


def encolar_aviso_devolucion(
    session: Session,
    turno: Turno,
    porcentaje: int,
    *,
    monto: object | None = None,
    resultado: str | None = None,
    comprobante_id: object | None = None,
) -> RecordatorioMail | None:
    """Encola (idempotente) el aviso de devolucion.

    C-08: con `monto/resultado` usa plantilla v2 y persiste contexto completo.
    Compatibilidad: llamada solo con porcentaje (cotizacion) usa v1.
    """
    if monto is None and resultado is None and comprobante_id is None:
        return _encolar(session, turno, "aviso_devolucion", False, {"porcentaje": porcentaje}, "v1")
    contexto: dict[str, object] = {"porcentaje": porcentaje, "resultado": resultado}
    if monto is not None:
        contexto["monto"] = str(monto)
    if comprobante_id is not None:
        contexto["comprobante_id"] = str(comprobante_id)
    return _encolar(session, turno, "aviso_devolucion", False, contexto, "v2")


def publicar_pendientes(session: Session) -> list[RecordatorioMail]:
    ahora = datetime.now(UTC)
    pendientes = (
        session.query(RecordatorioMail)
        .filter(
            RecordatorioMail.estado == "encolado",
            RecordatorioMail.publicado_at.is_(None),
            RecordatorioMail.is_active.is_(True),
        )
        .all()
    )
    for fila in pendientes:
        fila.publicado_at = ahora
    session.flush()
    return pendientes


def republicar_reintentando(session: Session) -> list[RecordatorioMail]:
    ahora = datetime.now(UTC)
    vencidos = (
        session.query(RecordatorioMail)
        .filter(
            RecordatorioMail.estado == "reintentando",
            RecordatorioMail.proximo_intento_at <= ahora,
            RecordatorioMail.publicado_at <= RecordatorioMail.proximo_intento_at,
            RecordatorioMail.is_active.is_(True),
        )
        .all()
    )
    for fila in vencidos:
        fila.publicado_at = None
    session.flush()
    return vencidos


def encolar_recordatorios_ventana(
    session: Session, ventana_hs: int, ahora: datetime | None = None,
) -> list[RecordatorioMail]:
    referencia = ahora or datetime.now(UTC)
    hasta = referencia + timedelta(hours=ventana_hs)
    turnos = (
        session.query(Turno)
        .filter(
            Turno.estado == "confirmado",
            Turno.inicio >= referencia,
            Turno.inicio <= hasta,
            Turno.is_active.is_(True),
        )
        .all()
    )
    creados: list[RecordatorioMail] = []
    for turno in turnos:
        if _obtener_existente(session, turno.id, "recordatorio") is not None:
            continue
        email = _paciente_email(session, turno.paciente_id)
        if email is None:
            continue
        creados.append(_crear_fila(session, turno.id, "recordatorio", email, True))
    return creados
