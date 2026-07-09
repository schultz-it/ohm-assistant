"""Bills CRUD API. Ripartition computation arrives in M3."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db

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
