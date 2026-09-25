import datetime
import re
from decimal import Decimal
from typing import Annotated, Optional

from pydantic import AfterValidator, BaseModel, EmailStr, field_serializer, field_validator

CENT = Decimal("0.01")
MAX_AMOUNT = Decimal("9999999999.99")
_PIN_PATTERN = re.compile(r"^[0-9]{4,6}$")

# ISO 3166-1 alpha-2 country codes (plain ASCII only).
ISO_COUNTRY_CODES = frozenset("""
AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ
BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM
DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS
GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN
KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ
MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM
PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV
SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI
VN VU WF WS YE YT ZA ZM ZW
""".split())


# ── helpers ──────────────────────────────────────────────────────────────────

def _validate_amount(value: Decimal) -> Decimal:
    """Money input: finite, at most 2 decimal places, sane magnitude. Never rounded."""
    if not value.is_finite():
        raise ValueError("amount must be a finite number")
    if abs(value) > MAX_AMOUNT:
        raise ValueError(f"amount must not exceed {MAX_AMOUNT}")
    if value != value.quantize(CENT):
        raise ValueError("amount must have at most 2 decimal places")
    return value.quantize(CENT)


Amount = Annotated[Decimal, AfterValidator(_validate_amount)]


def _validate_pin(value: str) -> str:
    if not _PIN_PATTERN.match(value):
        raise ValueError("pin must be 4 to 6 digits")
    return value


Pin = Annotated[str, AfterValidator(_validate_pin)]


def _money_str(value: Decimal | None) -> str | None:
    return None if value is None else f"{value:.2f}"


def _utc_iso(value: datetime.datetime) -> str:
    """Serialise timestamps as ISO-8601 UTC with a trailing Z."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=datetime.timezone.utc)
    return value.astimezone(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def mask_account_number(number: str) -> str:
    """Statements show only the last 4 digits, e.g. ****1234 (REQ-11)."""
    return "****" + number[-4:]


# ── request bodies ────────────────────────────────────────────────────────────

class AccountCreate(BaseModel):
    email: EmailStr
    country_code: str
    pin: Pin

    @field_validator("country_code")
    @classmethod
    def validate_country(cls, v: str) -> str:
        code = v.upper()
        if not (len(code) == 2 and code.isascii() and code in ISO_COUNTRY_CODES):
            raise ValueError("country_code must be an ISO 3166-1 alpha-2 code")
        return code


class DepositRequest(BaseModel):
    amount: Amount
    pin: str


class WithdrawRequest(BaseModel):
    amount: Amount
    pin: str


class TransferCreate(BaseModel):
    sender_id: int
    recipient_id: int
    amount: Amount
    pin: str


class ApproveRequest(BaseModel):
    approver_id: int
    pin: str


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
        return _money_str(v)

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
        return _money_str(v)

    @field_serializer("created_at")
    def serialize_created_at(self, v: datetime.datetime) -> str:
        return _utc_iso(v)

    model_config = {"from_attributes": True}


class AuditEntryResponse(BaseModel):
    id: int
    actor_id: int
    action: str
    amount: Optional[Decimal]
    account_id: Optional[int]
    related_account_id: Optional[int]
    detail: Optional[str]
    timestamp: datetime.datetime

    @field_serializer("amount")
    def serialize_amount(self, v: Optional[Decimal]) -> Optional[str]:
        return _money_str(v)

    @field_serializer("timestamp")
    def serialize_timestamp(self, v: datetime.datetime) -> str:
        return _utc_iso(v)

    model_config = {"from_attributes": True}


class StatementAccountResponse(AccountResponse):
    """AccountResponse variant used in statements: account_number is masked."""

    @field_serializer("account_number")
    def serialize_account_number(self, v: str) -> str:
        return mask_account_number(v)


class StatementResponse(BaseModel):
    account: StatementAccountResponse
    transactions: list[TransferResponse]
