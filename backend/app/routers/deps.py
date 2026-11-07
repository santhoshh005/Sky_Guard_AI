"""Shared router dependencies: write-endpoint auth, ID validation and PostgREST filter helpers."""
import hmac
import uuid
from typing import Any, Dict, Optional

from fastapi import Header, HTTPException, status

from app.config import settings


async def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    """Protect write endpoints when ``API_KEY`` is configured (constant-time comparison)."""
    if not settings.API_KEY:
        return
    if not x_api_key or not hmac.compare_digest(x_api_key, settings.API_KEY):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")


def ensure_uuid(value: str, what: str = "Resource") -> str:
    """Reject malformed IDs with 404 before they reach the database (which would 400/500)."""
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=404, detail=f"{what} not found")


def add_time_range(params: Dict[str, Any], column: str, start: Optional[Any], end: Optional[Any]) -> None:
    """Add an inclusive time window. Both bounds may be set (PostgREST ``and=(...)``)."""
    s = start.isoformat() if hasattr(start, "isoformat") else start
    e = end.isoformat() if hasattr(end, "isoformat") else end
    if s and e:
        params["and"] = f"({column}.gte.{s},{column}.lte.{e})"
    elif s:
        params[column] = f"gte.{s}"
    elif e:
        params[column] = f"lte.{e}"
