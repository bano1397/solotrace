"""
Tests for Spec Item 3: Withdrawals cannot make the balance negative.
"""
from ledgerlite.tests.conftest import make_account, verify_account, deposit


class TestWithdrawal:
    def _funded_account(self, client, email: str, amount: str = "500.00"):
        acct = make_account(client, email)
        verify_account(client, acct["id"])
        deposit(client, acct["id"], amount)
        return acct

    def _withdraw(self, client, account_id: int, amount: str, pin: str = "1234"):
        return client.post(
            f"/accounts/{account_id}/withdraw",
            json={"amount": amount, "pin": pin},
        )

    def test_withdrawal_reduces_balance(self, client):
        acct = self._funded_account(client, "alice@example.com")
        resp = self._withdraw(client, acct["id"], "100.00")
        assert resp.status_code == 200
        assert resp.json()["balance"] == "400.00"

    def test_withdrawal_exact_balance_allowed(self, client):
        acct = self._funded_account(client, "alice@example.com", "200.00")
        resp = self._withdraw(client, acct["id"], "200.00")
        assert resp.status_code == 200
        assert resp.json()["balance"] == "0.00"

    def test_withdrawal_overdraft_rejected(self, client):
        acct = self._funded_account(client, "alice@example.com", "100.00")
        resp = self._withdraw(client, acct["id"], "100.01")
        assert resp.status_code == 400
        assert "Insufficient" in resp.json()["detail"]

    def test_withdrawal_zero_rejected(self, client):
        acct = self._funded_account(client, "alice@example.com")
        resp = self._withdraw(client, acct["id"], "0")
        assert resp.status_code == 400

    def test_withdrawal_negative_rejected(self, client):
        acct = self._funded_account(client, "alice@example.com")
        resp = self._withdraw(client, acct["id"], "-50.00")
        assert resp.status_code == 400

    def test_balance_never_goes_negative(self, client):
        acct = self._funded_account(client, "alice@example.com", "10.00")
        self._withdraw(client, acct["id"], "10.00")
        resp = self._withdraw(client, acct["id"], "0.01")
        assert resp.status_code == 400
        # Confirm balance is still exactly 0.00, not negative
        check = client.get(f"/accounts/{acct['id']}")
        assert check.json()["balance"] == "0.00"
