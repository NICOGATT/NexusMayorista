"""Configuración por entorno, leída de variables de entorno o de `backend/.env`."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    entorno: str = Field(default="desarrollo", alias="ENTORNO")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Base de datos (Supabase / PostgreSQL)
    database_url: str = Field(alias="DATABASE_URL")

    # Supabase
    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_service_role_key: str = Field(default="", alias="SUPABASE_SERVICE_ROLE_KEY")
    supabase_jwt_secret: str = Field(alias="SUPABASE_JWT_SECRET")
    supabase_jwt_audience: str = Field(default="authenticated", alias="SUPABASE_JWT_AUDIENCE")

    # Claude
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")

    # Meta / WhatsApp
    meta_app_secret: str = Field(default="", alias="META_APP_SECRET")
    meta_verify_token: str = Field(default="", alias="META_VERIFY_TOKEN")
    whatsapp_token: str = Field(default="", alias="WHATSAPP_TOKEN")
    whatsapp_phone_number_id: str = Field(default="", alias="WHATSAPP_PHONE_NUMBER_ID")

    @property
    def sqlalchemy_url(self) -> str:
        """URL para SQLAlchemy con el driver psycopg 3.

        Supabase entrega `postgresql://...`; SQLAlchemy usaría psycopg2 por defecto.
        """
        url = self.database_url
        for prefijo in ("postgres://", "postgresql://"):
            if url.startswith(prefijo):
                return "postgresql+psycopg://" + url[len(prefijo) :]
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
