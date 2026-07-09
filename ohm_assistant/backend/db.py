"""Database setup: SQLite engine, session factory, declarative base.

The database lives in the add-on's persistent ``/data`` directory so it
survives add-on updates and restarts. For local development / tests, set the
``DATA_DIR`` environment variable to any writable folder.
"""
import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "ohm_assistant.db"

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class for all ORM models."""


def get_db():
    """FastAPI dependency: yield a session and always close it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Columns added after a table first shipped: (table, column, DDL type+default).
# SQLite's create_all() does not ALTER existing tables, so upgrades need these
# applied manually at startup (idempotent).
_MIGRATIONS: list[tuple[str, str, str]] = []


def apply_migrations() -> None:
    """Add any missing columns to existing tables (SQLite ALTER ADD COLUMN)."""
    with engine.begin() as conn:
        for table, column, ddl in _MIGRATIONS:
            cols = [r[1] for r in conn.execute(text(f"PRAGMA table_info({table})"))]
            if cols and column not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
