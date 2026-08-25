"""SQLAlchemy models and database connection utilities for SkyGuard AI.
Mirrors the Supabase schema specified in /docs/HANDOFF.md §1.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, relationship

from app.config import settings

Base = declarative_base()


def utcnow():
    return datetime.now(timezone.utc)


class Station(Base):
    __tablename__ = "stations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    station_code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    elevation_m = Column(Float, nullable=True)
    state = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True)
    station_type = Column(String(50), default="AWS")
    expected_interval_min = Column(Integer, default=15)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    observations = relationship("Observation", back_populates="station", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="station", cascade="all, delete-orphan")
    health_history = relationship("SensorHealthHistory", back_populates="station", cascade="all, delete-orphan")


class Observation(Base):
    __tablename__ = "observations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    station_id = Column(String(36), ForeignKey("stations.id", ondelete="CASCADE"), nullable=False, index=True)
    observed_at = Column(DateTime(timezone=True), nullable=False, index=True)
    temperature = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    pressure = Column(Float, nullable=True)
    wind_speed = Column(Float, nullable=True)
    wind_direction = Column(Float, nullable=True)
    rainfall = Column(Float, nullable=True)
    solar_radiation = Column(Float, nullable=True)
    ingested_at = Column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        UniqueConstraint("station_id", "observed_at", name="uq_station_observed_at"),
    )

    station = relationship("Station", back_populates="observations")
    anomaly_score = relationship("AnomalyScore", back_populates="observation", uselist=False, cascade="all, delete-orphan")
    corrected_values = relationship("CorrectedValue", back_populates="observation", cascade="all, delete-orphan")


class AnomalyScore(Base):
    __tablename__ = "anomaly_scores"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    observation_id = Column(String(36), ForeignKey("observations.id", ondelete="CASCADE"), unique=True, nullable=False)
    qc_score = Column(Float, nullable=False)
    if_score = Column(Float, nullable=False)
    ae_score = Column(Float, nullable=False)
    fused_score = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    is_anomaly = Column(Boolean, nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)  # 'normal', 'warning', 'critical'
    root_cause = Column(String(30), nullable=True, index=True)  # 'spike', 'frozen', 'drift', 'communication', 'multivariate'
    explanation = Column(Text, nullable=True)
    qc_flags = Column(JSONB, default=dict)
    shap_values = Column(JSONB, default=dict)
    scored_at = Column(DateTime(timezone=True), default=utcnow)

    observation = relationship("Observation", back_populates="anomaly_score")
    alerts = relationship("Alert", back_populates="anomaly_score")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    station_id = Column(String(36), ForeignKey("stations.id", ondelete="CASCADE"), nullable=False, index=True)
    anomaly_score_id = Column(String(36), ForeignKey("anomaly_scores.id", ondelete="SET NULL"), nullable=True)
    alert_type = Column(String(30), nullable=False)  # 'anomaly', 'health_degraded', 'maintenance_required', 'communication_loss'
    severity = Column(String(20), nullable=False, index=True)  # 'info', 'warning', 'critical'
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    parameter = Column(String(50), nullable=True)
    is_resolved = Column(Boolean, default=False, index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    station = relationship("Station", back_populates="alerts")
    anomaly_score = relationship("AnomalyScore", back_populates="alerts")


class SensorHealthHistory(Base):
    __tablename__ = "sensor_health_history"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    station_id = Column(String(36), ForeignKey("stations.id", ondelete="CASCADE"), nullable=False, index=True)
    parameter = Column(String(50), nullable=False)
    health_score = Column(Float, nullable=False)
    status = Column(String(30), nullable=False, index=True)  # 'healthy', 'degraded', 'maintenance_recommended', 'sensor_critical'
    anomaly_streak = Column(Integer, default=0)
    recorded_at = Column(DateTime(timezone=True), default=utcnow, index=True)

    station = relationship("Station", back_populates="health_history")


class CorrectedValue(Base):
    __tablename__ = "corrected_values"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    observation_id = Column(String(36), ForeignKey("observations.id", ondelete="CASCADE"), nullable=False, index=True)
    parameter = Column(String(50), nullable=False)
    raw_value = Column(Float, nullable=True)
    corrected_value = Column(Float, nullable=True)
    correction_method = Column(String(50), nullable=False)  # 'temporal_median', 'interpolation', 'diurnal_trend', 'cross_parameter_regression', 'none'
    correction_confidence = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        UniqueConstraint("observation_id", "parameter", name="uq_observation_parameter"),
    )

    observation = relationship("Observation", back_populates="corrected_values")


# ==============================================================================
# Supabase PostgREST Async Client (Direct & High-Performance)
# ==============================================================================

class SupabaseDB:
    def __init__(self):
        self.base_url = f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1"
        self.headers = {
            "apikey": settings.SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_ANON_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        limits = httpx.Limits(max_keepalive_connections=30, max_connections=100, keepalive_expiry=120.0)
        self.client = httpx.AsyncClient(timeout=15.0, limits=limits)

    async def get_client(self) -> httpx.AsyncClient:
        if self.client is None or self.client.is_closed:
            limits = httpx.Limits(max_keepalive_connections=30, max_connections=100, keepalive_expiry=120.0)
            self.client = httpx.AsyncClient(timeout=15.0, limits=limits)
        return self.client

    async def close(self):
        if self.client and not self.client.is_closed:
            await self.client.aclose()

    async def select(self, table: str, params: Optional[Dict[str, Any]] = None, select_fields: Optional[str] = None) -> List[Dict[str, Any]]:
        client = await self.get_client()
        url = f"{self.base_url}/{table}"
        p = dict(params or {})
        if select_fields:
            p["select"] = select_fields
        response = await client.get(url, headers=self.headers, params=p)
        if response.status_code >= 400:
            raise RuntimeError(f"Supabase GET {table} failed: {response.status_code} {response.text}")
        return response.json()

    async def count(self, table: str, params: Optional[Dict[str, Any]] = None) -> int:
        client = await self.get_client()
        url = f"{self.base_url}/{table}"
        headers = dict(self.headers)
        headers["Prefer"] = "count=exact"
        p = dict(params or {})
        p["limit"] = 0
        response = await client.get(url, headers=headers, params=p)
        if "content-range" in response.headers:
            cr = response.headers["content-range"]
            if "/" in cr:
                total = cr.split("/")[-1]
                if total.isdigit():
                    return int(total)
        return 0

    async def insert(self, table: str, data: Any, on_conflict: Optional[str] = None) -> List[Dict[str, Any]]:
        client = await self.get_client()
        url = f"{self.base_url}/{table}"
        headers = dict(self.headers)
        params = {}
        if on_conflict:
            headers["Prefer"] = "resolution=merge-duplicates,return=representation"
            params["on_conflict"] = on_conflict
        response = await client.post(url, headers=headers, params=params, json=data)
        if response.status_code >= 400:
            raise RuntimeError(f"Supabase POST {table} failed: {response.status_code} {response.text}")
        return response.json() if response.text else []

    async def update(self, table: str, params: Dict[str, Any], data: Dict[str, Any]) -> List[Dict[str, Any]]:
        client = await self.get_client()
        url = f"{self.base_url}/{table}"
        response = await client.patch(url, headers=self.headers, params=params, json=data)
        if response.status_code >= 400:
            raise RuntimeError(f"Supabase PATCH {table} failed: {response.status_code} {response.text}")
        return response.json() if response.text else []

    async def delete(self, table: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        client = await self.get_client()
        url = f"{self.base_url}/{table}"
        response = await client.delete(url, headers=self.headers, params=params)
        if response.status_code >= 400:
            raise RuntimeError(f"Supabase DELETE {table} failed: {response.status_code} {response.text}")
        return response.json() if response.text else []


db_client = SupabaseDB()
