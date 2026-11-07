"""Station endpoints: list, detail, observation series and registration."""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.models.database import DatabaseError, db_client
from app.models.schemas import (
    AlertResponse,
    HealthResponse,
    HealthStatus,
    ObservationPoint,
    ObservationSeriesResponse,
    ParameterHealthDetail,
    ParameterName,
    PARAMETERS,
    StationCreate,
    StationDetailResponse,
    StationListResponse,
    StationResponse,
    StationWithHealth,
)
from app.routers.deps import ensure_uuid, require_api_key
from app.routers.observations import get_station_by_id, health_scorer, station_cache, station_id_cache

router = APIRouter(prefix="/stations", tags=["Stations"])


def _health_response(station_id: str) -> HealthResponse:
    params = {}
    for p in PARAMETERS:
        st = health_scorer.get_state(station_id, p)
        params[p] = ParameterHealthDetail(
            score=round(st.health_score, 2), status=st.get_status(),
            anomaly_streak=st.anomaly_streak, last_updated=st.last_updated,
        )
    score, overall = health_scorer.get_overall_health(station_id)
    return HealthResponse(station_id=station_id, overall_health=score, overall_status=overall, parameters=params)


async def _latest_observation_time(station_id: str) -> Optional[str]:
    rows = await db_client.select(
        "observations",
        params={"station_id": f"eq.{station_id}", "order": "observed_at.desc", "limit": 1},
        select_fields="observed_at",
    )
    return rows[0]["observed_at"] if rows else None


@router.get("", response_model=StationListResponse)
async def list_stations(
    state: Optional[str] = Query(None, max_length=100),
    district: Optional[str] = Query(None, max_length=100),
    health_status: Optional[HealthStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """Stations with live health, last report time and open-alert counts."""
    params: Dict[str, Any] = {"order": "station_code.asc"}
    # PostgREST pattern chars are * and %; strip them plus filter syntax from user input
    if state:
        params["state"] = f"ilike.*{state.strip('*%,()')}*"
    if district:
        params["district"] = f"ilike.*{district.strip('*%,()')}*"

    stations, open_alerts = await asyncio.gather(
        db_client.select("stations", params=params),
        db_client.select("alerts", params={"is_resolved": "eq.false"}, select_fields="station_id"),
    )
    alert_counts: Dict[str, int] = {}
    for a in open_alerts:
        alert_counts[a["station_id"]] = alert_counts.get(a["station_id"], 0) + 1

    filtered = []
    for stn in stations:
        station_cache[stn["station_code"]] = stn
        station_id_cache[stn["id"]] = stn
        score, h_status = health_scorer.get_overall_health(stn["id"])
        if health_status and h_status != health_status:
            continue
        filtered.append((stn, score, h_status))

    page_items = filtered[(page - 1) * limit: page * limit]
    last_seen = await asyncio.gather(*(_latest_observation_time(s["id"]) for s, _, _ in page_items))

    enriched: List[StationWithHealth] = [
        StationWithHealth(
            **{k: stn.get(k) for k in ("id", "station_code", "name", "latitude", "longitude", "elevation_m", "state", "district")},
            station_type=stn.get("station_type") or "AWS",
            expected_interval_min=stn.get("expected_interval_min") or 15,
            is_active=stn.get("is_active", True),
            overall_health=round(score, 1),
            health_status=h_status,
            last_observation_at=seen,
            active_alerts=alert_counts.get(stn["id"], 0),
        )
        for (stn, score, h_status), seen in zip(page_items, last_seen)
    ]
    return StationListResponse(stations=enriched, total=len(filtered), page=page)


@router.get("/{station_id}", response_model=StationDetailResponse)
async def get_station_detail(station_id: str):
    """Station metadata, per-sensor health, recent alerts and latest observation."""
    station_id = ensure_uuid(station_id, "Station")
    stn = await get_station_by_id(station_id)
    if not stn:
        raise HTTPException(status_code=404, detail="Station not found")

    alerts_data, last_obs_data = await asyncio.gather(
        db_client.select("alerts", params={"station_id": f"eq.{station_id}", "order": "created_at.desc", "limit": 10}),
        db_client.select("observations", params={"station_id": f"eq.{station_id}", "order": "observed_at.desc", "limit": 1}),
    )
    recent_alerts = [
        AlertResponse(
            id=a["id"], station_id=a["station_id"], station_name=stn["name"], station_code=stn["station_code"],
            anomaly_score_id=a.get("anomaly_score_id"), alert_type=a["alert_type"], severity=a["severity"],
            title=a["title"], description=a.get("description"), parameter=a.get("parameter"),
            is_resolved=a.get("is_resolved", False), resolved_at=a.get("resolved_at"), created_at=a.get("created_at"),
        )
        for a in alerts_data
    ]
    return StationDetailResponse(
        station=StationResponse(**{k: v for k, v in stn.items() if k in StationResponse.model_fields and v is not None}),
        health=_health_response(station_id),
        recent_alerts=recent_alerts,
        last_observation=last_obs_data[0] if last_obs_data else None,
    )


@router.get("/{station_id}/observations", response_model=ObservationSeriesResponse)
async def get_station_observations(
    station_id: str,
    parameter: ParameterName = "temperature",
    hours: int = Query(24, ge=1, le=168),
):
    """Raw vs corrected time series for one parameter (for the dual-trace chart)."""
    station_id = ensure_uuid(station_id, "Station")
    if not await get_station_by_id(station_id):
        raise HTTPException(status_code=404, detail="Station not found")
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    rows = await db_client.select(
        "observations",
        params={
            "station_id": f"eq.{station_id}",
            "observed_at": f"gte.{since}",
            "order": "observed_at.asc",
            "limit": 1000,
            "corrected_values.parameter": f"eq.{parameter}",
        },
        select_fields=f"id,observed_at,{parameter},anomaly_scores(is_anomaly,severity),corrected_values(parameter,corrected_value)",
    )
    points = []
    for r in rows:
        score = r.get("anomaly_scores") or {}
        score = score[0] if isinstance(score, list) and score else (score if isinstance(score, dict) else {})
        corr = next((c.get("corrected_value") for c in (r.get("corrected_values") or []) if c.get("corrected_value") is not None), None)
        raw = r.get(parameter)
        points.append(ObservationPoint(
            observed_at=r["observed_at"], raw=raw, corrected=corr if corr is not None else raw,
            is_anomaly=bool(score.get("is_anomaly")), severity=score.get("severity") or "normal",
        ))
    return ObservationSeriesResponse(station_id=station_id, parameter=parameter, points=points)


@router.post("", response_model=StationResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_api_key)])
async def create_station(payload: StationCreate):
    """Register a new weather station."""
    now = datetime.now(timezone.utc).isoformat()
    data = {**payload.model_dump(), "id": str(uuid.uuid4()), "created_at": now, "updated_at": now}
    try:
        res = await db_client.insert("stations", data)
    except DatabaseError as exc:
        if exc.status_code == 409 or "23505" in exc.detail:
            raise HTTPException(status_code=409, detail="A station with this station_code already exists")
        raise
    created = res[0] if res else data
    station_cache[created["station_code"]] = created
    station_id_cache[created["id"]] = created
    return StationResponse(**created)
