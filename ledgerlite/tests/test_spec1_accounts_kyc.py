"""
Tests for Spec Item 1: Account creation and KYC gating.

- Unique email is required.
- Accounts cannot send or receive money until KYC is verified.
"""
import pytest
from ledgerlite.tests.conftest import make_account, verify_account, deposit


class TestAccountCreation:
    def test_create_account_success(self, client):
        data = make_account(client, "alice@example.com")
        assert data["email"] == "alice@example.com"
        assert data["kyc_status"] == "pending"
        assert len(data["account_number"]) == 10
        assert data["account_number"].isdigit()
        assert data["balance"] == "0.00"
        assert data["locked"] is False

    def test_duplicate_email_rejected(self, client):
        make_account(client, "alice@example.com")
        resp = client.post(
            "/accounts",
            json={"email": "alice@example.com", "country_code": "US", "pin": "9999"},
        )
        assert resp.status_code == 409
        assert "already registered" in resp.json()["detail"]

    def test_invalid_country_code_rejected(self, client):
        resp = client.post(
            "/accounts",
            json={"email": "bob@example.com", "country_code": "USA", "pin": "1234"},
        )
        assert resp.status_code == 422  # pydantic validation

    def test_country_code_normalised_to_uppercase(self, client):
        data = make_account(client, "carol@example.com")
        # We passed "US" — make sure it is stored uppercase
        assert data["country_code"] == "US"


class TestKYCGating:
    def test_deposit_blocked_before_kyc(self, client):
        acct = make_account(client, "alice@example.com")
        resp = deposit(client, acct["id"], "100.00")
        assert resp.status_code == 403
        assert "KYC" in resp.json()["detail"]

    def test_deposit_allowed_after_kyc(self, client):
        acct = make_account(client, "alice@example.com")
        verify_account(client, acct["id"])
        resp = deposit(client, acct["id"], "100.00")
        assert resp.status_code == 200
        assert resp.json()["balance"] == "100.00"

    def test_withdraw_blocked_before_kyc(self, client):
        acct = make_account(client, "alice@example.com")
        resp = client.post(
            f"/accounts/{acct['id']}/withdraw",
            json={"amount": "10.00", "pin": "1234"},
        )
        assert resp.status_code == 403

    def test_transfer_sender_blocked_before_kyc(self, client):
        sender = make_account(client, "alice@example.com")
        recip = make_account(client, "bob@example.com")
        verify_account(client, recip["id"])
        resp = client.post(
            "/transfers",
            json={
                "sender_id": sender["id"],
                "recipient_id": recip["id"],
                "amount": "50.00",
                "pin": "1234",
            },
        )
        assert resp.status_code == 403

    def test_transfer_recipient_blocked_before_kyc(self, client):
        sender = make_account(client, "alice@example.com")
        recip = make_account(client, "bob@example.com")
        verify_account(client, sender["id"])
        # seed balance
        deposit(client, sender["id"], "200.00")
        resp = client.post(
            "/transfers",
            json={
                "sender_id": sender["id"],
                "recipient_id": recip["id"],
                "amount": "50.00",
                "pin": "1234",
            },
        )
        assert resp.status_code == 403
