"""Demo and Anomaly Injection Endpoints for SIH26073 Judging Demonstration.
Implements POST /demo/inject-anomaly and POST /demo/generate-data.
Specified in /docs/HANDOFF.md §8.7, §9.2, §14.4.
"""
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status

from app.models.database import db_client
from app.models.schemas import (
    DemoGenerateRequest,
    DemoGenerateResponse,
    DemoInjectRequest,
    DemoInjectResponse,
    PARAMETERS,
)
from app.routers.observations import get_station_by_id, process_observation_pipeline
from app.services.data_generator import (
    create_drift_observations,
    create_frozen_observations,
    create_multivariate_observation,
    create_spike_observation,
    generate_time_series,
)

router = APIRouter(prefix="/demo", tags=["Demo Controls"])


@router.post("/inject-anomaly", response_model=DemoInjectResponse)
async def inject_synthetic_anomaly(payload: DemoInjectRequest):
    """
    Inject synthetic anomalies (Spike, Frozen, Drift, Missing, Multivariate).
    Routes through full processing pipeline per §14.4 (Score -> Health -> Root Cause -> Correction -> Alert -> WS).
    """
    station = await get_station_by_id(payload.station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    station_code = station["station_code"]
    elevation_m = station.get("elevation_m") or 0.0
    interval_min = station.get("expected_interval_min", 15)
    now = datetime.now(timezone.utc)

    anomaly_type = payload.anomaly_type.lower()
    target_params = payload.parameters or [random.choice(["temperature", "humidity", "pressure"])]
    magnitude = payload.magnitude or 3.0
    duration_min = payload.duration_minutes or payload.duration_min or 30

    injected_obs_ids: List[str] = []

    # --------------------------------------------------------------------------
    # 1. SPIKE
    # --------------------------------------------------------------------------
    if anomaly_type == "spike":
        spike_obs = create_spike_observation(
            station_code=station_code,
            timestamp=now,
            target_params=target_params,
            magnitude=magnitude,
            elevation_m=elevation_m
        )
        obs_id, _ = await process_observation_pipeline(spike_obs)
        injected_obs_ids.append(obs_id)
        msg = f"Injected sudden transient spike on {', '.join(target_params)} at {station['name']}."

    # --------------------------------------------------------------------------
    # 2. FROZEN
    # --------------------------------------------------------------------------
    elif anomaly_type == "frozen":
        count = max(4, duration_min // interval_min)
        start_t = now - timedelta(minutes=interval_min * (count - 1))
        frozen_series = create_frozen_observations(
            station_code=station_code,
            start_time=start_t,
            count=count,
            target_params=target_params,
            interval_min=interval_min,
            elevation_m=elevation_m
        )
        for obs in frozen_series:
            obs_id, _ = await process_observation_pipeline(obs)
            injected_obs_ids.append(obs_id)
        msg = f"Injected frozen sensor sequence ({count} readings) on {', '.join(target_params)}."

    # --------------------------------------------------------------------------
    # 3. DRIFT
    # --------------------------------------------------------------------------
    elif anomaly_type == "drift":
        count = max(4, duration_min // interval_min)
        start_t = now - timedelta(minutes=interval_min * (count - 1))
        drift_series = create_drift_observations(
            station_code=station_code,
            start_time=start_t,
            count=count,
            target_params=target_params,
            magnitude=magnitude,
            interval_min=interval_min,
            elevation_m=elevation_m
        )
        for obs in drift_series:
            obs_id, _ = await process_observation_pipeline(obs)
            injected_obs_ids.append(obs_id)
        msg = f"Injected gradual sensor drift sequence ({count} readings) on {', '.join(target_params)}."

    # --------------------------------------------------------------------------
    # 4. MULTIVARIATE
    # --------------------------------------------------------------------------
    elif anomaly_type == "multivariate":
        if not payload.parameters or len(payload.parameters) < 3:
            target_params = ["temperature", "humidity", "pressure", "wind_speed"]
        multi_obs = create_multivariate_observation(
            station_code=station_code,
            timestamp=now,
            target_params=target_params,
            magnitude=magnitude,
            elevation_m=elevation_m
        )
        obs_id, _ = await process_observation_pipeline(multi_obs)
        injected_obs_ids.append(obs_id)
        msg = f"Injected coupled multivariate anomaly across {', '.join(target_params)}."

    # --------------------------------------------------------------------------
    # 5. MISSING / COMMUNICATION
    # --------------------------------------------------------------------------
    elif anomaly_type in ("missing", "communication"):
        # Telemetry dropout: simulate observation with missing sensor fields
        missing_obs = {
            "station_code": station_code,
            "observed_at": now.isoformat(),
            "temperature": None,
            "humidity": None,
            "pressure": None,
            "wind_speed": None,
            "wind_direction": None,
            "rainfall": 0.0,
            "solar_radiation": None,
        }
        obs_id, _ = await process_observation_pipeline(missing_obs)
        injected_obs_ids.append(obs_id)
        target_params = ["temperature", "humidity", "pressure", "wind_speed", "solar_radiation"]
        msg = f"Injected station communication dropout (5 missing parameters) at {station['name']}."

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported anomaly_type: {anomaly_type}. Choose from spike, frozen, drift, missing, multivariate."
        )

    return DemoInjectResponse(
        injected_observations=injected_obs_ids,
        anomaly_type=anomaly_type,
        affected_parameters=target_params,
        message=msg,
    )


@router.post("/generate-data", response_model=DemoGenerateResponse)
async def generate_synthetic_normal_data(payload: DemoGenerateRequest):
    """Generate and ingest continuous clean historical observations for a station."""
    target_id = payload.station_id or (payload.station_ids[0] if payload.station_ids else None)
    if not target_id:
        raise HTTPException(status_code=400, detail="station_id or station_ids must be provided")

    station = await get_station_by_id(target_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    hours = payload.hours or ((payload.days or 1) * 24)
    station_code = station["station_code"]
    elevation_m = station.get("elevation_m") or 0.0
    interval_min = payload.interval_min or station.get("expected_interval_min", 15)
    num_obs = int((hours * 60) / interval_min)

    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=hours)

    series = generate_time_series(
        station_code=station_code,
        start_time=start_time,
        num_observations=num_obs,
        interval_min=interval_min,
        elevation_m=elevation_m
    )

    for obs in series:
        await process_observation_pipeline(obs)

    return DemoGenerateResponse(
        observation_count=len(series),
        from_time=start_time.isoformat(),
        to_time=now.isoformat(),
        message=f"Successfully generated and processed {len(series)} clean observations.",
    )
