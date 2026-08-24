"""Pydantic schemas for SkyGuard AI API endpoints.
Defines all request/response models specified in /docs/HANDOFF.md §8.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


# Parameter constants
PARAMETERS = [
    "temperature",
    "humidity",
    "pressure",
    "wind_speed",
    "wind_direction",
    "rainfall",
    "solar_radiation",
]


# ==============================================================================
# Observation Schemas
# ==============================================================================

class ObservationInput(BaseModel):
    station_code: str = Field(..., example="AWS_MUM_001")
    observed_at: datetime = Field(..., example="2026-08-24T10:30:00Z")
    temperature: Optional[float] = Field(None, example=32.5)
    humidity: Optional[float] = Field(None, example=78.2)
    pressure: Optional[float] = Field(None, example=1008.3)
    wind_speed: Optional[float] = Field(None, example=4.2)
    wind_direction: Optional[float] = Field(None, example=225.0)
    rainfall: Optional[float] = Field(None, example=0.0)
    solar_radiation: Optional[float] = Field(None, example=650.0)


class ObservationBatchInput(BaseModel):
    observations: List[ObservationInput]


class AnomalySummary(BaseModel):
    fused_score: float
    is_anomaly: bool
    severity: str  # 'normal', 'warning', 'critical'
    root_cause: Optional[str] = None  # 'spike', 'frozen', 'drift', 'communication', 'multivariate'
    confidence: float
    explanation: Optional[str] = None


class ObservationIngestResponse(BaseModel):
    observation_id: str
    anomaly: AnomalySummary


class BatchIngestError(BaseModel):
    index: int
    error: str


class ObservationBatchResponse(BaseModel):
    results: List[ObservationIngestResponse]
    accepted: int
    rejected: int
    errors: List[BatchIngestError] = []


# ==============================================================================
# Station Schemas
# ==============================================================================

class StationCreate(BaseModel):
    station_code: str
    name: str
    latitude: float
    longitude: float
    elevation_m: Optional[float] = None
    state: Optional[str] = None
    district: Optional[str] = None
    station_type: Optional[str] = "AWS"
    expected_interval_min: Optional[int] = 15


class StationResponse(BaseModel):
    id: str
    station_code: str
    name: str
    latitude: float
    longitude: float
    elevation_m: Optional[float] = None
    state: Optional[str] = None
    district: Optional[str] = None
    station_type: str = "AWS"
    expected_interval_min: int = 15
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class StationWithHealth(BaseModel):
    id: str
    station_code: str
    name: str
    latitude: float
    longitude: float
    elevation_m: Optional[float] = None
    state: Optional[str] = None
    district: Optional[str] = None
    station_type: str = "AWS"
    expected_interval_min: int = 15
    is_active: bool = True
    overall_health: float
    health_status: str
    last_observation_at: Optional[datetime] = None
    active_alerts: int = 0


class StationListResponse(BaseModel):
    stations: List[StationWithHealth]
    total: int
    page: int


# ==============================================================================
# Health Schemas
# ==============================================================================

class ParameterHealthDetail(BaseModel):
    score: float
    status: str  # 'healthy', 'degraded', 'maintenance_recommended', 'sensor_critical'
    anomaly_streak: int = 0
    last_updated: Optional[datetime] = None


class HealthResponse(BaseModel):
    station_id: str
    overall_health: float
    overall_status: str
    parameters: Dict[str, ParameterHealthDetail]


class HealthHistoryItem(BaseModel):
    recorded_at: datetime
    parameter: str
    health_score: float
    status: str


class HealthHistoryResponse(BaseModel):
    history: List[HealthHistoryItem]


# ==============================================================================
# Alert Schemas
# ==============================================================================

class AlertResponse(BaseModel):
    id: str
    station_id: str
    station_name: Optional[str] = None
    station_code: Optional[str] = None
    anomaly_score_id: Optional[str] = None
    alert_type: str
    severity: str  # 'info', 'warning', 'critical'
    title: str
    description: Optional[str] = None
    parameter: Optional[str] = None
    is_resolved: bool = False
    resolved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class AlertListResponse(BaseModel):
    alerts: List[AlertResponse]
    total: int
    page: int


# ==============================================================================
# Corrected Value Schemas
# ==============================================================================

class CorrectedValueSchema(BaseModel):
    parameter: str
    raw_value: Optional[float] = None
    corrected_value: Optional[float] = None
    correction_method: str  # 'temporal_median', 'interpolation', 'diurnal_trend', 'cross_parameter_regression', 'none'
    correction_confidence: float = 0.0


# ==============================================================================
# Anomaly Schemas
# ==============================================================================

class AnomalyListItem(BaseModel):
    id: str
    observation_id: str
    station_id: Optional[str] = None
    station_code: Optional[str] = None
    station_name: Optional[str] = None
    observed_at: datetime
    fused_score: float
    severity: str
    root_cause: Optional[str] = None
    confidence: float
    explanation: Optional[str] = None
    scored_at: Optional[datetime] = None


class AnomalyListResponse(BaseModel):
    anomalies: List[AnomalyListItem]
    total: int
    page: int


class AnomalyScoreDetail(BaseModel):
    id: str
    qc_score: float
    if_score: float
    ae_score: float
    fused_score: float
    confidence: float
    is_anomaly: bool
    severity: str
    root_cause: Optional[str] = None
    explanation: Optional[str] = None
    qc_flags: Dict[str, Any] = {}
    shap_values: Dict[str, Any] = {}


class AnomalyDetailResponse(BaseModel):
    anomaly: AnomalyScoreDetail
    observation: Dict[str, Any]
    corrected_values: List[CorrectedValueSchema] = []


# ==============================================================================
# Station Detail Schemas
# ==============================================================================

class StationDetailResponse(BaseModel):
    station: StationResponse
    health: HealthResponse
    recent_alerts: List[AlertResponse] = []
    last_observation: Optional[Dict[str, Any]] = None


# ==============================================================================
# Dashboard Summary Schemas
# ==============================================================================

class DashboardSummary(BaseModel):
    total_stations: int
    active_stations: int
    anomalies_24h: int
    critical_alerts: int
    avg_health: float
    stations_needing_maintenance: int
    observations_24h: int


# ==============================================================================
# Demo Endpoints Schemas
# ==============================================================================

class DemoInjectRequest(BaseModel):
    station_id: str
    anomaly_type: str = Field(..., example="spike")  # 'spike', 'frozen', 'drift', 'missing', 'multivariate'
    parameters: Optional[List[str]] = Field(None, example=["temperature"])
    duration_minutes: Optional[int] = 30
    magnitude: Optional[float] = 3.0


class DemoInjectResponse(BaseModel):
    injected_observations: List[str]
    anomaly_type: str
    affected_parameters: List[str]
    message: str


class DemoGenerateRequest(BaseModel):
    station_id: str
    hours: int = 24
    interval_min: Optional[int] = 15


class DemoGenerateResponse(BaseModel):
    observation_count: int
    from_time: str
    to_time: str
    message: str


# ==============================================================================
# WebSocket Message Schemas
# ==============================================================================

class WebSocketSubscription(BaseModel):
    action: str = "subscribe"
    station_ids: Optional[List[str]] = None


class WebSocketMessage(BaseModel):
    type: str  # 'anomaly', 'alert', 'health_update'
    data: Dict[str, Any]
