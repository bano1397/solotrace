"""
REQ-11 (new in v2.0) — Account statements must mask account numbers, showing only the
last 4 digits (e.g. ****1234).

AC: no full account number appears in any statement response.
"""
import re

from ledgerlite.tests.conftest import get_account, ready_account, transfer

MASK = re.compile(r"^\*{4}\d{4}$")


def _statement(client, account_id, pin="1234"):
    return client.get(f"/accounts/{account_id}/statement", headers={"X-PIN": pin})


def test_statement_masks_account_number_like_the_spec_example(client):
    acct = ready_account(client, "stmt@example.com", "100.00")
    resp = _statement(client, acct["id"])
    assert resp.status_code == 200
    masked = resp.json()["account"]["account_number"]
    assert MASK.match(masked), masked
    assert masked[-4:] == acct["account_number"][-4:]


def test_no_full_account_number_anywhere_in_a_statement(client):
    alice = ready_account(client, "alice@example.com", "1000.00")
    bob = ready_account(client, "bob@example.com", "1000.00")
    assert transfer(client, alice["id"], bob["id"], "10.00").status_code == 201
    assert transfer(client, bob["id"], alice["id"], "5.00").status_code == 201
    body = _statement(client, alice["id"]).text
    assert len(_statement(client, alice["id"]).json()["transactions"]) == 2
    assert alice["account_number"] not in body
    assert bob["account_number"] not in body


def test_statement_requires_the_account_pin(client):
    acct = ready_account(client, "private@example.com", "100.00")
    assert client.get(f"/accounts/{acct['id']}/statement").status_code == 422  # no PIN header
    assert _statement(client, acct["id"], pin="0000").status_code == 403


def test_owner_account_view_is_not_a_statement(client):
    """GET /accounts/{id} (owner, with PIN) still shows the full number."""
    acct = ready_account(client, "owner@example.com")
    resp = get_account(client, acct["id"])
    assert resp.status_code == 200
    assert resp.json()["account_number"] == acct["account_number"]


def test_no_full_account_number_in_statement_headers_either(client):
    acct = ready_account(client, "hdr@example.com", "100.00")
    resp = _statement(client, acct["id"])
    everything = resp.text + "\n".join(f"{k}: {v}" for k, v in resp.headers.items())
    assert acct["account_number"] not in everything
