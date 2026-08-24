"""Anomaly query endpoints for SkyGuard AI.
Implements GET /anomalies and GET /anomalies/{id}.
Specified in /docs/HANDOFF.md §8.3.
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query

from app.models.database import db_client
from app.models.schemas import (
    AnomalyDetailResponse,
    AnomalyListItem,
    AnomalyListResponse,
    AnomalyScoreDetail,
    CorrectedValueSchema,
)

router = APIRouter(prefix="/anomalies", tags=["Anomalies"])


@router.get("", response_model=AnomalyListResponse)
async def list_anomalies(
    station_id: Optional[str] = None,
    severity: Optional[str] = None,
    root_cause: Optional[str] = None,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """Query anomalous events with filtering by station, severity, root cause, and time range."""
    params: Dict[str, Any] = {
        "is_anomaly": "eq.true",
        "order": "scored_at.desc",
    }
    if severity:
        params["severity"] = f"eq.{severity}"
    if root_cause:
        params["root_cause"] = f"eq.{root_cause}"
    if from_date:
        params["scored_at"] = f"gte.{from_date}"
    if to_date:
        params["scored_at"] = f"lte.{to_date}"

    anomaly_scores = await db_client.select("anomaly_scores", params=params)

    # Fetch observation details for station mapping
    obs_ids = [a["observation_id"] for a in anomaly_scores]
    obs_map = {}
    if obs_ids:
        # Fetch stations for names
        stations = await db_client.select("stations")
        stn_map = {s["id"]: s for s in stations}

        # Query observations in batch
        for obs_id in obs_ids:
            res = await db_client.select("observations", params={"id": f"eq.{obs_id}", "limit": 1})
            if res:
                o = res[0]
                stn = stn_map.get(o["station_id"], {})
                obs_map[obs_id] = {
                    "station_id": o["station_id"],
                    "station_code": stn.get("station_code", "UNKNOWN"),
                    "station_name": stn.get("name", "Unknown Station"),
                    "observed_at": o["observed_at"],
                }

    items: List[AnomalyListItem] = []
    for a in anomaly_scores:
        obs_info = obs_map.get(a["observation_id"], {})
        items.append(AnomalyListItem(
            id=a["id"],
            observation_id=a["observation_id"],
            station_id=obs_info.get("station_id"),
            station_code=obs_info.get("station_code"),
            station_name=obs_info.get("station_name"),
            observed_at=obs_info.get("observed_at", a["scored_at"]),
            fused_score=a["fused_score"],
            severity=a["severity"],
            root_cause=a.get("root_cause"),
            confidence=a["confidence"],
            explanation=a.get("explanation"),
            scored_at=a.get("scored_at"),
        ))

    total = len(items)
    start_idx = (page - 1) * limit
    paginated = items[start_idx : start_idx + limit]

    return AnomalyListResponse(
        anomalies=paginated,
        total=total,
        page=page,
    )


@router.get("/{anomaly_score_id}", response_model=AnomalyDetailResponse)
async def get_anomaly_detail(anomaly_score_id: str):
    """Retrieve full anomaly breakdown including SHAP waterfall and estimated corrected values."""
    res = await db_client.select("anomaly_scores", params={"id": f"eq.{anomaly_score_id}", "limit": 1})
    if not res:
        raise HTTPException(status_code=404, detail="Anomaly score record not found")
    anom = res[0]

    # Fetch observation
    obs_id = anom["observation_id"]
    obs_res = await db_client.select("observations", params={"id": f"eq.{obs_id}", "limit": 1})
    obs_dict = obs_res[0] if obs_res else {}

    # Fetch corrected values
    corr_res = await db_client.select("corrected_values", params={"observation_id": f"eq.{obs_id}"})
    corrected_list = [
        CorrectedValueSchema(
            parameter=c["parameter"],
            raw_value=c.get("raw_value"),
            corrected_value=c.get("corrected_value"),
            correction_method=c.get("correction_method", "none"),
            correction_confidence=c.get("correction_confidence", 0.0),
        )
        for c in corr_res
    ]

    return AnomalyDetailResponse(
        anomaly=AnomalyScoreDetail(**anom),
        observation=obs_dict,
        corrected_values=corrected_list,
    )
