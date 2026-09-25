# SoloTrace Audit Report

**Generated:** 2026-09-25 16:36:38 UTC  
**Before audit:** `out-before`  
**After audit:** `out`  

## Executive Summary

| Metric | Before | After | Δ |
|--------|--------|-------|---|
| Compliance score | 33.3% | 33.3% | +0.0% |
| Covered | 4 | 4 | — |
| Untested | 4 | 4 | — |
| Contradicts | 1 | 1 | — |
| Missing | 3 | 3 | — |
| Total requirements | 12 | 12 | — |

## Traceability Matrix (after)

| ID | Title | Risk | Change | Status | Tests |
|----|-------|------|--------|--------|-------|
| REQ-01 | Unique email and KYC gating | High | none | ✅ covered | test_duplicate_email_rejected, test_deposit_blocked_before_kyc, test_withdraw_blocked_before_kyc, test_transfer_sender_blocked_before_kyc, test_transfer_recipient_blocked_before_kyc |
| REQ-02 | Deposit amount limits | Medium | none | ✅ covered | test_zero_rejected, test_negative_rejected, test_boundary_50000_01_rejected, test_boundary_50000_accepted, test_positive_amount_accepted, test_multiple_deposits_accumulate |
| REQ-03 | Withdrawal floor — no negative balance | High | none | ✅ covered | test_withdrawal_overdraft_rejected, test_balance_never_goes_negative, test_withdrawal_exact_balance_allowed |
| REQ-04 | Atomic transfers | High | none | ✅ covered | test_transfer_rolls_back_on_db_error, test_successful_transfer_debits_sender_credits_recipient |
| REQ-05 | Large-transfer pending approval threshold | High | changed | ❌ contradicts | — |
| REQ-06 | Audit log for every money movement | High | none | ⚠️ untested | — |
| REQ-07 | Account lockout after failed PIN attempts | Medium | none | ⚠️ untested | — |
| REQ-08 | Exact decimal arithmetic | Medium | none | ⚠️ untested | test_multiple_deposits_accumulate, test_boundary_50000_accepted |
| REQ-09 | Daily outgoing transfer cap | High | new | 🔴 missing | — |
| REQ-10 | Sanctions list blocking | High | new | 🔴 missing | — |
| REQ-11 | Masked account numbers in statements | Medium | new | 🔴 missing | — |
| REQ-12 | Audit log retention — no deletion | Medium | none | ⚠️ untested | — |

## Gaps and Suggested Fixes

### REQ-05 — Large-transfer pending approval threshold

**Status:** ❌ contradicts  
**Risk:** High  

**Reason:** The spec (v2.0) requires a pending_approval threshold of 5,000.00, but the implementation uses 10,000.00 — the old v1.0 threshold. Transfers between 5,000.00 and 9,999.99 are therefore completed immediately instead of being held for approval. The self-approval guard is correctly implemented.

**Suggested fix:**

```
1. In ledgerlite/services.py line 19, change the threshold constant from 10000.00 to 5000.00:
   _LARGE_TRANSFER_THRESHOLD = Decimal("5000.00")

2. Add a test asserting that a transfer of exactly 5,000.00 results in pending_approval status, for example:
   def test_transfer_at_threshold_is_pending_approval():
       response = client.post("/transfers", json={"amount": "5000.00", ...})
       assert response.json()["status"] == "pending_approval"

3. Add a complementary test confirming that a transfer of 4,999.99 is completed immediately (boundary below threshold).
```

**Code evidence:**

- `ledgerlite/services.py:20  _LARGE_TRANSFER_THRESHOLD = Decimal("10000.00")`
- `ledgerlite/services.py:182      large = amount >= _LARGE_TRANSFER_THRESHOLD`
- `ledgerlite/services.py:183      status = "pending_approval" if large else "completed"`
- `ledgerlite/services.py:222      if transfer.sender_id == approver_id:`
- `ledgerlite/services.py:223          raise HTTPException(status_code=403, detail="Initiator cannot approve their own transfer")`

### REQ-06 — Audit log for every money movement

**Status:** ⚠️ untested  
**Risk:** High  

**Reason:** Both acceptance criteria are correctly implemented — _write_audit() is called in deposit(), withdraw(), create_transfer(), and approve_transfer(), and no PATCH/PUT endpoint for audit entries exists — but no test in the suite asserts either criterion.

**Suggested fix:**

```
Add tests that (1) call GET /audit after each money-movement operation and assert exactly one new entry with correct actor/action/amount fields, and (2) assert that PATCH /audit and PUT /audit/1 return 404 or 405.
```

**Code evidence:**

- `ledgerlite/services.py:37  def _write_audit(`
- `ledgerlite/services.py:139      _write_audit(db, actor_id=account_id, action="deposit", amount=amount, account_id=account_id)`
- `ledgerlite/services.py:158      _write_audit(db, actor_id=account_id, action="withdrawal", amount=amount, account_id=account_id)`
- `ledgerlite/services.py:198          _write_audit(`
- `ledgerlite/services.py:233          _write_audit(`
- `ledgerlite/main.py:95  @app.get("/audit", response_model=list[AuditEntryResponse])`

### REQ-07 — Account lockout after failed PIN attempts

**Status:** ⚠️ untested  
**Risk:** Medium  

**Reason:** The lockout logic is correctly implemented in _check_pin(): failed_pin_attempts is incremented on each wrong PIN, account.locked is set to True when failed_pin_attempts >= 5 (_MAX_FAILED_PINS), locked accounts raise HTTP 423, and a successful PIN resets the counter to 0. However, no test in the suite exercises the PIN failure counter or lockout mechanism — neither acceptance criterion (5th wrong PIN locks the account; correct PIN resets the counter) is asserted anywhere.

**Suggested fix:**

```
Add tests that: (1) send 5 consecutive wrong PINs and assert the 5th returns HTTP 423 and account.locked is True, (2) send a correct PIN before the 5th failure and assert failed_pin_attempts resets to 0.
```

**Code evidence:**

- `ledgerlite/services.py:21  _MAX_FAILED_PINS = 5`
- `ledgerlite/services.py:68      if account.locked:`
- `ledgerlite/services.py:71      if not verify_pin(pin, account.pin_hash):`
- `ledgerlite/services.py:80      account.failed_pin_attempts = 0`

### REQ-08 — Exact decimal arithmetic

**Status:** ⚠️ untested  
**Risk:** Medium  

**Reason:** The implementation correctly uses exact decimal arithmetic throughout (Decimal(str(value)) conversions, Numeric(12,2) storage, and 2dp string serialisation via field_serializer), so no contradictions exist. Acceptance criterion 2 (2dp string format) is implicitly covered by multiple tests asserting responses such as '100.00', '300.00', and '50000.00'. However, acceptance criterion 1 (0.10 + 0.20 == 0.30 exactly) has no asserting test, leaving the most critical floating-point correctness claim unverified.

**Suggested fix:**

```
Add a test that deposits 0.10, then 0.20, and asserts the balance is exactly '0.30' (not '0.30000000000000004'), confirming Decimal arithmetic is used throughout.
```

**Code evidence:**

- `ledgerlite/models.py:24      balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))`
- `ledgerlite/services.py:11  from decimal import Decimal, InvalidOperation`
- `ledgerlite/services.py:88  def _to_decimal(value) -> Decimal:`
- `ledgerlite/services.py:106          balance=Decimal("0.00"),`
- `ledgerlite/schemas.py:64      @field_serializer("balance")`
- `ledgerlite/schemas.py:80      @field_serializer("amount")`

### REQ-09 — Daily outgoing transfer cap

**Status:** 🔴 missing  
**Risk:** High  

**Reason:** create_transfer() performs no daily outgoing total check. There is no query summing today's outgoing transfers for the sender, no daily cap constant, and no rejection path for exceeding 20,000.00 in a UTC calendar day. No test file covers this criterion.

**Suggested fix:**

```
In create_transfer(), before processing, query the sum of Transfer.amount for transfers where sender_id matches and created_at is on today's UTC date. If the sum plus the new amount would exceed Decimal('20000.00'), raise HTTPException(status_code=400, detail='Daily transfer limit exceeded'). Add a test that sends transfers totalling 20,000.00 then asserts the next transfer is rejected.
```

### REQ-10 — Sanctions list blocking

**Status:** 🔴 missing  
**Risk:** High  

**Reason:** No sanctions list check exists anywhere in the codebase. create_transfer() in ledgerlite/services.py performs KYC, balance, and large-transfer-threshold checks but contains no reference to SANCTIONED_COUNTRIES, KP, IR, SY, or CU. No audit entry is written for a sanctions-blocked transfer, and no test covers this behaviour.

**Suggested fix:**

```
Define SANCTIONED_COUNTRIES = {'KP', 'IR', 'SY', 'CU'} in services.py. In create_transfer(), after loading the recipient, check if recipient.country_code in SANCTIONED_COUNTRIES; if so, call _write_audit with action='transfer_blocked_sanctions' and raise HTTPException(status_code=403, detail='sanctions'). Add tests asserting (1) a transfer to a sanctioned country returns 403 with a detail containing 'sanctions', and (2) an audit entry with action='transfer_blocked_sanctions' is written.
```

### REQ-11 — Masked account numbers in statements

**Status:** 🔴 missing  
**Risk:** Medium  

**Reason:** No masking logic exists anywhere in the codebase. The statement endpoint returns a full AccountResponse whose account_number field is an unmasked string. No test verifies that account numbers are masked in statement responses.

**Suggested fix:**

```
Add a masked_account_number computed field to a new StatementAccountResponse schema variant used only for statements that returns '*' * 6 + account_number[-4:]. Use this schema in StatementResponse instead of the full AccountResponse. Add a test that calls GET /accounts/{id}/statement and asserts the account_number field contains only '****' followed by 4 digits and does not contain the full number.
```

**Code evidence:**

- `ledgerlite/schemas.py:56      email: str`
- `ledgerlite/main.py:49  @app.get("/accounts/{account_id}/statement", response_model=StatementResponse)`

### REQ-12 — Audit log retention — no deletion

**Status:** ⚠️ untested  
**Risk:** Medium  

**Reason:** No DELETE /audit or DELETE /audit/{id} route exists in the codebase, satisfying criterion 1. Criterion 2 (DELETE returns 405/404) is met implicitly by FastAPI's default method-not-allowed behaviour for the registered GET /audit path. However, no test in any test file sends a DELETE request to /audit and asserts a 405 or 404 response, so neither criterion has an asserting test.

**Suggested fix:**

```
Add a test that sends DELETE /audit and asserts the response status is 405 or 404, confirming the retention requirement is enforced by the API.
```

**Code evidence:**

- `ledgerlite/main.py:95  @app.get("/audit", response_model=list[AuditEntryResponse])`

## Evidence Verification

### Before (out-before)

| Metric | Count |
|--------|-------|
| Entries checked | 36 |
| Verified OK | 2 |
| Line corrected | 23 |
| Snippet replaced (verified=false) | 11 |
| File not found | 0 |
| Test entries removed | 4 |

### After (out)

| Metric | Count |
|--------|-------|
| Entries checked | 36 |
| Verified OK | 2 |
| Line corrected | 23 |
| Snippet replaced (verified=false) | 11 |
| File not found | 0 |
| Test entries removed | 4 |

## Stage Timings

### Before

| Stage | Started | Duration |
|-------|---------|----------|
| read | 2026-09-25T16:06:49.977275+00:00 | 0.0s |
| audit | 2026-09-25T16:17:43.226897+00:00 | 0.0s |

### After

| Stage | Started | Duration |
|-------|---------|----------|
| read | 2026-09-25T16:06:49.977275+00:00 | 0.0s |
| audit | 2026-09-25T16:17:43.226897+00:00 | 0.0s |

---
_Report generated by SoloTrace at 2026-09-25 16:36:38 UTC_
