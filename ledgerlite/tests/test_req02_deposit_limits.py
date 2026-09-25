"""
REQ-02 — Deposit amount limits.

AC: 0, negative and 50,000.01 are rejected; 50,000.00 is accepted.
"""
import pytest

from ledgerlite.tests.conftest import balance_of, deposit, ready_account


@pytest.fixture()
def acct(client):
    return ready_account(client, "alice@example.com")


def test_positive_amount_accepted(client, acct):
    resp = deposit(client, acct["id"], "1.00")
    assert resp.status_code == 200
    assert resp.json()["balance"] == "1.00"


@pytest.mark.parametrize("amount", ["0", "0.00", "-0.00", "-1.00"])
def test_zero_and_negative_rejected(client, acct, amount):
    resp = deposit(client, acct["id"], amount)
    assert resp.status_code == 400
    assert "greater than 0" in resp.json()["detail"]
    assert balance_of(client, acct["id"]) == "0.00"


def test_boundary_50000_accepted(client, acct):
    resp = deposit(client, acct["id"], "50000.00")
    assert resp.status_code == 200
    assert resp.json()["balance"] == "50000.00"


def test_boundary_50000_01_rejected(client, acct):
    resp = deposit(client, acct["id"], "50000.01")
    assert resp.status_code == 400
    assert "50000" in resp.json()["detail"]
    assert balance_of(client, acct["id"]) == "0.00"


@pytest.mark.parametrize("amount", ["abc", "NaN", "Infinity", None, "1e400"])
def test_non_numeric_amounts_rejected(client, acct, amount):
    resp = deposit(client, acct["id"], amount)
    assert resp.status_code == 422


def test_multiple_deposits_accumulate(client, acct):
    deposit(client, acct["id"], "100.00")
    deposit(client, acct["id"], "200.50")
    resp = deposit(client, acct["id"], "0.50")
    assert resp.json()["balance"] == "301.00"
