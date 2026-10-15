"""Settings centralizados C-01 — solo env vars, cero secretos hardcodeados (P5)."""

from pydantic import Field
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


def get_settings() -> Settings:
    return Settings()
