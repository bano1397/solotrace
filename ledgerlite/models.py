import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ledgerlite.db import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    account_number: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    kyc_status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    pin_hash: Mapped[str] = mapped_column(String, nullable=False)
    failed_pin_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

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
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="completed")
    approver_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("accounts.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.datetime.utcnow
    )

    sender: Mapped["Account"] = relationship("Account", foreign_keys=[sender_id], back_populates="sent_transfers")
    recipient: Mapped["Account"] = relationship("Account", foreign_keys=[recipient_id], back_populates="received_transfers")


class AuditEntry(Base):
    __tablename__ = "audit_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    actor_id: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id"), nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    account_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("accounts.id"), nullable=True)
    related_account_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("accounts.id"), nullable=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.datetime.utcnow
    )
