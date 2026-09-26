"""
REQ-05 (changed in v2.0) — A transfer of 5,000.00 or more is held as pending_approval
until a second, different user approves it.

AC1: a 5,000.00 transfer is pending, not completed.
AC2: the initiator cannot approve their own transfer.
"""
import pytest

from ledgerlite.tests.conftest import (
    ADMIN,
    approve,
    balance_of,
    make_account,
    make_approver,
    ready_account,
    run_concurrently,
    transfer,
)


@pytest.fixture()
def trio(client):
    sender = ready_account(client, "sender@example.com", "20000.00")
    recipient = ready_account(client, "recipient@example.com")
    approver = make_approver(client, "approver@example.com")
    return sender, recipient, approver


@pytest.mark.parametrize("amount", ["4999.00", "4999.99"])
def test_below_threshold_completes_immediately(client, trio, amount):
    sender, recipient, _ = trio
    resp = transfer(client, sender["id"], recipient["id"], amount)
    assert resp.status_code == 201, resp.json()
    assert resp.json()["status"] == "completed"
    assert balance_of(client, recipient["id"]) == amount


@pytest.mark.parametrize("amount", ["5000.00", "5000.01", "10000.00"])
def test_at_or_above_threshold_is_held(client, trio, amount):
    sender, recipient, _ = trio
    resp = transfer(client, sender["id"], recipient["id"], amount)
    assert resp.status_code == 201, resp.json()
    assert resp.json()["status"] == "pending_approval"
    assert resp.json()["approver_id"] is None
    assert balance_of(client, recipient["id"]) == "0.00"  # not credited yet


def test_sub_cent_amount_cannot_dodge_the_threshold(client, trio):
    sender, recipient, _ = trio
    resp = transfer(client, sender["id"], recipient["id"], "4999.999")
    assert resp.status_code == 422


def test_second_user_approval_completes_and_credits_once(client, trio):
    sender, recipient, approver = trio
    held = transfer(client, sender["id"], recipient["id"], "5000.00").json()
    resp = approve(client, held["id"], approver["id"])
    assert resp.status_code == 200, resp.json()
    assert resp.json()["status"] == "completed"
    assert resp.json()["approver_id"] == approver["id"]
    assert balance_of(client, recipient["id"]) == "5000.00"
    assert balance_of(client, sender["id"]) == "15000.00"


def _grant_role(client, account_id):
    assert client.post(f"/accounts/{account_id}/grant-approver", headers=ADMIN).status_code == 200


def test_initiator_cannot_approve_own_transfer(client, trio):
    """Even an initiator who holds the approver role cannot approve their own transfer."""
    sender, recipient, _ = trio
    _grant_role(client, sender["id"])
    held = transfer(client, sender["id"], recipient["id"], "5000.00").json()
    resp = approve(client, held["id"], sender["id"])
    assert resp.status_code == 403
    assert "Initiator" in resp.json()["detail"]
    assert balance_of(client, recipient["id"]) == "0.00"


def test_recipient_cannot_approve(client, trio):
    """Even a recipient who holds the approver role cannot approve a transfer to themselves."""
    sender, recipient, _ = trio
    _grant_role(client, recipient["id"])
    held = transfer(client, sender["id"], recipient["id"], "5000.00").json()
    resp = approve(client, held["id"], recipient["id"])
    assert resp.status_code == 403
    assert "Recipient" in resp.json()["detail"]
    assert balance_of(client, recipient["id"]) == "0.00"


def test_approver_needs_correct_pin(client, trio):
    sender, recipient, approver = trio
    held = transfer(client, sender["id"], recipient["id"], "5000.00").json()
    resp = approve(client, held["id"], approver["id"], pin="0000")
    assert resp.status_code == 403
    assert balance_of(client, recipient["id"]) == "0.00"


def test_unverified_approver_rejected(client, trio):
    sender, recipient, _ = trio
    stranger = make_account(client, "stranger@example.com")
    held = transfer(client, sender["id"], recipient["id"], "5000.00").json()
    resp = approve(client, held["id"], stranger["id"])
    assert resp.status_code == 403
    assert "Approver KYC" in resp.json()["detail"]


def test_double_approval_rejected_and_credits_once(client, trio):
    sender, recipient, approver = trio
    other = make_approver(client, "other@example.com")
    held = transfer(client, sender["id"], recipient["id"], "5000.00").json()
    assert approve(client, held["id"], approver["id"]).status_code == 200
    again = approve(client, held["id"], other["id"])
    assert again.status_code == 400
    assert balance_of(client, recipient["id"]) == "5000.00"


def test_concurrent_approvals_credit_exactly_once(client, trio):
    sender, recipient, approver = trio
    held = transfer(client, sender["id"], recipient["id"], "5000.00").json()
    results = run_concurrently([lambda: approve(client, held["id"], approver["id"])] * 6)
    codes = [r.status_code for r in results]
    assert codes.count(200) == 1, codes
    assert balance_of(client, recipient["id"]) == "5000.00"


def test_unknown_transfer_and_approver(client, trio):
    sender, recipient, _ = trio
    held = transfer(client, sender["id"], recipient["id"], "5000.00").json()
    assert approve(client, 9999, sender["id"]).status_code == 404
    assert approve(client, held["id"], 9999).status_code == 404


def test_completed_transfer_cannot_be_approved(client, trio):
    sender, recipient, approver = trio
    done = transfer(client, sender["id"], recipient["id"], "100.00").json()
    assert approve(client, done["id"], approver["id"]).status_code == 400


def test_customer_without_approver_role_cannot_approve(client, trio):
    sender, recipient, _ = trio
    customer = ready_account(client, "customer@example.com")
    held = transfer(client, sender["id"], recipient["id"], "5000.00").json()
    resp = approve(client, held["id"], customer["id"])
    assert resp.status_code == 403
    assert "not authorised" in resp.json()["detail"]
    assert balance_of(client, recipient["id"]) == "0.00"


def test_only_the_compliance_officer_can_grant_the_role(client):
    acct = ready_account(client, "wannabe@example.com")
    assert client.post(f"/accounts/{acct['id']}/grant-approver").status_code == 401
    unverified = make_account(client, "unverified@example.com")
    assert client.post(f"/accounts/{unverified['id']}/grant-approver", headers=ADMIN).status_code == 403
