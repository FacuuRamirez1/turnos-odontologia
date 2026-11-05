"""Endpoints públicos de mail C-09 — confirmar / cancelar / metricas.

`GET /api/mail/confirmar?token=` y `GET /api/mail/cancelar?token=` son
públicos (sin JWT), rate-limit por IP (`MAIL_RATE_LIMIT`, clave
`mail:ratelimit:{ip}`), `HTMLResponse` mínima y sin datos de otros pacientes.
El rate-limit se evalúa ANTES de consumir el token: una ráfaga no quema links
válidos.

`GET /api/mail/metricas` es staff-only (`odontologo|recepcionista|admin`).
"""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.security.dependencies import Identity, get_jwt_secret, require_role
from app.core.security.jwt import AuthError, ExpiredAuthError, decode_and_validate
from app.core.settings import get_settings
from app.domain.notificaciones.metricas import contar_por_estado
from app.domain.notificaciones.tokens import consumir_token_db, token_hash_raw
from app.domain.turnos.cancelacion import cotizar_devolucion
from app.domain.turnos.estados import (
    ActorNoAutorizado,
    GuardaTemporalRechazada,
    TransicionInvalida,
    VersionConflict,
    transition,
)
from app.infra.db.models import RecordatorioMail, Turno, TurnoHistorial
from app.infra.db.session import get_db
from app.infra.redis.rate_limit import LoginRateLimiter, build_rate_limiter

router = APIRouter(prefix="/mail", tags=["mail"])

MAIL_PREFIX = "mail:ratelimit:"
MAIL_WINDOW = 60
_mail_limiter: LoginRateLimiter | None = None


def get_mail_limiter() -> LoginRateLimiter:
    global _mail_limiter
    if _mail_limiter is None:
        try:
            limite = get_settings().mail_rate_limit
        except Exception:
            limite = 30
        _mail_limiter = build_rate_limiter(
            get_settings().redis_url, limit=limite, window_seconds=MAIL_WINDOW
        )
    return _mail_limiter


def reset_mail_limiter(
    limit: int = 30, window_seconds: int = MAIL_WINDOW,
) -> None:
    """Seam para tests: renueva el limitador en memoria."""
    global _mail_limiter
    _mail_limiter = LoginRateLimiter(client=None, limit=limit, window_seconds=window_seconds)


def _ip(request: Request) -> str:
    return request.client.host if request.client is not None else "desconocida"


def _html(titulo: str, cuerpo: str, status: int = 200) -> HTMLResponse:
    return HTMLResponse(
        status_code=status,
        content=(
            "<!DOCTYPE html><html><head><meta charset='utf-8'><title>"
            + f"{titulo}</title></head><body><h1>{titulo}</h1>{cuerpo}</body></html>"
        ),
    )


def _error_html(titulo: str, mensaje: str, status: int) -> HTMLResponse:
    return _html(titulo, f"<p>{mensaje}</p>", status=status)


def _buscar_fila_por_hash(session: Session, token: str) -> RecordatorioMail | None:
    """Busca la fila por sha256(token) sin consumir (para distinguir replay)."""
    try:
        decode_and_validate(token, "action", get_jwt_secret())
    except (AuthError, ExpiredAuthError):
        return None
    h = token_hash_raw(token)
    return (
        session.query(RecordatorioMail)
        .filter(RecordatorioMail.token_accion_hash == h,
                RecordatorioMail.is_active.is_(True))
        .first()
    )


def _consumir_o_ya_procesado(
    session: Session, token: str,
) -> tuple[RecordatorioMail | None, str | None]:
    """Devuelve (fila, estado_accion).

    estado_accion: "nuevo" (se consumió OK), "ya_procesado" (token ya usado
    y la fila ya refleja la acción), None (token inválido/inexistente).
    """
    fila = _buscar_fila_por_hash(session, token)
    if fila is None:
        return None, None
    if fila.token_usado_at is not None:
        # Replay: ya se consumió. Si la fila refleja la acción, es idempotente.
        if fila.estado in ("confirmado_desde_mail", "cancelado_desde_mail"):
            return fila, "ya_procesado"
        return None, None  # usado pero sin acción reflejada → tratar como inválido
    consumida = consumir_token_db(session, token)
    if consumida is None:
        return None, None
    return consumida, "nuevo"


def _turno_o_404(session: Session, turno_id: UUID) -> Turno:
    turno = (
        session.query(Turno)
        .filter(Turno.id == turno_id, Turno.is_active.is_(True))
        .first()
    )
    if turno is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "turno inexistente")
    return turno


def _escribir_historial(
    session: Session, turno_id: UUID, actor_tipo: str, actor_id: str,
    motivo: str | None, ahora: datetime,
) -> None:
    session.add(TurnoHistorial(
        turno_id=turno_id, estado_anterior="confirmado", estado_nuevo="confirmado",
        actor_tipo=actor_tipo, actor_id=actor_id, fecha=ahora, motivo=motivo,
    ))
    session.flush()


@router.get("/confirmar", response_class=HTMLResponse)
def confirmar(
    request: Request,
    token: str = Query(...),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Confirma un turno `confirmado` desde el mail (idempotente, sin tocar el turno)."""
    # Rate-limit antes de consumir el token.
    if not get_mail_limiter().check_and_count(f"{MAIL_PREFIX}{_ip(request)}"):
        return _error_html("Demasiadas solicitudes", "Intenta de nuevo en unos instantes.", 429)

    fila, accion = _consumir_o_ya_procesado(db, token)
    if fila is None:
        return _error_html("Token inválido o expirado", "El link ya no es válido.", 400)
    if accion == "ya_procesado":
        return _html(
            "Turno ya confirmado",
            "<p>Este link ya fue usado. El turno ya está confirmado.</p>",
        )

    turno = _turno_o_404(db, fila.turno_id)
    if str(turno.estado) != "confirmado":
        return _error_html("Estado incompatible", "El turno ya no está confirmado.", 409)

    ahora = datetime.now(UTC)
    fila.estado = "confirmado_desde_mail"
    fila.token_usado_at = ahora
    db.add(fila)
    _escribir_historial(db, turno.id, "paciente", str(turno.paciente_id),
                        "confirmado_desde_mail", ahora)
    db.commit()
    return _html(
        "Turno confirmado",
        f"<p>Tu turno del {turno.inicio:%d/%m/%Y %H:%M} quedó confirmado. Gracias.</p>",
    )


@router.get("/cancelar", response_class=HTMLResponse)
def cancelar(
    request: Request,
    token: str = Query(...),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Cancela un turno `confirmado` desde el mail y muestra la cotización."""
    if not get_mail_limiter().check_and_count(f"{MAIL_PREFIX}{_ip(request)}"):
        return _error_html("Demasiadas solicitudes", "Intenta de nuevo en unos instantes.", 429)

    fila, accion = _consumir_o_ya_procesado(db, token)
    if fila is None:
        return _error_html("Token inválido o expirado", "El link ya no es válido.", 400)
    if accion == "ya_procesado":
        return _html(
            "Turno ya cancelado",
            "<p>Este link ya fue usado. El turno ya está cancelado.</p>",
        )

    turno = _turno_o_404(db, fila.turno_id)
    if str(turno.estado) != "confirmado":
        return _error_html("Estado incompatible", "El turno ya no está confirmado.", 409)

    inicio = turno.inicio
    if inicio.tzinfo is None:
        inicio = inicio.replace(tzinfo=UTC)
    porcentaje = cotizar_devolucion(inicio, get_settings().anticipacion_min_hs)
    ahora = datetime.now(UTC)
    try:
        transition(
            db, UUID(str(turno.id)), "cancelado",
            actor_tipo="paciente", actor_id=str(turno.paciente_id),
            motivo="cancelado_desde_mail", ahora=ahora,
        )
    except TransicionInvalida as exc:
        return _error_html("No se puede cancelar", str(exc), 409)
    except ActorNoAutorizado as exc:
        return _error_html("No autorizado", str(exc), 403)
    except GuardaTemporalRechazada as exc:
        return _error_html("No se puede cancelar", str(exc), 409)
    except VersionConflict as exc:
        return _error_html("Conflicto", str(exc), 409)

    fila.estado = "cancelado_desde_mail"
    fila.token_usado_at = ahora
    db.add(fila)
    db.commit()
    db.refresh(turno)
    return _html(
        "Turno cancelado",
        (
            f"<p>Turno del {turno.inicio:%d/%m/%Y %H:%M} cancelado.</p>"
            f"<p>Devolución de la seña: <strong>{porcentaje} %</strong>.</p>"
            f"<p>(La devolución se gestiona por la administración.)</p>"
        ),
    )


@router.get("/metricas", response_class=HTMLResponse)
def metricas(
    ident: Identity = Depends(require_role("odontologo", "recepcionista", "admin")),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Conteos de entrega por estado (staff-only)."""
    conteos = contar_por_estado(db)
    filas = "".join(
        f"<tr><td>{estado}</td><td>{conteos.get(estado, 0)}</td></tr>"
        for estado in ("encolado", "enviado", "reintentando", "fallido",
                       "confirmado_desde_mail", "cancelado_desde_mail")
    )
    return _html(
        "Métricas de entrega de mail",
        f"<table><tr><th>Estado</td><th>Cantidad</th></tr>{filas}</table>",
    )
