"""
Tests for Spec Item 2: Deposit amount validation.

- Must be > 0
- Must be <= 50000.00
- Boundary values: 0, negative, 50000.00 (ok), 50000.01 (rejected)
"""
from ledgerlite.tests.conftest import make_account, verify_account, deposit


class TestDepositValidation:
    def _setup(self, client):
        acct = make_account(client, "alice@example.com")
        verify_account(client, acct["id"])
        return acct

    def test_positive_amount_accepted(self, client):
        acct = self._setup(client)
        resp = deposit(client, acct["id"], "1.00")
        assert resp.status_code == 200
        assert resp.json()["balance"] == "1.00"

    def test_zero_rejected(self, client):
        acct = self._setup(client)
        resp = deposit(client, acct["id"], "0")
        assert resp.status_code == 400
        assert "greater than 0" in resp.json()["detail"]

    def test_negative_rejected(self, client):
        acct = self._setup(client)
        resp = deposit(client, acct["id"], "-1.00")
        assert resp.status_code == 400

    def test_boundary_50000_accepted(self, client):
        acct = self._setup(client)
        resp = deposit(client, acct["id"], "50000.00")
        assert resp.status_code == 200
        assert resp.json()["balance"] == "50000.00"

    def test_boundary_50000_01_rejected(self, client):
        acct = self._setup(client)
        resp = deposit(client, acct["id"], "50000.01")
        assert resp.status_code == 400
        assert "50000" in resp.json()["detail"]

    def test_multiple_deposits_accumulate(self, client):
        acct = self._setup(client)
        deposit(client, acct["id"], "100.00")
        deposit(client, acct["id"], "200.50")
        resp = deposit(client, acct["id"], "0.50")
        assert resp.json()["balance"] == "301.00"
