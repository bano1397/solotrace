"""
REQ-08 — Exact decimal arithmetic.

AC1: 0.10 + 0.20 == 0.30 exactly (no floating-point drift).
AC2: balance is serialised as a 2-decimal-place string.
"""
import pytest
from fastapi.testclient import TestClient

from ledgerlite.tests.conftest import deposit, make_account, verify_account


def test_point_one_plus_point_two_equals_point_three(client: TestClient):
    acct = make_account(client, "decimal@test.com")
    verify_account(client, acct["id"])

    deposit(client, acct["id"], "0.10")
    resp = deposit(client, acct["id"], "0.20")
    assert resp.status_code == 200, resp.json()
    assert resp.json()["balance"] == "0.30", (
        f"Expected '0.30' but got '{resp.json()['balance']}' — floating-point drift detected"
    )


def test_balance_serialised_as_two_decimal_places(client: TestClient):
    acct = make_account(client, "twodp@test.com")
    verify_account(client, acct["id"])

    resp = deposit(client, acct["id"], "100.00")
    assert resp.status_code == 200
    balance = resp.json()["balance"]
    # Must be a string with exactly 2 decimal places
    assert isinstance(balance, str), "balance must be a string"
    assert "." in balance
    assert len(balance.split(".")[1]) == 2
