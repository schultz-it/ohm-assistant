"""HA entity API: listing + verification of the configured entity map."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core import ha
from ..db import get_db
from ..entities import merged_map
from .config import get_or_create

router = APIRouter(prefix="/api/ha", tags=["ha"])


@router.get("/entities")
async def list_entities(domain: str = "sensor"):
    """List HA entities of a domain via the Supervisor proxy."""
    states = await ha.all_states()
    entities = [
        {"entity_id": s["entity_id"], "state": s["state"],
         "name": s["attributes"].get("friendly_name", s["entity_id"])}
        for s in states if s["entity_id"].startswith(f"{domain}.")
    ]
    return {"domain": domain, "count": len(entities), "entities": entities}


@router.get("/verify")
async def verify(db: Session = Depends(get_db)):
    """Check every *configured* entity: found + current state/unit (SPEC 3)."""
    cfg = get_or_create(db)
    emap = merged_map(cfg.entity_map)
    by_id = await ha.states_by_id()

    out = []
    for key, eid in emap.items():
        s = by_id.get(eid)
        if s is None:
            out.append({"key": key, "entity_id": eid, "found": False})
        else:
            out.append({
                "key": key, "entity_id": eid, "found": True,
                "state": s["state"],
                "unit": s["attributes"].get("unit_of_measurement", ""),
                "name": s["attributes"].get("friendly_name", eid),
            })
    found = sum(1 for x in out if x["found"])
    return {"total": len(out), "found": found, "missing": len(out) - found,
            "entities": out}
