"""
REQ-08 — Monetary values are stored and calculated as exact decimals (never floating
point) and returned with exactly 2 decimal places.

AC: 0.10 + 0.20 equals 0.30 exactly; the API returns "0.30".
"""
import pytest
from sqlalchemy import text

from ledgerlite.tests.conftest import db_read, deposit, ready_account, transfer, withdraw


def test_point_one_plus_point_two_equals_point_three(client):
    acct = ready_account(client, "decimal@example.com")
    deposit(client, acct["id"], "0.10")
    resp = deposit(client, acct["id"], "0.20")
    assert resp.status_code == 200
    assert resp.json()["balance"] == "0.30"


def test_amounts_are_returned_with_exactly_two_decimals(client):
    acct = ready_account(client, "twodp@example.com")
    for amount, expected in (("100", "100.00"), ("0.5", "100.50"), (7, "107.50")):
        resp = deposit(client, acct["id"], amount)
        assert resp.status_code == 200
        assert resp.json()["balance"] == expected


def test_money_is_stored_as_integer_cents_not_real(client):
    acct = ready_account(client, "storage@example.com", "49999.99")
    other = ready_account(client, "other@example.com")
    transfer(client, acct["id"], other["id"], "0.99")
    rows = db_read(lambda s: s.execute(text("SELECT typeof(balance), balance FROM accounts ORDER BY id")).all())
    assert {kind for kind, _ in rows} == {"integer"}
    assert rows[0][1] == 4999900  # 49,999.00 in cents, exactly
    kinds = db_read(lambda s: s.execute(text("SELECT DISTINCT typeof(amount) FROM transfers")).scalars().all())
    assert kinds == ["integer"]


@pytest.mark.parametrize("amount", ["0.001", "0.005", "1.005", "4999.999"])
def test_more_than_two_decimals_is_rejected_not_rounded(client, amount):
    acct = ready_account(client, "subcent@example.com", "100.00")
    other = ready_account(client, "sink@example.com")
    assert deposit(client, acct["id"], amount).status_code == 422
    assert withdraw(client, acct["id"], amount).status_code == 422
    assert transfer(client, acct["id"], other["id"], amount).status_code == 422


def test_classic_float_traps_are_exact(client):
    """0.29, 0.57, 1.15 and 4.35 cannot be represented exactly as floats."""
    acct = ready_account(client, "traps@example.com")
    for amount in ("0.29", "0.57", "1.15", "4.35"):
        assert deposit(client, acct["id"], amount).status_code == 200
    resp = withdraw(client, acct["id"], "0.01")
    assert resp.json()["balance"] == "6.35"


def test_many_small_amounts_add_up_exactly(client):
    acct = ready_account(client, "sum@example.com")
    for _ in range(30):
        assert deposit(client, acct["id"], "0.10").status_code == 200
    resp = withdraw(client, acct["id"], "3.00")
    assert resp.status_code == 200
    assert resp.json()["balance"] == "0.00"


def test_transfer_amount_is_returned_as_a_two_decimal_string(client):
    sender = ready_account(client, "amt_s@example.com", "500.00")
    recipient = ready_account(client, "amt_r@example.com")
    assert transfer(client, sender["id"], recipient["id"], "100").json()["amount"] == "100.00"


def test_values_read_back_from_the_database_are_exact_decimals(client):
    from decimal import Decimal

    from ledgerlite.models import Account

    acct = ready_account(client, "orm@example.com")
    deposit(client, acct["id"], "0.10")
    deposit(client, acct["id"], "0.20")
    balance = db_read(lambda s: s.get(Account, acct["id"]).balance)
    assert balance == Decimal("0.30") and str(balance) == "0.30"


def test_daily_total_arithmetic_is_exact(client):
    sender = ready_account(client, "sum_s@example.com", "30000.00")
    recipient = ready_account(client, "sum_r@example.com")
    assert transfer(client, sender["id"], recipient["id"], "15000.01").status_code == 201
    assert transfer(client, sender["id"], recipient["id"], "4999.98").status_code == 201
    assert transfer(client, sender["id"], recipient["id"], "0.01").status_code == 201  # exactly 20,000.00
