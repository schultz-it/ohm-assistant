"""Bootstrap past billing periods from HA long-term statistics (SPEC 6).

The recorder keeps hourly/daily long-term statistics for energy sensors almost
forever, even after short-term history is purged. We read the *daily* statistics
over the billing period through the HA WebSocket API (Supervisor proxy) and
store each day's meter reading as a MeterSnapshot — exactly what the daily job
would have produced — so ``period_delta`` then works on past periods too.

We fetch from one day before the period so the day before d0 becomes the
baseline reading that ``period_delta`` needs.
"""
import json
import os
from datetime import date, datetime, timedelta, timezone

import websockets
from sqlalchemy.orm import Session

from .. import models
from ..entities import CALC_CUMULATIVE_KEYS, merged_map
from . import snapshot

WS_URL = "ws://supervisor/core/websocket"
TIMEOUT = 30.0


def _to_date(v) -> date:
    """HA returns period 'start' as a ms epoch (newer) or an ISO string."""
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(v / 1000, tz=timezone.utc).date()
    return datetime.fromisoformat(str(v).replace("Z", "+00:00")).date()


async def fetch_daily_statistics(statistic_ids: list[str], start: date,
                                 end: date) -> dict:
    """Daily statistics for the given ids over [start, end] (inclusive-ish)."""
    token = os.environ.get("SUPERVISOR_TOKEN", "")
    start_iso = datetime(start.year, start.month, start.day, tzinfo=timezone.utc).isoformat()
    end_dt = datetime(end.year, end.month, end.day, tzinfo=timezone.utc) + timedelta(days=1)
    end_iso = end_dt.isoformat()

    async with websockets.connect(WS_URL, max_size=None, open_timeout=TIMEOUT) as ws:
        await ws.recv()  # auth_required
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        auth = json.loads(await ws.recv())
        if auth.get("type") != "auth_ok":
            raise RuntimeError("HA websocket auth failed")
        await ws.send(json.dumps({
            "id": 1, "type": "recorder/statistics_during_period",
            "start_time": start_iso, "end_time": end_iso,
            "statistic_ids": list(statistic_ids), "period": "day",
        }))
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("id") == 1 and msg.get("type") == "result":
                if not msg.get("success", True):
                    raise RuntimeError(f"statistics error: {msg.get('error')}")
                return msg.get("result", {}) or {}


async def import_period(db: Session, cfg: models.Config, d0: date, d1: date) -> dict:
    """Fill snapshots for the calc sensors over [d0, d1] from HA statistics."""
    emap = merged_map(cfg.entity_map)
    id_by_key = {k: emap[k] for k in CALC_CUMULATIVE_KEYS}
    # Start one day early so we have the reading at the start of d0.
    stats = await fetch_daily_statistics(list(id_by_key.values()),
                                         d0 - timedelta(days=1), d1)
    summary = {}
    for key, eid in id_by_key.items():
        days = 0
        for entry in stats.get(eid, []):
            state = entry.get("state")
            if state is None:
                continue
            snapshot._upsert(db, _to_date(entry["start"]), eid, float(state))
            days += 1
        summary[key] = {"entity_id": eid, "days": days, "available": days > 0}
    db.commit()
    return summary
