"""
Shared pytest fixtures for LedgerLite tests.

Production-like by design: every test gets its own SQLite *file* database and
the app uses the real ``get_db`` dependency, so every HTTP request runs in its
own session, exactly as in production.  (An earlier version shared one session
across requests, which hid a real PIN-lockout bug.)
"""
import os
from concurrent.futures import ThreadPoolExecutor

# Fast PIN hashing for tests only (production default is 600,000 iterations).
os.environ["LEDGERLITE_PIN_ITERATIONS"] = "1000"
os.environ["LEDGERLITE_ADMIN_TOKEN"] = "test-admin-token"
os.environ["LEDGERLITE_SQLITE_FAST"] = "1"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import ledgerlite.db as db_module  # noqa: E402
from ledgerlite.main import app  # noqa: E402

ADMIN = {"X-Admin-Token": "test-admin-token"}
PIN = "1234"


@pytest.fixture()
def client(tmp_path):
    db_module.configure(f"sqlite:///{tmp_path / 'ledgerlite-test.db'}")
    with TestClient(app) as c:
        yield c
    db_module.engine.dispose()


@pytest.fixture()
def unsafe_client(client):
    """Same app and database, but server errors come back as HTTP 500 responses."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def db_read(query):
    """Run *query(session)* in a short-lived session that bypasses the API.

    The session is closed straight away so it never holds SQLite's write lock
    while the app is serving requests.
    """
    session = db_module.SessionLocal()
    try:
        return query(session)
    finally:
        session.rollback()
        session.close()


# ── helpers used across test files ────────────────────────────────────────────

def make_account(client: TestClient, email: str, pin: str = PIN, country: str = "US") -> dict:
    resp = client.post("/accounts", json={"email": email, "country_code": country, "pin": pin})
    assert resp.status_code == 201, resp.json()
    return resp.json()


def verify_account(client: TestClient, account_id: int) -> dict:
    resp = client.post(f"/accounts/{account_id}/verify-kyc", headers=ADMIN)
    assert resp.status_code == 200, resp.json()
    return resp.json()


def ready_account(client: TestClient, email: str, balance: str | None = None, country: str = "US") -> dict:
    """Create + KYC-verify an account, optionally funding it."""
    acct = make_account(client, email, country=country)
    verify_account(client, acct["id"])
    if balance is not None:
        resp = deposit(client, acct["id"], balance)
        assert resp.status_code == 200, resp.json()
    return acct


def deposit(client: TestClient, account_id: int, amount, pin: str = PIN):
    return client.post(f"/accounts/{account_id}/deposit", json={"amount": amount, "pin": pin})


def withdraw(client: TestClient, account_id: int, amount, pin: str = PIN):
    return client.post(f"/accounts/{account_id}/withdraw", json={"amount": amount, "pin": pin})


def transfer(client: TestClient, sender_id: int, recipient_id: int, amount, pin: str = PIN):
    return client.post(
        "/transfers",
        json={"sender_id": sender_id, "recipient_id": recipient_id, "amount": amount, "pin": pin},
    )


def approve(client: TestClient, transfer_id: int, approver_id: int, pin: str = PIN):
    return client.post(f"/transfers/{transfer_id}/approve", json={"approver_id": approver_id, "pin": pin})


def get_account(client: TestClient, account_id: int, pin: str = PIN):
    return client.get(f"/accounts/{account_id}", headers={"X-PIN": pin})


def balance_of(client: TestClient, account_id: int) -> str:
    resp = get_account(client, account_id)
    assert resp.status_code == 200, resp.json()
    return resp.json()["balance"]


def audit_log(client: TestClient) -> list[dict]:
    resp = client.get("/audit", headers=ADMIN)
    assert resp.status_code == 200, resp.json()
    return resp.json()


def run_concurrently(calls, workers: int = 10) -> list:
    """Run zero-argument callables at the same time; return their results in order."""
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda call: call(), calls))
