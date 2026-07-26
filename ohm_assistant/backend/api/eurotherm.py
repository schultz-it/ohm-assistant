"""Eurotherm SmartComfort 365 API: Modbus settings, live plant, discovery.

The regulator is optional: with `enabled: false` (the default) nothing here
ever touches the network, and the rest of the add-on is unaffected.
"""
from fastapi import APIRouter, Depends
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
    data = patch.model_dump(exclude_unset=True)  # nested models come out as dicts
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


@router.post("/discover")
async def discover(db: Session = Depends(get_db)) -> dict:
    """Walk the plant — subsystems, Smart Base, rooms — and propose it (no save)."""
    return await et.discover(config_for(db))


@router.post("/explore")
async def explore(req: schemas.EurothermExplore,
                  db: Session = Depends(get_db)) -> dict:
    """Sweep an address range and show every register that answers.

    The SmartBase and air-machine parameters aren't publicly documented, so
    this is how you find them: scan, watch which values move, pin the ones you
    recognise.
    """
    return await et.explore(config_for(db), req.start, req.count)


def _specs(specs: list[dict]) -> list[dict]:
    """Register specs without the raw enum dicts, values spelled out instead."""
    return [{k: v for k, v in s.items() if k != "enum"}
            | ({"values": s["enum"]} if "enum" in s else {}) for s in specs]


@router.get("/registers")
def registers(db: Session = Depends(get_db)) -> dict:
    """The documented register map, for the explorer UI and the docs."""
    cfg = config_for(db)
    return {
        "presets": et.explore_presets(cfg),
        "air_models": et.AIR_MODELS,
        "explore_max": et.EXPLORE_MAX,
        "layout": {
            "system_base": et.SYSTEM_BASE,
            "zone_base": et.ZONE_BASE, "zone_stride": et.ZONE_STRIDE,
            "module_base": et.MODULE_BASE, "module_stride": et.MODULE_STRIDE,
            "room_offset": et.ROOM_OFFSET, "room_stride": et.ROOM_STRIDE,
            "rooms_per_module": et.ROOMS_PER_MODULE,
        },
        "system": _specs(et.SYSTEM_REGISTERS),
        "zone": _specs(et.ZONE_REGISTERS),
        "module": _specs(et.MODULE_REGISTERS),
        "room": _specs(et.ROOM_REGISTERS),
        "addresses": {
            b["name"]: {"base": et.module_addr(b["id"]),
                        "rooms": [et.room_addr(b["id"], r)
                                  for r in range(et.ROOMS_PER_MODULE)]}
            for b in cfg["bases"]
        },
    }
