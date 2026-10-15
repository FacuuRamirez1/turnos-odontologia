"""Envelope de error consistente + logging de request (C-01 §2.3)."""

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger("turnos-odontologia")


class ErrorEnvelope(BaseModel):
    """Envelope estable para errores — P2 extra='forbid'."""

    model_config = ConfigDict(extra="forbid")

    error: str
    detail: str
    path: str


async def logging_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s -> %s (%.1fms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


async def not_found_handler(request: Request, _exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=ErrorEnvelope(
            error="not_found",
            detail=f"Ruta no encontrada: {request.url.path}",
            path=request.url.path,
        ).model_dump(),
    )


async def internal_error_handler(request: Request, _exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content=ErrorEnvelope(
            error="internal_error",
            detail="Error interno del servidor",
            path=request.url.path,
        ).model_dump(),
    )
