"""Database seeder for SkyGuard AI.
Inserts the 5 IMD demo stations and 7 days of initial clean observation data into Supabase.
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from app.models.database import db_client
from app.services.data_generator import DEMO_STATIONS, PARAMETERS, generate_time_series


async def seed_stations() -> List[Dict]:
    """Seed the 5 demo stations into Supabase stations table."""
    print("[+] Seeding 5 AWS stations...")
    existing = await db_client.select("stations")
    existing_codes = {s["station_code"]: s for s in existing}
    
    saved_stations = []
    for stn in DEMO_STATIONS:
        code = stn["station_code"]
        if code in existing_codes:
            saved_stations.append(existing_codes[code])
            print(f"  [OK] Station {code} already exists ({existing_codes[code]['id']})")
        else:
            payload = dict(stn)
            payload["id"] = str(uuid.uuid4())
            res = await db_client.insert("stations", payload)
            created = res[0] if res else payload
            saved_stations.append(created)
            print(f"  [+] Created station {code} ({created.get('id')})")
            
    return saved_stations


async def seed_baseline_observations(stations: List[Dict], days: int = 7) -> int:
    """Seed 7 days of 15-minute observations for each station."""
    print(f"[+] Seeding {days} days of baseline observations...")
    total_count = 0
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=days)
    obs_per_station = int((days * 24 * 60) / 15)  # 672 per station

    for stn in stations:
        station_id = stn["id"]
        station_code = stn["station_code"]
        elevation = stn.get("elevation_m") or 0.0
        
        # Check if observations already exist
        existing_obs = await db_client.select(
            "observations",
            params={"station_id": f"eq.{station_id}", "limit": 1}
        )
        if existing_obs:
            print(f"  [OK] Observations for {station_code} already seeded. Skipping.")
            continue

        raw_series = generate_time_series(
            station_code=station_code,
            start_time=start_time,
            num_observations=obs_per_station,
            interval_min=15,
            elevation_m=elevation
        )

        # Batch insert in chunks of 100
        chunk_size = 100
        records_to_insert = []
        for r in raw_series:
            record = {
                "id": str(uuid.uuid4()),
                "station_id": station_id,
                "observed_at": r["observed_at"],
                "temperature": r["temperature"],
                "humidity": r["humidity"],
                "pressure": r["pressure"],
                "wind_speed": r["wind_speed"],
                "wind_direction": r["wind_direction"],
                "rainfall": r["rainfall"],
                "solar_radiation": r["solar_radiation"],
            }
            records_to_insert.append(record)

        for i in range(0, len(records_to_insert), chunk_size):
            chunk = records_to_insert[i : i + chunk_size]
            await db_client.insert("observations", chunk)
            
        print(f"  [+] Seeded {len(records_to_insert)} observations for {station_code}")
        total_count += len(records_to_insert)

    return total_count


async def run_seed():
    try:
        stations = await seed_stations()
        total_obs = await seed_baseline_observations(stations, days=7)
        print(f"\n[DONE] Seeding complete! Inserted {len(stations)} stations and {total_obs} observations.")
    finally:
        await db_client.close()


if __name__ == "__main__":
    asyncio.run(run_seed())
