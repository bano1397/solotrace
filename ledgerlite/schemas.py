import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, EmailStr, field_serializer, field_validator


# ── helpers ──────────────────────────────────────────────────────────────────

def _fmt(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return f"{value:.2f}"


# ── request bodies ────────────────────────────────────────────────────────────

class AccountCreate(BaseModel):
    email: EmailStr
    country_code: str
    pin: str

    @field_validator("country_code")
    @classmethod
    def validate_country(cls, v: str) -> str:
        if len(v) != 2 or not v.isalpha():
            raise ValueError("country_code must be a 2-letter ISO code")
        return v.upper()


class DepositRequest(BaseModel):
    amount: Decimal
    pin: str


class WithdrawRequest(BaseModel):
    amount: Decimal
    pin: str


class TransferCreate(BaseModel):
    sender_id: int
    recipient_id: int
    amount: Decimal
    pin: str


class ApproveRequest(BaseModel):
    approver_id: int


# ── response models ───────────────────────────────────────────────────────────

class AccountResponse(BaseModel):
    id: int
    email: str
    account_number: str
    country_code: str
    balance: Decimal
    kyc_status: str
    failed_pin_attempts: int
    locked: bool

    @field_serializer("balance")
    def serialize_balance(self, v: Decimal) -> str:
        return f"{v:.2f}"

    model_config = {"from_attributes": True}


class TransferResponse(BaseModel):
    id: int
    sender_id: int
    recipient_id: int
    amount: Decimal
    status: str
    approver_id: Optional[int]
    created_at: datetime.datetime

    @field_serializer("amount")
    def serialize_amount(self, v: Decimal) -> str:
        return f"{v:.2f}"

    model_config = {"from_attributes": True}


class AuditEntryResponse(BaseModel):
    id: int
    actor_id: int
    action: str
    amount: Optional[Decimal]
    account_id: Optional[int]
    related_account_id: Optional[int]
    timestamp: datetime.datetime

    @field_serializer("amount")
    def serialize_amount(self, v: Optional[Decimal]) -> Optional[str]:
        return _fmt(v)

    model_config = {"from_attributes": True}


class StatementAccountResponse(AccountResponse):
    """AccountResponse variant used in statements: account_number is masked."""

    @field_serializer("account_number")
    def serialize_account_number(self, v: str) -> str:
        return "******" + v[-4:]


class StatementResponse(BaseModel):
    account: StatementAccountResponse
    transactions: list[TransferResponse]
