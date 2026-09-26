"""
REQ-07 — An account is locked after 5 consecutive failed PIN attempts.
A locked account cannot move money.

AC1: the 5th wrong PIN locks the account.
AC2: a correct PIN before that resets the counter.

Every request below runs in its own database session (see conftest), so these
tests prove the counter and the lock are really persisted.
"""
import pytest

from ledgerlite.models import Account
from ledgerlite.tests.conftest import db_read, deposit, get_account, ready_account, transfer, withdraw


def _stored(account_id: int) -> tuple[int, bool]:
    """(failed_pin_attempts, locked) exactly as persisted in the database."""
    def query(session):
        account = session.get(Account, account_id)
        return account.failed_pin_attempts, account.locked
    return db_read(query)


def test_failed_attempts_are_persisted_between_requests(client):
    acct = ready_account(client, "count@example.com", "100.00")
    for _ in range(3):
        assert deposit(client, acct["id"], "1.00", pin="0000").status_code == 403
    assert _stored(acct["id"]) == (3, False)


def test_fifth_wrong_pin_locks_account(client):
    acct = ready_account(client, "lockout@example.com", "100.00")
    codes = [deposit(client, acct["id"], "1.00", pin="0000").status_code for _ in range(5)]
    assert codes == [403, 403, 403, 403, 423]

    assert _stored(acct["id"]) == (5, True)

    # The correct PIN no longer works: the account is locked.
    assert deposit(client, acct["id"], "1.00").status_code == 423


def test_locked_account_cannot_move_money_anywhere(client):
    acct = ready_account(client, "frozen@example.com", "100.00")
    other = ready_account(client, "other@example.com")
    for _ in range(5):
        deposit(client, acct["id"], "1.00", pin="0000")
    assert withdraw(client, acct["id"], "1.00").status_code == 423
    assert transfer(client, acct["id"], other["id"], "1.00").status_code == 423
    assert get_account(client, acct["id"]).status_code == 423


def test_correct_pin_resets_counter(client):
    acct = ready_account(client, "reset@example.com", "100.00")
    for _ in range(4):
        assert deposit(client, acct["id"], "1.00", pin="0000").status_code == 403
    assert deposit(client, acct["id"], "1.00").status_code == 200

    assert _stored(acct["id"]) == (0, False)
    # After the reset it again takes five fresh failures to lock.
    codes = [deposit(client, acct["id"], "1.00", pin="0000").status_code for _ in range(4)]
    assert codes == [403, 403, 403, 403]


def test_brute_force_is_stopped(client):
    acct = ready_account(client, "target@example.com", "100.00")
    guesses = [f"{n:04d}" for n in range(20) if f"{n:04d}" != "1234"]
    codes = [deposit(client, acct["id"], "1.00", pin=g).status_code for g in guesses]
    assert codes[:5] == [403, 403, 403, 403, 423]
    assert set(codes[5:]) == {423}



def _pin_call(client, kind, acct, other, pin):
    return {
        "withdraw": lambda: withdraw(client, acct["id"], "1.00", pin=pin),
        "transfer": lambda: transfer(client, acct["id"], other["id"], "1.00", pin=pin),
        "read": lambda: get_account(client, acct["id"], pin=pin),
        "statement": lambda: client.get(f"/accounts/{acct['id']}/statement", headers={"X-PIN": pin}),
    }[kind]()


@pytest.mark.parametrize("kind", ["withdraw", "transfer", "read", "statement"])
def test_fifth_wrong_pin_locks_on_every_endpoint(client, kind):
    acct = ready_account(client, f"lock_{kind}@example.com", "100.00")
    other = ready_account(client, f"other_{kind}@example.com")
    codes = [_pin_call(client, kind, acct, other, "0000").status_code for _ in range(5)]
    assert codes == [403, 403, 403, 403, 423]
    assert _stored(acct["id"]) == (5, True)


@pytest.mark.parametrize("kind", ["withdraw", "transfer", "read", "statement"])
def test_correct_pin_on_every_endpoint_resets_the_counter(client, kind):
    acct = ready_account(client, f"reset_{kind}@example.com", "100.00")
    other = ready_account(client, f"peer_{kind}@example.com")
    for _ in range(4):
        deposit(client, acct["id"], "1.00", pin="0000")
    assert _pin_call(client, kind, acct, other, "1234").status_code in (200, 201)
    assert _stored(acct["id"]) == (0, False)
