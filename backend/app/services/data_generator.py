"""Synthetic weather data generator and anomaly injector for SkyGuard AI.
Implements profiles and recipes from /docs/HANDOFF.md §9 & §13.
"""
import copy
import math
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

PARAMETERS = [
    "temperature",
    "humidity",
    "pressure",
    "wind_speed",
    "wind_direction",
    "rainfall",
    "solar_radiation",
]

NORMAL_PROFILES: Dict[str, Dict[str, Any]] = {
    "temperature": {
        "base": 30.0,
        "diurnal_amp": 5.0,
        "noise_std": 0.5,
        "peak_hour": 14,
        "min_bound": 10.0,
        "max_bound": 45.0,
    },
    "humidity": {
        "base": 70.0,
        "diurnal_amp": 15.0,
        "noise_std": 2.0,
        "peak_hour": 5,  # humidity peaks at dawn
        "min_bound": 20.0,
        "max_bound": 99.0,
    },
    "pressure": {
        "base": 1010.0,
        "diurnal_amp": 2.0,
        "noise_std": 0.5,
        "peak_hour": 10,
        "min_bound": 980.0,
        "max_bound": 1035.0,
    },
    "wind_speed": {
        "base": 3.0,
        "diurnal_amp": 2.0,
        "noise_std": 1.0,
        "peak_hour": 15,
        "min_bound": 0.0,
        "max_bound": 25.0,
    },
    "wind_direction": {
        "base": 225.0,
        "diurnal_amp": 30.0,
        "noise_std": 10.0,
        "peak_hour": 12,
        "min_bound": 0.0,
        "max_bound": 360.0,
    },
    "rainfall": {
        "base": 0.0,
        "probability": 0.05,
        "rain_range": [0.2, 15.0],
    },
    "solar_radiation": {
        "base": 0.0,
        "max_value": 900.0,
        "sunrise": 6,
        "sunset": 18,
    },
}

DEMO_STATIONS = [
    {
        "station_code": "AWS_MUM_001",
        "name": "Mumbai Colaba",
        "latitude": 18.907,
        "longitude": 72.805,
        "elevation_m": 11.0,
        "state": "Maharashtra",
        "district": "Mumbai",
        "station_type": "AWS",
        "expected_interval_min": 15,
    },
    {
        "station_code": "AWS_DEL_001",
        "name": "Delhi Safdarjung",
        "latitude": 28.585,
        "longitude": 77.208,
        "elevation_m": 216.0,
        "state": "Delhi",
        "district": "New Delhi",
        "station_type": "AWS",
        "expected_interval_min": 15,
    },
    {
        "station_code": "AWS_CHN_001",
        "name": "Chennai Nungambakkam",
        "latitude": 13.066,
        "longitude": 80.251,
        "elevation_m": 16.0,
        "state": "Tamil Nadu",
        "district": "Chennai",
        "station_type": "AWS",
        "expected_interval_min": 15,
    },
    {
        "station_code": "AWS_KOL_001",
        "name": "Kolkata Alipore",
        "latitude": 22.534,
        "longitude": 88.339,
        "elevation_m": 6.0,
        "state": "West Bengal",
        "district": "Kolkata",
        "station_type": "AWS",
        "expected_interval_min": 15,
    },
    {
        "station_code": "AWS_BLR_001",
        "name": "Bengaluru HAL",
        "latitude": 12.950,
        "longitude": 77.668,
        "elevation_m": 920.0,
        "state": "Karnataka",
        "district": "Bengaluru",
        "station_type": "AWS",
        "expected_interval_min": 15,
    },
]


def generate_value(param: str, hour: float, elevation_offset: float = 0.0) -> float:
    """Generate a realistic physical weather reading for a given hour."""
    profile = NORMAL_PROFILES[param]

    if param == "rainfall":
        if random.random() < profile["probability"]:
            return round(random.uniform(*profile["rain_range"]), 2)
        return 0.0

    if param == "solar_radiation":
        if profile["sunrise"] <= hour <= profile["sunset"]:
            progress = (hour - profile["sunrise"]) / (profile["sunset"] - profile["sunrise"])
            val = profile["max_value"] * math.sin(progress * math.pi) + random.gauss(0, 20)
            return round(max(0.0, val), 2)
        return 0.0

    # Diurnal sinusoid
    diurnal = profile["diurnal_amp"] * math.sin(2 * math.pi * (hour - profile["peak_hour"] + 6) / 24)
    base = profile["base"]

    # Mild elevation adjustments
    if param == "temperature":
        base -= (elevation_offset / 100.0) * 0.65  # lapse rate ~0.65C per 100m
    elif param == "pressure":
        base -= (elevation_offset / 10.0) * 1.2  # ~1.2 hPa drop per 10m

    raw = base + diurnal + random.gauss(0, profile["noise_std"])

    if "min_bound" in profile and "max_bound" in profile:
        raw = max(profile["min_bound"], min(profile["max_bound"], raw))

    return round(raw, 2)


def generate_observation_dict(
    station_code: str,
    timestamp: datetime,
    elevation_m: float = 0.0
) -> Dict[str, Any]:
    """Generate a single clean observation dictionary."""
    hour = timestamp.hour + timestamp.minute / 60.0
    obs = {
        "station_code": station_code,
        "observed_at": timestamp.isoformat(),
    }
    for p in PARAMETERS:
        obs[p] = generate_value(p, hour, elevation_offset=elevation_m)
    return obs


def generate_time_series(
    station_code: str,
    start_time: datetime,
    num_observations: int,
    interval_min: int = 15,
    elevation_m: float = 0.0
) -> List[Dict[str, Any]]:
    """Generate a sequence of continuous clean observations."""
    records = []
    current_time = start_time
    for _ in range(num_observations):
        obs = generate_observation_dict(station_code, current_time, elevation_m)
        records.append(obs)
        current_time += timedelta(minutes=interval_min)
    return records


# ==============================================================================
# Anomaly Injections
# ==============================================================================

def create_spike_observation(
    station_code: str,
    timestamp: datetime,
    target_params: List[str],
    magnitude: float = 3.0,
    elevation_m: float = 0.0
) -> Dict[str, Any]:
    """Create a single observation with sudden spikes in target params."""
    obs = generate_observation_dict(station_code, timestamp, elevation_m)
    for p in target_params:
        std = NORMAL_PROFILES[p].get("noise_std", 1.0)
        direction = random.choice([-1, 1])
        # Sudden 5x-10x sigma spike
        jump = magnitude * 10.0 * std * direction
        obs[p] = round(obs[p] + jump, 2)
    return obs


def create_frozen_observations(
    station_code: str,
    start_time: datetime,
    count: int,
    target_params: List[str],
    interval_min: int = 15,
    elevation_m: float = 0.0
) -> List[Dict[str, Any]]:
    """Create a sequence where target params are frozen at their first value."""
    records = []
    first_obs = generate_observation_dict(station_code, start_time, elevation_m)
    frozen_vals = {p: first_obs[p] for p in target_params}
    records.append(first_obs)

    curr_time = start_time + timedelta(minutes=interval_min)
    for _ in range(count - 1):
        obs = generate_observation_dict(station_code, curr_time, elevation_m)
        for p in target_params:
            obs[p] = frozen_vals[p]
        records.append(obs)
        curr_time += timedelta(minutes=interval_min)

    return records


def create_drift_observations(
    station_code: str,
    start_time: datetime,
    count: int,
    target_params: List[str],
    magnitude: float = 2.0,
    interval_min: int = 15,
    elevation_m: float = 0.0
) -> List[Dict[str, Any]]:
    """Create a sequence where target params gradually drift upward or downward."""
    records = []
    curr_time = start_time
    direction = random.choice([-1, 1])
    for i in range(count):
        obs = generate_observation_dict(station_code, curr_time, elevation_m)
        progress = (i + 1) / float(count)
        for p in target_params:
            std = NORMAL_PROFILES[p].get("noise_std", 1.0)
            drift = magnitude * 5.0 * std * progress * direction
            obs[p] = round(obs[p] + drift, 2)
        records.append(obs)
        curr_time += timedelta(minutes=interval_min)

    return records


def create_multivariate_observation(
    station_code: str,
    timestamp: datetime,
    target_params: Optional[List[str]] = None,
    magnitude: float = 2.5,
    elevation_m: float = 0.0
) -> Dict[str, Any]:
    """Create a single observation with coupled physical anomalies across >=3 parameters."""
    if not target_params or len(target_params) < 3:
        target_params = ["temperature", "humidity", "pressure", "wind_speed"]

    obs = generate_observation_dict(station_code, timestamp, elevation_m)
    # Physically anomalous coupling: High temp + high humidity + low pressure + gust
    for p in target_params:
        std = NORMAL_PROFILES[p].get("noise_std", 1.0)
        shift = magnitude * 4.0 * std
        if p == "humidity":
            obs[p] = round(min(99.0, obs[p] + shift), 2)
        elif p == "pressure":
            obs[p] = round(max(900.0, obs[p] - shift), 2)
        elif p == "temperature":
            obs[p] = round(obs[p] + shift, 2)
        else:
            obs[p] = round(obs[p] + shift, 2)
    return obs
