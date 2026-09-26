"""
REQ-06 — Every money movement (deposit, withdrawal, transfer, approval) writes an audit
entry with actor, action, amount, account(s) and UTC timestamp. Entries cannot be edited.

AC1: each operation adds exactly one entry.
AC2: no update endpoint exists for audit entries.
"""
import datetime

import pytest

from ledgerlite.main import app
from ledgerlite.tests.conftest import (
    ADMIN,
    approve,
    audit_log,
    deposit,
    make_approver,
    ready_account,
    transfer,
    withdraw,
)


def _new_entries(client, before: int) -> list[dict]:
    return audit_log(client)[before:]


def _assert_utc(ts: str) -> None:
    assert ts.endswith("Z"), ts
    parsed = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    assert parsed.utcoffset() == datetime.timedelta(0)


def test_deposit_writes_exactly_one_entry(client):
    acct = ready_account(client, "dep@example.com")
    before = len(audit_log(client))
    assert deposit(client, acct["id"], "100.00").status_code == 200
    new = _new_entries(client, before)
    assert len(new) == 1
    entry = new[0]
    assert (entry["action"], entry["actor_id"], entry["amount"], entry["account_id"]) == (
        "deposit", acct["id"], "100.00", acct["id"],
    )
    _assert_utc(entry["timestamp"])


def test_withdrawal_writes_exactly_one_entry(client):
    acct = ready_account(client, "wd@example.com", "200.00")
    before = len(audit_log(client))
    assert withdraw(client, acct["id"], "50.00").status_code == 200
    new = _new_entries(client, before)
    assert len(new) == 1
    assert (new[0]["action"], new[0]["actor_id"], new[0]["amount"], new[0]["account_id"]) == (
        "withdrawal", acct["id"], "50.00", acct["id"],
    )
    _assert_utc(new[0]["timestamp"])


def test_transfer_writes_exactly_one_entry(client):
    sender = ready_account(client, "s@example.com", "1000.00")
    recipient = ready_account(client, "r@example.com")
    before = len(audit_log(client))
    assert transfer(client, sender["id"], recipient["id"], "100.00").status_code == 201
    new = _new_entries(client, before)
    assert len(new) == 1
    entry = new[0]
    assert entry["action"] == "transfer_initiated"
    assert (entry["actor_id"], entry["amount"], entry["account_id"], entry["related_account_id"]) == (
        sender["id"], "100.00", sender["id"], recipient["id"],
    )
    _assert_utc(entry["timestamp"])


def test_approval_writes_exactly_one_entry(client):
    sender = ready_account(client, "s@example.com", "9000.00")
    recipient = ready_account(client, "r@example.com")
    approver = make_approver(client, "a@example.com")
    held = transfer(client, sender["id"], recipient["id"], "6000.00").json()
    before = len(audit_log(client))
    assert approve(client, held["id"], approver["id"]).status_code == 200
    new = _new_entries(client, before)
    assert len(new) == 1
    entry = new[0]
    assert entry["action"] == "transfer_approved"
    assert (entry["actor_id"], entry["amount"], entry["account_id"], entry["related_account_id"]) == (
        approver["id"], "6000.00", sender["id"], recipient["id"],
    )


def test_rejected_operations_write_no_money_movement_entry(client):
    acct = ready_account(client, "poor@example.com", "10.00")
    before = len(audit_log(client))
    assert withdraw(client, acct["id"], "50.00").status_code == 400
    assert deposit(client, acct["id"], "0").status_code == 400
    assert _new_entries(client, before) == []


def test_audit_log_requires_admin_token(client):
    assert client.get("/audit").status_code == 401


@pytest.mark.parametrize("method", ["PUT", "PATCH", "POST", "DELETE"])
def test_audit_collection_cannot_be_modified(client, method):
    resp = client.request(method, "/audit", headers=ADMIN, json={})
    assert resp.status_code == 405


@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
def test_existing_entry_cannot_be_modified(client, method):
    acct = ready_account(client, "imm@example.com", "100.00")
    entry = audit_log(client)[-1]
    resp = client.request(method, f"/audit/{entry['id']}", headers=ADMIN, json={"amount": "0.01"})
    assert resp.status_code in (404, 405)
    assert audit_log(client)[-1] == entry
    assert acct["id"] == entry["account_id"]


def test_no_route_can_change_audit_entries():
    """Route table check: the only audit route is read-only GET /audit."""
    audit_routes = [r for r in app.routes if getattr(r, "path", "").startswith("/audit")]
    assert [(r.path, sorted(r.methods)) for r in audit_routes] == [("/audit", ["GET"])]
