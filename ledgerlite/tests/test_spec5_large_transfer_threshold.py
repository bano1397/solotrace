"""
REQ-05 — Large-transfer pending-approval threshold.

v2.0 spec: transfers >= 5,000.00 go to pending_approval; < 5,000.00 complete immediately.
"""
import pytest
from fastapi.testclient import TestClient

from ledgerlite.tests.conftest import deposit, make_account, verify_account


def _setup_pair(client: TestClient):
    sender = make_account(client, "sender5@test.com")
    recipient = make_account(client, "recipient5@test.com")
    verify_account(client, sender["id"])
    verify_account(client, recipient["id"])
    deposit(client, sender["id"], "20000.00")
    return sender, recipient


def test_transfer_below_threshold_completed(client: TestClient):
    """4,999.99 is below the 5,000.00 threshold → status must be 'completed'."""
    sender, recipient = _setup_pair(client)
    resp = client.post(
        "/transfers",
        json={
            "sender_id": sender["id"],
            "recipient_id": recipient["id"],
            "amount": "4999.99",
            "pin": "1234",
        },
    )
    assert resp.status_code == 201, resp.json()
    assert resp.json()["status"] == "completed"


def test_transfer_at_threshold_pending(client: TestClient):
    """Exactly 5,000.00 must be held as pending_approval."""
    sender, recipient = _setup_pair(client)
    resp = client.post(
        "/transfers",
        json={
            "sender_id": sender["id"],
            "recipient_id": recipient["id"],
            "amount": "5000.00",
            "pin": "1234",
        },
    )
    assert resp.status_code == 201, resp.json()
    assert resp.json()["status"] == "pending_approval"


def test_transfer_above_threshold_pending(client: TestClient):
    """10,000.00 (old threshold) must also be pending under v2.0."""
    sender, recipient = _setup_pair(client)
    resp = client.post(
        "/transfers",
        json={
            "sender_id": sender["id"],
            "recipient_id": recipient["id"],
            "amount": "10000.00",
            "pin": "1234",
        },
    )
    assert resp.status_code == 201, resp.json()
    assert resp.json()["status"] == "pending_approval"


def test_transfer_just_below_threshold_completed(client: TestClient):
    """4,999.00 is strictly below 5,000.00 → completed."""
    sender, recipient = _setup_pair(client)
    resp = client.post(
        "/transfers",
        json={
            "sender_id": sender["id"],
            "recipient_id": recipient["id"],
            "amount": "4999.00",
            "pin": "1234",
        },
    )
    assert resp.status_code == 201, resp.json()
    assert resp.json()["status"] == "completed"
