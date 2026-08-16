"""Shared-expense ledger API (SPEC 12) — the everyday-money side of the add-on.

Every row records who paid (or, for an income, who cashed it) and how the money
is divided between the two units; the running balance is the sum of the
unsettled shares, expenses and incomes together — an income received by Andrea
cuts what Genitori owe him by their quota. Bills computed by the ripartition
engine can be pushed in here (see ``POST /api/bills/{id}/to_expense``) so there
is a single balance for the house.
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
def categories(kind: str = "expense"):
    """Category list for the UI (id, label, icon) — keywords stay server-side.

    ``kind`` picks the expense or the income list; both sets are also returned
    under ``by_kind`` so the UI can fill the two menus with a single call.
    """
    trim = lambda cats: [{k: c[k] for k in ("id", "label", "icon")} for c in cats]
    return {
        "kind": core.normalize_kind(kind),
        "categories": trim(core.categories_for(kind)),
        "by_kind": {k: trim(v) for k, v in core.CATEGORIES_BY_KIND.items()},
    }


@router.get("/suggest")
def suggest(description: str = "", kind: str = "expense"):
    """Propose a category from the description (local keyword match, no AI)."""
    return core.suggest_category(description, kind)


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    """Totals and the running balance of the ledger.

    ``net`` is positive when Genitori owe Andrea and negative the other way
    round, computed over the unsettled rows only — incomes included, with the
    sign that puts whoever cashed them in debt for the other's quota.
    Expense and income totals stay in separate buckets so money out is never
    added to money in.
    """
    cfg = get_or_create(db)
    rows = db.scalars(select(models.Expense)).all()

    paid = {"andrea": 0.0, "genitori": 0.0}       # expenses, by who paid
    received = {"andrea": 0.0, "genitori": 0.0}   # incomes, by who cashed them
    shares = {"andrea": 0.0, "genitori": 0.0}
    income_shares = {"andrea": 0.0, "genitori": 0.0}
    by_category: dict[str, float] = {}
    income_by_category: dict[str, float] = {}
    net = 0.0
    unsettled = 0
    income_count = 0
    for e in rows:
        income = e.kind == "income"
        if income:
            income_count += 1
        totals, buckets = ((received, income_by_category) if income
                           else (paid, by_category))
        totals[e.paid_by] += e.amount
        buckets[e.category] = round(buckets.get(e.category, 0.0) + e.amount, 2)
        target = income_shares if income else shares
        target["andrea"] += e.andrea_share
        target["genitori"] += e.genitori_share
        if not e.settled:
            unsettled += 1
            net += core.signed_balance(e.kind, e.paid_by,
                                       e.andrea_share, e.genitori_share)

    rnd = lambda d: {k: round(v, 2) for k, v in d.items()}
    return {
        "names": {"andrea": cfg.andrea_name, "genitori": cfg.genitori_name},
        "count": len(rows),
        "income_count": income_count,
        "unsettled_count": unsettled,
        "paid": rnd(paid),
        "received": rnd(received),
        "totals": rnd(shares),
        "income_totals": rnd(income_shares),
        "by_category": by_category,
        "income_by_category": income_by_category,
        "net": round(net, 2),
    }


# --- CRUD ---

@router.get("", response_model=list[schemas.ExpenseOut])
def list_expenses(category: str | None = None, settled: bool | None = None,
                  kind: str | None = None, db: Session = Depends(get_db)):
    stmt = select(models.Expense).order_by(
        models.Expense.date.desc(), models.Expense.id.desc())
    if category:
        stmt = stmt.where(models.Expense.category == category)
    if settled is not None:
        stmt = stmt.where(models.Expense.settled == settled)
    if kind:
        stmt = stmt.where(models.Expense.kind == kind)
    return db.scalars(stmt).all()


@router.post("", response_model=schemas.ExpenseOut, status_code=201)
def create_expense(data: schemas.ExpenseIn, db: Session = Depends(get_db)):
    payload = data.model_dump()
    payload["category"] = core.normalize_category(
        payload["category"], payload["description"], payload["kind"])
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
    kind = data.get("kind") or exp.kind
    if data.get("category") is not None and data["category"] not in core.category_ids(kind):
        raise HTTPException(422, f"categoria sconosciuta: {data['category']}")
    if data.get("amount") is not None and data["amount"] <= 0:
        raise HTTPException(422, "l'importo deve essere positivo")
    for k, v in data.items():
        setattr(exp, k, v)
    # Switching expense ↔ income leaves the old category meaningless: repropose.
    if "kind" in data and exp.category not in core.category_ids(exp.kind):
        exp.category = core.normalize_category(None, exp.description, exp.kind)
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
