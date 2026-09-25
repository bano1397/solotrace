"""
REQ-11 — Masked account numbers in statements.

v2.0 spec: the statement endpoint returns account numbers masked as ****last4
(6 asterisks followed by the last 4 digits of the account number).
"""
import re
import pytest
from fastapi.testclient import TestClient

from ledgerlite.tests.conftest import deposit, make_account, verify_account

MASK_PATTERN = re.compile(r"^\*{6}\d{4}$")


def test_statement_masks_account_number(client: TestClient):
    """GET /accounts/{id}/statement must return account_number as ******NNNN."""
    acct = make_account(client, "stmt_mask@test.com")
    verify_account(client, acct["id"])
    deposit(client, acct["id"], "100.00")

    resp = client.get(f"/accounts/{acct['id']}/statement")
    assert resp.status_code == 200, resp.json()

    masked = resp.json()["account"]["account_number"]
    assert MASK_PATTERN.match(masked), (
        f"Expected account_number matching ******NNNN but got '{masked}'"
    )


def test_statement_mask_preserves_last4(client: TestClient):
    """The last 4 digits of the masked number must match the real account number."""
    acct = make_account(client, "stmt_last4@test.com")
    verify_account(client, acct["id"])
    deposit(client, acct["id"], "100.00")

    real_number = acct["account_number"]
    resp = client.get(f"/accounts/{acct['id']}/statement")
    assert resp.status_code == 200, resp.json()

    masked = resp.json()["account"]["account_number"]
    assert masked[-4:] == real_number[-4:], (
        f"Last 4 of masked '{masked}' do not match last 4 of real '{real_number}'"
    )


def test_account_detail_endpoint_not_masked(client: TestClient):
    """GET /accounts/{id} (not statement) must still return the full account number."""
    acct = make_account(client, "acct_full@test.com")
    resp = client.get(f"/accounts/{acct['id']}")
    assert resp.status_code == 200, resp.json()
    assert resp.json()["account_number"] == acct["account_number"]
