"""Alert management endpoints for SkyGuard AI.
Implements GET /alerts and PATCH /alerts/{id}/resolve.
Specified in /docs/HANDOFF.md §8.4.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query

from app.models.database import db_client
from app.models.schemas import AlertListResponse, AlertResponse

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    station_id: Optional[str] = None,
    severity: Optional[str] = None,
    is_resolved: Optional[bool] = None,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """List system and sensor alerts with resolution status and severity filters."""
    params: Dict[str, Any] = {
        "order": "created_at.desc",
    }
    if station_id:
        params["station_id"] = f"eq.{station_id}"
    if severity:
        params["severity"] = f"eq.{severity}"
    if is_resolved is not None:
        params["is_resolved"] = f"eq.{str(is_resolved).lower()}"
    if from_date:
        params["created_at"] = f"gte.{from_date}"
    if to_date:
        params["created_at"] = f"lte.{to_date}"

    alerts_data = await db_client.select("alerts", params=params)

    # Fetch station metadata for names
    stations = await db_client.select("stations")
    stn_map = {s["id"]: s for s in stations}

    alerts: List[AlertResponse] = []
    for a in alerts_data:
        stn = stn_map.get(a["station_id"], {})
        alerts.append(AlertResponse(
            id=a["id"],
            station_id=a["station_id"],
            station_name=stn.get("name", "Unknown Station"),
            station_code=stn.get("station_code", "UNKNOWN"),
            anomaly_score_id=a.get("anomaly_score_id"),
            alert_type=a["alert_type"],
            severity=a["severity"],
            title=a["title"],
            description=a.get("description"),
            parameter=a.get("parameter"),
            is_resolved=a.get("is_resolved", False),
            resolved_at=a.get("resolved_at"),
            created_at=a.get("created_at"),
        ))

    total = len(alerts)
    start_idx = (page - 1) * limit
    paginated = alerts[start_idx : start_idx + limit]

    return AlertListResponse(
        alerts=paginated,
        total=total,
        page=page,
    )


@router.patch("/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert(alert_id: str):
    """Mark an active alert as acknowledged and resolved."""
    res = await db_client.select("alerts", params={"id": f"eq.{alert_id}", "limit": 1})
    if not res:
        raise HTTPException(status_code=404, detail="Alert not found")

    updated_time = datetime.now(timezone.utc).isoformat()
    update_res = await db_client.update(
        "alerts",
        params={"id": f"eq.{alert_id}"},
        data={"is_resolved": True, "resolved_at": updated_time}
    )
    updated = update_res[0] if update_res else res[0]
    updated["is_resolved"] = True
    updated["resolved_at"] = updated_time

    # Fetch station
    stn_res = await db_client.select("stations", params={"id": f"eq.{updated['station_id']}", "limit": 1})
    stn = stn_res[0] if stn_res else {}

    return AlertResponse(
        id=updated["id"],
        station_id=updated["station_id"],
        station_name=stn.get("name"),
        station_code=stn.get("station_code"),
        anomaly_score_id=updated.get("anomaly_score_id"),
        alert_type=updated["alert_type"],
        severity=updated["severity"],
        title=updated["title"],
        description=updated.get("description"),
        parameter=updated.get("parameter"),
        is_resolved=True,
        resolved_at=updated_time,
        created_at=updated.get("created_at"),
    )
