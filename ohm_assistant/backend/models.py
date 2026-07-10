"""SQLAlchemy ORM models (SPEC 5)."""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Config(Base):
    """Singleton settings row (id always 1)."""
    __tablename__ = "config"

    id: Mapped[int] = mapped_column(primary_key=True)
    andrea_name: Mapped[str] = mapped_column(default="Andrea")
    genitori_name: Mapped[str] = mapped_column(default="Genitori")
    currency: Mapped[str] = mapped_column(default="EUR")
    language: Mapped[str] = mapped_column(default="it")
    canone_rai_default: Mapped[float] = mapped_column(default=0.0)
    # Overrides to DEFAULT_MAP: {key: entity_id}. Empty = all defaults.
    entity_map: Mapped[dict] = mapped_column(JSON, default=dict)


class Bill(Base):
    """A single utility bill and (once computed) its ripartition."""
    __tablename__ = "bills"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str]  # "electric" | "gas"
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    billed: Mapped[float]          # kWh (electric) or Smc (gas)
    cost_total: Mapped[float]      # € total on the bill
    canone_rai: Mapped[float] = mapped_column(default=0.0)  # electric only
    source: Mapped[str] = mapped_column(default="manual")   # manual | ai
    status: Mapped[str] = mapped_column(default="draft")    # draft | final
    settled: Mapped[bool] = mapped_column(default=False)    # Genitori reimbursed?
    notes: Mapped[str | None] = mapped_column(default=None)
    pdf_path: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Allocation — filled by the engine in M3 (nullable until computed).
    andrea_amount: Mapped[float | None] = mapped_column(default=None)
    genitori_amount: Mapped[float | None] = mapped_column(default=None)
    andrea_qty: Mapped[float | None] = mapped_column(default=None)
    genitori_qty: Mapped[float | None] = mapped_column(default=None)
    f_andrea: Mapped[float | None] = mapped_column(default=None)
    breakdown: Mapped[dict | None] = mapped_column(JSON, default=None)


class MeterSnapshot(Base):
    """Daily reading of a cumulative sensor, for period deltas (SPEC 6)."""
    __tablename__ = "meter_snapshots"
    __table_args__ = (UniqueConstraint("date", "entity_id", name="uq_snapshot"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    entity_id: Mapped[str] = mapped_column(index=True)
    value: Mapped[float]
