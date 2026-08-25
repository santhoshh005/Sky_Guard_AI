import asyncio
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
from app.routers.observations import station_id_cache

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
        "limit": limit,
        "offset": (page - 1) * limit,
    }
    if severity:
        params["severity"] = f"eq.{severity}"
    if root_cause:
        params["root_cause"] = f"eq.{root_cause}"
    if from_date:
        params["scored_at"] = f"gte.{from_date}"
    if to_date:
        params["scored_at"] = f"lte.{to_date}"

    # Query paginated anomaly scores and total count in parallel
    count_params = {k: v for k, v in params.items() if k not in ["limit", "offset", "order"]}
    scores_task = db_client.select("anomaly_scores", params=params)
    count_task = db_client.count("anomaly_scores", params=count_params)

    anomaly_scores, total_count = await asyncio.gather(scores_task, count_task)

    # Fetch observation details for only the paginated slice in parallel
    obs_ids = list({a["observation_id"] for a in anomaly_scores if a.get("observation_id")})
    obs_map = {}
    if obs_ids:
        obs_tasks = [
            db_client.select("observations", params={"id": f"eq.{oid}", "limit": 1})
            for oid in obs_ids
        ]
        obs_results = await asyncio.gather(*obs_tasks)
        for res_list in obs_results:
            if res_list:
                o = res_list[0]
                s_id = o.get("station_id")
                stn = station_id_cache.get(s_id, {})
                obs_map[o["id"]] = {
                    "station_id": s_id,
                    "station_code": stn.get("station_code", "AWS"),
                    "station_name": stn.get("name", "Automatic Weather Station"),
                    "observed_at": o.get("observed_at"),
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
            confidence=a.get("confidence", 0.5),
            severity=a["severity"],
            root_cause=a.get("root_cause"),
            explanation=a.get("explanation"),
            scored_at=a["scored_at"],
        ))

    return AnomalyListResponse(
        anomalies=items,
        total=total_count,
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
