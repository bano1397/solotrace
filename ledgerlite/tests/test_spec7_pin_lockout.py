"""
REQ-07 — Account lockout after failed PIN attempts.

AC1: the 5th consecutive wrong PIN locks the account (HTTP 423).
AC2: a correct PIN resets the failed-attempt counter to 0.
"""
import pytest
from fastapi.testclient import TestClient

from ledgerlite.tests.conftest import deposit, make_account, verify_account


def test_fifth_wrong_pin_locks_account(client: TestClient):
    acct = make_account(client, "lockout@test.com")
    verify_account(client, acct["id"])
    deposit(client, acct["id"], "100.00")

    # 4 wrong PINs — each should be 403 (not locked yet)
    for _ in range(4):
        resp = client.post(
            f"/accounts/{acct['id']}/deposit",
            json={"amount": "1.00", "pin": "0000"},
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.json()}"

    # 5th wrong PIN — must lock the account and return 423
    resp = client.post(
        f"/accounts/{acct['id']}/deposit",
        json={"amount": "1.00", "pin": "0000"},
    )
    assert resp.status_code == 423, resp.json()

    # Subsequent correct PIN must also be rejected (account is locked)
    resp = client.post(
        f"/accounts/{acct['id']}/deposit",
        json={"amount": "1.00", "pin": "1234"},
    )
    assert resp.status_code == 423, resp.json()


def test_correct_pin_resets_counter(client: TestClient):
    acct = make_account(client, "pinreset@test.com")
    verify_account(client, acct["id"])
    deposit(client, acct["id"], "100.00")

    # 4 wrong PINs
    for _ in range(4):
        client.post(
            f"/accounts/{acct['id']}/deposit",
            json={"amount": "1.00", "pin": "0000"},
        )

    # Correct PIN — must succeed and reset counter
    resp = client.post(
        f"/accounts/{acct['id']}/deposit",
        json={"amount": "1.00", "pin": "1234"},
    )
    assert resp.status_code == 200, resp.json()

    # Verify counter is back to 0
    acct_resp = client.get(f"/accounts/{acct['id']}")
    assert acct_resp.status_code == 200
    assert acct_resp.json()["failed_pin_attempts"] == 0
    assert acct_resp.json()["locked"] is False
