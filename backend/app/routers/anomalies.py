"""Anomaly endpoints: GET /anomalies and GET /anomalies/{id}."""
import asyncio
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.database import db_client
from app.models.schemas import (
    AnomalyDetailResponse,
    AnomalyListItem,
    AnomalyListResponse,
    AnomalyScoreDetail,
    CorrectedValueSchema,
    RootCause,
    Severity,
)
from app.routers.deps import add_time_range, ensure_uuid
from app.routers.observations import get_station_by_id

router = APIRouter(prefix="/anomalies", tags=["Anomalies"])

# Embedded many-to-one join (anomaly_scores.observation_id -> observations.id); `!inner`
# lets us filter anomalies by the observation's station in the same request.
LIST_SELECT = (
    "id,observation_id,fused_score,confidence,severity,root_cause,explanation,scored_at,"
    "observations!inner(station_id,observed_at)"
)


def _embedded(row: Dict[str, Any]) -> Dict[str, Any]:
    obs = row.get("observations") or {}
    return obs[0] if isinstance(obs, list) and obs else (obs if isinstance(obs, dict) else {})


@router.get("", response_model=AnomalyListResponse)
async def list_anomalies(
    station_id: Optional[str] = None,
    severity: Optional[Severity] = None,
    root_cause: Optional[RootCause] = None,
    from_date: Optional[datetime] = Query(None, alias="from"),
    to_date: Optional[datetime] = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """Anomalous observations (newest first) filtered by station, severity, root cause and time."""
    params: Dict[str, Any] = {
        "is_anomaly": "eq.true",
        "order": "scored_at.desc",
        "limit": limit,
        "offset": (page - 1) * limit,
    }
    if station_id:
        params["observations.station_id"] = f"eq.{ensure_uuid(station_id, 'Station')}"
    if severity:
        params["severity"] = f"eq.{severity}"
    if root_cause:
        params["root_cause"] = f"eq.{root_cause}"
    add_time_range(params, "scored_at", from_date, to_date)

    rows, total = await db_client.select_with_count("anomaly_scores", params=params, select_fields=LIST_SELECT)

    items = []
    for a in rows:
        obs = _embedded(a)
        stn = await get_station_by_id(obs["station_id"]) if obs.get("station_id") else None
        stn = stn or {}
        items.append(AnomalyListItem(
            id=a["id"],
            observation_id=a["observation_id"],
            station_id=obs.get("station_id"),
            station_code=stn.get("station_code"),
            station_name=stn.get("name"),
            observed_at=obs.get("observed_at") or a["scored_at"],
            fused_score=a["fused_score"],
            confidence=a.get("confidence", 0.0),
            severity=a["severity"],
            root_cause=a.get("root_cause"),
            explanation=a.get("explanation"),
            scored_at=a.get("scored_at"),
        ))
    return AnomalyListResponse(anomalies=items, total=total, page=page)


@router.get("/{anomaly_score_id}", response_model=AnomalyDetailResponse)
async def get_anomaly_detail(anomaly_score_id: str):
    """Full anomaly breakdown: channel scores, QC flags, SHAP attribution and corrected values."""
    anomaly_score_id = ensure_uuid(anomaly_score_id, "Anomaly")
    res = await db_client.select("anomaly_scores", params={"id": f"eq.{anomaly_score_id}", "limit": 1})
    if not res:
        raise HTTPException(status_code=404, detail="Anomaly score record not found")
    anom = res[0]
    obs_id = anom["observation_id"]

    obs_res, corr_res = await asyncio.gather(
        db_client.select("observations", params={"id": f"eq.{obs_id}", "limit": 1}),
        db_client.select("corrected_values", params={"observation_id": f"eq.{obs_id}"}),
    )
    obs_dict = obs_res[0] if obs_res else {}
    if obs_dict.get("station_id"):
        stn = await get_station_by_id(obs_dict["station_id"]) or {}
        obs_dict = {**obs_dict, "station_code": stn.get("station_code"), "station_name": stn.get("name")}

    return AnomalyDetailResponse(
        anomaly=AnomalyScoreDetail(**{k: v for k, v in anom.items() if k in AnomalyScoreDetail.model_fields}),
        observation=obs_dict,
        corrected_values=[
            CorrectedValueSchema(
                parameter=c["parameter"],
                raw_value=c.get("raw_value"),
                corrected_value=c.get("corrected_value"),
                correction_method=c.get("correction_method", "none"),
                correction_confidence=c.get("correction_confidence", 0.0),
            )
            for c in corr_res
        ],
    )
