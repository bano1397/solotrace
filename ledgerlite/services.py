"""
Business logic for LedgerLite.

All money arithmetic uses Python Decimal.  Services raise fastapi.HTTPException
so routes stay thin.
"""
import datetime
from datetime import timezone
import random
import string
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ledgerlite.models import Account, AuditEntry, Transfer
from ledgerlite.security import hash_pin, verify_pin

_MAX_DEPOSIT = Decimal("50000.00")
_LARGE_TRANSFER_THRESHOLD = Decimal("10000.00")
_MAX_FAILED_PINS = 5


# ── helpers ───────────────────────────────────────────────────────────────────

def _random_account_number() -> str:
    return "".join(random.choices(string.digits, k=10))


def _unique_account_number(db: Session) -> str:
    for _ in range(20):
        number = _random_account_number()
        if not db.query(Account).filter(Account.account_number == number).first():
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
) -> AuditEntry:
    entry = AuditEntry(
        actor_id=actor_id,
        action=action,
        amount=amount,
        account_id=account_id,
        related_account_id=related_account_id,
        timestamp=datetime.datetime.now(timezone.utc),
    )
    db.add(entry)
    return entry


def _get_account_or_404(db: Session, account_id: int) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


def _check_pin(account: Account, pin: str) -> None:
    """Verify PIN; update failure counter / locked flag; raise on failure."""
    if account.locked:
        raise HTTPException(status_code=423, detail="Account is locked due to too many failed PIN attempts")

    if not verify_pin(pin, account.pin_hash):
        account.failed_pin_attempts += 1
        if account.failed_pin_attempts >= _MAX_FAILED_PINS:
            account.locked = True
            raise HTTPException(status_code=423, detail="Account locked after too many failed PIN attempts")
        raise HTTPException(
            status_code=403,
            detail=f"Invalid PIN ({_MAX_FAILED_PINS - account.failed_pin_attempts} attempts remaining)",
        )

    account.failed_pin_attempts = 0


def _require_kyc(account: Account) -> None:
    if account.kyc_status != "verified":
        raise HTTPException(status_code=403, detail="Account KYC is not verified")


def _to_decimal(value) -> Decimal:
    try:
        return Decimal(str(value))
    except InvalidOperation:
        raise HTTPException(status_code=400, detail="Invalid amount")


# ── account operations ────────────────────────────────────────────────────────

def create_account(db: Session, *, email: str, country_code: str, pin: str) -> Account:
    if db.query(Account).filter(Account.email == email).first():
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
    db.commit()
    db.refresh(account)
    return account


def verify_kyc(db: Session, account_id: int) -> Account:
    account = _get_account_or_404(db, account_id)
    account.kyc_status = "verified"
    db.commit()
    db.refresh(account)
    return account


def deposit(db: Session, account_id: int, *, amount: Decimal, pin: str) -> Account:
    amount = _to_decimal(amount)
    account = _get_account_or_404(db, account_id)

    _check_pin(account, pin)
    _require_kyc(account)

    if amount <= Decimal("0"):
        raise HTTPException(status_code=400, detail="Deposit amount must be greater than 0")
    if amount > _MAX_DEPOSIT:
        raise HTTPException(status_code=400, detail=f"Deposit amount must not exceed {_MAX_DEPOSIT}")

    account.balance += amount
    _write_audit(db, actor_id=account_id, action="deposit", amount=amount, account_id=account_id)
    db.commit()
    db.refresh(account)
    return account


def withdraw(db: Session, account_id: int, *, amount: Decimal, pin: str) -> Account:
    amount = _to_decimal(amount)
    account = _get_account_or_404(db, account_id)

    _check_pin(account, pin)
    _require_kyc(account)

    if amount <= Decimal("0"):
        raise HTTPException(status_code=400, detail="Withdrawal amount must be greater than 0")
    if account.balance - amount < Decimal("0"):
        raise HTTPException(status_code=400, detail="Insufficient funds")

    account.balance -= amount
    _write_audit(db, actor_id=account_id, action="withdrawal", amount=amount, account_id=account_id)
    db.commit()
    db.refresh(account)
    return account


# ── transfer operations ───────────────────────────────────────────────────────

def create_transfer(
    db: Session, *, sender_id: int, recipient_id: int, amount: Decimal, pin: str
) -> Transfer:
    amount = _to_decimal(amount)
    sender = _get_account_or_404(db, sender_id)
    recipient = _get_account_or_404(db, recipient_id)

    _check_pin(sender, pin)
    _require_kyc(sender)
    _require_kyc(recipient)

    if amount <= Decimal("0"):
        raise HTTPException(status_code=400, detail="Transfer amount must be greater than 0")
    if sender.balance - amount < Decimal("0"):
        raise HTTPException(status_code=400, detail="Insufficient funds")

    large = amount >= _LARGE_TRANSFER_THRESHOLD
    status = "pending_approval" if large else "completed"

    try:
        sender.balance -= amount
        if not large:
            recipient.balance += amount

        transfer = Transfer(
            sender_id=sender_id,
            recipient_id=recipient_id,
            amount=amount,
            status=status,
        )
        db.add(transfer)
        db.flush()  # get transfer.id before audit write

        _write_audit(
            db,
            actor_id=sender_id,
            action="transfer_initiated",
            amount=amount,
            account_id=sender_id,
            related_account_id=recipient_id,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(transfer)
    return transfer


def approve_transfer(db: Session, transfer_id: int, *, approver_id: int) -> Transfer:
    transfer = db.get(Transfer, transfer_id)
    if transfer is None:
        raise HTTPException(status_code=404, detail="Transfer not found")
    if transfer.status != "pending_approval":
        raise HTTPException(status_code=400, detail="Transfer is not pending approval")
    if transfer.sender_id == approver_id:
        raise HTTPException(status_code=403, detail="Initiator cannot approve their own transfer")

    approver = _get_account_or_404(db, approver_id)
    _ = approver  # existence check only

    try:
        recipient = _get_account_or_404(db, transfer.recipient_id)
        recipient.balance += transfer.amount
        transfer.status = "completed"
        transfer.approver_id = approver_id

        _write_audit(
            db,
            actor_id=approver_id,
            action="transfer_approved",
            amount=transfer.amount,
            account_id=transfer.sender_id,
            related_account_id=transfer.recipient_id,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(transfer)
    return transfer
