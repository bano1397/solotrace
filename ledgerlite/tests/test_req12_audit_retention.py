"""
REQ-12 — Audit log entries must never be deleted through the API (7-year retention).

AC: no delete endpoint exists for audit entries; a DELETE request returns 405 or 404.
"""
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
