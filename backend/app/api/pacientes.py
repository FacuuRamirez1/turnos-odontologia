"""Router ficha mínima C-06 — POST staff + reconocimiento A2 + historial acotado.

- Staff-only (`require_role("odontologo","recepcionista","admin")`, P8) salvo
  self-service por mail-action token (seam C-03) en detalle/historial.
- Schemas Pydantic v2 `extra='forbid'` (P2); DNI 7–8 dígitos normalizado.
- Gate RN-CONSENTIMIENTO en `PacienteService` → 422 `CONSENTIMIENTO_REQUERIDO`
  sin persistir nada (design D1). Duplicado → 409.
- Rate-limit staff 60/min por IP (hereda `LoginRateLimiter` C-03, P12 § ráfaga).
- Historial: `SELECT` solo columnas del contrato contra `turno` (design D2/D3);
  sin tabla (pre-C-05) → `[]` en vez de 500 (deploy incremental).
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.core.security.action_tokens import ActionTokenStore, build_action_store
from app.core.security.dependencies import Identity, get_jwt_secret, require_role
from app.core.security.jwt import AuthError, decode_and_validate
from app.core.settings import get_settings
from app.domain.pacientes.service import (
    ConsentimientoRequerido,
    PacienteDuplicado,
    PacienteService,
    normalizar_dni,
    validar_formato_dni,
)
from app.infra.db.models import Paciente
from app.infra.db.session import get_db
from app.infra.redis.rate_limit import LoginRateLimiter, build_rate_limiter

router = APIRouter(prefix="/pacientes", tags=["pacientes"])
STAFF = require_role("odontologo", "recepcionista", "admin")
U422 = status.HTTP_422_UNPROCESSABLE_ENTITY

PACIENTES_LIMIT = 60
PACIENTES_WINDOW = 60

_pacientes_limiter: LoginRateLimiter | None = None
_action_store: ActionTokenStore | None = None


def get_pacientes_limiter() -> LoginRateLimiter:
    """Limitador staff (lazy env; `reset_pacientes_limiter` lo renueva en tests)."""
    global _pacientes_limiter
    if _pacientes_limiter is None:
        _pacientes_limiter = build_rate_limiter(
            get_settings().redis_url, limit=PACIENTES_LIMIT, window_seconds=PACIENTES_WINDOW
        )
    return _pacientes_limiter


def reset_pacientes_limiter(
    limit: int = PACIENTES_LIMIT, window_seconds: int = PACIENTES_WINDOW
) -> None:
    """Renueva el limitador en memoria (seam solo para tests)."""
    global _pacientes_limiter
    _pacientes_limiter = LoginRateLimiter(client=None, limit=limit, window_seconds=window_seconds)


def get_paciente_action_store() -> ActionTokenStore:
    """Store de mail-action tokens (un uso; `reset_paciente_action_store` en tests)."""
    global _action_store
    if _action_store is None:
        _action_store = build_action_store(get_settings().redis_url)
    return _action_store


def reset_paciente_action_store() -> None:
    """Renueva el store en memoria (seam solo para tests)."""
    global _action_store
    _action_store = ActionTokenStore(client=None)


def _rate_limit_or_429(request: Request) -> None:
    ip = request.client.host if request.client is not None else "desconocida"
    if not get_pacientes_limiter().check_and_count(f"pacientes:ratelimit:{ip}"):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "demasiadas consultas")


class PacienteCreate(BaseModel):
    """Alta de ficha mínima — P2 `extra='forbid'`."""

    model_config = ConfigDict(extra="forbid")

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


class PacienteUpdate(BaseModel):
    """Edición parcial de contacto — P2 `extra='forbid'` (DNI inmutable)."""

    model_config = ConfigDict(extra="forbid")

    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    apellido: str | None = Field(default=None, min_length=1, max_length=120)
    email: str | None = Field(default=None, max_length=255)
    telefono: str | None = Field(default=None, max_length=50)


class PacienteRead(BaseModel):
    """Ficha mínima expuesta — P2 `extra='forbid'`, sin nada clínico por construcción."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    dni: str
    nombre: str
    apellido: str
    email: str | None = None
    telefono: str | None = None
    consentimiento_datos: bool
    consentimiento_fecha: datetime | None = None


class ReconocimientoOut(BaseModel):
    """Respuesta uniforme A2 `{found, paciente|null}` — 200 siempre (design D4)."""

    model_config = ConfigDict(extra="forbid")

    found: bool
    paciente: PacienteRead | None = None


class TurnoAcotado(BaseModel):
    """Ventana acotada no-clínica — schema cerrado (design D2)."""

    model_config = ConfigDict(extra="forbid")

    turno_id: uuid.UUID
    odontologo_id: uuid.UUID
    inicio: datetime
    fin: datetime
    estado: str


def _out(fila: Paciente) -> PacienteRead:
    return PacienteRead(
        id=uuid.UUID(str(fila.id)),
        dni=fila.dni,
        nombre=fila.nombre,
        apellido=fila.apellido,
        email=fila.email,
        telefono=fila.telefono,
        consentimiento_datos=bool(fila.consentimiento_datos),
        consentimiento_fecha=fila.consentimiento_fecha,
    )


def _consentimiento_422() -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "code": "CONSENTIMIENTO_REQUERIDO",
            "detail": "se requiere consentimiento_datos=true con fecha",
        },
    )


@router.post("", response_model=PacienteRead, status_code=201)
def crear_paciente(
    body: PacienteCreate,
    request: Request,
    ident: Identity = Depends(STAFF),
    db: Session = Depends(get_db),
) -> PacienteRead:
    """Alta manual staff con gate bloqueante (nada persiste sin consentimiento)."""
    _ = ident
    _rate_limit_or_429(request)
    try:
        fila = PacienteService(db).create(
            dni=body.dni,
            nombre=body.nombre,
            apellido=body.apellido,
            email=body.email,
            telefono=body.telefono,
            consentimiento_datos=body.consentimiento_datos,
            consentimiento_fecha=body.consentimiento_fecha,
        )
    except ConsentimientoRequerido:
        return _consentimiento_422()  # type: ignore[return-value]
    except PacienteDuplicado as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return _out(fila)


@router.get("", response_model=ReconocimientoOut)
def reconocer_por_dni(
    request: Request,
    dni: str = Query(min_length=1, max_length=20),
    ident: Identity = Depends(STAFF),
    db: Session = Depends(get_db),
) -> ReconocimientoOut:
    """Reconocimiento A2: match exacto normalizado → ficha; sin match → 200 vacío."""
    _ = ident
    _rate_limit_or_429(request)
    try:
        normalizado = normalizar_dni(dni)
        validar_formato_dni(normalizado)
    except ValueError as exc:
        raise HTTPException(U422, str(exc)) from exc
    fila = (
        db.query(Paciente)
        .filter(Paciente.dni == normalizado, Paciente.is_active.is_(True))
        .first()
    )
    if fila is None:
        return ReconocimientoOut(found=False, paciente=None)
    return ReconocimientoOut(found=True, paciente=_out(fila))


def _identidad_staff_opcional(request: Request) -> Identity | None:
    """Staff Bearer opcional: `None` si falta/inválido (luego se prueba action-token)."""
    auth = request.headers.get("authorization")
    if not auth or not auth.lower().startswith("bearer "):
        return None
    raw = auth.split(" ", 1)[1].strip()
    try:
        claims = decode_and_validate(raw, "access", get_jwt_secret())
    except AuthError:
        return None
    odontologo_id = claims.get("odontologo_id")
    return Identity(
        sub=str(claims["sub"]),
        rol=str(claims.get("rol", "")),
        odontologo_id=str(odontologo_id) if odontologo_id is not None else None,
        jti=str(claims["jti"]),
    )


def _autorizar_ficha(
    request: Request, paciente_id: uuid.UUID, token_query: str | None = None
) -> Identity | dict[str, object]:
    """Staff JWT o mail-action propio; mismatch → 403, sin token → 401 (P12)."""
    staff = _identidad_staff_opcional(request)
    if staff is not None:
        if staff.rol not in ("odontologo", "recepcionista", "admin"):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "rol no autorizado")
        if staff.rol == "odontologo" and staff.odontologo_id is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "odontólogo sin perfil vinculado")
        return staff
    raw = token_query
    if raw is None:
        auth = request.headers.get("authorization")
        if auth and auth.lower().startswith("bearer "):
            raw = auth.split(" ", 1)[1].strip()
    if not raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "se requiere autenticación")
    try:
        claims = decode_and_validate(raw, "action", get_jwt_secret())
    except AuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    if not get_paciente_action_store().consume(raw, get_settings().jwt_action_min * 60):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token de acción ya usado")
    if str(claims.get("sub")) != str(paciente_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "token no autoriza esta ficha")
    return {"sub": str(claims.get("sub")), "proposito": str(claims.get("proposito", ""))}


@router.get("/{paciente_id}", response_model=PacienteRead)
def ver_ficha(
    paciente_id: uuid.UUID,
    request: Request,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> PacienteRead:
    """Detalle: staff ve cualquiera; paciente solo la propia vía mail-action token."""
    _rate_limit_or_429(request)
    _autorizar_ficha(request, paciente_id, token)
    fila = (
        db.query(Paciente)
        .filter(Paciente.id == paciente_id, Paciente.is_active.is_(True))
        .first()
    )
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "paciente inexistente")
    return _out(fila)


@router.patch("/{paciente_id}", response_model=PacienteRead)
def editar_ficha(
    paciente_id: uuid.UUID,
    body: PacienteUpdate,
    request: Request,
    ident: Identity = Depends(STAFF),
    db: Session = Depends(get_db),
) -> PacienteRead:
    """Edición staff de contacto (DNI inmutable); inexistente → 404."""
    _ = ident
    _rate_limit_or_429(request)
    fila = (
        db.query(Paciente)
        .filter(Paciente.id == paciente_id, Paciente.is_active.is_(True))
        .first()
    )
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "paciente inexistente")
    datos = body.model_dump(exclude_unset=True)
    for campo, valor in datos.items():
        setattr(fila, campo, valor.strip() if isinstance(valor, str) else valor)
    db.commit()
    db.refresh(fila)
    return _out(fila)


def _historial_filas(
    db: Session, paciente_id: uuid.UUID, odontologo_id: uuid.UUID | None = None
) -> list[TurnoAcotado]:
    """Query ORM solo-columnas-contrato (design D3; portable PG/SQLite)."""
    from app.infra.db.models import Turno

    query = (
        db.query(Turno)
        .filter(Turno.paciente_id == paciente_id, Turno.is_active.is_(True))
        .order_by(Turno.inicio.asc(), Turno.id.asc())
    )
    if odontologo_id is not None:
        query = query.filter(Turno.odontologo_id == odontologo_id)
    return [
        TurnoAcotado(
            turno_id=uuid.UUID(str(f.id)),
            odontologo_id=uuid.UUID(str(f.odontologo_id)),
            inicio=f.inicio,
            fin=f.fin,
            estado=str(f.estado),
        )
        for f in query.all()
    ]


@router.get("/{paciente_id}/turnos", response_model=list[TurnoAcotado])
def historial(
    paciente_id: uuid.UUID,
    request: Request,
    token: str | None = Query(default=None),
    odontologo_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[TurnoAcotado]:
    """Historial acotado pasado+futuro; staff o propio vía mail-action (mismatch → 403).

    Filtro `?odontologo_id` opt-in (default sin filtrar — design D-riesgo 2).
    """
    _rate_limit_or_429(request)
    acceso = _autorizar_ficha(request, paciente_id, token)
    fila = (
        db.query(Paciente)
        .filter(Paciente.id == paciente_id, Paciente.is_active.is_(True))
        .first()
    )
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "paciente inexistente")
    _ = acceso
    return _historial_filas(db, paciente_id, odontologo_id)
