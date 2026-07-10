"""Aggregate stats for the Storico dashboard (SPEC 7 tab 2)."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db
from .config import get_or_create

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    """Totals per party/type + the cumulative balance Genitori owe Andrea.

    Andrea fronts the bills; each computed bill's ``genitori_amount`` is owed to
    Andrea until marked settled. The outstanding balance is the sum over the
    unsettled computed bills.
    """
    cfg = get_or_create(db)
    bills = db.scalars(
        select(models.Bill).where(models.Bill.andrea_amount.is_not(None))
    ).all()

    tot = {"andrea": 0.0, "genitori": 0.0}
    by_type = {"electric": {"andrea": 0.0, "genitori": 0.0},
               "gas": {"andrea": 0.0, "genitori": 0.0}}
    outstanding = 0.0
    for b in bills:
        tot["andrea"] += b.andrea_amount
        tot["genitori"] += b.genitori_amount
        by_type[b.type]["andrea"] += b.andrea_amount
        by_type[b.type]["genitori"] += b.genitori_amount
        if not b.settled:
            outstanding += b.genitori_amount

    rnd = lambda d: {k: round(v, 2) for k, v in d.items()}
    return {
        "names": {"andrea": cfg.andrea_name, "genitori": cfg.genitori_name},
        "count": len(bills),
        "totals": rnd(tot),
        "by_type": {t: rnd(v) for t, v in by_type.items()},
        "outstanding_genitori_to_andrea": round(outstanding, 2),
    }
