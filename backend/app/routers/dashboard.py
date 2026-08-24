"""Dashboard summary KPI endpoint for SkyGuard AI.
Implements GET /dashboard/summary.
Specified in /docs/HANDOFF.md §8.6.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
import numpy as np
from fastapi import APIRouter

from app.models.database import db_client
from app.models.schemas import DashboardSummary
from app.routers.observations import health_scorer

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary():
    """Retrieve high-level network statistics and health KPIs for the dashboard landing page."""
    stations = await db_client.select("stations")
    total_stations = len(stations)
    active_stations = len([s for s in stations if s.get("is_active", True)])

    now = datetime.now(timezone.utc)
    t_24h_ago = (now - timedelta(hours=24)).isoformat()

    # Anomalies in last 24h
    anomalies_24h_data = await db_client.select(
        "anomaly_scores",
        params={"is_anomaly": "eq.true", "scored_at": f"gte.{t_24h_ago}"}
    )
    anomalies_count = len(anomalies_24h_data)

    # Observations in last 24h
    obs_24h_data = await db_client.select(
        "observations",
        params={"observed_at": f"gte.{t_24h_ago}"}
    )
    obs_count = len(obs_24h_data)

    # Unresolved critical alerts
    critical_alerts_data = await db_client.select(
        "alerts",
        params={"is_resolved": "eq.false", "severity": "eq.critical"}
    )
    critical_alerts_count = len(critical_alerts_data)

    # Sensor health calculations
    health_scores = []
    needing_maintenance = 0

    for stn in stations:
        score, status_str = health_scorer.get_overall_health(stn["id"])
        health_scores.append(score)
        if score < 40.0:
            needing_maintenance += 1

    avg_health = float(np.mean(health_scores)) if health_scores else 100.0

    return DashboardSummary(
        total_stations=total_stations,
        active_stations=active_stations,
        anomalies_24h=anomalies_count,
        critical_alerts=critical_alerts_count,
        avg_health=round(avg_health, 1),
        stations_needing_maintenance=needing_maintenance,
        observations_24h=obs_count,
    )
