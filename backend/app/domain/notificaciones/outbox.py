"""Outbox transaccional C-09 — servicios de encolado y publicación.

Los servicios `encolar_*` solo insertan/actualizan la fila en la misma
sesión/transacción del caller (la transacción del turno o del historial).
Nunca publican a Redis ni envían SMTP. La publicación la hace `publicar_pendientes`
y el worker la consume de `mail:pendientes`.

Idempotencia: `UNIQUE (turno_id, tipo)`; si ya existe se devuelve. Si dos
transacciones compiten, el `UNIQUE` arbitra (`IntegrityError` → rollback →
requery), igual que el patrón C-05.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security.action_tokens import issue_action_token
from app.core.settings import get_settings
from app.domain.notificaciones.tokens import token_hash_raw
from app.infra.db.models import Paciente, RecordatorioMail, Turno


def _paciente_email(session: Session, paciente_id: uuid.UUID) -> str | None:
    """Email del paciente si existe y es usable (no blanco)."""
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
    """Devuelve el registro activo por (turno_id, tipo) o None."""
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
    """Hace flush de `fila`; ante carrera por UNIQUE, rollback y reconsulta."""
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
) -> RecordatorioMail:
    """Crea y persiste una fila (sin verificar duplicado previo)."""
    ahora = datetime.now(UTC)
    if email is None:
        fila = RecordatorioMail(
            turno_id=turno_id,
            tipo=tipo,
            destinatario="",
            estado="fallido",
            intentos=0,
            ultimo_error="paciente sin email",
            # publicado_at se deja None: nunca se publica (terminal sin reintento).
        )
    else:
        fila = RecordatorioMail(
            turno_id=turno_id,
            tipo=tipo,
            destinatario=email,
            estado="encolado",
            intentos=0,
        )
        if emitir_token:
            token = issue_action_token(
                str(fila.id), "mail_accion",
                action_min=get_settings().mail_action_ttl_min,
            )
            fila.token_accion_hash = token_hash_raw(token)
            fila.token_expira_at = ahora + timedelta(
                minutes=get_settings().mail_action_ttl_min
            )
    session.add(fila)
    return _flush_o_requery(session, fila, turno_id, tipo)


def _encolar(
    session: Session, turno: Turno, tipo: str, emitir_token: bool,
    contexto: dict[str, object] | None = None,
) -> RecordatorioMail | None:
    """Núcleo de encolado idempotente por (turno_id, tipo)."""
    existente = _obtener_existente(session, turno.id, tipo)
    if existente is not None:
        return existente
    email = _paciente_email(session, turno.paciente_id)
    fila = _crear_fila(session, turno.id, tipo, email, emitir_token)
    if contexto is not None and email is not None:
        fila.contexto_json = contexto
        session.add(fila)
        session.flush()
    return fila


def encolar_confirmacion(session: Session, turno: Turno) -> RecordatorioMail | None:
    """Encola (o devuelve existente) la confirmación de un turno confirmado."""
    return _encolar(session, turno, "confirmacion", emitir_token=True)


def encolar_recordatorio(session: Session, turno: Turno) -> RecordatorioMail | None:
    """Encola (o devuelve existente) el recordatorio de un turno confirmado."""
    return _encolar(session, turno, "recordatorio", emitir_token=True)


def encolar_aviso_devolucion(
    session: Session, turno: Turno, porcentaje: int,
) -> RecordatorioMail | None:
    """Encola (o devuelve existente) el aviso de devolución con la cotización.

    No ejecuta devolución real (C-08 pendiente); solo deja constancia del
    porcentaje en `contexto_json` para que el mail lo muestre al enviar.
    """
    return _encolar(
        session,
        turno,
        "aviso_devolucion",
        emitir_token=False,
        contexto={"porcentaje": porcentaje},
    )


def publicar_pendientes(session: Session) -> list[RecordatorioMail]:
    """Publica filas `encolado` sin `publicado_at` y las marca con ahora().

    Fuente de verdad para el worker: cubre caídas entre commit y push.
    Devuelve las filas publicadas.
    """
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
    """Re-publica `reintentando` vencidos cuyo `proximo_intento_at` pasó.

    `publicado_at <= proximo_intento_at` evita republicar entre ticks.
    """
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
        fila.publicado_at = None  # el worker lo vuelve a recoger
    session.flush()
    return vencidos


def encolar_recordatorios_ventana(
    session: Session, ventana_hs: int, ahora: datetime | None = None,
) -> list[RecordatorioMail]:
    """Encola un `recordatorio` por turno `confirmado` que inicie dentro de
    `ventana_hs` y aún no tenga recordatorio (una sola vez por turno)."""
    from datetime import timedelta

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
        existente = _obtener_existente(session, turno.id, "recordatorio")
        if existente is not None:
            continue
        email = _paciente_email(session, turno.paciente_id)
        if email is None:
            continue  # sin email: se salta (fallido solo si se invoca _crear_fila)
        fila = _crear_fila(session, turno.id, "recordatorio", email, emitir_token=True)
        creados.append(fila)
    return creados
