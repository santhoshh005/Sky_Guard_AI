import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.models.database import db_client
from app.routers import (
    alerts,
    anomalies,
    dashboard,
    demo,
    health,
    observations,
    stations,
    websocket,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Pre-warm models and cache stations
    print("[*] Starting SkyGuard AI backend services...")
    try:
        stns = await db_client.select("stations")
        for s in stns:
            observations.station_cache[s["station_code"]] = s
            observations.station_id_cache[s["id"]] = s
        print(f"  [OK] Cached {len(stns)} AWS stations.")
    except Exception as e:
        print(f"  [WARN] Initial station caching deferred: {e}")

    yield

    # Shutdown: Close database client
    print("[*] Shutting down SkyGuard AI backend...")
    await db_client.close()


app = FastAPI(
    title="SkyGuard AI — Weather Station Anomaly Detection Platform",
    description="MoES / IMD AWS Anomaly Detection, Sensor Health Scoring, and Value Correction API (SIH26073)",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API v1 Routers
api_v1_prefix = "/api/v1"
app.include_router(observations.router, prefix=api_v1_prefix)
app.include_router(stations.router, prefix=api_v1_prefix)
app.include_router(anomalies.router, prefix=api_v1_prefix)
app.include_router(alerts.router, prefix=api_v1_prefix)
app.include_router(health.router, prefix=api_v1_prefix)
app.include_router(demo.router, prefix=api_v1_prefix)
app.include_router(dashboard.router, prefix=api_v1_prefix)
app.include_router(websocket.router, prefix=api_v1_prefix)


@app.get("/")
async def root():
    return {
        "service": "SkyGuard AI API",
        "status": "online",
        "version": "1.0.0",
        "docs_url": "/docs",
    }


@app.get("/api/v1/healthz")
async def healthz():
    return {"status": "healthy", "service": "skyguard-ai-backend"}
