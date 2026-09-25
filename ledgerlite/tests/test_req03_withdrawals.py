"""
REQ-03 — A withdrawal must never make the account balance negative.

AC: withdrawing more than the balance is rejected and the balance is unchanged.
"""
from ledgerlite.tests.conftest import balance_of, ready_account, run_concurrently, withdraw


def test_withdrawal_reduces_balance(client):
    acct = ready_account(client, "alice@example.com", "500.00")
    resp = withdraw(client, acct["id"], "100.00")
    assert resp.status_code == 200
    assert resp.json()["balance"] == "400.00"


def test_withdrawal_exact_balance_allowed(client):
    acct = ready_account(client, "alice@example.com", "200.00")
    resp = withdraw(client, acct["id"], "200.00")
    assert resp.status_code == 200
    assert resp.json()["balance"] == "0.00"


def test_overdraft_rejected_and_balance_unchanged(client):
    acct = ready_account(client, "alice@example.com", "100.00")
    resp = withdraw(client, acct["id"], "100.01")
    assert resp.status_code == 400
    assert "Insufficient" in resp.json()["detail"]
    assert balance_of(client, acct["id"]) == "100.00"


def test_zero_and_negative_withdrawals_rejected(client):
    acct = ready_account(client, "alice@example.com", "500.00")
    assert withdraw(client, acct["id"], "0").status_code == 400
    assert withdraw(client, acct["id"], "-50.00").status_code == 400
    assert balance_of(client, acct["id"]) == "500.00"


def test_balance_never_goes_negative(client):
    acct = ready_account(client, "alice@example.com", "10.00")
    assert withdraw(client, acct["id"], "10.00").status_code == 200
    assert withdraw(client, acct["id"], "0.01").status_code == 400
    assert balance_of(client, acct["id"]) == "0.00"


def test_concurrent_withdrawals_cannot_overdraw(client):
    """Ten simultaneous withdrawals of the whole balance: exactly one may succeed."""
    acct = ready_account(client, "alice@example.com", "100.00")
    results = run_concurrently([lambda: withdraw(client, acct["id"], "100.00")] * 10)
    codes = [r.status_code for r in results]
    assert codes.count(200) == 1, codes
    assert codes.count(400) == 9, codes
    assert balance_of(client, acct["id"]) == "0.00"
