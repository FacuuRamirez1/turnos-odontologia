"""Settings centralizados C-01 — solo env vars, cero secretos hardcodeados (P5).

C-03 agrega TTLs JWT + `ENVIRONMENT` (falla en producción sin secreto real).
"""

from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Contrato de entorno v1 — ver .env.example y 08 §4."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(
        default="postgresql+psycopg://turnos:turnos@localhost:5432/turnos",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    jwt_secret: str = Field(default="cambiar-en-produccion", alias="JWT_SECRET")
    mp_access_token: str = Field(default="", alias="MP_ACCESS_TOKEN")
    mp_webhook_secret: str = Field(default="", alias="MP_WEBHOOK_SECRET")
    smtp_host: str = Field(default="localhost", alias="SMTP_HOST")
    smtp_port: int = Field(default=1025, alias="SMTP_PORT")
    smtp_user: str = Field(default="", alias="SMTP_USER")
    smtp_pass: str = Field(default="", alias="SMTP_PASS")
    mail_from: str = Field(
        default="turnos@clinica-ficticia.example.ar",
        alias="MAIL_FROM",
    )
    recordatorio_ventana_hs: int = Field(default=24, alias="RECORDATORIO_VENTANA_HS")
    reserva_ttl_min: int = Field(default=15, alias="RESERVA_TTL_MIN")
    frontend_url: str = Field(default="http://localhost:5173", alias="FRONTEND_URL")
    whatsapp_enabled: bool = Field(default=False, alias="WHATSAPP_ENABLED")
    arca_enabled: bool = Field(default=False, alias="ARCA_ENABLED")
    # --- Auth JWT C-03 (design D7) ---
    jwt_access_min: int = Field(default=15, alias="JWT_ACCESS_MIN")
    jwt_refresh_dias: int = Field(default=7, alias="JWT_REFRESH_DIAS")
    jwt_action_min: int = Field(default=15, alias="JWT_ACTION_MIN")
    environment: str = Field(default="dev", alias="ENVIRONMENT")
    # --- Disponibilidad C-04 (design D-ANT + D-TZ) ---
    anticipacion_min_hs: int = Field(default=24, alias="ANTICIPACION_MIN_HS")
    timezone: str = Field(default="America/Argentina/Cordoba", alias="TIMEZONE")
    # --- Reserva pública C-05 (design D8: rate-limit tunable) ---
    reserva_rate_limit: int = Field(default=10, alias="RESERVA_RATE_LIMIT")

    @model_validator(mode="after")
    def _rechazar_secreto_debil_en_produccion(self) -> Self:
        """P5: en producción no se firma con vacío ni con el placeholder de ejemplo."""
        if self.environment == "production" and self.jwt_secret in (
            "",
            "cambiar-en-produccion",
        ):
            raise ValueError("JWT_SECRET debe ser un secreto real en producción (P5).")
        return self

    @property
    def cookie_secure(self) -> bool:
        """`Secure` solo con TLS: http local → False, resto → True (design Riesgos)."""
        return not self.frontend_url.startswith(("http://localhost", "http://127."))


def get_settings() -> Settings:
    return Settings()
