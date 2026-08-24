"""Application configuration via pydantic-settings.

Implement Settings class with:
- DATABASE_URL: str (Supabase PostgreSQL connection string)
- SUPABASE_URL: str
- SUPABASE_ANON_KEY: str
- ML_MODEL_DIR: str = 'ml/models'
- ANOMALY_THRESHOLD: float = 0.5
- CRITICAL_THRESHOLD: float = 0.8
- HEALTH_MAINTENANCE_THRESHOLD: float = 40.0
- WS_CHANNEL: str = 'skyguard_live'
"""
