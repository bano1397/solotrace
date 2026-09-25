"""General API hygiene checks (not tied to one requirement)."""
from ledgerlite.tests.conftest import get_account


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
