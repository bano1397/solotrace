"""
REQ-10 — Sanctions list blocking.

v2.0 spec: transfers where the sender OR recipient has country_code in
{KP, IR, SY, CU} must be rejected with HTTP 400, detail "sanctions",
and a "sanctions_blocked" audit entry must be written.
"""
import pytest
from fastapi.testclient import TestClient

from ledgerlite.tests.conftest import deposit, make_account, verify_account


def _make_country_account(client: TestClient, email: str, country: str, pin: str = "1234") -> dict:
    resp = client.post(
        "/accounts",
        json={"email": email, "country_code": country, "pin": pin},
    )
    assert resp.status_code == 201, resp.json()
    return resp.json()


def _ready_sanctioned_sender(client: TestClient, country: str) -> tuple[dict, dict]:
    sender = _make_country_account(client, f"sanc_s_{country}@test.com", country)
    recipient = make_account(client, f"sanc_r_{country}@test.com")
    verify_account(client, sender["id"])
    verify_account(client, recipient["id"])
    deposit(client, sender["id"], "5000.00")
    return sender, recipient


@pytest.mark.parametrize("country", ["KP", "IR", "SY", "CU"])
def test_sanctioned_sender_blocked(client: TestClient, country: str):
    """Transfer from a sanctioned country must return 400 with detail 'sanctions'."""
    sender, recipient = _ready_sanctioned_sender(client, country)
    resp = client.post(
        "/transfers",
        json={
            "sender_id": sender["id"],
            "recipient_id": recipient["id"],
            "amount": "100.00",
            "pin": "1234",
        },
    )
    assert resp.status_code == 400, resp.json()
    assert resp.json()["detail"] == "sanctions"


@pytest.mark.parametrize("country", ["KP", "IR", "SY", "CU"])
def test_sanctioned_recipient_blocked(client: TestClient, country: str):
    """Transfer TO a sanctioned country must return 400 with detail 'sanctions'."""
    sender = make_account(client, f"clean_s_{country}@test.com")
    recipient = _make_country_account(client, f"sanc_r2_{country}@test.com", country)
    verify_account(client, sender["id"])
    verify_account(client, recipient["id"])
    deposit(client, sender["id"], "5000.00")

    resp = client.post(
        "/transfers",
        json={
            "sender_id": sender["id"],
            "recipient_id": recipient["id"],
            "amount": "100.00",
            "pin": "1234",
        },
    )
    assert resp.status_code == 400, resp.json()
    assert resp.json()["detail"] == "sanctions"


def test_audit_entry_written_for_sanctions_block(client: TestClient):
    """A sanctions_blocked audit entry must be written even when the transfer is rejected."""
    sender = _make_country_account(client, "sanc_audit_s@test.com", "KP")
    recipient = make_account(client, "sanc_audit_r@test.com")
    verify_account(client, sender["id"])
    verify_account(client, recipient["id"])
    deposit(client, sender["id"], "1000.00")

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
    sanctions_entries = [e for e in entries if e["action"] == "sanctions_blocked"]
    assert len(sanctions_entries) >= 1
