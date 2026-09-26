"""General API hygiene checks (not tied to one requirement)."""
import pytest

from ledgerlite.tests.conftest import get_account, ready_account


def test_root_describes_the_service(client):
    body = client.get("/").json()
    assert body["service"] == "LedgerLite"
    assert body["version"] == "2.0.0"


def test_out_of_range_ids_are_validation_errors_not_500(client):
    huge = 2**63
    assert get_account(client, huge).status_code == 422
    assert client.post(f"/transfers/{huge}/approve", json={"approver_id": 1, "pin": "1234"}).status_code == 422


def test_unknown_account_is_404(client):
    assert get_account(client, 424242).status_code == 404


def test_admin_endpoints_disabled_without_configured_token(client, monkeypatch):
    monkeypatch.delenv("LEDGERLITE_ADMIN_TOKEN")
    assert client.get("/audit", headers={"X-Admin-Token": "anything"}).status_code == 503


@pytest.mark.parametrize("field", ["sender_id", "recipient_id"])
@pytest.mark.parametrize("value", [2**63, 10**40, 0, -1])
def test_out_of_range_ids_in_the_body_are_validation_errors(client, field, value):
    body = {"sender_id": 1, "recipient_id": 2, "amount": "1.00", "pin": "1234", field: value}
    assert client.post("/transfers", json=body).status_code == 422


def test_out_of_range_approver_id_is_a_validation_error(client):
    assert client.post("/transfers/1/approve", json={"approver_id": 2**63, "pin": "1234"}).status_code == 422


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity", "1e400"])
def test_non_finite_json_numbers_are_rejected_cleanly(client, literal):
    acct = ready_account(client, "nan@example.com")
    raw = '{"amount": ' + literal + ', "pin": "1234"}'
    resp = client.post(f"/accounts/{acct['id']}/deposit", content=raw, headers={"Content-Type": "application/json"})
    assert resp.status_code == 422
    assert resp.json()["detail"]


def test_non_ascii_admin_token_is_rejected_not_500(client):
    resp = client.get("/audit", headers={"X-Admin-Token": "tökén".encode("latin-1")})
    assert resp.status_code == 401
