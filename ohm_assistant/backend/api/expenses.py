"""Shared-expense ledger API (SPEC 12) — the Splitwise-style side of the add-on.

Every expense records who paid and how the cost is divided between the two
units; the running balance is the sum of the unsettled shares. Bills computed
by the ripartition engine can be pushed in here (see
``POST /api/bills/{id}/to_expense``) so there is a single balance for the house.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..core import expenses as core
from ..db import get_db
from .config import get_or_create

router = APIRouter(prefix="/api/expenses", tags=["expenses"])


def _get(db: Session, expense_id: int) -> models.Expense:
    exp = db.get(models.Expense, expense_id)
    if exp is None:
        raise HTTPException(404, "spesa non trovata")
    return exp


def _apply_split(exp: models.Expense) -> None:
    try:
        exp.andrea_share, exp.genitori_share = core.compute_shares(
            exp.amount, exp.split_mode, exp.split_config)
    except core.SplitError as e:
        raise HTTPException(422, str(e))


# --- Static routes first: they must not be swallowed by /{expense_id}. ---

@router.get("/categories")
def categories():
    """Category list for the UI (id, label, icon) — keywords stay server-side."""
    return {"categories": [{k: c[k] for k in ("id", "label", "icon")}
                           for c in core.CATEGORIES]}


@router.get("/suggest")
def suggest(description: str = ""):
    """Propose a category from the description (local keyword match, no AI)."""
    return core.suggest_category(description)


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    """Totals and the running balance of the ledger.

    ``net`` is positive when Genitori owe Andrea and negative the other way
    round, computed over the unsettled expenses only.
    """
    cfg = get_or_create(db)
    rows = db.scalars(select(models.Expense)).all()

    paid = {"andrea": 0.0, "genitori": 0.0}
    shares = {"andrea": 0.0, "genitori": 0.0}
    by_category: dict[str, float] = {}
    net = 0.0
    unsettled = 0
    for e in rows:
        paid[e.paid_by] += e.amount
        shares["andrea"] += e.andrea_share
        shares["genitori"] += e.genitori_share
        by_category[e.category] = round(by_category.get(e.category, 0.0) + e.amount, 2)
        if not e.settled:
            unsettled += 1
            # The payer fronted the other party's share.
            net += e.genitori_share if e.paid_by == "andrea" else -e.andrea_share

    rnd = lambda d: {k: round(v, 2) for k, v in d.items()}
    return {
        "names": {"andrea": cfg.andrea_name, "genitori": cfg.genitori_name},
        "count": len(rows),
        "unsettled_count": unsettled,
        "paid": rnd(paid),
        "totals": rnd(shares),
        "by_category": by_category,
        "net": round(net, 2),
    }


# --- CRUD ---

@router.get("", response_model=list[schemas.ExpenseOut])
def list_expenses(category: str | None = None, settled: bool | None = None,
                  db: Session = Depends(get_db)):
    stmt = select(models.Expense).order_by(
        models.Expense.date.desc(), models.Expense.id.desc())
    if category:
        stmt = stmt.where(models.Expense.category == category)
    if settled is not None:
        stmt = stmt.where(models.Expense.settled == settled)
    return db.scalars(stmt).all()


@router.post("", response_model=schemas.ExpenseOut, status_code=201)
def create_expense(data: schemas.ExpenseIn, db: Session = Depends(get_db)):
    payload = data.model_dump()
    payload["category"] = core.normalize_category(payload["category"],
                                                  payload["description"])
    exp = models.Expense(**payload)
    _apply_split(exp)
    db.add(exp)
    db.commit()
    return exp


@router.get("/{expense_id}", response_model=schemas.ExpenseOut)
def get_expense(expense_id: int, db: Session = Depends(get_db)):
    return _get(db, expense_id)


@router.put("/{expense_id}", response_model=schemas.ExpenseOut)
def update_expense(expense_id: int, patch: schemas.ExpenseUpdate,
                   db: Session = Depends(get_db)):
    exp = _get(db, expense_id)
    data = patch.model_dump(exclude_unset=True)
    if data.get("category") is not None and data["category"] not in core.CATEGORY_IDS:
        raise HTTPException(422, f"categoria sconosciuta: {data['category']}")
    if data.get("amount") is not None and data["amount"] <= 0:
        raise HTTPException(422, "l'importo deve essere positivo")
    for k, v in data.items():
        setattr(exp, k, v)
    if {"amount", "split_mode", "split_config"} & data.keys():
        _apply_split(exp)
    # A ledger entry born from a bill keeps the bill's "saldato" flag in sync,
    # so Storico and Spese never disagree about what is still owed.
    if "settled" in data and exp.bill is not None:
        exp.bill.settled = exp.settled
    db.commit()
    return exp


@router.delete("/{expense_id}", status_code=204)
def delete_expense(expense_id: int, db: Session = Depends(get_db)):
    db.delete(_get(db, expense_id))
    db.commit()
