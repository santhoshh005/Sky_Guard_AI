"""SkyGuard AI FastAPI application."""
import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Make the repository root importable so `ml.inference` resolves when run from backend/
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from app.config import settings  # noqa: E402
from app.models.database import DatabaseError, db_client  # noqa: E402
from app.models.schemas import PARAMETERS  # noqa: E402
from app.routers import alerts, anomalies, dashboard, demo, health, observations, stations, websocket  # noqa: E402

logging.basicConfig(level=settings.LOG_LEVEL.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("skyguard")
API_V1 = "/api/v1"


async def _warm_start() -> None:
    """Cache stations and restore the latest persisted health state per sensor."""
    stations_list = await db_client.select("stations")
    for s in stations_list:
        observations.station_cache[s["station_code"]] = s
        observations.station_id_cache[s["id"]] = s

    async def restore(station_id: str) -> int:
        rows = await db_client.select(
            "sensor_health_history",
            params={"station_id": f"eq.{station_id}", "order": "recorded_at.desc", "limit": len(PARAMETERS) * 4},
        )
        seen = set()
        for r in rows:
            if r["parameter"] in seen:
                continue
            seen.add(r["parameter"])
            observations.health_scorer.restore_state(
                station_id, r["parameter"], r["health_score"], r.get("anomaly_streak", 0), r.get("recorded_at")
            )
        return len(seen)

    restored = await asyncio.gather(*(restore(s["id"]) for s in stations_list))
    logger.info("Cached %d stations; restored health for %d sensors", len(stations_list), sum(restored))


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not db_client.configured:
        logger.error("SUPABASE_URL / SUPABASE_ANON_KEY are not set; database calls will fail.")
    if not settings.API_KEY:
        logger.warning("API_KEY is not set: write endpoints are unauthenticated. Set it in production.")
    if not (observations.if_inference.loaded and observations.ae_inference.loaded):
        logger.warning("ML artifacts missing; run `python -m ml.training.train_models`.")
    try:
        await _warm_start()
    except DatabaseError as exc:
        logger.warning("Warm start skipped (database unavailable): %s", exc)
    yield
    await db_client.close()


app = FastAPI(
    title="SkyGuard AI - Weather Station Anomaly Detection Platform",
    description="AWS anomaly detection, sensor health scoring and value correction API (SIH26073, MoES / IMD)",
    version="1.1.0",
    lifespan=lifespan,
)

_origins = settings.cors_origin_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,  # the dashboard uses no cookies; keeps "*" safe if configured
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


@app.exception_handler(DatabaseError)
async def database_error_handler(request: Request, exc: DatabaseError):
    # Upstream details are logged by the client; never leak them to callers
    return JSONResponse(status_code=503, content={"detail": "Database temporarily unavailable"})


for module in (observations, stations, anomalies, alerts, health, dashboard, websocket):
    app.include_router(module.router, prefix=API_V1)
if settings.ENABLE_DEMO_ENDPOINTS:
    app.include_router(demo.router, prefix=API_V1)


@app.get("/")
async def root():
    return {"service": "SkyGuard AI API", "status": "online", "version": app.version, "docs_url": "/docs"}


@app.get(f"{API_V1}/healthz")
async def healthz():
    return {
        "status": "healthy",
        "service": "skyguard-ai-backend",
        "database_configured": db_client.configured,
        "models_loaded": observations.if_inference.loaded and observations.ae_inference.loaded,
        "demo_endpoints": settings.ENABLE_DEMO_ENDPOINTS,
    }
