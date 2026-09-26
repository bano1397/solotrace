"""
REQ-12 — Audit log entries must never be deleted through the API (7-year retention).

AC: no delete endpoint exists for audit entries; a DELETE request returns 405 or 404.
"""
from fastapi.routing import APIRoute

from ledgerlite.main import app
from ledgerlite.tests.conftest import ADMIN, audit_log, ready_account


def test_delete_audit_collection_returns_405(client):
    ready_account(client, "keep@example.com", "10.00")
    assert client.delete("/audit", headers=ADMIN).status_code == 405
    assert len(audit_log(client)) == 1


def test_delete_existing_audit_entry_is_refused_and_entry_survives(client):
    ready_account(client, "keep@example.com", "10.00")
    entry = audit_log(client)[0]
    resp = client.delete(f"/audit/{entry['id']}", headers=ADMIN)
    assert resp.status_code in (404, 405)
    assert audit_log(client) == [entry]


def test_no_delete_route_exists_for_audit_entries():
    deletable = [
        r.path for r in app.routes
        if "DELETE" in getattr(r, "methods", set()) and "audit" in getattr(r, "path", "")
    ]
    assert deletable == []


def test_route_inventory_is_exactly_the_reviewed_set():
    """REQ-06 and REQ-12: any new route (a hidden edit or purge endpoint) must be reviewed first."""
    routes = {(r.path, m) for r in app.routes if isinstance(r, APIRoute) for m in r.methods}
    assert routes == {
        ("/", "GET"), ("/accounts", "POST"), ("/accounts/{account_id}/verify-kyc", "POST"),
        ("/accounts/{account_id}/grant-approver", "POST"), ("/accounts/{account_id}", "GET"),
        ("/accounts/{account_id}/statement", "GET"), ("/accounts/{account_id}/deposit", "POST"),
        ("/accounts/{account_id}/withdraw", "POST"), ("/transfers", "POST"),
        ("/transfers/{transfer_id}/approve", "POST"), ("/audit", "GET"),
    }


def test_deleting_an_account_cannot_remove_its_audit_trail(client):
    acct = ready_account(client, "gone@example.com", "10.00")
    before = audit_log(client)
    assert client.delete(f"/accounts/{acct['id']}", headers=ADMIN).status_code in (404, 405)
    assert audit_log(client) == before


def test_no_purge_action_removes_audit_entries(client):
    ready_account(client, "purge@example.com", "10.00")
    before = audit_log(client)
    for path in ("/admin/audit/purge?older_than_days=0", "/audit/purge"):
        assert client.post(path, headers=ADMIN).status_code in (404, 405)
    assert audit_log(client) == before
