"""Reserva pública C-05 — POST /api/reservas (03 §3.2, P12, spec § reserva).

- Sin JWT (ruta pública cerrada); rate-limit fixed-window Redis
  `ratelimit:reservas:{ip}` (default 10/min/IP, env `RESERVA_RATE_LIMIT`).
- DNI normalizado (puntos/espacios/guiones) → `resolve_or_create` C-06:
  reutiliza existente o crea con gate de consentimiento; sin consentimiento
  → 422 `CONSENTIMIENTO_REQUERIDO` sin persistir nada (P11).
- Validación del slot contra motor C-04 + ocupados C-05 + anticipación
  (RN-PASADO/DOBLE/SOLAPE/ANTICIPACION); `fin` lo fija la franja, no el cliente.
- `Idempotency-Key` UNIQUE (P4): replay misma key → 200 original;
  carrera keys distintas → IntegrityError → 409 `SLOT_OCUPADO`.
- Schemas Pydantic v2 `extra='forbid'` (P2).
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security.dependencies import Identity, get_blacklist, get_jwt_secret, require_role
from app.core.security.jwt import AuthError, decode_and_validate
from app.core.settings import get_settings
from app.domain.disponibilidad.motor import Slot, generar_slots, resolver_zona
from app.domain.pacientes.service import (
    ConsentimientoRequerido,
    PacienteDuplicado,
    PacienteService,
    normalizar_dni,
    validar_formato_dni,
)
from app.domain.turnos.cancelacion import cotizar_devolucion
from app.domain.turnos.estados import (
    ActorNoAutorizado,
    GuardaTemporalRechazada,
    TransicionInvalida,
    VersionConflict,
    transition,
)
from app.domain.turnos.ocupados import hay_solape, ocupados_rango
from app.infra.db.models import Bloqueo, Disponibilidad, Odontologo, Paciente, Turno
from app.infra.db.session import get_db
from app.infra.redis.rate_limit import LoginRateLimiter, build_rate_limiter

router = APIRouter(prefix="/reservas", tags=["reservas"])

RESERVAS_LIMIT = 10
RESERVAS_WINDOW = 60

_reservas_limiter: LoginRateLimiter | None = None


def get_reservas_limiter() -> LoginRateLimiter:
    """Limitador público (lazy env; `reset_reservas_limiter` lo renueva en tests)."""
    global _reservas_limiter
    if _reservas_limiter is None:
        try:
            limite = get_settings().reserva_rate_limit
        except Exception:
            limite = RESERVAS_LIMIT
        _reservas_limiter = build_rate_limiter(
            get_settings().redis_url, limit=limite, window_seconds=RESERVAS_WINDOW
        )
    return _reservas_limiter


def reset_reservas_limiter(
    limit: int = RESERVAS_LIMIT, window_seconds: int = RESERVAS_WINDOW
) -> None:
    """Renueva el limitador en memoria (seam solo para tests)."""
    global _reservas_limiter
    _reservas_limiter = LoginRateLimiter(client=None, limit=limit, window_seconds=window_seconds)


class ReservaCreate(BaseModel):
    """Pedido de reserva pública — P2 `extra='forbid'`."""

    model_config = ConfigDict(extra="forbid")

    odontologo_id: uuid.UUID
    inicio: datetime
    dni: str = Field(min_length=1, max_length=20)
    nombre: str = Field(min_length=1, max_length=120)
    apellido: str = Field(min_length=1, max_length=120)
    email: str | None = Field(default=None, max_length=255)
    telefono: str | None = Field(default=None, max_length=50)
    consentimiento_datos: bool = False
    consentimiento_fecha: datetime | None = None

    @field_validator("dni")
    @classmethod
    def _dni_normalizado(cls, value: str) -> str:
        normalizado = normalizar_dni(value)
        try:
            validar_formato_dni(normalizado)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        return normalizado


class ReservaOut(BaseModel):
    """Turno creado — P2 `extra='forbid'`."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    paciente_id: uuid.UUID
    odontologo_id: uuid.UUID
    inicio: datetime
    fin: datetime
    estado: str
    canal: str


def _out(fila: Turno) -> ReservaOut:
    return ReservaOut(
        id=uuid.UUID(str(fila.id)),
        paciente_id=uuid.UUID(str(fila.paciente_id)),
        odontologo_id=uuid.UUID(str(fila.odontologo_id)),
        inicio=fila.inicio,
        fin=fila.fin,
        estado=str(fila.estado),
        canal=str(fila.canal),
    )


def _slot_ofrecido(
    db: Session, odontologo_id: uuid.UUID, inicio: datetime,
    ttl_min: int, anticipacion_hs: int, zona: object,
) -> datetime | None:
    """`fin` del hueco ofrecido que arranca en `inicio`, o None si no hay.

    Compone franjas vigentes + bloqueos + ocupados sobre el motor puro C-04
    (misma composición que `GET /disponibilidad`, design D7).
    """
    from zoneinfo import ZoneInfo

    zona_tz = zona if isinstance(zona, ZoneInfo) else resolver_zona(None)
    ini_utc = inicio if inicio.tzinfo is not None else inicio.replace(tzinfo=UTC)
    ini_local = ini_utc.astimezone(zona_tz)
    fecha = ini_local.date()
    franjas = (
        db.query(Disponibilidad)
        .filter(
            Disponibilidad.odontologo_id == odontologo_id,
            Disponibilidad.is_active.is_(True),
            Disponibilidad.dia_semana == fecha.weekday(),
        )
        .all()
    )
    vigentes = [
        f for f in franjas
        if (f.vigente_desde is None or f.vigente_desde <= fecha)
        and (f.vigente_hasta is None or f.vigente_hasta >= fecha)
    ]
    if not vigentes:
        return None
    medianoche = datetime(fecha.year, fecha.month, fecha.day, tzinfo=zona_tz)
    bloqueos_db = (
        db.query(Bloqueo)
        .filter(
            Bloqueo.odontologo_id == odontologo_id,
            Bloqueo.is_active.is_(True),
            Bloqueo.desde < medianoche.replace(hour=23, minute=59, second=59),
            Bloqueo.hasta > medianoche.replace(hour=0, minute=0),
        )
        .all()
    )
    bloques = [
        Slot(inicio=b.desde if b.desde.tzinfo else b.desde.replace(tzinfo=zona_tz),
             fin=b.hasta if b.hasta.tzinfo else b.hasta.replace(tzinfo=zona_tz))
        for b in bloqueos_db
    ]
    ahora = datetime.now(UTC)
    for franja in vigentes:
        ocupados = [
            Slot(inicio=o[0] if o[0].tzinfo else o[0].replace(tzinfo=UTC),
                 fin=o[1] if o[1].tzinfo else o[1].replace(tzinfo=UTC))
            for o in ocupados_rango(
                db, odontologo_id,
                medianoche.replace(hour=0, minute=0),
                medianoche.replace(hour=23, minute=59, second=59),
                ttl_min, ahora)
        ]
        for slot in generar_slots(
            dia_semana=franja.dia_semana, hora_inicio=franja.hora_inicio,
            hora_fin=franja.hora_fin, duracion_min=franja.duracion_min,
            tope_dia=franja.tope_dia, fecha=fecha, ahora=ahora,
            anticipacion_hs=anticipacion_hs, bloqueos=bloques,
            ocupados=ocupados, tz=zona_tz,
        ):
            if slot.inicio == ini_local:
                return slot.fin.astimezone(UTC)
    return None


def crear_reserva(
    db: Session, cuerpo: ReservaCreate, idempotency_key: str, canal: str = "web",
) -> tuple[Turno, bool]:
    """Núcleo compartido web/recepción: valida y persiste (o replays).

    Retorna `(turno, creado)`. Levanta `ConsentimientoRequerido`,
    `ValueError` (slot/fecha) o `SlotOcupado`.
    """
    settings = get_settings()
    ttl_min = settings.reserva_ttl_min
    anticipacion_hs = settings.anticipacion_min_hs
    zona = resolver_zona(settings.timezone)

    existente = (
        db.query(Turno).filter(Turno.idempotency_key == idempotency_key).first()
    )
    if existente is not None:
        return existente, False

    svc = PacienteService(db)
    try:
        paciente, _ = svc.resolve_or_create(
            dni=cuerpo.dni, nombre=cuerpo.nombre, apellido=cuerpo.apellido,
            email=cuerpo.email, telefono=cuerpo.telefono,
            consentimiento_datos=cuerpo.consentimiento_datos,
            consentimiento_fecha=cuerpo.consentimiento_fecha,
        )
    except PacienteDuplicado:
        # Carrera de alta con mismo DNI: el UNIQUE arbitró, reutiliza el ganador.
        db.rollback()
        ganador = (
            db.query(Paciente)
            .filter(Paciente.dni == normalizar_dni(cuerpo.dni),
                    Paciente.is_active.is_(True))
            .first()
        )
        if ganador is None:
            raise
        paciente = ganador

    ahora = datetime.now(UTC)
    inicio = cuerpo.inicio if cuerpo.inicio.tzinfo else cuerpo.inicio.replace(tzinfo=UTC)
    if inicio <= ahora:
        raise ValueError("inicio en el pasado (RN-PASADO)")
    if (inicio - ahora).total_seconds() < anticipacion_hs * 3600:
        raise ValueError("fuera de anticipación mínima (RN-ANTICIPACION)")

    od = db.query(Odontologo).filter(Odontologo.id == cuerpo.odontologo_id).first()
    if od is None or not bool(od.is_active and od.activo):
        raise ValueError("odontólogo desconocido")

    fin = _slot_ofrecido(db, cuerpo.odontologo_id, inicio, ttl_min, anticipacion_hs, zona)
    if fin is None:
        if hay_solape(db, cuerpo.odontologo_id, inicio,
                       inicio + _duracion_franja(db, cuerpo.odontologo_id, inicio, zona),
                       ttl_min, ahora):
            raise SlotOcupado("slot ocupado")
        raise ValueError("slot no ofrecible")

    fila = Turno(
        paciente_id=paciente.id, odontologo_id=cuerpo.odontologo_id,
        inicio=inicio, fin=fin, estado="creado", canal=canal,
        idempotency_key=idempotency_key,
    )
    db.add(fila)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        replay = (
            db.query(Turno).filter(Turno.idempotency_key == idempotency_key).first()
        )
        if replay is not None:
            return replay, False
        raise SlotOcupado("slot ocupado (RN-DOBLE/RN-SOLAPE)") from exc
    db.commit()
    db.refresh(fila)
    return fila, True


def _duracion_franja(
    db: Session, odontologo_id: uuid.UUID, inicio: datetime, zona: object,
) -> timedelta:
    """Duración fallback (30 min) para el chequeo de solape pre-motor."""
    _ = (db, odontologo_id, inicio, zona)
    return timedelta(minutes=30)


class SlotOcupado(Exception):
    """Slot tomado por otro turno → 409 reintentable."""


@router.post("", response_model=ReservaOut, status_code=201)
def reservar(
    cuerpo: ReservaCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> ReservaOut | JSONResponse:
    """Crea la pre-reserva `creado` (público, rate-limited, idempotente)."""
    ip = request.client.host if request.client is not None else "desconocida"
    if not get_reservas_limiter().check_and_count(f"ratelimit:reservas:{ip}"):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "demasiadas reservas")
    key = request.headers.get("Idempotency-Key") or request.headers.get("idempotency-key")
    if not key:
        key = f"auto-{uuid.uuid4().hex}"
    try:
        fila, creado = crear_reserva(db, cuerpo, key.strip(), canal="web")
    except ConsentimientoRequerido as exc:
        return JSONResponse(
            status_code=422, content={"code": "CONSENTIMIENTO_REQUERIDO", "detail": str(exc)})
    except SlotOcupado as exc:
        return JSONResponse(
            status_code=409, content={"code": "SLOT_OCUPADO", "detail": str(exc)})
    except ValueError as exc:
        return JSONResponse(
            status_code=422, content={"code": "SLOT_NO_DISPONIBLE", "detail": str(exc)})
    if not creado:
        return JSONResponse(status_code=200, content=_out(fila).model_dump(mode="json"))
    return _out(fila)


TELEFONICA = require_role("recepcionista", "admin")


@router.post("/telefonica", response_model=ReservaOut, status_code=201)
def reservar_telefonica(
    cuerpo: ReservaCreate,
    request: Request,
    ident: Identity = Depends(TELEFONICA),
    db: Session = Depends(get_db),
) -> ReservaOut | JSONResponse:
    """Reserva a nombre del paciente (`canal='recepcion'`, datos mínimos
    DNI+mail+consentimiento; odontólogo → 403 por el guard, matriz 03 §2)."""
    _ = ident
    key = request.headers.get("Idempotency-Key") or request.headers.get("idempotency-key")
    if not key:
        key = f"tel-{uuid.uuid4().hex}"
    try:
        fila, _ = crear_reserva(db, cuerpo, key.strip(), canal="recepcion")
    except ConsentimientoRequerido as exc:
        return JSONResponse(
            status_code=422, content={"code": "CONSENTIMIENTO_REQUERIDO", "detail": str(exc)})
    except SlotOcupado as exc:
        return JSONResponse(
            status_code=409, content={"code": "SLOT_OCUPADO", "detail": str(exc)})
    except ValueError as exc:
        return JSONResponse(
            status_code=422, content={"code": "SLOT_NO_DISPONIBLE", "detail": str(exc)})
    return _out(fila)


# --- Cancelación en dos pasos: cotizar → confirmar (design D5, B1–B3) ---

ROLES_STAFF = ("odontologo", "recepcionista", "admin")


class CancelarBody(BaseModel):
    """Confirmación de cancelación — P2 `extra='forbid'`."""

    model_config = ConfigDict(extra="forbid")

    motivo: str | None = Field(default=None, max_length=500)


class CotizacionOut(BaseModel):
    """Regla aplicable antes de confirmar — P2 `extra='forbid'`."""

    model_config = ConfigDict(extra="forbid")

    porcentaje: int


def _actor_para_turno(
    request: Request, db: Session, turno: Turno,
    dni: str | None, token: str | None,
) -> tuple[str, str, str | None]:
    """(actor_tipo, actor_id, token_a_consumir).

    Staff via Bearer access (P8 + scope propio); paciente via mail-action
    token `?token=` cuyo `sub` es su DNI (P12). Sin credencial → 401,
    mismatch → 403. El consumo single-use lo hace el caller que escribe.
    """
    auth = request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        raw = auth.split(" ", 1)[1].strip()
        try:
            claims = decode_and_validate(raw, "access", get_jwt_secret())
        except AuthError as exc:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
        if get_blacklist().is_listed(str(claims["jti"])):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token revocado")
        rol = str(claims.get("rol", ""))
        if rol not in ROLES_STAFF:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "rol no autorizado")
        if rol == "odontologo":
            propio = claims.get("odontologo_id")
            if propio is None or str(propio) != str(turno.odontologo_id):
                raise HTTPException(status.HTTP_403_FORBIDDEN, "turno de otro profesional")
        return rol, str(claims["sub"]), None
    if not token or not dni:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "se requiere autenticación")
    try:
        claims = decode_and_validate(token, "action", get_jwt_secret())
    except AuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    if str(claims.get("sub")) != normalizar_dni(dni):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "token no autoriza este turno")
    paciente = (
        db.query(Paciente)
        .filter(Paciente.dni == normalizar_dni(dni), Paciente.is_active.is_(True))
        .first()
    )
    if paciente is None or str(paciente.id) != str(turno.paciente_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "token no autoriza este turno")
    return "paciente", str(paciente.id), token


def _turno_o_404(db: Session, turno_id: uuid.UUID) -> Turno:
    turno = (
        db.query(Turno)
        .filter(Turno.id == turno_id, Turno.is_active.is_(True))
        .first()
    )
    if turno is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "turno inexistente")
    return turno


def _transicion_http(
    db: Session, turno: Turno, destino: str,
    actor_tipo: str, actor_id: str, motivo: str | None,
) -> Turno:
    try:
        fila = transition(db, uuid.UUID(str(turno.id)), destino,
                           actor_tipo=actor_tipo, actor_id=actor_id, motivo=motivo)
    except TransicionInvalida as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except GuardaTemporalRechazada as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except ActorNoAutorizado as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except VersionConflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    db.commit()
    db.refresh(fila)
    return fila


@router.get("/{turno_id}/cotizar-cancelacion", response_model=CotizacionOut)
def cotizar_cancelacion(
    turno_id: uuid.UUID,
    request: Request,
    dni: str | None = None,
    token: str | None = None,
    db: Session = Depends(get_db),
) -> CotizacionOut:
    """Cuota aplicable (100/60/0) — pura, sin escritura ni consumo del token."""
    turno = _turno_o_404(db, turno_id)
    _actor_para_turno(request, db, turno, dni, token)
    inicio = turno.inicio if turno.inicio.tzinfo else turno.inicio.replace(tzinfo=UTC)
    return CotizacionOut(porcentaje=cotizar_devolucion(
        inicio, get_settings().anticipacion_min_hs))


@router.post("/{turno_id}/cancelar")
def cancelar(
    turno_id: uuid.UUID,
    cuerpo: CancelarBody,
    request: Request,
    dni: str | None = None,
    token: str | None = None,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """`confirmado→cancelado` + liberación en el mismo commit (RN-LIBERACION).

    Crea el registro de devolución `pendiente` con porcentaje (entidad lógica
    que C-08 materializa; viaja en la respuesta para la bandeja).
    """
    turno = _turno_o_404(db, turno_id)
    actor_tipo, actor_id, a_consumir = _actor_para_turno(request, db, turno, dni, token)
    inicio = turno.inicio if turno.inicio.tzinfo else turno.inicio.replace(tzinfo=UTC)
    porcentaje = cotizar_devolucion(inicio, get_settings().anticipacion_min_hs)
    fila = _transicion_http(db, turno, "cancelado", actor_tipo, actor_id, cuerpo.motivo)
    if a_consumir is not None:
        from app.api.pacientes import get_paciente_action_store

        get_paciente_action_store().consume(
            a_consumir, get_settings().jwt_action_min * 60)
    return JSONResponse(status_code=200, content={
        "id": str(fila.id), "estado": str(fila.estado),
        "devolucion": {"estado": "pendiente", "porcentaje": porcentaje},
    })


class ReprogramarBody(BaseModel):
    """Nuevo slot objetivo — P2 `extra='forbid'`."""

    model_config = ConfigDict(extra="forbid")

    nuevo_inicio: datetime


@router.post("/{turno_id}/reprogramar")
def reprogramar(
    turno_id: uuid.UUID,
    cuerpo: ReprogramarBody,
    request: Request,
    dni: str | None = None,
    token: str | None = None,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Atómica: origen → `reprogramado` + nuevo `confirmado` heredando `pago_id`.

    Mismo commit (origen + nuevo + ambos historiales); slot objetivo validado
    RN-PASADO/DOBLE/SOLAPE/ANTICIPACION antes del commit; carrera → rollback
    total (origen sigue `confirmado`). Seña original ante diferencia (Q3).
    """
    from app.infra.db.models import TurnoHistorial

    turno = _turno_o_404(db, turno_id)
    actor_tipo, actor_id, a_consumir = _actor_para_turno(request, db, turno, dni, token)
    if str(turno.estado) != "confirmado":
        return JSONResponse(status_code=422, content={
            "code": "REPROGRAMAR_SOLO_CONFIRMADO",
            "detail": "solo un turno confirmado puede reprogramarse"})
    settings = get_settings()
    ahora = datetime.now(UTC)
    nuevo = cuerpo.nuevo_inicio
    nuevo = nuevo if nuevo.tzinfo else nuevo.replace(tzinfo=UTC)
    if nuevo <= ahora:
        return JSONResponse(status_code=422, content={
            "code": "SLOT_NO_DISPONIBLE", "detail": "inicio en el pasado (RN-PASADO)"})
    if (nuevo - ahora).total_seconds() < settings.anticipacion_min_hs * 3600:
        return JSONResponse(status_code=422, content={
            "code": "SLOT_NO_DISPONIBLE",
            "detail": "fuera de anticipación mínima (RN-ANTICIPACION)"})
    zona = resolver_zona(settings.timezone)
    fin = _slot_ofrecido(db, uuid.UUID(str(turno.odontologo_id)), nuevo,
                         settings.reserva_ttl_min,
                         settings.anticipacion_min_hs, zona)
    if fin is None:
        if hay_solape(db, uuid.UUID(str(turno.odontologo_id)), nuevo,
                       nuevo + timedelta(minutes=30),
                       settings.reserva_ttl_min, ahora,
                       excluir_turno_id=uuid.UUID(str(turno.id))):
            return JSONResponse(status_code=409, content={
                "code": "SLOT_OCUPADO", "detail": "slot objetivo ocupado"})
        return JSONResponse(status_code=422, content={
            "code": "SLOT_NO_DISPONIBLE", "detail": "slot no ofrecible"})
    key = request.headers.get("Idempotency-Key") or request.headers.get("idempotency-key")
    nueva_key = key.strip() if key else f"reprog-{uuid.uuid4().hex}"
    if db.query(Turno).filter(Turno.idempotency_key == nueva_key).first() is not None:
        return JSONResponse(status_code=409, content={
            "code": "SLOT_OCUPADO", "detail": "Idempotency-Key ya usada"})

    origen_id = uuid.UUID(str(turno.id))
    try:
        transition(db, origen_id, "reprogramado",
                   actor_tipo=actor_tipo, actor_id=actor_id,
                   motivo=f"reprogramado a {nuevo.isoformat()}")
        nuevo_turno = Turno(
            paciente_id=turno.paciente_id, odontologo_id=turno.odontologo_id,
            inicio=nuevo, fin=fin, estado="confirmado", canal=str(turno.canal),
            idempotency_key=nueva_key, pago_id=turno.pago_id,
            reprogramado_de_id=origen_id)
        db.add(nuevo_turno)
        db.flush()
        db.add(TurnoHistorial(
            turno_id=nuevo_turno.id, estado_anterior="reprogramado",
            estado_nuevo="confirmado", actor_tipo=actor_tipo, actor_id=actor_id,
            fecha=ahora, motivo=f"reprogramado desde {origen_id}"))
        db.flush()
    except (TransicionInvalida, GuardaTemporalRechazada) as exc:
        db.rollback()
        return JSONResponse(status_code=422, content={
            "code": "TRANSICION_INVALIDA", "detail": str(exc)})
    except ActorNoAutorizado as exc:
        db.rollback()
        return JSONResponse(status_code=403, content={
            "code": "NO_AUTORIZADO", "detail": str(exc)})
    except (VersionConflict, IntegrityError) as exc:
        # La DB arbitra la carrera (UNIQUE/EXCLUDE): rollback total, origen intacto.
        db.rollback()
        return JSONResponse(status_code=409, content={
            "code": "SLOT_OCUPADO", "detail": str(exc)})
    db.commit()
    if a_consumir is not None:
        from app.api.pacientes import get_paciente_action_store

        get_paciente_action_store().consume(
            a_consumir, get_settings().jwt_action_min * 60)
    return JSONResponse(status_code=200, content={
        "origen": {"id": str(origen_id), "estado": "reprogramado"},
        "nuevo": {"id": str(nuevo_turno.id), "estado": "confirmado",
                  "pago_id": str(nuevo_turno.pago_id) if nuevo_turno.pago_id else None,
                  "reprogramado_de_id": str(origen_id)},
    })
