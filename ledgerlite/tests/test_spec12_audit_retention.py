"""
REQ-12 — Audit log retention — no deletion.

AC1: no DELETE endpoint exists for audit entries.
AC2: attempting DELETE /audit returns 405 (Method Not Allowed).
"""
import pytest
from fastapi.testclient import TestClient


def test_delete_audit_returns_405(client: TestClient):
    """DELETE /audit must be rejected — no such operation is defined."""
    resp = client.delete("/audit")
    assert resp.status_code == 405, resp.json()


def test_delete_audit_entry_returns_405(client: TestClient):
    """DELETE /audit/1 must also be rejected."""
    resp = client.delete("/audit/1")
    assert resp.status_code in (404, 405), (
        f"Expected 404 or 405 for undefined route, got {resp.status_code}"
    )
