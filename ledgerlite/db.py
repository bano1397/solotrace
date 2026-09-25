"""
Database engine and session handling for LedgerLite.

Design notes
------------
* SQLite is used for the demo.  Every transaction starts with ``BEGIN IMMEDIATE``
  so that read-check-write sequences (balance checks, the daily cap) are
  serialised: two concurrent withdrawals can never both see the old balance.
* Each request gets its own session from ``get_db`` — exactly one unit of work
  per request.  Tests use the very same code path (see ``configure``).
* ``LEDGERLITE_SQLITE_FAST=1`` (tests only) skips fsync for speed; it never
  changes transaction semantics.
"""
import os

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DEFAULT_URL = "sqlite:///./ledgerlite.db"


class Base(DeclarativeBase):
    pass


def make_engine(url: str = DEFAULT_URL) -> Engine:
    """Create an engine; SQLite engines get serialised (IMMEDIATE) transactions."""
    if not url.startswith("sqlite"):
        return create_engine(url)

    engine = create_engine(
        url,
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection, _record):
        # Let SQLAlchemy (not the sqlite3 driver) decide when transactions begin.
        dbapi_connection.isolation_level = None
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        if os.environ.get("LEDGERLITE_SQLITE_FAST") == "1":
            cursor.execute("PRAGMA synchronous=OFF")
            cursor.execute("PRAGMA journal_mode=MEMORY")
        cursor.close()

    @event.listens_for(engine, "begin")
    def _on_begin(connection):
        # Take the write lock at the start of every transaction.
        connection.exec_driver_sql("BEGIN IMMEDIATE")

    return engine


engine = make_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=True, bind=engine)


def configure(url: str) -> Engine:
    """Point LedgerLite at another database (used by tests and the demo)."""
    global engine, SessionLocal
    engine.dispose()
    engine = make_engine(url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=True, bind=engine)
    return engine


def get_db():
    """FastAPI dependency: one fresh session per request, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
