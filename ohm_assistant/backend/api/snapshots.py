"""Snapshot API: manual trigger, listing, period deltas, bootstrap entry."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..core import history, snapshot
from ..db import get_db
from ..entities import merged_map
from .config import get_or_create

router = APIRouter(prefix="/api/snapshots", tags=["snapshots"])


class ManualSnapshotIn(BaseModel):
    date: date
    value: float
    key: str | None = None        # canonical key (resolved via config map), or
    entity_id: str | None = None  # a raw entity_id directly


@router.post("/now")
def snapshot_now(db: Session = Depends(get_db)):
    """Take a snapshot right now (also runs daily at 00:05 UTC)."""
    return snapshot.take_snapshot(db)


@router.get("")
def list_snapshots(entity_id: str | None = None, from_: date | None = None,
                   to: date | None = None, db: Session = Depends(get_db)):
    stmt = select(models.MeterSnapshot).order_by(
        models.MeterSnapshot.date.desc(), models.MeterSnapshot.entity_id)
    if entity_id:
        stmt = stmt.where(models.MeterSnapshot.entity_id == entity_id)
    if from_:
        stmt = stmt.where(models.MeterSnapshot.date >= from_)
    if to:
        stmt = stmt.where(models.MeterSnapshot.date <= to)
    rows = db.scalars(stmt.limit(2000)).all()
    return [{"date": r.date.isoformat(), "entity_id": r.entity_id, "value": r.value}
            for r in rows]


@router.get("/delta")
def deltas(from_: date, to: date, db: Session = Depends(get_db)):
    """Period delta for every calc cumulative key (feeds the M3 engine)."""
    if to < from_:
        raise HTTPException(422, "to before from")
    cfg = get_or_create(db)
    return {"from": from_.isoformat(), "to": to.isoformat(),
            "deltas": snapshot.period_deltas(db, cfg, from_, to)}


@router.post("/import_history")
async def import_history(from_: date, to: date, db: Session = Depends(get_db)):
    """Backfill snapshots for a past period from HA long-term statistics."""
    if to < from_:
        raise HTTPException(422, "to before from")
    cfg = get_or_create(db)
    try:
        summary = await history.import_period(db, cfg, from_, to)
    except Exception as e:  # noqa: BLE001 — surface the reason to the UI
        raise HTTPException(502, f"import da storico HA fallito: {e}")
    imported = sum(1 for v in summary.values() if v["available"])
    return {"from": from_.isoformat(), "to": to.isoformat(),
            "keys_imported": imported, "keys_total": len(summary), "detail": summary}


@router.post("/manual")
def manual(entry: ManualSnapshotIn, db: Session = Depends(get_db)):
    """Insert/overwrite a reading by hand (bootstrap of past billing periods)."""
    eid = entry.entity_id
    if eid is None and entry.key:
        emap = merged_map(get_or_create(db).entity_map)
        eid = emap.get(entry.key)
    if not eid:
        raise HTTPException(422, "provide a valid key or entity_id")
    snapshot._upsert(db, entry.date, eid, entry.value)
    db.commit()
    return {"date": entry.date.isoformat(), "entity_id": eid, "value": entry.value}
