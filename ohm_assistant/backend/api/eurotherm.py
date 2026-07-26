"""Eurotherm Smart365 API: Modbus TCP settings, live zones, discovery.

The regulator is optional: with `enabled: false` (the default) nothing here
ever touches the network, and the rest of the add-on is unaffected.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import schemas
from ..core import eurotherm as et
from ..db import get_db
from .config import get_or_create

router = APIRouter(prefix="/api/eurotherm", tags=["eurotherm"])


def config_for(db: Session) -> dict:
    """Effective Eurotherm configuration (defaults + stored settings)."""
    return et.merged_config(get_or_create(db).eurotherm)


@router.get("/config")
def read_config(db: Session = Depends(get_db)) -> dict:
    return config_for(db)


@router.put("/config")
def update_config(patch: schemas.EurothermConfig,
                  db: Session = Depends(get_db)) -> dict:
    cfg = get_or_create(db)
    data = patch.model_dump(exclude_unset=True)
    if "zones" in data and data["zones"] is not None:
        data["zones"] = [z if isinstance(z, dict) else z.model_dump()
                         for z in data["zones"]]
    merged = et.merged_config({**(cfg.eurotherm or {}),
                               **{k: v for k, v in data.items() if v is not None}})
    cfg.eurotherm = merged
    db.commit()
    et.invalidate_cache()  # host/zones may have moved: drop the stale reading
    return merged


@router.get("/live")
async def live(db: Session = Depends(get_db)) -> dict:
    return await et.read_live_cached(config_for(db))


@router.post("/test")
async def test(db: Session = Depends(get_db)) -> dict:
    """Connectivity check for the Setup tab — runs even when disabled."""
    return await et.test_connection(config_for(db))


@router.post("/scan")
async def scan(max_zones: int = Query(et.MAX_ZONES, ge=1, le=64),
               db: Session = Depends(get_db)) -> dict:
    """Probe the zone slots and propose the ones that answer (does not save)."""
    return await et.scan_zones(config_for(db), max_zones)


@router.get("/registers")
def registers(db: Session = Depends(get_db)) -> dict:
    """The register map in use, so the UI (and DOCS) can show what is read."""
    cfg = config_for(db)
    return {
        "system": [{k: v for k, v in s.items() if k != "enum"} | (
            {"values": s["enum"]} if "enum" in s else {})
            for s in et.SYSTEM_REGISTERS],
        "zone": [{k: v for k, v in s.items() if k != "enum"} | (
            {"values": s["enum"]} if "enum" in s else {})
            for s in et.ZONE_REGISTERS],
        "zone_base": cfg["zone_base"],
        "zone_stride": cfg["zone_stride"],
        "input_type": cfg["input_type"],
        "example": {z["index"]: et.zone_base(cfg, z["index"])
                    for z in cfg["zones"]} or {1: et.zone_base(cfg, 1),
                                               2: et.zone_base(cfg, 2)},
    }
