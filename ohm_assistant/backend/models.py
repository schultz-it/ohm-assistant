"""SQLAlchemy ORM models (SPEC 5)."""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

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

    # Set once the computed bill is pushed to the shared-expense ledger (SPEC 12).
    expense: Mapped["Expense | None"] = relationship(
        back_populates="bill", cascade="all, delete-orphan", uselist=False
    )

    @property
    def expense_id(self) -> int | None:
        return self.expense.id if self.expense else None


class Expense(Base):
    """A shared household expense split between the two units (SPEC 12).

    ``amount`` is what was actually paid, by ``paid_by``; ``andrea_share`` +
    ``genitori_share`` always add up to it exactly (the engine derives the
    second share by subtraction, so cents never go missing). A row with
    ``bill_id`` set was generated from a computed bill and carries its split.
    """
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    description: Mapped[str]
    category: Mapped[str] = mapped_column(default="altro")
    amount: Mapped[float]
    paid_by: Mapped[str] = mapped_column(default="andrea")     # andrea | genitori
    split_mode: Mapped[str] = mapped_column(default="equal")   # equal | percent | amount
    split_config: Mapped[dict | None] = mapped_column(JSON, default=None)
    andrea_share: Mapped[float] = mapped_column(default=0.0)
    genitori_share: Mapped[float] = mapped_column(default=0.0)
    settled: Mapped[bool] = mapped_column(default=False)
    notes: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    bill_id: Mapped[int | None] = mapped_column(
        ForeignKey("bills.id"), default=None, unique=True
    )
    bill: Mapped["Bill | None"] = relationship(back_populates="expense")


class MeterSnapshot(Base):
    """Daily reading of a cumulative sensor, for period deltas (SPEC 6)."""
    __tablename__ = "meter_snapshots"
    __table_args__ = (UniqueConstraint("date", "entity_id", name="uq_snapshot"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    entity_id: Mapped[str] = mapped_column(index=True)
    value: Mapped[float]
