"""Live dashboard API: instantaneous heat-cost-allocator + PV readings (SPEC 7)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core import ha
from ..db import get_db
from ..entities import merged_map
from .config import get_or_create

router = APIRouter(prefix="/api/live", tags=["live"])

METRICS = ["flow_temp", "return_temp", "temp_diff", "power", "volume_flow"]
_BAD = {"unavailable", "unknown", "none", ""}


def _reading(by_id: dict, entity_id: str) -> dict:
    s = by_id.get(entity_id)
    if s is None or str(s.get("state", "")).lower() in _BAD:
        return {"entity_id": entity_id, "value": None,
                "unit": "", "available": False}
    try:
        value = float(s["state"])
    except (TypeError, ValueError):
        value = None
    return {"entity_id": entity_id, "value": value,
            "unit": s["attributes"].get("unit_of_measurement", ""),
            "available": value is not None}


@router.get("")
async def live(db: Session = Depends(get_db)):
    cfg = get_or_create(db)
    emap = merged_map(cfg.entity_map)
    by_id = await ha.states_by_id()

    units = {}
    for unit in ("andrea", "genitori"):
        units[unit] = {m: _reading(by_id, emap[f"{unit}_{m}"]) for m in METRICS}

    pv = {"load_power": _reading(by_id, emap["pv_load_power"])}

    # Derived: instantaneous heat split by thermal power.
    pa = units["andrea"]["power"]["value"]
    pg = units["genitori"]["power"]["value"]
    total_power = (pa or 0) + (pg or 0)
    heat_split_andrea = (pa / total_power) if (pa is not None and pg is not None
                                               and total_power > 0) else None

    return {
        "names": {"andrea": cfg.andrea_name, "genitori": cfg.genitori_name},
        "units": units,
        "pv": pv,
        "derived": {
            "total_power": round(total_power, 3) if (pa is not None or pg is not None) else None,
            "heat_split_andrea": round(heat_split_andrea, 3) if heat_split_andrea is not None else None,
        },
    }
