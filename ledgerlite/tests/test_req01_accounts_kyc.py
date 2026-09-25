"""
REQ-01 — Unique email and KYC gating.

AC1: duplicate email is rejected.
AC2: any money movement on an unverified account is rejected.
"""
import pytest

from ledgerlite.tests.conftest import (
    ADMIN,
    deposit,
    make_account,
    ready_account,
    run_concurrently,
    transfer,
    verify_account,
    withdraw,
)


class TestUniqueEmail:
    def test_create_account_success(self, client):
        data = make_account(client, "alice@example.com")
        assert data["email"] == "alice@example.com"
        assert data["kyc_status"] == "pending"
        assert len(data["account_number"]) == 10 and data["account_number"].isdigit()
        assert data["balance"] == "0.00"
        assert data["locked"] is False

    def test_duplicate_email_rejected(self, client):
        make_account(client, "alice@example.com")
        resp = client.post("/accounts", json={"email": "alice@example.com", "country_code": "US", "pin": "9999"})
        assert resp.status_code == 409
        assert "already registered" in resp.json()["detail"]

    def test_duplicate_email_is_case_insensitive(self, client):
        make_account(client, "alice@example.com")
        resp = client.post("/accounts", json={"email": "Alice@Example.COM", "country_code": "US", "pin": "9999"})
        assert resp.status_code == 409

    def test_email_stored_lower_case(self, client):
        data = make_account(client, "Bob.Smith@Example.com")
        assert data["email"] == "bob.smith@example.com"

    def test_concurrent_duplicate_signups_give_one_account(self, client):
        body = {"email": "race@example.com", "country_code": "US", "pin": "1234"}
        results = run_concurrently([lambda: client.post("/accounts", json=body)] * 8)
        codes = sorted(r.status_code for r in results)
        assert codes.count(201) == 1
        assert set(codes) == {201, 409}, codes  # never a 500


class TestAccountInputValidation:
    @pytest.mark.parametrize("code", ["USA", "XX", "", "U", "ＫＰ", "1A"])
    def test_invalid_country_code_rejected(self, client, code):
        resp = client.post("/accounts", json={"email": "c@example.com", "country_code": code, "pin": "1234"})
        assert resp.status_code == 422

    def test_country_code_normalised_to_uppercase(self, client):
        data = make_account(client, "carol@example.com", country="gb")
        assert data["country_code"] == "GB"

    @pytest.mark.parametrize("pin", ["", "12", "abcd", "1234567"])
    def test_invalid_pin_rejected(self, client, pin):
        resp = client.post("/accounts", json={"email": "p@example.com", "country_code": "US", "pin": pin})
        assert resp.status_code == 422


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
        resp = withdraw(client, acct["id"], "10.00")
        assert resp.status_code == 403
        assert "KYC" in resp.json()["detail"]

    def test_transfer_sender_blocked_before_kyc(self, client):
        sender = make_account(client, "alice@example.com")
        recipient = ready_account(client, "bob@example.com")
        resp = transfer(client, sender["id"], recipient["id"], "50.00")
        assert resp.status_code == 403
        assert "Sender KYC" in resp.json()["detail"]

    def test_transfer_recipient_blocked_before_kyc(self, client):
        sender = ready_account(client, "alice@example.com", "200.00")
        recipient = make_account(client, "bob@example.com")
        resp = transfer(client, sender["id"], recipient["id"], "50.00")
        assert resp.status_code == 403
        assert "Recipient KYC" in resp.json()["detail"]

    def test_kyc_verification_requires_admin_token(self, client):
        acct = make_account(client, "alice@example.com")
        assert client.post(f"/accounts/{acct['id']}/verify-kyc").status_code == 401
        bad = client.post(f"/accounts/{acct['id']}/verify-kyc", headers={"X-Admin-Token": "wrong"})
        assert bad.status_code == 401
        ok = client.post(f"/accounts/{acct['id']}/verify-kyc", headers=ADMIN)
        assert ok.status_code == 200 and ok.json()["kyc_status"] == "verified"
