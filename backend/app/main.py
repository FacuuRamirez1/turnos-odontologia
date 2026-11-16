"""FastAPI minima C-01 — solo GET /api/health, sin logica de dominio."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.agenda import router as agenda_router
from app.api.auth import router as auth_router
from app.api.comprobantes import router as comprobantes_router
from app.api.devoluciones import router as devoluciones_router
from app.api.disponibilidad import router as disponibilidad_router
from app.api.health import router as health_router
from app.api.mail import router as mail_router
from app.api.mis_turnos import router as mis_turnos_router
from app.api.odontologos import router as odontologos_router
from app.api.pacientes import router as pacientes_router
from app.api.pagos import router as pagos_router
from app.api.public_disponibilidad import router as publica_disponibilidad_router
from app.api.reservas import router as reservas_router
from app.core.errors import (
    ErrorEnvelope,
    internal_error_handler,
    logging_middleware,
    not_found_handler,
)
from app.core.settings import Settings, get_settings

logging.basicConfig(level=logging.INFO)


def verificar_guard_produccion(settings: Settings | None = None) -> None:
    """P15: modo simulado prohibido en producción."""
    cfg = settings or get_settings()
    if cfg.environment == "production" and cfg.pago_modo == "simulado":
        raise ValueError(
            "P15: PAGO_MODO=simulado prohibido en ENVIRONMENT=production"
        )


app = FastAPI(title="Turnos Odontología", version="0.1.0")

# --- P15: guard de arranque — modo simulado prohibido en producción ---
verificar_guard_produccion()

app.middleware("http")(logging_middleware)
app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(disponibilidad_router, prefix="/api")
app.include_router(odontologos_router, prefix="/api")
app.include_router(pacientes_router, prefix="/api")
app.include_router(pagos_router, prefix="/api")
app.include_router(devoluciones_router, prefix="/api")
app.include_router(comprobantes_router, prefix="/api")
app.include_router(publica_disponibilidad_router, prefix="/api")
app.include_router(reservas_router, prefix="/api")
app.include_router(agenda_router, prefix="/api")
app.include_router(mis_turnos_router, prefix="/api")
app.include_router(mail_router, prefix="/api")
app.add_exception_handler(404, not_found_handler)
app.add_exception_handler(500, internal_error_handler)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    path = request.url.path
    status = exc.status_code
    if status == 404:
        return await not_found_handler(request, exc)
    return JSONResponse(
        status_code=status,
        content=ErrorEnvelope(
            error="http_error",
            detail=str(exc.detail),
            path=path,
        ).model_dump(),
    )


@app.exception_handler(HTTPException)
async def fastapi_http_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return await http_exception_handler(request, exc)
