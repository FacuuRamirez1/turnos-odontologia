"""Tokens de acción un solo uso persistidos en DB (C-09).

- Emisión: JWT `type='action'`, `proposito='mail_accion'`,
  `sub=str(recordatorio_id)`, TTL `MAIL_ACTION_TTL_MIN`; se guarda solo
  `sha256(token)` en `token_accion_hash` + `token_expira_at`; nunca el raw.
- Consumo: `UPDATE ... WHERE token_accion_hash = :hash AND token_usado_at IS NULL`
  (single-use en DB, no depende de `ActionTokenStore` ni de Redis/memoria).
- El caller (endpoint) valida firma/expiración con `decode_and_validate`
  antes de llamar a `consumir_token_db`.
"""

import hashlib
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.security.action_tokens import issue_action_token
from app.core.settings import get_settings
from app.infra.db.models import RecordatorioMail


def token_hash_raw(token: str) -> str:
    """sha256 hex del token: lo único que se persiste, nunca el raw (P12)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def emitir_token_para_recordatorio(
    session: Session, recordatorio: RecordatorioMail,
) -> str:
    """Emite un token action y persiste hash + expira en la fila. Devuelve el raw."""
    settings = get_settings()
    ahora = datetime.now(UTC)
    token = issue_action_token(
        str(recordatorio.id), "mail_accion",
        action_min=settings.mail_action_ttl_min,
    )
    recordatorio.token_accion_hash = token_hash_raw(token)
    recordatorio.token_expira_at = ahora + timedelta(
        minutes=settings.mail_action_ttl_min
    )
    session.add(recordatorio)
    session.flush()
    return token


def consumir_token_db(
    session: Session, token: str,
) -> RecordatorioMail | None:
    """Consumo single-use en DB: fila donde hash coincida y no usado aún.

    Devuelve la fila si el consumo tuvo éxito; None si ya usada, inexistente
    o expirada. No toca `ActionTokenStore` (regla de un uso vive en DB).
    """
    h = token_hash_raw(token)
    ahora = datetime.now(UTC)
    fila = (
        session.query(RecordatorioMail)
        .filter(
            RecordatorioMail.token_accion_hash == h,
            RecordatorioMail.token_usado_at.is_(None),
            RecordatorioMail.is_active.is_(True),
        )
        .first()
    )
    if fila is None:
        return None
    if fila.token_expira_at is not None and ahora > fila.token_expira_at:
        return None  # expirado
    fila.token_usado_at = ahora
    session.add(fila)
    session.flush()
    return fila
