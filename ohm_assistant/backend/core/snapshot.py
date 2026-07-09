"""Daily meter snapshots + period-delta computation (SPEC 6).

Cumulative sensors are read once a day and stored; a billing-period delta is the
sum of positive day-to-day increments between the snapshots inside the period,
which transparently handles meter resets (a decrease = reset, count the new
reading). Everything here is synchronous so it can run in the scheduler thread
and in FastAPI's threadpool for the sync endpoints.
"""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..entities import CALC_CUMULATIVE_KEYS, merged_map
from . import ha

_BAD_STATES = {"unavailable", "unknown", "none", ""}


def _calc_entities(cfg: models.Config) -> dict[str, str]:
    """{key: entity_id} for the cumulative sensors the math relies on."""
    emap = merged_map(cfg.entity_map)
    return {k: emap[k] for k in CALC_CUMULATIVE_KEYS}


def _upsert(db: Session, day: date, entity_id: str, value: float) -> None:
    row = db.scalar(
        select(models.MeterSnapshot).where(
            models.MeterSnapshot.date == day,
            models.MeterSnapshot.entity_id == entity_id,
        )
    )
    if row is None:
        db.add(models.MeterSnapshot(date=day, entity_id=entity_id, value=value))
    else:
        row.value = value


def take_snapshot(db: Session, day: date | None = None) -> dict:
    """Read every calc cumulative sensor and store today's reading (idempotent)."""
    day = day or date.today()
    cfg = db.get(models.Config, 1)
    if cfg is None:
        cfg = models.Config(id=1, entity_map={})
        db.add(cfg)
        db.commit()

    by_id = ha.states_by_id_sync()
    stored, skipped = [], []
    for key, eid in _calc_entities(cfg).items():
        s = by_id.get(eid)
        raw = (s or {}).get("state", "")
        if s is None or str(raw).lower() in _BAD_STATES:
            skipped.append({"key": key, "entity_id": eid, "reason":
                            "missing" if s is None else str(raw)})
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            skipped.append({"key": key, "entity_id": eid, "reason": f"non-numeric: {raw}"})
            continue
        _upsert(db, day, eid, value)
        stored.append({"key": key, "entity_id": eid, "value": value})
    db.commit()
    return {"date": day.isoformat(), "stored": len(stored),
            "skipped": len(skipped), "details": {"stored": stored, "skipped": skipped}}


def period_delta(db: Session, entity_id: str, d0: date, d1: date) -> dict | None:
    """Consumption of a cumulative sensor over [d0, d1] from stored snapshots.

    The baseline is the reading just *before* d0 (so the whole period is
    captured); the end is the last reading within the period. Returns None when
    fewer than two points are available (needs import / manual entry). Meter
    resets (a decrease) are handled by counting the new reading.
    """
    rows_in = db.scalars(
        select(models.MeterSnapshot)
        .where(models.MeterSnapshot.entity_id == entity_id,
               models.MeterSnapshot.date >= d0,
               models.MeterSnapshot.date <= d1)
        .order_by(models.MeterSnapshot.date)
    ).all()
    baseline = db.scalar(
        select(models.MeterSnapshot)
        .where(models.MeterSnapshot.entity_id == entity_id,
               models.MeterSnapshot.date < d0)
        .order_by(models.MeterSnapshot.date.desc())
        .limit(1)
    )
    rows = ([baseline] if baseline is not None else []) + list(rows_in)
    if len(rows) < 2:
        return None

    total, resets = 0.0, 0
    for prev, cur in zip(rows, rows[1:]):
        if cur.value >= prev.value:
            total += cur.value - prev.value
        else:  # reset / rollover
            total += cur.value
            resets += 1
    return {
        "entity_id": entity_id,
        "value": round(total, 3),
        "start_date": rows[0].date.isoformat(),
        "end_date": rows[-1].date.isoformat(),
        "start_value": rows[0].value,
        "end_value": rows[-1].value,
        "points": len(rows),
        "resets": resets,
    }


def period_deltas(db: Session, cfg: models.Config, d0: date, d1: date) -> dict:
    """Deltas for every calc cumulative key over the period (for the M3 engine)."""
    out = {}
    for key, eid in _calc_entities(cfg).items():
        out[key] = period_delta(db, eid, d0, d1)
    return out
