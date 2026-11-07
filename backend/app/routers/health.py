"""Sensor health endpoints for SkyGuard AI.
Implements GET /health/{station_id} and GET /health/{station_id}/history.
Specified in /docs/HANDOFF.md §8.5.
"""
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.database import db_client
from app.models.schemas import (
    HealthHistoryItem,
    HealthHistoryResponse,
    HealthResponse,
    ParameterHealthDetail,
    ParameterName,
    PARAMETERS,
)
from app.routers.deps import add_time_range, ensure_uuid
from app.routers.observations import get_station_by_id, health_scorer

router = APIRouter(prefix="/health", tags=["Sensor Health"])


@router.get("/{station_id}", response_model=HealthResponse)
async def get_station_health(station_id: str):
    """Retrieve current sensor health score and status for all 7 weather parameters."""
    station_id = ensure_uuid(station_id, "Station")
    if not await get_station_by_id(station_id):
        raise HTTPException(status_code=404, detail="Station not found")

    param_details = {}
    for p in PARAMETERS:
        state = health_scorer.get_state(station_id, p)
        param_details[p] = ParameterHealthDetail(
            score=round(state.health_score, 2),
            status=state.get_status(),
            anomaly_streak=state.anomaly_streak,
            last_updated=state.last_updated,
        )

    overall_score, overall_status = health_scorer.get_overall_health(station_id)
    return HealthResponse(
        station_id=station_id,
        overall_health=overall_score,
        overall_status=overall_status,
        parameters=param_details,
    )


@router.get("/{station_id}/history", response_model=HealthHistoryResponse)
async def get_sensor_health_history(
    station_id: str,
    parameter: Optional[ParameterName] = None,
    from_date: Optional[datetime] = Query(None, alias="from"),
    to_date: Optional[datetime] = Query(None, alias="to"),
    limit: int = Query(100, ge=1, le=500),
):
    """Query chronological sensor health degradation and recovery history."""
    station_id = ensure_uuid(station_id, "Station")
    params: Dict[str, Any] = {
        "station_id": f"eq.{station_id}",
        "order": "recorded_at.desc",
        "limit": limit,
    }
    if parameter:
        params["parameter"] = f"eq.{parameter}"
    add_time_range(params, "recorded_at", from_date, to_date)

    history_records = await db_client.select("sensor_health_history", params=params)

    items = [
        HealthHistoryItem(
            recorded_at=h["recorded_at"],
            parameter=h["parameter"],
            health_score=h["health_score"],
            status=h["status"],
        )
        for h in history_records
    ]

    return HealthHistoryResponse(history=items)
