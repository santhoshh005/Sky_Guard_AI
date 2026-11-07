"""Application configuration via pydantic-settings.

All secrets come from the environment (or a local, git-ignored ``backend/.env``).
Nothing sensitive is hardcoded here.
"""
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    # Supabase PostgREST connection (required for a working deployment)
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    DB_TIMEOUT_SECONDS: float = 15.0

    # ML artifacts
    ML_MODEL_DIR: str = str(PROJECT_ROOT / "ml" / "models")

    # Anomaly / health thresholds
    ANOMALY_THRESHOLD: float = 0.5
    CRITICAL_THRESHOLD: float = 0.8
    HEALTH_MAINTENANCE_THRESHOLD: float = 40.0
    HEALTH_CRITICAL_THRESHOLD: float = 15.0

    # Comma-separated list of allowed browser origins. "*" disables credentials.
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000"

    # Optional shared secret. When set, every write endpoint (ingestion, station
    # creation, alert resolution, demo injection) requires header `X-API-Key`.
    API_KEY: str = ""

    # Demo / fault-injection endpoints. Disable in production.
    ENABLE_DEMO_ENDPOINTS: bool = True

    # Request-size guards
    MAX_BATCH_SIZE: int = 500
    MAX_DEMO_GENERATE_HOURS: int = 72

    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=(str(BACKEND_DIR / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
