"""Unit tests for the detection services (no I/O)."""
import random
from datetime import datetime, timedelta, timezone

import pytest

from app.services.anomaly_detector import AnomalyDetector
from app.services.corrector import ValueCorrector
from app.services.data_generator import (
    create_drift_observations,
    create_frozen_observations,
    generate_time_series,
    station_pressure_base,
)
from app.services.drift import DriftDetector
from app.services.feature_engineer import local_solar_hour, param_delta
from app.services.health_scorer import HealthScorer
from app.services.quality_checks import QualityChecker
from app.services.root_cause import RootCauseClassifier

START = datetime(2026, 3, 1, tzinfo=timezone.utc)
CODE = "AWS_MUM_001"


@pytest.fixture(autouse=True)
def _seed():
    random.seed(7)


def history(n=100, start=START):
    return generate_time_series(CODE, start, n, 15, 11.0)


def next_time(hist):
    return datetime.fromisoformat(hist[-1]["observed_at"]) + timedelta(minutes=15)


def test_wind_direction_delta_is_circular():
    assert param_delta("wind_direction", 2.0, 358.0) == pytest.approx(4.0)
    assert param_delta("temperature", 2.0, 358.0) == pytest.approx(-356.0)


def test_local_solar_hour_uses_longitude():
    # 06:30 UTC at 77.6E is ~11:40 local solar time
    assert local_solar_hour(datetime(2026, 1, 1, 6, 30, tzinfo=timezone.utc), 77.6) == pytest.approx(11.67, abs=0.01)


def test_bengaluru_pressure_reflects_elevation():
    assert 900 < station_pressure_base(920.0) < 912  # real HAL station pressure ~907 hPa


def test_clean_observation_has_no_qc_flags():
    hist = history()
    obs = generate_time_series(CODE, next_time(hist), 1, 15, 11.0)[0]
    score, flags = QualityChecker.run_checks(obs, hist, 15, 72.8)
    assert score == 0.0
    assert all(not flags[p] for p in flags if p != "qc_score")


def test_single_hard_flag_dominates_qc_score():
    hist = history()
    obs = dict(generate_time_series(CODE, next_time(hist), 1, 15, 11.0)[0], temperature=75.0)
    score, flags = QualityChecker.run_checks(obs, hist, 15, 72.8)
    assert "range" in flags["temperature"] and "spike" in flags["temperature"]
    assert score > 0.99


def test_spike_is_not_reflagged_on_return_to_normal():
    hist = history()
    spike = dict(generate_time_series(CODE, next_time(hist), 1, 15, 11.0)[0])
    spike["temperature"] += 20
    hist.append(spike)
    recovery = generate_time_series(CODE, next_time(hist), 1, 15, 11.0)[0]
    _, flags = QualityChecker.run_checks(recovery, hist, 15, 72.8)
    assert "spike" not in flags["temperature"]


def test_frozen_detected_but_natural_zeros_are_not():
    hist = history()
    run = create_frozen_observations(CODE, next_time(hist), 4, ["humidity"], 15, 11.0)
    hist.extend(run[:3])
    _, flags = QualityChecker.run_checks(run[3], hist, 15, 72.8)
    assert "frozen" in flags["humidity"]
    assert "frozen" not in flags["rainfall"]  # 0 mm is natural


def test_fusion_hard_flag_forces_anomaly_with_high_confidence():
    res = AnomalyDetector.fuse_scores(0.9, 0.1, 0.1, hard_qc_flag=True)
    assert res.is_anomaly and res.severity == "warning" and res.confidence >= 0.9
    assert not AnomalyDetector.fuse_scores(0.0, 0.3, 0.3).is_anomaly
    assert AnomalyDetector.fuse_scores(1.0, 1.0, 1.0).severity == "critical"


def test_health_does_not_decay_under_normal_operation():
    """Regression: SHAP shares (which always sum to 1) used to penalise 2-3 sensors per reading."""
    scorer = HealthScorer()
    shap = {"parameter_contributions": {"temperature": 0.3, "humidity": 0.25, "pressure": 0.2}}
    t = START
    for _ in range(200):
        scorer.update_sensor_health("s1", {"observed_at": t.isoformat(), "temperature": 30.0},
                                    {}, shap, is_anomaly=False)
        t += timedelta(minutes=15)
    assert scorer.get_overall_health("s1") == (100.0, "healthy")


def test_health_penalises_flagged_sensor_and_caps_gap_decay():
    scorer = HealthScorer()
    scorer.update_sensor_health("s1", {"observed_at": START.isoformat()}, {"temperature": ["spike"]}, {})
    assert scorer.get_state("s1", "temperature").health_score < 100
    later = START + timedelta(days=3)
    scorer.update_sensor_health("s1", {"observed_at": later.isoformat()}, {}, {}, is_anomaly=False)
    assert scorer.get_state("s1", "humidity").health_score >= 90  # 3-day outage costs <= 10 points


def test_drift_detected_on_ramp_not_on_clean_data():
    detector = DriftDetector()  # diurnal-persistence fallback (no station regression)
    hist = history(110)
    clean = generate_time_series(CODE, next_time(hist), 1, 15, 11.0)[0]
    assert detector.detect(CODE, clean, hist) == {}

    ramp = create_drift_observations(CODE, next_time(hist), 8, ["temperature"], magnitude=3.0, interval_min=15, elevation_m=11.0)
    found = {}
    for o in ramp:
        found = detector.detect(CODE, o, hist) or found
        hist.append(o)
    assert "temperature" in found


def test_root_cause_order():
    obs = {"observed_at": START.isoformat(), "temperature": None, "humidity": None, "pressure": None}
    assert RootCauseClassifier.classify(obs, {}, {}, 0.0, True, []).root_cause == "communication"
    obs = {"observed_at": START.isoformat(), "temperature": 30.0, "humidity": 70.0, "pressure": 1000.0,
           "wind_speed": 3.0, "wind_direction": 200.0, "rainfall": 0.0, "solar_radiation": 100.0}
    res = RootCauseClassifier.classify(obs, {"humidity": ["frozen"], "temperature": ["spike"]}, {}, 0.0, True, [])
    assert res.root_cause == "frozen" and res.parameters == ["humidity"]
    res = RootCauseClassifier.classify(obs, {"temperature": ["spike"]}, {}, 0.0, True, [dict(obs, temperature=20.0)])
    assert res.root_cause == "spike" and res.parameters == ["temperature"]
    assert RootCauseClassifier.classify(obs, {}, {}, 0.0, False, []).root_cause is None


def test_corrector_only_touches_affected_parameters():
    corrector = ValueCorrector()
    hist = history()
    obs = dict(generate_time_series(CODE, next_time(hist), 1, 15, 11.0)[0])
    true_temp = obs["temperature"]
    obs["temperature"] += 25
    assert corrector.estimate_corrections(obs, False, 0.9, None, CODE, hist, ["temperature"]) == []
    out = corrector.estimate_corrections(obs, True, 0.9, "spike", CODE, hist, ["temperature"])
    assert [c.parameter for c in out] == ["temperature"]
    assert out[0].correction_method == "temporal_median"
    assert abs(out[0].corrected_value - true_temp) < 2.5
