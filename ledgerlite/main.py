"""LedgerLite — a small payments API used as SoloTrace's audit target.

Authentication model (deliberately simple for a demo):
* money movement and account reads require the account PIN
  (JSON field ``pin`` or header ``X-PIN``);
* compliance-officer endpoints (KYC verification, audit log) require the
  ``X-Admin-Token`` header matching the ``LEDGERLITE_ADMIN_TOKEN`` env variable.
"""
import secrets
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Path
from sqlalchemy.orm import Session

import ledgerlite.db as db
import ledgerlite.services as svc
from ledgerlite.schemas import (
    AccountCreate,
    AccountResponse,
    ApproveRequest,
    AuditEntryResponse,
    DepositRequest,
    StatementResponse,
    TransferCreate,
    TransferResponse,
    WithdrawRequest,
)

MAX_ID = 2**63 - 1
AccountId = Annotated[int, Path(ge=1, le=MAX_ID)]
TransferId = Annotated[int, Path(ge=1, le=MAX_ID)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.Base.metadata.create_all(bind=db.engine)
    yield


app = FastAPI(
    title="LedgerLite",
    version="2.0.0",
    description="Sample payments API implementing the LedgerLite requirements spec v2.0.",
    lifespan=lifespan,
)


def require_admin(x_admin_token: Annotated[str | None, Header()] = None) -> None:
    expected = svc.admin_token()
    if expected is None:
        raise HTTPException(status_code=503, detail="Admin endpoints are disabled: set LEDGERLITE_ADMIN_TOKEN")
    if x_admin_token is None or not secrets.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=401, detail="Invalid admin token")


PinHeader = Annotated[str, Header(alias="X-PIN")]


@app.get("/")
def root():
    return {"service": "LedgerLite", "version": app.version, "docs": "/docs"}


# ── accounts ──────────────────────────────────────────────────────────────────

@app.post("/accounts", response_model=AccountResponse, status_code=201)
def create_account(body: AccountCreate, session: Session = Depends(db.get_db)):
    return svc.create_account(session, email=body.email, country_code=body.country_code, pin=body.pin)


@app.post("/accounts/{account_id}/verify-kyc", response_model=AccountResponse, dependencies=[Depends(require_admin)])
def verify_kyc(account_id: AccountId, session: Session = Depends(db.get_db)):
    return svc.verify_kyc(session, account_id)


@app.get("/accounts/{account_id}", response_model=AccountResponse)
def get_account(account_id: AccountId, pin: PinHeader, session: Session = Depends(db.get_db)):
    return svc.read_account(session, account_id, pin)


@app.get("/accounts/{account_id}/statement", response_model=StatementResponse)
def get_statement(account_id: AccountId, pin: PinHeader, session: Session = Depends(db.get_db)):
    account, transactions = svc.statement(session, account_id, pin)
    return StatementResponse(account=account, transactions=transactions)


# ── money movement ────────────────────────────────────────────────────────────

@app.post("/accounts/{account_id}/deposit", response_model=AccountResponse)
def deposit(account_id: AccountId, body: DepositRequest, session: Session = Depends(db.get_db)):
    return svc.deposit(session, account_id, amount=body.amount, pin=body.pin)


@app.post("/accounts/{account_id}/withdraw", response_model=AccountResponse)
def withdraw(account_id: AccountId, body: WithdrawRequest, session: Session = Depends(db.get_db)):
    return svc.withdraw(session, account_id, amount=body.amount, pin=body.pin)


# ── transfers ─────────────────────────────────────────────────────────────────

@app.post("/transfers", response_model=TransferResponse, status_code=201)
def create_transfer(body: TransferCreate, session: Session = Depends(db.get_db)):
    return svc.create_transfer(
        session,
        sender_id=body.sender_id,
        recipient_id=body.recipient_id,
        amount=body.amount,
        pin=body.pin,
    )


@app.post("/transfers/{transfer_id}/approve", response_model=TransferResponse)
def approve_transfer(transfer_id: TransferId, body: ApproveRequest, session: Session = Depends(db.get_db)):
    return svc.approve_transfer(session, transfer_id, approver_id=body.approver_id, pin=body.pin)


# ── audit (read-only by design: no update or delete route exists — REQ-06, REQ-12) ──

@app.get("/audit", response_model=list[AuditEntryResponse], dependencies=[Depends(require_admin)])
def get_audit(session: Session = Depends(db.get_db)):
    return svc.list_audit(session)
