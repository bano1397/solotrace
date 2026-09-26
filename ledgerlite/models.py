"""Database models for LedgerLite: accounts, transfers and the append-only audit log."""
import datetime
from decimal import ROUND_HALF_EVEN, Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ledgerlite.db import Base

CENT = Decimal("0.01")


class Money(TypeDecorator):
    """Exact money column: stored as an INTEGER number of cents, never as REAL.

    Python code always sees ``Decimal`` values with exactly two decimal places.
    Values with more than two decimal places are refused instead of rounded.
    """

    impl = Integer
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        value = Decimal(value)
        if value != value.quantize(CENT):
            raise ValueError(f"money value {value} has more than 2 decimal places")
        return int((value * 100).to_integral_value(rounding=ROUND_HALF_EVEN))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return (Decimal(int(value)) / 100).quantize(CENT)


def utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    account_number: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    balance: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0.00"))
    kyc_status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    pin_hash: Mapped[str] = mapped_column(String, nullable=False)
    failed_pin_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_approve: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    sent_transfers: Mapped[list["Transfer"]] = relationship(
        "Transfer", foreign_keys="Transfer.sender_id", back_populates="sender"
    )
    received_transfers: Mapped[list["Transfer"]] = relationship(
        "Transfer", foreign_keys="Transfer.recipient_id", back_populates="recipient"
    )


class Transfer(Base):
    __tablename__ = "transfers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sender_id: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id"), nullable=False)
    recipient_id: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="completed")
    approver_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("accounts.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, default=utc_now)

    sender: Mapped["Account"] = relationship("Account", foreign_keys=[sender_id], back_populates="sent_transfers")
    recipient: Mapped["Account"] = relationship("Account", foreign_keys=[recipient_id], back_populates="received_transfers")


class AuditEntry(Base):
    __tablename__ = "audit_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    actor_id: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id"), nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    account_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("accounts.id"), nullable=True)
    related_account_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("accounts.id"), nullable=True)
    detail: Mapped[str | None] = mapped_column(String, nullable=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
