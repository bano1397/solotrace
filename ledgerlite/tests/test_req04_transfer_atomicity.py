"""
REQ-04 — Atomic transfers: both the debit and the credit happen, or neither does.

AC: if the credit fails, the debit is rolled back.
"""
from unittest.mock import patch

from ledgerlite import services as svc
from ledgerlite.models import Transfer
from ledgerlite.tests.conftest import audit_log, balance_of, db_read, ready_account, transfer


def _pair(client, sender_balance="500.00"):
    sender = ready_account(client, "alice@example.com", sender_balance)
    recipient = ready_account(client, "bob@example.com")
    return sender, recipient


def test_successful_transfer_debits_sender_and_credits_recipient(client):
    sender, recipient = _pair(client)
    resp = transfer(client, sender["id"], recipient["id"], "200.00")
    assert resp.status_code == 201
    assert resp.json()["status"] == "completed"
    assert balance_of(client, sender["id"]) == "300.00"
    assert balance_of(client, recipient["id"]) == "200.00"


def test_insufficient_funds_rejected_without_side_effects(client):
    sender, recipient = _pair(client, "100.00")
    resp = transfer(client, sender["id"], recipient["id"], "100.01")
    assert resp.status_code == 400
    assert "Insufficient" in resp.json()["detail"]
    assert balance_of(client, sender["id"]) == "100.00"
    assert balance_of(client, recipient["id"]) == "0.00"


def test_zero_negative_and_self_transfers_rejected(client):
    sender, recipient = _pair(client)
    assert transfer(client, sender["id"], recipient["id"], "0").status_code == 400
    assert transfer(client, sender["id"], recipient["id"], "-10.00").status_code == 400
    assert transfer(client, sender["id"], sender["id"], "10.00").status_code == 400


def test_unknown_accounts_return_404(client):
    sender, recipient = _pair(client)
    assert transfer(client, 9999, recipient["id"], "10.00").status_code == 404
    assert transfer(client, sender["id"], 9999, "10.00").status_code == 404


def test_failed_credit_rolls_back_the_debit(client, unsafe_client):
    """Crash exactly at the credit step: the sender must not lose money."""
    sender, recipient = _pair(client)
    with patch.object(svc, "_credit", side_effect=RuntimeError("simulated failure during credit")):
        resp = transfer(unsafe_client, sender["id"], recipient["id"], "100.00")
    assert resp.status_code == 500
    assert balance_of(client, sender["id"]) == "500.00"
    assert balance_of(client, recipient["id"]) == "0.00"
    assert db_read(lambda s: s.query(Transfer).count()) == 0
    assert [e for e in audit_log(client) if e["action"] == "transfer_initiated"] == []


def test_failed_audit_write_rolls_back_everything(client, unsafe_client):
    """Crash after debit and credit but before commit: nothing may persist."""
    sender, recipient = _pair(client)
    real_write_audit = svc._write_audit

    def fail_on_transfer(db, **kwargs):
        if kwargs.get("action") == "transfer_initiated":
            raise RuntimeError("simulated failure writing the audit entry")
        return real_write_audit(db, **kwargs)

    with patch.object(svc, "_write_audit", side_effect=fail_on_transfer):
        resp = transfer(unsafe_client, sender["id"], recipient["id"], "100.00")
    assert resp.status_code == 500
    assert balance_of(client, sender["id"]) == "500.00"
    assert balance_of(client, recipient["id"]) == "0.00"
    assert db_read(lambda s: s.query(Transfer).count()) == 0
