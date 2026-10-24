"""Database access. The engine is created lazily so importing this module
never touches the network (the cloud build imports your server)."""

import os
import sys

from dotenv import load_dotenv
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    func,
)
from sqlalchemy.engine import Engine

metadata = MetaData()

expenses = Table(
    "expenses",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("amount_paise", Integer, nullable=False),  # money as integer paise
    Column("category", String(50), nullable=False),
    Column("description", String(200), nullable=False, default=""),
    Column("spent_on_date", Date, nullable=False),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
)

_engine: Engine | None = None


def _normalize(url: str) -> str:
    # Hosted Postgres gives "postgres://" or "postgresql://"; tell SQLAlchemy
    # to use the psycopg v3 driver.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        load_dotenv()  # local dev: reads .env if present; never overrides real env vars
        url = _normalize(os.environ.get("DATABASE_URL", "sqlite:///expenses.db"))
        _engine = create_engine(url, pool_pre_ping=True)
        metadata.create_all(_engine)
        print(
            f"[db] using {_engine.dialect.name}", file=sys.stderr
        )  # never print the URL
    return _engine


def reset_engine() -> None:
    """Used by tests."""
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None
