"""
REQ-09 (new in v2.0) — Total outgoing transfers per account must not exceed 20,000.00
per UTC calendar day.

AC: a transfer that would take the day's total above 20,000.00 is rejected.
"""
import datetime

import pytest

from ledgerlite import services as svc
from ledgerlite.tests.conftest import ready_account, run_concurrently, transfer

UTC = datetime.timezone.utc


@pytest.fixture()
def pair(client):
    sender = ready_account(client, "cap_s@example.com", "30000.00")
    extra = ready_account(client, "cap_extra@example.com", "30000.00")
    recipient = ready_account(client, "cap_r@example.com")
    return sender, recipient, extra


def test_exactly_20000_accepted(client, pair):
    sender, recipient, _ = pair
    assert transfer(client, sender["id"], recipient["id"], "10000.00").status_code == 201
    assert transfer(client, sender["id"], recipient["id"], "10000.00").status_code == 201


def test_one_cent_over_the_cap_rejected(client, pair):
    sender, recipient, _ = pair
    assert transfer(client, sender["id"], recipient["id"], "10000.00").status_code == 201
    assert transfer(client, sender["id"], recipient["id"], "10000.00").status_code == 201
    resp = transfer(client, sender["id"], recipient["id"], "0.01")
    assert resp.status_code == 400
    assert "daily" in resp.json()["detail"].lower()


def test_third_of_three_7000_transfers_blocked(client, pair):
    sender, recipient, _ = pair
    assert transfer(client, sender["id"], recipient["id"], "7000.00").status_code == 201
    assert transfer(client, sender["id"], recipient["id"], "7000.00").status_code == 201
    assert transfer(client, sender["id"], recipient["id"], "7000.00").status_code == 400


def test_cap_is_per_sender(client, pair):
    sender, recipient, extra = pair
    assert transfer(client, sender["id"], recipient["id"], "20000.00").status_code == 201
    assert transfer(client, extra["id"], recipient["id"], "20000.00").status_code == 201


def test_rejected_transfers_do_not_count(client, pair):
    sender, recipient, _ = pair
    assert transfer(client, sender["id"], recipient["id"], "40000.00").status_code == 400  # insufficient
    assert transfer(client, sender["id"], recipient["id"], "20000.00").status_code == 201


def test_yesterdays_transfers_do_not_count(client, pair, monkeypatch):
    sender, recipient, _ = pair
    now = datetime.datetime.now(UTC)
    yesterday_late = datetime.datetime(now.year, now.month, now.day, tzinfo=UTC) - datetime.timedelta(minutes=1)
    monkeypatch.setattr(svc, "_now", lambda: yesterday_late)
    assert transfer(client, sender["id"], recipient["id"], "15000.00").status_code == 201
    monkeypatch.setattr(svc, "_now", lambda: now)
    assert transfer(client, sender["id"], recipient["id"], "15000.00").status_code == 201


def test_concurrent_transfers_cannot_exceed_the_cap(client, pair):
    sender, recipient, _ = pair
    results = run_concurrently([lambda: transfer(client, sender["id"], recipient["id"], "4000.00")] * 10)
    codes = [r.status_code for r in results]
    assert codes.count(201) == 5, codes  # 5 x 4,000 = 20,000
    assert codes.count(400) == 5, codes


DAY = datetime.datetime(2026, 9, 26, tzinfo=UTC)


def test_transfer_just_after_midnight_counts_for_the_whole_day(client, pair, monkeypatch):
    sender, recipient, _ = pair
    monkeypatch.setattr(svc, "_now", lambda: DAY + datetime.timedelta(microseconds=1))
    assert transfer(client, sender["id"], recipient["id"], "15000.00").status_code == 201
    monkeypatch.setattr(svc, "_now", lambda: DAY + datetime.timedelta(hours=12, microseconds=500000))
    assert transfer(client, sender["id"], recipient["id"], "15000.00").status_code == 400


def test_the_day_is_the_utc_day_not_the_server_local_day(client, pair, monkeypatch, karachi_tz):
    sender, recipient, _ = pair
    monkeypatch.setattr(svc, "_now", lambda: DAY + datetime.timedelta(hours=21))
    assert transfer(client, sender["id"], recipient["id"], "15000.00").status_code == 201
    monkeypatch.setattr(svc, "_now", lambda: DAY + datetime.timedelta(hours=23))
    assert transfer(client, sender["id"], recipient["id"], "15000.00").status_code == 400
