"""Application configuration via pydantic-settings.
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Supabase / Database settings
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"
    SUPABASE_URL: str = "https://ncjejgcosipagizirjxs.supabase.co"
    SUPABASE_ANON_KEY: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5jamVqZ2Nvc2lwYWdpemlyanhzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODc1ODY2MzQsImV4cCI6MjEwMzE2MjYzNH0.swzM3VfO-FLilm93D_AwTjRoJlAxWGjMZfgHPt1WrHw"
    
    # ML settings
    ML_MODEL_DIR: str = str(Path(__file__).resolve().parent.parent.parent / "ml" / "models")
    
    # Anomaly thresholds
    ANOMALY_THRESHOLD: float = 0.5
    CRITICAL_THRESHOLD: float = 0.8
    HEALTH_MAINTENANCE_THRESHOLD: float = 40.0
    HEALTH_CRITICAL_THRESHOLD: float = 15.0
    
    # WebSocket and CORS
    WS_CHANNEL: str = "skyguard_live"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000,*"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
