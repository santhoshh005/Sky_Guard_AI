import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

root_dir = Path(__file__).resolve().parent.parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
from fastapi import APIRouter, HTTPException, status
from pydantic import ValidationError

from app.models.database import db_client
from app.models.schemas import (
    AnomalySummary,
    BatchIngestError,
    ObservationBatchInput,
    ObservationBatchResponse,
    ObservationIngestResponse,
    ObservationInput,
    PARAMETERS,
)
from app.routers.websocket import ws_manager
from app.services.anomaly_detector import AnomalyDetector
from app.services.corrector import ValueCorrector
from app.services.feature_engineer import FeatureEngineer
from app.services.health_scorer import HealthScorer
from app.services.quality_checks import QualityChecker
from app.services.root_cause import RootCauseClassifier
from ml.inference.autoencoder import AutoencoderInference
from ml.inference.isolation_forest import IsolationForestInference

router = APIRouter(prefix="/observations", tags=["Observations"])

# Global shared service singletons
if_inference = IsolationForestInference()
ae_inference = AutoencoderInference()
health_scorer = HealthScorer()
value_corrector = ValueCorrector()

# In-memory station code cache: station_code -> station_dict
station_cache: Dict[str, Dict[str, Any]] = {}
station_id_cache: Dict[str, Dict[str, Any]] = {}


async def get_station_by_code(code: str) -> Optional[Dict[str, Any]]:
    if code in station_cache:
        return station_cache[code]
    res = await db_client.select("stations", params={"station_code": f"eq.{code}", "limit": 1})
    if res:
        stn = res[0]
        station_cache[code] = stn
        station_id_cache[stn["id"]] = stn
        return stn
    return None


async def get_station_by_id(stn_id: str) -> Optional[Dict[str, Any]]:
    if stn_id in station_id_cache:
        return station_id_cache[stn_id]
    res = await db_client.select("stations", params={"id": f"eq.{stn_id}", "limit": 1})
    if res:
        stn = res[0]
        station_id_cache[stn_id] = stn
        station_cache[stn["station_code"]] = stn
        return stn
    return None


async def get_recent_history(station_id: str, limit: int = 96) -> List[Dict[str, Any]]:
    """Query the most recent observation history for a station."""
    res = await db_client.select(
        "observations",
        params={
            "station_id": f"eq.{station_id}",
            "order": "observed_at.desc",
            "limit": limit
        }
    )
    # Reverse to return in chronological ascending order
    return list(reversed(res)) if res else []


async def process_observation_pipeline(obs_dict: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """
    Full end-to-end processing pipeline for a single observation dict.
    Returns (observation_id, anomaly_summary_dict).
    """
    station_code = obs_dict.get("station_code")
    station = await get_station_by_code(station_code)
    if not station:
        raise HTTPException(status_code=400, detail=f"Unknown station_code: {station_code}")

    station_id = station["id"]
    station_name = station["name"]
    expected_interval = station.get("expected_interval_min", 15)

    obs_time = obs_dict.get("observed_at")
    if isinstance(obs_time, str):
        obs_dt = datetime.fromisoformat(obs_time.replace("Z", "+00:00"))
    elif isinstance(obs_time, datetime):
        obs_dt = obs_time
    else:
        obs_dt = datetime.now(timezone.utc)

    iso_obs_time = obs_dt.isoformat()

    # 1. Fetch recent history for feature engineering and checks
    recent_history = await get_recent_history(station_id, limit=96)

    # 2. Extract features
    full_vec, compact_vec, _ = FeatureEngineer.extract_features(obs_dict, recent_history)

    # 3. Deterministic Quality Checks
    qc_score, qc_flags = QualityChecker.run_checks(obs_dict, recent_history, expected_interval)

    # 4. ML Model Scoring
    if_score = if_inference.score(full_vec)
    shap_values = if_inference.explain(full_vec)
    ae_score, orig_scaled, recon = ae_inference.score(compact_vec)

    # Calculate per-parameter AE reconstruction errors
    ae_param_errors = {}
    for p in PARAMETERS:
        ae_param_errors[p] = ae_inference.get_per_parameter_error(recon, orig_scaled, p)

    # 5. 3-Channel Fusion
    fusion_res = AnomalyDetector.fuse_scores(qc_score, if_score, ae_score)

    # 6. Root-Cause Classification
    rc_res = RootCauseClassifier.classify(
        observation=obs_dict,
        qc_flags=qc_flags,
        shap_values=shap_values,
        ae_score=ae_score,
        is_anomaly=fusion_res.is_anomaly,
        recent_history=recent_history,
    )

    # 7. Sensor Health Scoring
    health_updates = health_scorer.update_sensor_health(
        station_id=station_id,
        observation=obs_dict,
        qc_flags=qc_flags,
        shap_values=shap_values,
        ae_param_errors=ae_param_errors,
        expected_interval_min=expected_interval
    )

    # 8. Corrected Value Estimation
    corrections = value_corrector.estimate_corrections(
        observation=obs_dict,
        fused_score=fusion_res.fused_score,
        confidence=fusion_res.confidence,
        root_cause=rc_res.root_cause,
        station_code=station_code,
        recent_history=recent_history,
    )

    # 9. Database Persistence
    obs_id = str(uuid.uuid4())
    observation_record = {
        "id": obs_id,
        "station_id": station_id,
        "observed_at": iso_obs_time,
        "temperature": obs_dict.get("temperature"),
        "humidity": obs_dict.get("humidity"),
        "pressure": obs_dict.get("pressure"),
        "wind_speed": obs_dict.get("wind_speed"),
        "wind_direction": obs_dict.get("wind_direction"),
        "rainfall": obs_dict.get("rainfall"),
        "solar_radiation": obs_dict.get("solar_radiation"),
    }
    await db_client.insert("observations", observation_record)

    # Insert anomaly score
    anomaly_score_id = str(uuid.uuid4())
    score_record = {
        "id": anomaly_score_id,
        "observation_id": obs_id,
        "qc_score": fusion_res.qc_score,
        "if_score": fusion_res.if_score,
        "ae_score": fusion_res.ae_score,
        "fused_score": fusion_res.fused_score,
        "confidence": fusion_res.confidence,
        "is_anomaly": fusion_res.is_anomaly,
        "severity": fusion_res.severity,
        "root_cause": rc_res.root_cause,
        "explanation": rc_res.explanation,
        "qc_flags": qc_flags,
        "shap_values": shap_values,
        "scored_at": datetime.now(timezone.utc).isoformat(),
    }
    await db_client.insert("anomaly_scores", score_record)

    # Insert corrected values
    corrected_records = []
    for c in corrections:
        corrected_records.append({
            "id": str(uuid.uuid4()),
            "observation_id": obs_id,
            "parameter": c.parameter,
            "raw_value": c.raw_value,
            "corrected_value": c.corrected_value,
            "correction_method": c.correction_method,
            "correction_confidence": c.correction_confidence,
        })
    if corrected_records:
        await db_client.insert("corrected_values", corrected_records)

    # Insert sensor health history records
    health_history_records = []
    for p, (h_state, h_status, h_alert_type) in health_updates.items():
        health_history_records.append({
            "id": str(uuid.uuid4()),
            "station_id": station_id,
            "parameter": p,
            "health_score": round(h_state.health_score, 2),
            "status": h_status,
            "anomaly_streak": h_state.anomaly_streak,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        })
        if h_alert_type:
            # Create sensor health degradation alert
            alert_sev = "critical" if h_alert_type == "health_degraded" else "warning"
            h_alert = {
                "id": str(uuid.uuid4()),
                "station_id": station_id,
                "anomaly_score_id": anomaly_score_id,
                "alert_type": h_alert_type,
                "severity": alert_sev,
                "title": f"Sensor {p.capitalize()} at {station_name} status: {h_status}",
                "description": f"Health score dropped to {h_state.health_score:.1f}%. Action recommended.",
                "parameter": p,
                "is_resolved": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db_client.insert("alerts", h_alert)
            await ws_manager.broadcast("alert", h_alert, station_id=station_id)

    if health_history_records:
        await db_client.insert("sensor_health_history", health_history_records)

    # If anomaly is warning/critical, generate an anomaly alert
    if fusion_res.is_anomaly and fusion_res.severity in ("warning", "critical"):
        anom_alert = {
            "id": str(uuid.uuid4()),
            "station_id": station_id,
            "anomaly_score_id": anomaly_score_id,
            "alert_type": "anomaly",
            "severity": fusion_res.severity,
            "title": f"{rc_res.root_cause.capitalize() if rc_res.root_cause else 'Anomaly'} at {station_name}",
            "description": rc_res.explanation,
            "parameter": rc_res.root_cause,
            "is_resolved": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db_client.insert("alerts", anom_alert)
        await ws_manager.broadcast("alert", anom_alert, station_id=station_id)

    # 10. WebSocket Live Broadcast
    ws_event_data = {
        "observation_id": obs_id,
        "station_id": station_id,
        "station_code": station_code,
        "station_name": station_name,
        "fused_score": fusion_res.fused_score,
        "severity": fusion_res.severity,
        "is_anomaly": fusion_res.is_anomaly,
        "root_cause": rc_res.root_cause,
        "confidence": fusion_res.confidence,
        "explanation": rc_res.explanation,
        "observed_at": iso_obs_time,
    }
    await ws_manager.broadcast("anomaly", ws_event_data, station_id=station_id)

    overall_h_score, overall_h_status = health_scorer.get_overall_health(station_id)
    await ws_manager.broadcast("health_update", {
        "station_id": station_id,
        "station_code": station_code,
        "overall_health": overall_h_score,
        "overall_status": overall_h_status,
    }, station_id=station_id)

    anomaly_summary = {
        "fused_score": fusion_res.fused_score,
        "is_anomaly": fusion_res.is_anomaly,
        "severity": fusion_res.severity,
        "root_cause": rc_res.root_cause,
        "confidence": fusion_res.confidence,
        "explanation": rc_res.explanation,
    }

    return obs_id, anomaly_summary


@router.post("", response_model=ObservationIngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_single_observation(payload: ObservationInput):
    """Ingest a single observation into the real-time AI anomaly detection pipeline."""
    obs_id, anomaly_summary = await process_observation_pipeline(payload.model_dump())
    return ObservationIngestResponse(
        observation_id=obs_id,
        anomaly=AnomalySummary(**anomaly_summary)
    )


@router.post("/batch", response_model=ObservationBatchResponse, status_code=status.HTTP_201_CREATED)
async def ingest_batch_observations(payload: ObservationBatchInput):
    """Ingest a batch of observations sequentially through the pipeline."""
    results: List[ObservationIngestResponse] = []
    errors: List[BatchIngestError] = []
    accepted = 0
    rejected = 0

    for idx, obs in enumerate(payload.observations):
        try:
            obs_id, anomaly_summary = await process_observation_pipeline(obs.model_dump())
            results.append(ObservationIngestResponse(
                observation_id=obs_id,
                anomaly=AnomalySummary(**anomaly_summary)
            ))
            accepted += 1
        except Exception as e:
            rejected += 1
            errors.append(BatchIngestError(index=idx, error=str(e)))

    return ObservationBatchResponse(
        results=results,
        accepted=accepted,
        rejected=rejected,
        errors=errors
    )
