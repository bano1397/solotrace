"""
Shared pytest fixtures for LedgerLite tests.

Each test gets a fresh in-memory SQLite database backed by a StaticPool so that
all connections (the session AND any new connections opened by the lifespan) share
exactly the same in-memory database instance.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import ledgerlite.db as db_module
import ledgerlite.main as main_module
from ledgerlite.db import Base, get_db
from ledgerlite.main import app


@pytest.fixture()
def db_engine():
    """
    Yield a SQLAlchemy engine backed by a StaticPool in-memory SQLite.

    StaticPool ensures every connection() call returns the same underlying
    connection, so the tables created here are visible to all users of the
    engine — including the FastAPI lifespan's create_all() call.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    """Yield a session bound to the per-test in-memory engine."""
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_engine, db_session):
    """
    Return a TestClient with:
    - get_db overridden to yield the per-test session
    - module-level engine attributes patched so the lifespan's create_all
      hits the same StaticPool engine (tables already exist → no-op).
    """
    from unittest.mock import patch

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with patch.object(db_module, "engine", db_engine), \
         patch.object(main_module, "engine", db_engine):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c

    app.dependency_overrides.clear()


# ── small helpers used in multiple test files ─────────────────────────────────

def make_account(client: TestClient, email: str, pin: str = "1234") -> dict:
    resp = client.post(
        "/accounts",
        json={"email": email, "country_code": "US", "pin": pin},
    )
    assert resp.status_code == 201, resp.json()
    return resp.json()


def verify_account(client: TestClient, account_id: int) -> dict:
    resp = client.post(f"/accounts/{account_id}/verify-kyc")
    assert resp.status_code == 200, resp.json()
    return resp.json()


def deposit(client: TestClient, account_id: int, amount: str, pin: str = "1234"):
    return client.post(
        f"/accounts/{account_id}/deposit",
        json={"amount": amount, "pin": pin},
    )
