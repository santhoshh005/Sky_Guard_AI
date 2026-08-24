"""Station management endpoints for SkyGuard AI.
Implements GET /stations, GET /stations/{id}, and POST /stations.
Specified in /docs/HANDOFF.md §8.2.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from app.models.database import db_client
from app.models.schemas import (
    AlertResponse,
    HealthResponse,
    ParameterHealthDetail,
    PARAMETERS,
    StationCreate,
    StationDetailResponse,
    StationListResponse,
    StationResponse,
    StationWithHealth,
)
from app.routers.observations import health_scorer

router = APIRouter(prefix="/stations", tags=["Stations"])


@router.get("", response_model=StationListResponse)
async def list_stations(
    state: Optional[str] = None,
    district: Optional[str] = None,
    health_status: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """List weather stations with real-time health metrics and active alert counts."""
    params: Dict[str, Any] = {
        "order": "station_code.asc",
    }
    if state:
        params["state"] = f"ilike.*{state}*"
    if district:
        params["district"] = f"ilike.*{district}*"

    stations = await db_client.select("stations", params=params)

    # Enrich stations with health status, latest observation, and active alerts
    enriched: List[StationWithHealth] = []
    for stn in stations:
        stn_id = stn["id"]
        h_score, h_stat = health_scorer.get_overall_health(stn_id)

        # Filter by status if query param provided
        if health_status and h_stat != health_status:
            continue

        # Get last observation timestamp
        last_obs = await db_client.select(
            "observations",
            params={"station_id": f"eq.{stn_id}", "order": "observed_at.desc", "limit": 1}
        )
        last_obs_time = last_obs[0]["observed_at"] if last_obs else None

        # Get count of active unresolved alerts
        unresolved_alerts = await db_client.select(
            "alerts",
            params={"station_id": f"eq.{stn_id}", "is_resolved": "eq.false"}
        )
        active_alerts_count = len(unresolved_alerts)

        enriched.append(StationWithHealth(
            id=stn["id"],
            station_code=stn["station_code"],
            name=stn["name"],
            latitude=stn["latitude"],
            longitude=stn["longitude"],
            elevation_m=stn.get("elevation_m"),
            state=stn.get("state"),
            district=stn.get("district"),
            station_type=stn.get("station_type", "AWS"),
            expected_interval_min=stn.get("expected_interval_min", 15),
            is_active=stn.get("is_active", True),
            overall_health=h_score,
            health_status=h_stat,
            last_observation_at=last_obs_time,
            active_alerts=active_alerts_count,
        ))

    total = len(enriched)
    start_idx = (page - 1) * limit
    paginated = enriched[start_idx : start_idx + limit]

    return StationListResponse(
        stations=paginated,
        total=total,
        page=page,
    )


@router.get("/{station_id}", response_model=StationDetailResponse)
async def get_station_detail(station_id: str):
    """Retrieve full station details with parameter health breakdown and recent alerts."""
    res = await db_client.select("stations", params={"id": f"eq.{station_id}", "limit": 1})
    if not res:
        raise HTTPException(status_code=404, detail="Station not found")
    stn = res[0]

    # Health details per parameter
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
    health_resp = HealthResponse(
        station_id=station_id,
        overall_health=overall_score,
        overall_status=overall_status,
        parameters=param_details,
    )

    # Recent alerts
    recent_alerts_data = await db_client.select(
        "alerts",
        params={"station_id": f"eq.{station_id}", "order": "created_at.desc", "limit": 10}
    )
    recent_alerts = [
        AlertResponse(
            id=a["id"],
            station_id=a["station_id"],
            station_name=stn["name"],
            station_code=stn["station_code"],
            anomaly_score_id=a.get("anomaly_score_id"),
            alert_type=a["alert_type"],
            severity=a["severity"],
            title=a["title"],
            description=a.get("description"),
            parameter=a.get("parameter"),
            is_resolved=a.get("is_resolved", False),
            resolved_at=a.get("resolved_at"),
            created_at=a.get("created_at"),
        )
        for a in recent_alerts_data
    ]

    # Last observation
    last_obs_data = await db_client.select(
        "observations",
        params={"station_id": f"eq.{station_id}", "order": "observed_at.desc", "limit": 1}
    )
    last_obs = last_obs_data[0] if last_obs_data else None

    return StationDetailResponse(
        station=StationResponse(**stn),
        health=health_resp,
        recent_alerts=recent_alerts,
        last_observation=last_obs,
    )


@router.post("", response_model=StationResponse, status_code=status.HTTP_201_CREATED)
async def create_station(payload: StationCreate):
    """Register a new weather station."""
    data = payload.model_dump()
    data["id"] = str(uuid.uuid4())
    data["created_at"] = datetime.now(timezone.utc).isoformat()
    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    res = await db_client.insert("stations", data)
    created = res[0] if res else data
    return StationResponse(**created)
