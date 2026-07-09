"""Bills CRUD API. Ripartition computation arrives in M3."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..core import engine, snapshot
from ..db import get_db
from .config import get_or_create

router = APIRouter(prefix="/api/bills", tags=["bills"])


def _get(db: Session, bill_id: int) -> models.Bill:
    bill = db.get(models.Bill, bill_id)
    if bill is None:
        raise HTTPException(404, "bill not found")
    return bill


@router.get("", response_model=list[schemas.BillOut])
def list_bills(type: str | None = None, db: Session = Depends(get_db)):
    stmt = select(models.Bill).order_by(models.Bill.period_start.desc())
    if type:
        stmt = stmt.where(models.Bill.type == type)
    return db.scalars(stmt).all()


@router.post("", response_model=schemas.BillOut, status_code=201)
def create_bill(data: schemas.BillIn, db: Session = Depends(get_db)):
    if data.period_end < data.period_start:
        raise HTTPException(422, "period_end before period_start")
    bill = models.Bill(**data.model_dump())
    db.add(bill)
    db.commit()
    return bill


@router.get("/{bill_id}", response_model=schemas.BillOut)
def get_bill(bill_id: int, db: Session = Depends(get_db)):
    return _get(db, bill_id)


@router.put("/{bill_id}", response_model=schemas.BillOut)
def update_bill(bill_id: int, patch: schemas.BillUpdate, db: Session = Depends(get_db)):
    bill = _get(db, bill_id)
    for k, v in patch.model_dump(exclude_unset=True).items():
        setattr(bill, k, v)
    db.commit()
    return bill


@router.delete("/{bill_id}", status_code=204)
def delete_bill(bill_id: int, db: Session = Depends(get_db)):
    db.delete(_get(db, bill_id))
    db.commit()


@router.post("/{bill_id}/compute")
def compute_bill(bill_id: int, persist: bool = True, db: Session = Depends(get_db)):
    """Run the ripartition for a bill from the period meter deltas (SPEC 4).

    Returns ``ok=false`` + ``missing`` keys when snapshots don't cover the
    period yet (import history or enter readings first). Persists the allocation
    onto the bill only when the computation succeeds and ``persist`` is set.
    """
    bill = _get(db, bill_id)
    cfg = get_or_create(db)
    deltas = snapshot.period_deltas(db, cfg, bill.period_start, bill.period_end)
    res = engine.compute(bill.type, bill.billed, bill.cost_total,
                         bill.canone_rai, deltas)
    if res.get("ok") and persist:
        bill.andrea_amount = res["andrea_amount"]
        bill.genitori_amount = res["genitori_amount"]
        bill.andrea_qty = res["andrea_qty"]
        bill.genitori_qty = res["genitori_qty"]
        bill.f_andrea = res["f_andrea"]
        bill.breakdown = res["breakdown"]
        db.commit()
    res["deltas"] = {k: (v["value"] if v else None) for k, v in deltas.items()}
    return res
