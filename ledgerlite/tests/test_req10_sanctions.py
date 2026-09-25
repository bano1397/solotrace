"""
REQ-10 (new in v2.0) — Transfers to an account whose country code is on the sanctions
list (KP, IR, SY, CU) are blocked and logged.

AC: the transfer is rejected with reason "sanctions" and an audit entry is written.
(LedgerLite also blocks transfers *from* sanctioned countries.)
"""
import pytest

from ledgerlite.tests.conftest import audit_log, balance_of, make_account, ready_account, transfer

SANCTIONED = ["KP", "IR", "SY", "CU"]


def _sanctions_entries(client) -> list[dict]:
    return [e for e in audit_log(client) if e["action"] == "sanctions_blocked"]


@pytest.mark.parametrize("country", SANCTIONED)
def test_transfer_to_sanctioned_recipient_blocked_and_logged(client, country):
    sender = ready_account(client, "clean@example.com", "5000.00")
    recipient = ready_account(client, f"r_{country.lower()}@example.com", country=country)
    resp = transfer(client, sender["id"], recipient["id"], "100.00")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "sanctions"
    entries = _sanctions_entries(client)
    assert len(entries) == 1
    assert entries[0]["account_id"] == sender["id"]
    assert entries[0]["related_account_id"] == recipient["id"]
    assert entries[0]["amount"] == "100.00"
    assert country in entries[0]["detail"]
    assert balance_of(client, sender["id"]) == "5000.00"


@pytest.mark.parametrize("country", SANCTIONED)
def test_transfer_from_sanctioned_sender_blocked_and_logged(client, country):
    sender = ready_account(client, f"s_{country.lower()}@example.com", "5000.00", country=country)
    recipient = ready_account(client, "clean@example.com")
    resp = transfer(client, sender["id"], recipient["id"], "100.00")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "sanctions"
    assert len(_sanctions_entries(client)) == 1
    assert balance_of(client, recipient["id"]) == "0.00"


def test_lower_case_country_code_is_still_screened(client):
    sender = ready_account(client, "clean@example.com", "1000.00")
    recipient = ready_account(client, "lower@example.com", country="kp")
    assert recipient["country_code"] == "KP"
    assert transfer(client, sender["id"], recipient["id"], "10.00").json()["detail"] == "sanctions"


def test_sanctions_hit_is_logged_even_before_kyc(client):
    """Screening runs before KYC checks, so a hit on an unverified account is still logged."""
    sender = ready_account(client, "clean@example.com", "1000.00")
    recipient = make_account(client, "unverified_ir@example.com", country="IR")
    resp = transfer(client, sender["id"], recipient["id"], "10.00")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "sanctions"
    assert len(_sanctions_entries(client)) == 1


def test_clean_countries_are_not_blocked(client):
    sender = ready_account(client, "us@example.com", "1000.00")
    recipient = ready_account(client, "pk@example.com", country="PK")
    assert transfer(client, sender["id"], recipient["id"], "10.00").status_code == 201
    assert _sanctions_entries(client) == []
