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


class EurothermRoom(BaseModel):
    """Name/unit for a room, addressed as the protocol does: base + room id."""
    base: int = Field(ge=0, le=7)
    room: int = Field(ge=0, le=7)
    name: str = ""
    enabled: bool = True
    unit: str | None = Field(default=None, pattern="^(andrea|genitori|comune)$")


class EurothermBase(BaseModel):
    """A Smart Base module and the air machine wired to it."""
    id: int = Field(ge=0, le=7)
    name: str = ""
    unit: str | None = Field(default=None, pattern="^(andrea|genitori|comune)$")
    enabled: bool = True
    air_model: str = ""


class EurothermCustom(BaseModel):
    """A register identified with the explorer and pinned to the Live tab."""
    address: int = Field(ge=0, le=65535)
    name: str = ""
    group: str = "sistema"          # sistema | base:<n> | air:<n>
    scale: float = 1.0
    unit: str = ""
    kind: str = Field(default="number", pattern="^(number|bool|temp)$")


class EurothermExplore(BaseModel):
    start: int = Field(ge=0, le=65535)
    count: int = Field(default=256, ge=1, le=2048)


class EurothermMap(BaseModel):
    """A slice of the address space to probe for populated regions."""
    start: int = Field(default=0, ge=0, le=65535)
    end: int = Field(default=65535, ge=0, le=65535)
    stride: int = Field(default=8, ge=1, le=256)
    max_probes: int = Field(default=2000, ge=100, le=20000)


class EurothermConfig(BaseModel):
    """Modbus TCP settings for the Eurotherm Smart365 regulator."""
    enabled: bool | None = None
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    unit_id: int | None = Field(default=None, ge=0, le=247)
    input_type: str | None = Field(default=None, pattern="^(holding|input)$")
    timeout: float | None = Field(default=None, gt=0, le=60)
    poll_interval: int | None = Field(default=None, ge=5, le=3600)
    bases: list[EurothermBase] | None = None
    rooms: list[EurothermRoom] | None = None
    custom: list[EurothermCustom] | None = None


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
