"""Pydantic request/response schemas."""
import datetime as dt
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


# ---- Config ----
class ConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    andrea_name: str
    genitori_name: str
    currency: str
    language: str
    canone_rai_default: float
    entity_map: dict  # effective map (defaults + overrides), key -> entity_id


class ConfigUpdate(BaseModel):
    andrea_name: str | None = None
    genitori_name: str | None = None
    currency: str | None = None
    language: str | None = None
    canone_rai_default: float | None = None
    entity_map: dict | None = None  # partial overrides {key: entity_id}


# ---- Bill ----
class BillIn(BaseModel):
    type: str = Field(pattern="^(electric|gas)$")
    period_start: date
    period_end: date
    billed: float
    cost_total: float
    canone_rai: float = 0.0
    source: str = "manual"
    status: str = "draft"
    notes: str | None = None


class BillUpdate(BaseModel):
    period_start: date | None = None
    period_end: date | None = None
    billed: float | None = None
    cost_total: float | None = None
    canone_rai: float | None = None
    status: str | None = None
    settled: bool | None = None
    notes: str | None = None


class BillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    type: str
    period_start: date
    period_end: date
    billed: float
    cost_total: float
    canone_rai: float
    source: str
    status: str
    settled: bool
    notes: str | None
    pdf_path: str | None
    created_at: datetime
    andrea_amount: float | None
    genitori_amount: float | None
    andrea_qty: float | None
    genitori_qty: float | None
    f_andrea: float | None
    breakdown: dict | None
    expense_id: int | None = None   # set once pushed to the expense ledger


# ---- Expense (shared-expense ledger, SPEC 12) ----
# The field is called ``date``, which shadows the imported name inside the class
# body once a default is assigned — hence the ``dt.date`` annotations below.
class ExpenseIn(BaseModel):
    date: dt.date
    description: str = Field(min_length=1)
    amount: float = Field(gt=0)
    category: str | None = None        # None / unknown → proposed from description
    paid_by: str = Field(default="andrea", pattern="^(andrea|genitori)$")
    split_mode: str = Field(default="equal", pattern="^(equal|percent|amount)$")
    split_config: dict | None = None   # {"andrea": x, "genitori": y}
    notes: str | None = None


class ExpenseUpdate(BaseModel):
    date: dt.date | None = None
    description: str | None = None
    amount: float | None = None
    category: str | None = None
    paid_by: str | None = Field(default=None, pattern="^(andrea|genitori)$")
    split_mode: str | None = Field(default=None, pattern="^(equal|percent|amount)$")
    split_config: dict | None = None
    settled: bool | None = None
    notes: str | None = None


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    date: dt.date
    description: str
    category: str
    amount: float
    paid_by: str
    split_mode: str
    split_config: dict | None
    andrea_share: float
    genitori_share: float
    settled: bool
    notes: str | None
    bill_id: int | None
    created_at: datetime
