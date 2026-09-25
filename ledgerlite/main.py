from contextlib import asynccontextmanager
from decimal import Decimal

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

import ledgerlite.services as svc
from ledgerlite.db import Base, engine, get_db
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
from ledgerlite.models import Transfer


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="LedgerLite", version="1.0.0", lifespan=lifespan)


# ── accounts ──────────────────────────────────────────────────────────────────

@app.post("/accounts", response_model=AccountResponse, status_code=201)
def create_account(body: AccountCreate, db: Session = Depends(get_db)):
    return svc.create_account(db, email=body.email, country_code=body.country_code, pin=body.pin)


@app.post("/accounts/{account_id}/verify-kyc", response_model=AccountResponse)
def verify_kyc(account_id: int, db: Session = Depends(get_db)):
    return svc.verify_kyc(db, account_id)


@app.get("/accounts/{account_id}", response_model=AccountResponse)
def get_account(account_id: int, db: Session = Depends(get_db)):
    return svc._get_account_or_404(db, account_id)


@app.get("/accounts/{account_id}/statement", response_model=StatementResponse)
def get_statement(account_id: int, db: Session = Depends(get_db)):
    account = svc._get_account_or_404(db, account_id)
    transactions = (
        db.query(Transfer)
        .filter(
            (Transfer.sender_id == account_id) | (Transfer.recipient_id == account_id)
        )
        .order_by(Transfer.created_at.desc())
        .all()
    )
    return StatementResponse(account=account, transactions=transactions)


# ── money movement ────────────────────────────────────────────────────────────

@app.post("/accounts/{account_id}/deposit", response_model=AccountResponse)
def deposit(account_id: int, body: DepositRequest, db: Session = Depends(get_db)):
    return svc.deposit(db, account_id, amount=body.amount, pin=body.pin)


@app.post("/accounts/{account_id}/withdraw", response_model=AccountResponse)
def withdraw(account_id: int, body: WithdrawRequest, db: Session = Depends(get_db)):
    return svc.withdraw(db, account_id, amount=body.amount, pin=body.pin)


# ── transfers ─────────────────────────────────────────────────────────────────

@app.post("/transfers", response_model=TransferResponse, status_code=201)
def create_transfer(body: TransferCreate, db: Session = Depends(get_db)):
    return svc.create_transfer(
        db,
        sender_id=body.sender_id,
        recipient_id=body.recipient_id,
        amount=body.amount,
        pin=body.pin,
    )


@app.post("/transfers/{transfer_id}/approve", response_model=TransferResponse)
def approve_transfer(transfer_id: int, body: ApproveRequest, db: Session = Depends(get_db)):
    return svc.approve_transfer(db, transfer_id, approver_id=body.approver_id)


# ── audit ─────────────────────────────────────────────────────────────────────

@app.get("/audit", response_model=list[AuditEntryResponse])
def get_audit(db: Session = Depends(get_db)):
    from ledgerlite.models import AuditEntry
    return db.query(AuditEntry).order_by(AuditEntry.timestamp.asc()).all()
