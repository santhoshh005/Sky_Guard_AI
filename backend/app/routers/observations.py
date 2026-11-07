"""Observation ingestion: the real-time scoring pipeline (POST /observations, /observations/batch)."""
import asyncio
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import settings
from app.models.database import DatabaseError, db_client
from app.models.schemas import (
    AnomalySummary,
    BatchIngestError,
    ObservationBatchInput,
    ObservationBatchResponse,
    ObservationIngestResponse,
    ObservationInput,
    PARAMETERS,
)
from app.routers.deps import require_api_key
from app.routers.websocket import ws_manager
from app.services.corrector import ValueCorrector
from app.services.drift import DriftDetector
from app.services.feature_engineer import parse_ts
from app.services.health_scorer import HealthScorer
from app.services.pipeline import score_observation
from ml.inference.autoencoder import AutoencoderInference
from ml.inference.isolation_forest import IsolationForestInference

logger = logging.getLogger("skyguard.ingest")
router = APIRouter(prefix="/observations", tags=["Observations"])

HISTORY_DEPTH = 110  # >24 h at 15-min cadence: rolling windows + same-time-yesterday lookups

# Shared service singletons
if_inference = IsolationForestInference()
ae_inference = AutoencoderInference()
health_scorer = HealthScorer()
value_corrector = ValueCorrector()
drift_detector = DriftDetector(value_corrector.regression_models)

# Station caches: station_code -> station, id -> station
station_cache: Dict[str, Dict[str, Any]] = {}
station_id_cache: Dict[str, Dict[str, Any]] = {}

# Serialise processing per station so history reads and health-state updates stay ordered
_station_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


def _cache_station(stn: Dict[str, Any]) -> Dict[str, Any]:
    station_cache[stn["station_code"]] = stn
    station_id_cache[stn["id"]] = stn
    return stn


async def get_station_by_code(code: str) -> Optional[Dict[str, Any]]:
    if code in station_cache:
        return station_cache[code]
    res = await db_client.select("stations", params={"station_code": f"eq.{code}", "limit": 1})
    return _cache_station(res[0]) if res else None


async def get_station_by_id(stn_id: str) -> Optional[Dict[str, Any]]:
    """Look up a station by UUID or, for convenience, by station_code."""
    if stn_id in station_id_cache:
        return station_id_cache[stn_id]
    if stn_id in station_cache:
        return station_cache[stn_id]
    try:
        uuid.UUID(str(stn_id))
        column = "id"
    except (ValueError, AttributeError, TypeError):
        column = "station_code"
    res = await db_client.select("stations", params={column: f"eq.{stn_id}", "limit": 1})
    return _cache_station(res[0]) if res else None


def _alert(station_id: str, anomaly_score_id: str, alert_type: str, severity: str, title: str,
           description: Optional[str], parameter: Optional[str]) -> Dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "station_id": station_id,
        "anomaly_score_id": anomaly_score_id,
        "alert_type": alert_type,
        "severity": severity,
        "title": title[:500],
        "description": description,
        "parameter": parameter,
        "is_resolved": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


async def process_observation_pipeline(obs_dict: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Score, persist and broadcast one observation. Returns (observation_id, anomaly_summary)."""
    station_code = obs_dict.get("station_code")
    station = await get_station_by_code(station_code)
    if not station:
        raise HTTPException(status_code=400, detail=f"Unknown station_code: {station_code}")

    async with _station_locks[station["id"]]:
        return await _process_locked(obs_dict, station)


async def _process_locked(obs_dict: Dict[str, Any], station: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    station_id, station_code, station_name = station["id"], station["station_code"], station["name"]
    expected_interval = station.get("expected_interval_min") or 15

    obs_dt = parse_ts(obs_dict.get("observed_at")) or datetime.now(timezone.utc)
    iso_obs_time = obs_dt.isoformat()
    obs_dict = {**obs_dict, "observed_at": iso_obs_time}

    # 1. History strictly before this observation (correct for back-filled data too)
    hist = await db_client.select("observations", params={
        "station_id": f"eq.{station_id}",
        "observed_at": f"lt.{iso_obs_time}",
        "order": "observed_at.desc",
        "limit": HISTORY_DEPTH,
    })
    recent_history = list(reversed(hist or []))

    # 2-6. QC + ML + fusion + drift + root cause. CPU-bound: keep it off the event loop.
    scored = await asyncio.to_thread(
        score_observation, obs_dict, recent_history,
        station_code=station_code, if_inference=if_inference, ae_inference=ae_inference,
        drift_detector=drift_detector, expected_interval_min=expected_interval,
        longitude=station.get("longitude"),
    )
    fusion, rc = scored.fusion, scored.root_cause

    # 7. Sensor health
    health_updates = health_scorer.update_sensor_health(
        station_id=station_id, observation=obs_dict, qc_flags=scored.qc_flags,
        shap_values=scored.shap_values, ae_param_errors=scored.ae_param_errors,
        is_drifting_map={p: True for p in scored.drift}, expected_interval_min=expected_interval,
        is_anomaly=fusion.is_anomaly, anomalous_params=rc.parameters,
    )

    # 8. Corrected values for the affected parameters
    corrections = value_corrector.estimate_corrections(
        observation=obs_dict, is_anomaly=fusion.is_anomaly, confidence=fusion.confidence,
        root_cause=rc.root_cause, station_code=station_code, recent_history=recent_history,
        target_params=rc.parameters,
    )

    # 9. Persistence: observation first (FK parent), then the score, then the rest in parallel
    obs_id, score_id = str(uuid.uuid4()), str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        await db_client.insert("observations", {
            "id": obs_id, "station_id": station_id, "observed_at": iso_obs_time,
            **{p: obs_dict.get(p) for p in PARAMETERS},
        })
    except DatabaseError as exc:
        if exc.status_code == 409 or "23505" in exc.detail:
            raise HTTPException(status_code=409, detail="An observation for this station and time already exists")
        raise

    await db_client.insert("anomaly_scores", {
        "id": score_id, "observation_id": obs_id,
        "qc_score": fusion.qc_score, "if_score": fusion.if_score, "ae_score": fusion.ae_score,
        "fused_score": fusion.fused_score, "confidence": fusion.confidence,
        "is_anomaly": fusion.is_anomaly, "severity": fusion.severity,
        "root_cause": rc.root_cause, "explanation": rc.explanation,
        "qc_flags": scored.qc_flags, "shap_values": scored.shap_values, "scored_at": now_iso,
    })

    alerts: List[Dict[str, Any]] = []
    health_rows = []
    for p, (state, h_status, alert_type) in health_updates.items():
        health_rows.append({
            "id": str(uuid.uuid4()), "station_id": station_id, "parameter": p,
            "health_score": round(state.health_score, 2), "status": h_status,
            "anomaly_streak": state.anomaly_streak, "recorded_at": now_iso,
        })
        if alert_type:
            alerts.append(_alert(
                station_id, score_id, alert_type,
                "critical" if alert_type == "health_degraded" else "warning",
                f"{p.replace('_', ' ').title()} sensor at {station_name}: {h_status.replace('_', ' ')}",
                f"Health score dropped to {state.health_score:.1f}/100. Inspection recommended.", p,
            ))
    if fusion.is_anomaly:
        cause = rc.root_cause or "anomaly"
        alerts.append(_alert(
            station_id, score_id, "communication_loss" if cause == "communication" else "anomaly",
            fusion.severity, f"{cause.capitalize()} anomaly at {station_name}", rc.explanation,
            rc.parameters[0] if rc.parameters else None,
        ))

    writes = [db_client.insert("sensor_health_history", health_rows)]
    if corrections:
        writes.append(db_client.insert("corrected_values", [{
            "id": str(uuid.uuid4()), "observation_id": obs_id, "parameter": c.parameter,
            "raw_value": c.raw_value, "corrected_value": c.corrected_value,
            "correction_method": c.correction_method, "correction_confidence": c.correction_confidence,
        } for c in corrections]))
    if alerts:
        writes.append(db_client.insert("alerts", alerts))
    await asyncio.gather(*writes)

    # 10. Live push
    overall_score, overall_status = health_scorer.get_overall_health(station_id)
    summary = {
        "fused_score": fusion.fused_score, "is_anomaly": fusion.is_anomaly, "severity": fusion.severity,
        "root_cause": rc.root_cause, "confidence": fusion.confidence, "explanation": rc.explanation,
    }
    for a in alerts:
        await ws_manager.broadcast("alert", {**a, "station_code": station_code, "station_name": station_name}, station_id)
    await ws_manager.broadcast("anomaly", {
        **summary, "observation_id": obs_id, "anomaly_score_id": score_id, "station_id": station_id,
        "station_code": station_code, "station_name": station_name, "observed_at": iso_obs_time,
    }, station_id)
    await ws_manager.broadcast("health_update", {
        "station_id": station_id, "station_code": station_code,
        "overall_health": overall_score, "overall_status": overall_status,
    }, station_id)

    return obs_id, summary


@router.post("", response_model=ObservationIngestResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_api_key)])
async def ingest_single_observation(payload: ObservationInput):
    """Ingest one observation into the real-time anomaly detection pipeline."""
    obs_id, summary = await process_observation_pipeline(payload.model_dump())
    return ObservationIngestResponse(observation_id=obs_id, anomaly=AnomalySummary(**summary))


@router.post("/batch", response_model=ObservationBatchResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_api_key)])
async def ingest_batch_observations(payload: ObservationBatchInput):
    """Ingest a batch in chronological order; per-item failures are reported, not fatal."""
    if len(payload.observations) > settings.MAX_BATCH_SIZE:
        raise HTTPException(status_code=413, detail=f"Batch exceeds {settings.MAX_BATCH_SIZE} observations")

    results: List[ObservationIngestResponse] = []
    errors: List[BatchIngestError] = []
    ordered = sorted(enumerate(payload.observations), key=lambda item: item[1].observed_at)
    for idx, obs in ordered:
        try:
            obs_id, summary = await process_observation_pipeline(obs.model_dump())
            results.append(ObservationIngestResponse(observation_id=obs_id, anomaly=AnomalySummary(**summary)))
        except HTTPException as exc:
            errors.append(BatchIngestError(index=idx, error=str(exc.detail)))
        except DatabaseError:
            errors.append(BatchIngestError(index=idx, error="Database error"))
    return ObservationBatchResponse(results=results, accepted=len(results), rejected=len(errors), errors=errors)
