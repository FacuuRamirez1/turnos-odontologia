"""Modelos y router de salud — unico endpoint de C-01."""

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Respuesta de GET /api/health — P2 extra='forbid'."""

    model_config = ConfigDict(extra="forbid")

    status: str
    service: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="turnos-odontologia")
