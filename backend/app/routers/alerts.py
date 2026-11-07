"""Alert endpoints: GET /alerts and PATCH /alerts/{id}/resolve."""
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.models.database import db_client
from app.models.schemas import AlertListResponse, AlertResponse, AlertSeverity
from app.routers.deps import add_time_range, ensure_uuid, require_api_key
from app.routers.observations import get_station_by_id

router = APIRouter(prefix="/alerts", tags=["Alerts"])


async def _to_response(a: Dict[str, Any]) -> AlertResponse:
    stn = await get_station_by_id(a["station_id"]) or {}
    return AlertResponse(
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
    )


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    station_id: Optional[str] = None,
    severity: Optional[AlertSeverity] = None,
    is_resolved: Optional[bool] = None,
    from_date: Optional[datetime] = Query(None, alias="from"),
    to_date: Optional[datetime] = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """List alerts (newest first) with station, severity, resolution and time filters."""
    params: Dict[str, Any] = {"order": "created_at.desc", "limit": limit, "offset": (page - 1) * limit}
    if station_id:
        params["station_id"] = f"eq.{ensure_uuid(station_id, 'Station')}"
    if severity:
        params["severity"] = f"eq.{severity}"
    if is_resolved is not None:
        params["is_resolved"] = f"eq.{str(is_resolved).lower()}"
    add_time_range(params, "created_at", from_date, to_date)

    rows, total = await db_client.select_with_count("alerts", params=params)
    return AlertListResponse(alerts=[await _to_response(a) for a in rows], total=total, page=page)


@router.patch("/{alert_id}/resolve", response_model=AlertResponse, dependencies=[Depends(require_api_key)])
async def resolve_alert(alert_id: str):
    """Mark an alert as resolved (idempotent)."""
    alert_id = ensure_uuid(alert_id, "Alert")
    updated = await db_client.update(
        "alerts",
        params={"id": f"eq.{alert_id}"},
        data={"is_resolved": True, "resolved_at": datetime.now(timezone.utc).isoformat()},
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Alert not found")
    return await _to_response(updated[0])
