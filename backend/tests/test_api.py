"""API workflow tests against the in-memory PostgREST stand-in."""
from datetime import datetime, timedelta, timezone

from app.config import settings


def _latest(fake_db, station_id):
    times = [datetime.fromisoformat(o["observed_at"]) for o in fake_db.tables["observations"] if o["station_id"] == station_id]
    return max(times)


def _clean_reading(seeded, when):
    from app.services.data_generator import generate_observation_dict

    return generate_observation_dict(seeded["station_code"], when, seeded["elevation_m"])


def test_health_and_validation(client):
    assert client.get("/api/v1/healthz").json()["models_loaded"] is True
    assert client.get("/api/v1/stations/not-a-uuid").status_code == 404
    assert client.get("/api/v1/alerts", params={"severity": "bogus"}).status_code == 422
    bad = {"station_code": "AWS_MUM_001", "observed_at": "2026-01-01T00:00:00Z", "temperature": "NaN"}
    assert client.post("/api/v1/observations", json=bad).status_code == 422


def test_ingest_clean_then_spike(client, seeded, fake_db):
    t = _latest(fake_db, seeded["id"]) + timedelta(minutes=15)
    res = client.post("/api/v1/observations", json=_clean_reading(seeded, t))
    assert res.status_code == 201, res.text
    assert res.json()["anomaly"]["is_anomaly"] is False
    assert fake_db.tables["corrected_values"] == []  # no placeholder rows for normal data

    spike = _clean_reading(seeded, t + timedelta(minutes=15))
    spike["temperature"] += 20
    body = client.post("/api/v1/observations", json=spike).json()["anomaly"]
    assert body["is_anomaly"] is True and body["root_cause"] == "spike"
    corr = fake_db.tables["corrected_values"]
    assert [c["parameter"] for c in corr] == ["temperature"]
    assert corr[0]["correction_method"] == "temporal_median"

    # duplicate timestamp -> 409, not 500
    assert client.post("/api/v1/observations", json=spike).status_code == 409


def test_anomaly_list_filters_by_station_and_detail(client, seeded, fake_db):
    t = _latest(fake_db, seeded["id"]) + timedelta(minutes=15)
    spike = _clean_reading(seeded, t)
    spike["humidity"] = 140.0
    client.post("/api/v1/observations", json=spike)

    listing = client.get("/api/v1/anomalies", params={"station_id": seeded["id"]}).json()
    assert listing["total"] == 1 and listing["anomalies"][0]["station_code"] == "AWS_MUM_001"
    other = client.get("/api/v1/anomalies", params={"station_id": "00000000-0000-0000-0000-000000000000"}).json()
    assert other["total"] == 0

    detail = client.get(f"/api/v1/anomalies/{listing['anomalies'][0]['id']}").json()
    assert "range" in detail["anomaly"]["qc_flags"]["humidity"]


def test_alerts_resolve_and_date_range(client, seeded, fake_db):
    t = _latest(fake_db, seeded["id"]) + timedelta(minutes=15)
    obs = {"station_code": seeded["station_code"], "observed_at": t.isoformat(), "rainfall": 0.0}
    client.post("/api/v1/observations", json=obs)  # 6 missing sensors -> communication alert

    alerts = client.get("/api/v1/alerts", params={"is_resolved": "false"}).json()
    assert alerts["total"] >= 1
    comm = [a for a in alerts["alerts"] if a["alert_type"] == "communication_loss"]
    assert comm, alerts

    now = datetime.now(timezone.utc)
    window = {"from": (now - timedelta(hours=1)).isoformat(), "to": (now + timedelta(hours=1)).isoformat()}
    assert client.get("/api/v1/alerts", params=window).json()["total"] == alerts["total"]
    past = {"from": (now - timedelta(days=3)).isoformat(), "to": (now - timedelta(days=2)).isoformat()}
    assert client.get("/api/v1/alerts", params=past).json()["total"] == 0

    resolved = client.patch(f"/api/v1/alerts/{comm[0]['id']}/resolve").json()
    assert resolved["is_resolved"] is True and resolved["resolved_at"]
    assert client.patch("/api/v1/alerts/00000000-0000-0000-0000-000000000000/resolve").status_code == 404


def test_stations_series_and_dashboard(client, seeded):
    stations = client.get("/api/v1/stations").json()
    assert stations["total"] == 1 and stations["stations"][0]["last_observation_at"]
    series = client.get(f"/api/v1/stations/{seeded['id']}/observations", params={"parameter": "pressure", "hours": 6}).json()
    assert 20 <= len(series["points"]) <= 26
    summary = client.get("/api/v1/dashboard/summary").json()
    assert summary["total_stations"] == 1 and summary["observations_24h"] > 0


def test_demo_injection_flows(client, seeded):
    res = client.post("/api/v1/demo/inject-anomaly",
                      json={"station_id": seeded["station_code"], "anomaly_type": "frozen", "parameters": ["humidity"]})
    assert res.status_code == 200, res.text
    assert res.json()["affected_parameters"] == ["humidity"]
    causes = [a["root_cause"] for a in client.get("/api/v1/anomalies").json()["anomalies"]]
    assert "frozen" in causes  # injected run must form consecutive identical readings
    assert client.post("/api/v1/demo/inject-anomaly",
                       json={"station_id": seeded["station_code"], "anomaly_type": "bogus"}).status_code == 422


def test_api_key_protects_writes(client, seeded, monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "s3cret-test-key")
    payload = {"station_code": "AWS_NEW_001", "name": "Test", "latitude": 20.0, "longitude": 78.0}
    assert client.post("/api/v1/stations", json=payload).status_code == 401
    assert client.post("/api/v1/stations", json=payload, headers={"X-API-Key": "wrong"}).status_code == 401
    ok = client.post("/api/v1/stations", json=payload, headers={"X-API-Key": "s3cret-test-key"})
    assert ok.status_code == 201
    assert client.post("/api/v1/stations", json=payload, headers={"X-API-Key": "s3cret-test-key"}).status_code == 409
    assert client.get("/api/v1/stations").status_code == 200  # reads stay public
