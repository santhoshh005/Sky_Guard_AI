"""Async Supabase PostgREST client for SkyGuard AI.

The authoritative table definitions live in ``backend/schema.sql``.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.config import settings

logger = logging.getLogger("skyguard.db")


class DatabaseError(RuntimeError):
    """Raised when the PostgREST backend rejects or fails a request.

    ``detail`` holds the upstream response for server-side logs only; it is
    never returned to API clients.
    """

    def __init__(self, message: str, status_code: Optional[int] = None, detail: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


def _parse_total(content_range: Optional[str]) -> int:
    if content_range and "/" in content_range:
        total = content_range.rsplit("/", 1)[-1]
        if total.isdigit():
            return int(total)
    return 0


class SupabaseDB:
    def __init__(self) -> None:
        self.base_url = f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1"
        self.headers = {
            "apikey": settings.SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_ANON_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        self.client: Optional[httpx.AsyncClient] = None

    @property
    def configured(self) -> bool:
        return bool(settings.SUPABASE_URL and settings.SUPABASE_ANON_KEY)

    async def get_client(self) -> httpx.AsyncClient:
        if self.client is None or self.client.is_closed:
            limits = httpx.Limits(max_keepalive_connections=30, max_connections=100, keepalive_expiry=120.0)
            self.client = httpx.AsyncClient(timeout=settings.DB_TIMEOUT_SECONDS, limits=limits)
        return self.client

    async def close(self) -> None:
        if self.client and not self.client.is_closed:
            await self.client.aclose()

    async def _request(self, method: str, table: str, *, params=None, json=None, headers=None) -> httpx.Response:
        if not self.configured:
            raise DatabaseError("Database is not configured (set SUPABASE_URL and SUPABASE_ANON_KEY).")
        client = await self.get_client()
        try:
            response = await client.request(
                method,
                f"{self.base_url}/{table}",
                params=params,
                json=json,
                headers=headers or self.headers,
            )
        except httpx.HTTPError as exc:
            logger.error("Supabase %s %s transport error: %s", method, table, exc)
            raise DatabaseError("Database is unreachable.") from exc
        if response.status_code >= 400:
            logger.error("Supabase %s %s failed: %s %s", method, table, response.status_code, response.text[:500])
            raise DatabaseError(
                f"Database {method} on {table} failed.",
                status_code=response.status_code,
                detail=response.text,
            )
        return response

    async def select(
        self,
        table: str,
        params: Optional[Dict[str, Any]] = None,
        select_fields: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        p = dict(params or {})
        if select_fields:
            p["select"] = select_fields
        response = await self._request("GET", table, params=p)
        return response.json()

    async def select_with_count(
        self,
        table: str,
        params: Optional[Dict[str, Any]] = None,
        select_fields: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Return one page of rows plus the exact total, in a single request."""
        p = dict(params or {})
        if select_fields:
            p["select"] = select_fields
        headers = dict(self.headers)
        headers["Prefer"] = "count=exact"
        response = await self._request("GET", table, params=p, headers=headers)
        rows = response.json()
        return rows, _parse_total(response.headers.get("content-range")) or len(rows)

    async def count(self, table: str, params: Optional[Dict[str, Any]] = None) -> int:
        headers = dict(self.headers)
        headers["Prefer"] = "count=exact"
        p = dict(params or {})
        p["limit"] = 0
        p.setdefault("select", "id")
        response = await self._request("GET", table, params=p, headers=headers)
        return _parse_total(response.headers.get("content-range"))

    async def insert(self, table: str, data: Any, on_conflict: Optional[str] = None) -> List[Dict[str, Any]]:
        headers = dict(self.headers)
        params = {}
        if on_conflict:
            headers["Prefer"] = "resolution=merge-duplicates,return=representation"
            params["on_conflict"] = on_conflict
        response = await self._request("POST", table, params=params, json=data, headers=headers)
        return response.json() if response.text else []

    async def update(self, table: str, params: Dict[str, Any], data: Dict[str, Any]) -> List[Dict[str, Any]]:
        response = await self._request("PATCH", table, params=params, json=data)
        return response.json() if response.text else []

    async def delete(self, table: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        response = await self._request("DELETE", table, params=params)
        return response.json() if response.text else []


db_client = SupabaseDB()
