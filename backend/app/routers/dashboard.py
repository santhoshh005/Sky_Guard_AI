import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
import numpy as np
from fastapi import APIRouter

from app.models.database import db_client
from app.models.schemas import DashboardSummary
from app.routers.observations import health_scorer, station_cache

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# Lightweight in-memory cached summary
_cached_summary = None
_cached_time = 0.0


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary():
    """Retrieve high-level network statistics and health KPIs with sub-100ms parallel queries."""
    global _cached_summary, _cached_time
    import time
    now_ts = time.time()
    if _cached_summary and (now_ts - _cached_time < 3.0):
        return _cached_summary

    now = datetime.now(timezone.utc)
    t_24h_ago = (now - timedelta(hours=24)).isoformat()

    # Query stations, counts in parallel
    stations_task = db_client.select("stations", select_fields="id,name,station_code,is_active") if not station_cache else None
    anomalies_task = db_client.count("anomaly_scores", params={"is_anomaly": "eq.true", "scored_at": f"gte.{t_24h_ago}"})
    obs_task = db_client.count("observations", params={"observed_at": f"gte.{t_24h_ago}"})
    alerts_task = db_client.count("alerts", params={"is_resolved": "eq.false", "severity": "eq.critical"})

    tasks = [anomalies_task, obs_task, alerts_task]
    if stations_task:
        tasks.insert(0, stations_task)
        results = await asyncio.gather(*tasks)
        stations = results[0]
        anomalies_count = results[1]
        obs_count = results[2]
        critical_alerts_count = results[3]
    else:
        stations = list(station_cache.values())
        results = await asyncio.gather(*tasks)
        anomalies_count = results[0]
        obs_count = results[1]
        critical_alerts_count = results[2]

    total_stations = len(stations)
    active_stations = len([s for s in stations if s.get("is_active", True)])

    # Sensor health calculations from in-memory health scorer state
    health_scores = []
    needing_maintenance = 0

    for stn in stations:
        score, status_str = health_scorer.get_overall_health(stn["id"])
        health_scores.append(score)
        if score < 40.0:
            needing_maintenance += 1

    avg_health = float(np.mean(health_scores)) if health_scores else 100.0

    res = DashboardSummary(
        total_stations=total_stations,
        active_stations=active_stations,
        anomalies_24h=anomalies_count,
        critical_alerts=critical_alerts_count,
        avg_health=round(avg_health, 1),
        stations_needing_maintenance=needing_maintenance,
        observations_24h=obs_count,
    )
    _cached_summary = res
    _cached_time = now_ts
    return res
