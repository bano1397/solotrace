"""
Business logic for LedgerLite.

Rules of the house
------------------
* Money is ``Decimal`` in Python and integer cents in the database (see models.Money).
* Every service call is one database transaction.  On SQLite the transaction is
  ``BEGIN IMMEDIATE`` (see db.py), and balance changes additionally use
  conditional UPDATEs, so concurrent requests can never overdraw an account,
  approve a transfer twice or exceed the daily cap.
* Failed PIN attempts are committed *before* the error is raised, so the lockout
  counter survives the request (REQ-07).
* Services raise fastapi.HTTPException so routes stay thin.
"""
import datetime
import os
import secrets
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ledgerlite.models import Account, AuditEntry, Transfer
from ledgerlite.security import hash_pin, verify_pin

MAX_DEPOSIT = Decimal("50000.00")                 # REQ-02
LARGE_TRANSFER_THRESHOLD = Decimal("5000.00")     # REQ-05 (v2.0; was 10,000.00 in v1.0)
MAX_FAILED_PINS = 5                               # REQ-07
DAILY_TRANSFER_CAP = Decimal("20000.00")          # REQ-09
SANCTIONED_COUNTRIES = frozenset({"KP", "IR", "SY", "CU"})  # REQ-10

_COUNTED_STATUSES = ("completed", "pending_approval")


def _now() -> datetime.datetime:
    """Current UTC time (a single seam so tests can move the clock)."""
    return datetime.datetime.now(datetime.timezone.utc)


# ── helpers ───────────────────────────────────────────────────────────────────

def _unique_account_number(db: Session) -> str:
    for _ in range(20):
        number = f"{secrets.randbelow(10**10):010d}"
        if db.scalar(select(Account.id).where(Account.account_number == number)) is None:
            return number
    raise RuntimeError("Could not generate a unique account number")  # pragma: no cover


def _write_audit(
    db: Session,
    *,
    actor_id: int,
    action: str,
    amount: Decimal | None = None,
    account_id: int | None = None,
    related_account_id: int | None = None,
    detail: str | None = None,
) -> AuditEntry:
    """Append one audit entry (REQ-06). Entries are never updated or deleted."""
    entry = AuditEntry(
        actor_id=actor_id,
        action=action,
        amount=amount,
        account_id=account_id,
        related_account_id=related_account_id,
        detail=detail,
        timestamp=_now(),
    )
    db.add(entry)
    return entry


def get_account_or_404(db: Session, account_id: int) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


def _check_pin(db: Session, account: Account, pin: str) -> None:
    """Verify a PIN. Failed attempts are committed before raising (REQ-07)."""
    if account.locked:
        raise HTTPException(status_code=423, detail="Account is locked due to too many failed PIN attempts")

    if verify_pin(pin, account.pin_hash):
        if account.failed_pin_attempts:
            account.failed_pin_attempts = 0  # a correct PIN resets the counter
            db.commit()
        return

    account.failed_pin_attempts += 1
    locked_now = account.failed_pin_attempts >= MAX_FAILED_PINS
    if locked_now:
        account.locked = True
    remaining = MAX_FAILED_PINS - account.failed_pin_attempts
    db.commit()  # persist the counter / lock even though the request fails
    if locked_now:
        raise HTTPException(status_code=423, detail="Account locked after too many failed PIN attempts")
    raise HTTPException(status_code=403, detail=f"Invalid PIN ({remaining} attempts remaining)")


def _require_kyc(account: Account, role: str = "Account") -> None:
    if account.kyc_status != "verified":
        raise HTTPException(status_code=403, detail=f"{role} KYC is not verified")


def _require_positive(amount: Decimal, what: str) -> None:
    if amount <= Decimal("0"):
        raise HTTPException(status_code=400, detail=f"{what} amount must be greater than 0")


def _debit(db: Session, account_id: int, amount: Decimal) -> bool:
    """Atomically subtract *amount* unless that would make the balance negative."""
    result = db.execute(
        update(Account)
        .where(Account.id == account_id, Account.balance >= amount)
        .values(balance=Account.balance - amount)
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1


def _credit(db: Session, account_id: int, amount: Decimal) -> None:
    db.execute(
        update(Account)
        .where(Account.id == account_id)
        .values(balance=Account.balance + amount)
        .execution_options(synchronize_session=False)
    )


def _utc_day_start(moment: datetime.datetime) -> datetime.datetime:
    day = moment.astimezone(datetime.timezone.utc).date()
    return datetime.datetime(day.year, day.month, day.day, tzinfo=datetime.timezone.utc)


def outgoing_total_today(db: Session, sender_id: int, now: datetime.datetime) -> Decimal:
    """Sum of today's (UTC) completed + pending outgoing transfers (REQ-09)."""
    total = db.scalar(
        select(func.coalesce(func.sum(Transfer.amount), Decimal("0.00"))).where(
            Transfer.sender_id == sender_id,
            Transfer.status.in_(_COUNTED_STATUSES),
            Transfer.created_at >= _utc_day_start(now),
        )
    )
    return Decimal(total or 0)


# ── account operations ────────────────────────────────────────────────────────

def create_account(db: Session, *, email: str, country_code: str, pin: str) -> Account:
    email = email.strip().lower()
    if db.scalar(select(Account.id).where(Account.email == email)) is not None:
        raise HTTPException(status_code=409, detail="Email already registered")

    account = Account(
        email=email,
        account_number=_unique_account_number(db),
        country_code=country_code.upper(),
        balance=Decimal("0.00"),
        kyc_status="pending",
        pin_hash=hash_pin(pin),
        failed_pin_attempts=0,
        locked=False,
    )
    db.add(account)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email already registered")
    db.refresh(account)
    return account


def verify_kyc(db: Session, account_id: int) -> Account:
    account = get_account_or_404(db, account_id)
    account.kyc_status = "verified"
    db.commit()
    db.refresh(account)
    return account


def read_account(db: Session, account_id: int, pin: str) -> Account:
    """Account details are only shown to someone who knows the account PIN."""
    account = get_account_or_404(db, account_id)
    _check_pin(db, account, pin)
    db.commit()
    db.refresh(account)
    return account


def statement(db: Session, account_id: int, pin: str) -> tuple[Account, list[Transfer]]:
    account = read_account(db, account_id, pin)
    transactions = db.scalars(
        select(Transfer)
        .where((Transfer.sender_id == account_id) | (Transfer.recipient_id == account_id))
        .order_by(Transfer.created_at.desc(), Transfer.id.desc())
    ).all()
    return account, list(transactions)


def list_audit(db: Session) -> list[AuditEntry]:
    return list(db.scalars(select(AuditEntry).order_by(AuditEntry.id.asc())).all())


# ── money movement ────────────────────────────────────────────────────────────

def deposit(db: Session, account_id: int, *, amount: Decimal, pin: str) -> Account:
    account = get_account_or_404(db, account_id)
    _check_pin(db, account, pin)
    _require_kyc(account)

    _require_positive(amount, "Deposit")
    if amount > MAX_DEPOSIT:
        raise HTTPException(status_code=400, detail=f"Deposit amount must not exceed {MAX_DEPOSIT}")

    _credit(db, account_id, amount)
    _write_audit(db, actor_id=account_id, action="deposit", amount=amount, account_id=account_id)
    db.commit()
    db.refresh(account)
    return account


def withdraw(db: Session, account_id: int, *, amount: Decimal, pin: str) -> Account:
    account = get_account_or_404(db, account_id)
    _check_pin(db, account, pin)
    _require_kyc(account)
    _require_positive(amount, "Withdrawal")

    if not _debit(db, account_id, amount):  # REQ-03: never below zero, even under concurrency
        db.rollback()
        raise HTTPException(status_code=400, detail="Insufficient funds")

    _write_audit(db, actor_id=account_id, action="withdrawal", amount=amount, account_id=account_id)
    db.commit()
    db.refresh(account)
    return account


def create_transfer(db: Session, *, sender_id: int, recipient_id: int, amount: Decimal, pin: str) -> Transfer:
    _require_positive(amount, "Transfer")
    if sender_id == recipient_id:
        raise HTTPException(status_code=400, detail="Sender and recipient must be different accounts")

    sender = get_account_or_404(db, sender_id)
    recipient = get_account_or_404(db, recipient_id)
    _check_pin(db, sender, pin)

    # REQ-10: sanctions screening happens before any other business check and is always logged.
    blocked = sorted(
        {c for c in (sender.country_code, recipient.country_code) if c in SANCTIONED_COUNTRIES}
    )
    if blocked:
        _write_audit(
            db,
            actor_id=sender_id,
            action="sanctions_blocked",
            amount=amount,
            account_id=sender_id,
            related_account_id=recipient_id,
            detail="sanctioned country: " + ", ".join(blocked),
        )
        db.commit()
        raise HTTPException(status_code=400, detail="sanctions")

    _require_kyc(sender, "Sender")
    _require_kyc(recipient, "Recipient")

    now = _now()
    # REQ-09: daily outgoing cap (completed + pending count; serialised by BEGIN IMMEDIATE).
    if outgoing_total_today(db, sender_id, now) + amount > DAILY_TRANSFER_CAP:
        raise HTTPException(
            status_code=400,
            detail=f"Daily outgoing transfer limit of {DAILY_TRANSFER_CAP} exceeded",
        )

    large = amount >= LARGE_TRANSFER_THRESHOLD  # REQ-05
    status = "pending_approval" if large else "completed"

    try:
        # REQ-04: debit, credit, transfer row and audit entry commit together or not at all.
        if not _debit(db, sender_id, amount):
            db.rollback()
            raise HTTPException(status_code=400, detail="Insufficient funds")
        if not large:
            _credit(db, recipient_id, amount)

        transfer = Transfer(
            sender_id=sender_id,
            recipient_id=recipient_id,
            amount=amount,
            status=status,
            created_at=now,
        )
        db.add(transfer)
        db.flush()
        _write_audit(
            db,
            actor_id=sender_id,
            action="transfer_initiated",
            amount=amount,
            account_id=sender_id,
            related_account_id=recipient_id,
            detail=f"transfer {transfer.id}: {status}",
        )
        db.commit()
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise

    db.refresh(transfer)
    return transfer


def approve_transfer(db: Session, transfer_id: int, *, approver_id: int, pin: str) -> Transfer:
    """Four-eyes approval of a held transfer (REQ-05)."""
    transfer = db.get(Transfer, transfer_id)
    if transfer is None:
        raise HTTPException(status_code=404, detail="Transfer not found")
    if transfer.status != "pending_approval":
        raise HTTPException(status_code=400, detail="Transfer is not pending approval")
    if approver_id == transfer.sender_id:
        raise HTTPException(status_code=403, detail="Initiator cannot approve their own transfer")
    if approver_id == transfer.recipient_id:
        raise HTTPException(status_code=403, detail="Recipient cannot approve a transfer to themselves")

    approver = get_account_or_404(db, approver_id)
    _check_pin(db, approver, pin)
    _require_kyc(approver, "Approver")
    if approver.country_code in SANCTIONED_COUNTRIES:
        raise HTTPException(status_code=403, detail="Approver is not permitted to approve transfers")

    try:
        # Only one approval can ever win, even if two arrive at the same time.
        result = db.execute(
            update(Transfer)
            .where(Transfer.id == transfer_id, Transfer.status == "pending_approval")
            .values(status="completed", approver_id=approver_id)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=400, detail="Transfer is not pending approval")
        _credit(db, transfer.recipient_id, transfer.amount)
        _write_audit(
            db,
            actor_id=approver_id,
            action="transfer_approved",
            amount=transfer.amount,
            account_id=transfer.sender_id,
            related_account_id=transfer.recipient_id,
            detail=f"transfer {transfer_id} approved",
        )
        db.commit()
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise

    db.refresh(transfer)
    return transfer


def admin_token() -> str | None:
    """Token for compliance-officer endpoints (KYC verification, audit log)."""
    token = os.environ.get("LEDGERLITE_ADMIN_TOKEN", "").strip()
    return token or None
