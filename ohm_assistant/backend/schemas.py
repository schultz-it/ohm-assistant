"""Pydantic request/response schemas."""
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
    notes: str | None
    pdf_path: str | None
    created_at: datetime
    andrea_amount: float | None
    genitori_amount: float | None
    andrea_qty: float | None
    genitori_qty: float | None
    f_andrea: float | None
    breakdown: dict | None
