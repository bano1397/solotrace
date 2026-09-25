"""
REQ-09 — Daily outgoing transfer cap.

v2.0 spec: a sender cannot send more than 20,000.00 in outgoing transfers
in a single UTC calendar day (completed + pending_approval both count).
"""
import pytest
from fastapi.testclient import TestClient

from ledgerlite.tests.conftest import deposit, make_account, verify_account


def _ready_pair(client: TestClient, sender_email: str, recipient_email: str, balance: str = "30000.00"):
    sender = make_account(client, sender_email)
    recipient = make_account(client, recipient_email)
    verify_account(client, sender["id"])
    verify_account(client, recipient["id"])
    deposit(client, sender["id"], balance)
    return sender, recipient


def _transfer(client: TestClient, sender_id: int, recipient_id: int, amount: str):
    return client.post(
        "/transfers",
        json={"sender_id": sender_id, "recipient_id": recipient_id, "amount": amount, "pin": "1234"},
    )


def test_daily_cap_exact_boundary_accepted(client: TestClient):
    """Exactly 20,000.00 outgoing in one day must be accepted."""
    sender, recipient = _ready_pair(client, "cap_exact_s@test.com", "cap_exact_r@test.com")
    # Two transfers of 10,000.00 → total 20,000.00 (each is pending_approval under v2.0)
    r1 = _transfer(client, sender["id"], recipient["id"], "10000.00")
    assert r1.status_code == 201, r1.json()
    r2 = _transfer(client, sender["id"], recipient["id"], "10000.00")
    assert r2.status_code == 201, r2.json()


def test_daily_cap_exceeded_rejected(client: TestClient):
    """Sending 20,000.01 total in one day must be rejected with 400."""
    sender, recipient = _ready_pair(client, "cap_over_s@test.com", "cap_over_r@test.com")
    r1 = _transfer(client, sender["id"], recipient["id"], "10000.00")
    assert r1.status_code == 201, r1.json()
    r2 = _transfer(client, sender["id"], recipient["id"], "10000.00")
    assert r2.status_code == 201, r2.json()
    # This one pushes total to 20,000.01
    r3 = _transfer(client, sender["id"], recipient["id"], "0.01")
    assert r3.status_code == 400, r3.json()
    assert "daily" in r3.json()["detail"].lower()


def test_daily_cap_three_transfers_third_blocked(client: TestClient):
    """3 × 7,000.00 = 21,000.00 → 3rd transfer must be blocked."""
    sender, recipient = _ready_pair(client, "cap3_s@test.com", "cap3_r@test.com")
    r1 = _transfer(client, sender["id"], recipient["id"], "7000.00")
    assert r1.status_code == 201, r1.json()
    r2 = _transfer(client, sender["id"], recipient["id"], "7000.00")
    assert r2.status_code == 201, r2.json()
    r3 = _transfer(client, sender["id"], recipient["id"], "7000.00")
    assert r3.status_code == 400, r3.json()
    assert "daily" in r3.json()["detail"].lower()
