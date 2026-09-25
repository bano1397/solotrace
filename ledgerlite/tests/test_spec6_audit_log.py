"""
REQ-06 — Audit log for every money movement.

AC1: every deposit, withdrawal, and transfer writes an immutable audit entry.
AC2: no PATCH/PUT endpoint exists to mutate audit entries (DELETE also blocked).
"""
import pytest
from fastapi.testclient import TestClient

from ledgerlite.tests.conftest import deposit, make_account, verify_account


def _ready_account(client: TestClient, email: str, balance: str = "500.00") -> dict:
    acct = make_account(client, email)
    verify_account(client, acct["id"])
    deposit(client, acct["id"], balance)
    return acct


def test_audit_entry_written_on_deposit(client: TestClient):
    acct = make_account(client, "audit_dep@test.com")
    verify_account(client, acct["id"])
    deposit(client, acct["id"], "100.00")

    resp = client.get("/audit")
    assert resp.status_code == 200
    entries = resp.json()
    deposit_entries = [e for e in entries if e["action"] == "deposit"]
    assert len(deposit_entries) >= 1
    assert deposit_entries[-1]["amount"] == "100.00"
    assert deposit_entries[-1]["account_id"] == acct["id"]


def test_audit_entry_written_on_withdrawal(client: TestClient):
    acct = _ready_account(client, "audit_wd@test.com", "200.00")
    client.post(
        f"/accounts/{acct['id']}/withdraw",
        json={"amount": "50.00", "pin": "1234"},
    )

    resp = client.get("/audit")
    assert resp.status_code == 200
    entries = resp.json()
    wd_entries = [e for e in entries if e["action"] == "withdrawal"]
    assert len(wd_entries) >= 1
    assert wd_entries[-1]["amount"] == "50.00"


def test_audit_entry_written_on_transfer(client: TestClient):
    sender = _ready_account(client, "audit_s@test.com", "1000.00")
    recipient = make_account(client, "audit_r@test.com")
    verify_account(client, recipient["id"])

    client.post(
        "/transfers",
        json={
            "sender_id": sender["id"],
            "recipient_id": recipient["id"],
            "amount": "100.00",
            "pin": "1234",
        },
    )

    resp = client.get("/audit")
    assert resp.status_code == 200
    entries = resp.json()
    transfer_entries = [e for e in entries if e["action"] == "transfer_initiated"]
    assert len(transfer_entries) >= 1
    assert transfer_entries[-1]["amount"] == "100.00"


def test_no_audit_delete_endpoint(client: TestClient):
    """DELETE /audit must not be 200 or 204 — FastAPI returns 405."""
    resp = client.delete("/audit")
    assert resp.status_code == 405


def test_no_audit_patch_endpoint(client: TestClient):
    """PATCH /audit must not be 200 — FastAPI returns 405."""
    resp = client.patch("/audit", json={})
    assert resp.status_code == 405
