"""FastAPI minima C-01 — solo GET /api/health, sin logica de dominio."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.auth import router as auth_router
from app.api.disponibilidad import router as disponibilidad_router
from app.api.health import router as health_router
from app.api.odontologos import router as odontologos_router
from app.api.pacientes import router as pacientes_router
from app.api.public_disponibilidad import router as publica_disponibilidad_router
from app.core.errors import (
    ErrorEnvelope,
    internal_error_handler,
    logging_middleware,
    not_found_handler,
)

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Turnos Odontología", version="0.1.0")

app.middleware("http")(logging_middleware)
app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(disponibilidad_router, prefix="/api")
app.include_router(odontologos_router, prefix="/api")
app.include_router(pacientes_router, prefix="/api")
app.include_router(publica_disponibilidad_router, prefix="/api")
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
