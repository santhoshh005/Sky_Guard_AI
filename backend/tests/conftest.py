"""Test fixtures: an in-memory stand-in for the Supabase PostgREST API.

Implements the subset of PostgREST used by the app: eq/lt/gte/lte/ilike filters, and=(...),
order, limit/offset, exact counts, and the embedded resources the routers request.
"""
import copy
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "backend", ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from app.models.database import DatabaseError, db_client  # noqa: E402
from app.services.feature_engineer import parse_ts  # noqa: E402

UNIQUE = {"stations": [("station_code",)], "observations": [("station_id", "observed_at")]}


def _coerce(v: Any):
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v)
    if s in ("true", "false"):
        return s == "true"
    if re.match(r"^\d{4}-\d{2}-\d{2}T", s):
        return parse_ts(s)
    try:
        return float(s)
    except ValueError:
        return s


def _match(value: Any, expr: str) -> bool:
    op, _, arg = expr.partition(".")
    if op == "ilike":
        pattern = "^" + re.escape(arg).replace(r"\*", ".*") + "$"
        return value is not None and re.match(pattern, str(value), re.I) is not None
    a, b = _coerce(value), _coerce(arg)
    if op == "eq":
        return a == b
    if a is None:
        return False
    return {"lt": a < b, "lte": a <= b, "gt": a > b, "gte": a >= b}[op]


def _split_top(select: str) -> List[str]:
    parts, depth, cur = [], 0, ""
    for ch in select:
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
            continue
        depth += ch == "("
        depth -= ch == ")"
        cur += ch
    return parts + ([cur] if cur else [])


class FakePostgREST:
    def __init__(self):
        self.tables: Dict[str, List[Dict[str, Any]]] = {
            t: [] for t in ("stations", "observations", "anomaly_scores", "alerts", "sensor_health_history", "corrected_values")
        }

    # -- embedding ---------------------------------------------------------
    def _embed(self, table: str, row: Dict[str, Any], name: str, cols: List[str], filters: Dict[str, str]):
        pick = lambda r: {c: r.get(c) for c in cols}  # noqa: E731
        if table == "anomaly_scores" and name == "observations":
            target = next((o for o in self.tables["observations"] if o["id"] == row["observation_id"]), None)
            if target and all(_match(target.get(k), v) for k, v in filters.items()):
                return pick(target)
            return None
        children = [r for r in self.tables[name] if r.get("observation_id") == row["id"]]
        children = [r for r in children if all(_match(r.get(k), v) for k, v in filters.items())]
        if name == "anomaly_scores":
            return pick(children[0]) if children else None
        return [pick(r) for r in children]

    def query(self, table: str, params: Optional[Dict[str, Any]]):
        params = dict(params or {})
        select = params.pop("select", "*")
        order = params.pop("order", None)
        limit = params.pop("limit", None)
        offset = int(params.pop("offset", 0) or 0)
        and_expr = params.pop("and", None)
        embedded_filters: Dict[str, Dict[str, str]] = {}
        plain = {}
        for k, v in params.items():
            if "." in k:
                rel, col = k.split(".", 1)
                embedded_filters.setdefault(rel, {})[col] = v
            else:
                plain[k] = v
        rows = [r for r in self.tables[table] if all(_match(r.get(k), v) for k, v in plain.items())]
        if and_expr:
            for cond in and_expr.strip("()").split(","):
                col, expr = cond.split(".", 1)
                rows = [r for r in rows if _match(r.get(col), expr)]

        out = []
        for r in rows:
            item, keep = {}, True
            for field in _split_top(select):
                m = re.match(r"^(\w+)(!inner)?\((.*)\)$", field)
                if m:
                    name, inner, cols = m.group(1), m.group(2), m.group(3).split(",")
                    val = self._embed(table, r, name, cols, embedded_filters.get(name, {}))
                    if inner and not val:
                        keep = False
                    item[name] = val
                elif field == "*":
                    item.update(copy.deepcopy(r))
                else:
                    item[field] = r.get(field)
            if keep:
                out.append(item)

        if order:
            col, _, direction = order.partition(".")
            out.sort(key=lambda r: (_coerce(r.get(col)) is None, _coerce(r.get(col))), reverse=direction == "desc")
        total = len(out)
        if limit is not None:
            out = out[offset: offset + int(limit)]
        return out, total

    # -- client API (mirrors SupabaseDB) -------------------------------------
    async def select(self, table, params=None, select_fields=None):
        p = dict(params or {})
        if select_fields:
            p["select"] = select_fields
        return self.query(table, p)[0]

    async def select_with_count(self, table, params=None, select_fields=None):
        p = dict(params or {})
        if select_fields:
            p["select"] = select_fields
        return self.query(table, p)

    async def count(self, table, params=None):
        p = dict(params or {})
        p.pop("limit", None)
        return self.query(table, p)[1]

    async def insert(self, table, data, on_conflict=None):
        rows = data if isinstance(data, list) else [data]
        for r in rows:
            for cols in UNIQUE.get(table, []):
                key = tuple(_coerce(r.get(c)) for c in cols)
                if any(tuple(_coerce(e.get(c)) for c in cols) == key for e in self.tables[table]):
                    raise DatabaseError("duplicate", status_code=409, detail='{"code":"23505"}')
        self.tables[table].extend(copy.deepcopy(rows))
        return copy.deepcopy(rows)

    async def update(self, table, params, data):
        matched, _ = self.query(table, params)
        ids = {m["id"] for m in matched}
        out = []
        for r in self.tables[table]:
            if r["id"] in ids:
                r.update(data)
                out.append(copy.deepcopy(r))
        return out

    async def close(self):
        return None


@pytest.fixture()
def fake_db(monkeypatch):
    fake = FakePostgREST()
    for name in ("select", "select_with_count", "count", "insert", "update", "close"):
        monkeypatch.setattr(db_client, name, getattr(fake, name))
    from app.routers import dashboard, observations

    observations.station_cache.clear()
    observations.station_id_cache.clear()
    observations.health_scorer.states.clear()
    dashboard._cached_summary = None
    return fake


@pytest.fixture()
def seeded(fake_db):
    """One demo station (Mumbai) with 26 h of clean 15-min history ending 15 min ago."""
    import uuid

    from app.services.data_generator import DEMO_STATIONS, generate_time_series

    stn = {**DEMO_STATIONS[0], "id": str(uuid.uuid4()), "is_active": True}
    fake_db.tables["stations"].append(stn)
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    start = now - timedelta(minutes=15 * 104)
    for o in generate_time_series(stn["station_code"], start, 104, 15, stn["elevation_m"]):
        fake_db.tables["observations"].append({
            "id": str(uuid.uuid4()), "station_id": stn["id"],
            **{k: v for k, v in o.items() if k != "station_code"},
        })
    return stn


@pytest.fixture()
def client(fake_db):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
