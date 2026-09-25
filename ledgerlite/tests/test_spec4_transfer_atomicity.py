"""
Tests for Spec Item 4: Transfers are atomic — debit and credit happen in one
DB transaction and roll back on failure.
"""
from decimal import Decimal
from unittest.mock import patch

import pytest

from ledgerlite.tests.conftest import make_account, verify_account, deposit
from ledgerlite import services as svc


class TestTransferAtomicity:
    def _setup(self, client, sender_balance: str = "500.00"):
        sender = make_account(client, "alice@example.com")
        recip = make_account(client, "bob@example.com")
        verify_account(client, sender["id"])
        verify_account(client, recip["id"])
        deposit(client, sender["id"], sender_balance)
        return sender, recip

    def _transfer(self, client, sender_id, recip_id, amount, pin="1234"):
        return client.post(
            "/transfers",
            json={
                "sender_id": sender_id,
                "recipient_id": recip_id,
                "amount": amount,
                "pin": pin,
            },
        )

    def test_successful_transfer_debits_sender_credits_recipient(self, client):
        sender, recip = self._setup(client)
        resp = self._transfer(client, sender["id"], recip["id"], "200.00")
        assert resp.status_code == 201
        assert resp.json()["status"] == "completed"

        s = client.get(f"/accounts/{sender['id']}").json()
        r = client.get(f"/accounts/{recip['id']}").json()
        assert s["balance"] == "300.00"
        assert r["balance"] == "200.00"

    def test_insufficient_funds_rejected(self, client):
        sender, recip = self._setup(client, "100.00")
        resp = self._transfer(client, sender["id"], recip["id"], "100.01")
        assert resp.status_code == 400
        assert "Insufficient" in resp.json()["detail"]

    def test_transfer_zero_rejected(self, client):
        sender, recip = self._setup(client)
        resp = self._transfer(client, sender["id"], recip["id"], "0")
        assert resp.status_code == 400

    def test_transfer_negative_rejected(self, client):
        sender, recip = self._setup(client)
        resp = self._transfer(client, sender["id"], recip["id"], "-10.00")
        assert resp.status_code == 400

    def test_transfer_rolls_back_on_db_error(self, client, db_session):
        """
        Force an exception after the sender is debited but before commit.
        Both balances must remain unchanged — proving the transaction rolled back.
        """
        sender, recip = self._setup(client)

        original_balance_sender = Decimal("500.00")
        original_balance_recip = Decimal("0.00")

        def boom(*args, **kwargs):
            raise RuntimeError("simulated DB failure mid-transaction")

        # Patch _write_audit so the crash fires after the balance mutation
        # but before commit — exercising the rollback path.
        # Use raise_server_exceptions=False so the 500 is returned as a response
        # rather than being re-raised into the test process.
        from starlette.testclient import TestClient as _TC
        from ledgerlite.main import app as _app
        from unittest.mock import patch as _patch

        with patch.object(svc, "_write_audit", side_effect=boom):
            with _TC(_app, raise_server_exceptions=False) as safe_client:
                # The safe_client also needs the DB override
                from ledgerlite.db import get_db as _get_db

                def _override():
                    try:
                        yield db_session
                    finally:
                        pass

                _app.dependency_overrides[_get_db] = _override
                resp = safe_client.post(
                    "/transfers",
                    json={
                        "sender_id": sender["id"],
                        "recipient_id": recip["id"],
                        "amount": "100.00",
                        "pin": "1234",
                    },
                )

        assert resp.status_code == 500  # server sees unhandled RuntimeError

        # After the rollback the session may be in a bad state; expire all to re-read
        db_session.expire_all()

        s = client.get(f"/accounts/{sender['id']}").json()
        r = client.get(f"/accounts/{recip['id']}").json()
        assert Decimal(s["balance"]) == original_balance_sender
        assert Decimal(r["balance"]) == original_balance_recip

    def test_non_existent_sender_returns_404(self, client):
        _, recip = self._setup(client)
        resp = self._transfer(client, 9999, recip["id"], "10.00")
        assert resp.status_code == 404

    def test_non_existent_recipient_returns_404(self, client):
        sender, _ = self._setup(client)
        resp = self._transfer(client, sender["id"], 9999, "10.00")
        assert resp.status_code == 404
