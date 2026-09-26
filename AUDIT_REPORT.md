# SoloTrace audit report — LedgerLite Payments API

*Generated 2026-09-26T00:46:06+00:00 by SoloTrace 2.0.0 · verdicts by INTERIM — round-1 verdicts, to be replaced by the final IBM Bob audit.*

> **Result:** 0 of 12 requirements are **proven**: implemented, cited with verified file:line evidence, covered by passing tests, and every deliberate sabotage of them was caught by the tests.

## 1. Scope

| Item | Value |
|---|---|
| Specification | `demo-data/LedgerLite-Requirements-v2.0.pdf` (version 2.0) |
| Specification SHA-256 | `cf06e0a2c238e7806ae6692702a6d4a713816333b83e22a8b2e7ff14007f9250` |
| Code audited | commit `cad816684d7f1f8af758e0962416aec1dc2c975f` (uncommitted changes present) |
| Test suite | `ledgerlite/tests`: 135 passed, 0 failed, 0 skipped |
| Evidence verification | 24/57 code citations verified against the audited commit |
| Mutation testing | 45/45 mutations killed |
| Auditor | INTERIM — round-1 verdicts, to be replaced by the final IBM Bob audit |
| Audited at | 2026-09-26T00:45:31+00:00 |

## 2. Results across audit rounds

| Round | Code | AI says covered | Citations verified | Tests | Mutations killed | Proven |
|---|---|---|---|---|---|---|
| Baseline (IBM Bob task 1) | `b52c5e4` | 4/12 | 27/36 | 28 passed / 0 failed | — | not tested |
| Round 1 (after Bob's fixes, task 3) | `149d409` | 12/12 | 55/57 | 58 passed / 0 failed | 23/34 | 6/12 |
| Round 2 (final) | `cad8166` | 12/12 | 24/57 | 135 passed / 0 failed | 45/45 | 0/12 |

*Proven* = the AI verdict is `covered`, at least one code citation is verified verbatim, at least one cited test exists and passed, and every mutation of the requirement was killed by the test suite.

## 3. Traceability matrix

| Req | Requirement | Risk | Change | Baseline | Round 1 | Final | Evidence | Tests | Mutations |
|---|---|---|---|---|---|---|---|---|---|
| REQ-01 | Unique email and KYC gating | High | none | ☑️ covered | ✅ proven | ⚠️ untested | 1/3 | 0/5 | 3/3 |
| REQ-02 | Deposit amount limits | Medium | none | ☑️ covered | ✅ proven | ⚠️ untested | 1/5 | 0/6 | 3/3 |
| REQ-03 | Withdrawal floor — no negative balance | High | none | ☑️ covered | ✅ proven | ⚠️ untested | 1/3 | 0/3 | 2/2 |
| REQ-04 | Atomic transfers | High | none | ⚠️ unverified | 🟠 weak | ⚠️ untested | 3/7 | 0/2 | 2/2 |
| REQ-05 | Large-transfer pending approval threshold | High | changed | ❌ contradicts | 🟠 weak | ⚠️ untested | 1/3 | 0/4 | 7/7 |
| REQ-06 | Audit log for every money movement | High | none | ⚠️ untested | 🟠 weak | ⚠️ untested | 4/5 | 0/5 | 6/6 |
| REQ-07 | Account lockout after failed PIN attempts | Medium | none | ⚠️ untested | ✅ proven | ⚠️ untested | 5/8 | 0/2 | 5/5 |
| REQ-08 | Exact decimal arithmetic | Medium | none | ⚠️ untested | 🟠 weak | ⚠️ untested | 1/6 | 0/4 | 3/3 |
| REQ-09 | Daily outgoing transfer cap | High | new | ⛔ missing | 🟠 weak | ⚠️ untested | 1/7 | 0/3 | 5/5 |
| REQ-10 | Sanctions list blocking | High | new | ⛔ missing | ✅ proven | ⚠️ untested | 2/4 | 0/9 | 4/4 |
| REQ-11 | Masked account numbers in statements | Medium | new | ⛔ missing | ✅ proven | ⚠️ untested | 4/5 | 0/3 | 3/3 |
| REQ-12 | Audit log retention — no deletion | Medium | none | ⚠️ untested | 🟠 weak | ⚠️ unverified | 0/1 | 0/2 | 2/2 |

## 4. Requirement detail

### REQ-01 — Unique email and KYC gating

**Risk:** High · **Change in v2.0:** none · **Final status:** ⚠️ untested

> An account can only be created with a unique email address. An account may not send or receive money until its KYC status is verified.

Acceptance criteria:
- Duplicate email is rejected.
- Any money movement on an unverified account is rejected.

Auditor's reasoning: Unique email is enforced at account creation by querying for an existing Account with the same email before inserting (services.py:101). KYC gating is enforced by _require_kyc(), which raises HTTP 403 when kyc_status != 'verified' (services.py:86-87); this guard is called before every deposit, withdrawal, and transfer operation. All four gating paths and the duplicate-email path are each covered by a dedicated test.

Code evidence:
- `ledgerlite/services.py:101` `if db.query(Account).filter(Account.email == email).first():` — ✘ not_found
- `ledgerlite/services.py:86` `def _require_kyc(account: Account) -> None:` — ✘ not_found
- `ledgerlite/services.py:118` `if account.kyc_status != "verified":` — ✔ verified

Tests:
- `ledgerlite/tests/test_spec1_accounts_kyc.py` · `test_duplicate_email_rejected` — ✘ not found
- `ledgerlite/tests/test_spec1_accounts_kyc.py` · `test_deposit_blocked_before_kyc` — ✘ not found
- `ledgerlite/tests/test_spec1_accounts_kyc.py` · `test_withdraw_blocked_before_kyc` — ✘ not found
- `ledgerlite/tests/test_spec1_accounts_kyc.py` · `test_transfer_sender_blocked_before_kyc` — ✘ not found
- `ledgerlite/tests/test_spec1_accounts_kyc.py` · `test_transfer_recipient_blocked_before_kyc` — ✘ not found

Mutations (deliberate sabotage — each must make a test fail):
- REQ-01-M1: KYC gate never fires (unverified accounts can move money) — **killed** by `test_deposit_blocked_before_kyc`
- REQ-01-M2: skip the recipient KYC check on transfers — **killed** by `test_transfer_recipient_blocked_before_kyc`
- REQ-01-M3: make the unique-email check case-sensitive — **killed** by `test_duplicate_email_is_case_insensitive`

### REQ-02 — Deposit amount limits

**Risk:** Medium · **Change in v2.0:** none · **Final status:** ⚠️ untested

> A deposit amount must be greater than 0 and at most 50,000.00 per transaction.

Acceptance criteria:
- Deposits of 0 are rejected.
- Negative deposit amounts are rejected.
- A deposit of 50,000.01 is rejected.
- A deposit of 50,000.00 is accepted.

Auditor's reasoning: Deposit validation enforces a lower bound (amount must be > 0) and an upper bound (amount must not exceed 50 000.00) at the service layer. Six dedicated tests exercise zero, negative, boundary-exact-reject, boundary-exact-accept, a general positive value, and accumulation across multiple deposits.

Code evidence:
- `ledgerlite/services.py:19` `_MAX_DEPOSIT = Decimal("50000.00")` — ✘ not_found
- `ledgerlite/services.py:123` `if amount <= Decimal("0"):` — ✔ verified
- `ledgerlite/services.py:136` `raise HTTPException(status_code=400, detail="Deposit amount must be greater than 0")` — ✘ not_found
- `ledgerlite/services.py:137` `if amount > _MAX_DEPOSIT:` — ✘ not_found
- `ledgerlite/services.py:138` `raise HTTPException(status_code=400, detail=f"Deposit amount must not exceed {_MAX_DEPOSIT}")` — ✘ not_found

Tests:
- `ledgerlite/tests/test_spec2_deposit_limits.py` · `test_zero_rejected` — ✘ not found
- `ledgerlite/tests/test_spec2_deposit_limits.py` · `test_negative_rejected` — ✘ not found
- `ledgerlite/tests/test_spec2_deposit_limits.py` · `test_boundary_50000_01_rejected` — ✘ not found
- `ledgerlite/tests/test_spec2_deposit_limits.py` · `test_boundary_50000_accepted` — ✘ not found
- `ledgerlite/tests/test_spec2_deposit_limits.py` · `test_positive_amount_accepted` — ✘ not found
- `ledgerlite/tests/test_spec2_deposit_limits.py` · `test_multiple_deposits_accumulate` — ✘ not found

Mutations (deliberate sabotage — each must make a test fail):
- REQ-02-M1: lower the deposit maximum by one cent — **killed** by `test_boundary_50000_accepted`
- REQ-02-M2: allow a deposit of 50,000.01 — **killed** by `test_boundary_50000_01_rejected`
- REQ-02-M3: accept zero and negative deposits — **killed** by `test_zero_and_negative_rejected[0]`

### REQ-03 — Withdrawal floor — no negative balance

**Risk:** High · **Change in v2.0:** none · **Final status:** ⚠️ untested

> A withdrawal must never make the account balance negative.

Acceptance criteria:
- Withdrawing more than the balance is rejected.
- The balance is unchanged after a rejected withdrawal.

Auditor's reasoning: The withdrawal floor is enforced in services.py at lines 156-157: before applying any debit the service checks that the resulting balance would not be less than zero, and raises HTTP 400 with 'Insufficient funds' if it would. Line 159 then performs the actual debit only when that guard passes. Three tests cover the requirement: test_withdrawal_overdraft_rejected confirms a withdrawal of one cent above the balance is rejected with HTTP 400 and the 'Insufficient' message; test_balance_never_goes_negative drains the account to exactly 0.00 and then confirms a further withdrawal is rejected and the balance remains 0.00; test_withdrawal_exact_balance_allowed confirms that withdrawing exactly the full balance succeeds and leaves the balance at 0.00.

Code evidence:
- `ledgerlite/services.py:156` `if account.balance - amount < Decimal("0"):` — ✘ not_found
- `ledgerlite/services.py:261` `raise HTTPException(status_code=400, detail="Insufficient funds")` — ✔ verified
- `ledgerlite/services.py:159` `account.balance -= amount` — ✘ not_found

Tests:
- `ledgerlite/tests/test_spec3_withdrawals.py` · `test_withdrawal_overdraft_rejected` — ✘ not found
- `ledgerlite/tests/test_spec3_withdrawals.py` · `test_balance_never_goes_negative` — ✘ not found
- `ledgerlite/tests/test_spec3_withdrawals.py` · `test_withdrawal_exact_balance_allowed` — ✘ not found

Mutations (deliberate sabotage — each must make a test fail):
- REQ-03-M1: debit without checking the balance — **killed** by `test_overdraft_rejected_and_balance_unchanged`
- REQ-03-M2: accept negative withdrawals (which increase the balance) — **killed** by `test_zero_and_negative_withdrawals_rejected`

### REQ-04 — Atomic transfers

**Risk:** High · **Change in v2.0:** none · **Final status:** ⚠️ untested

> A transfer between two accounts is atomic: either both the debit and the credit happen, or neither does.

Acceptance criteria:
- If the credit fails, the debit is rolled back.

Auditor's reasoning: The transfer service wraps the balance mutation, Transfer insert, flush, and audit write inside a single try/except block (services.py:220-245). The debit is applied to sender.balance (line 221) and the credit to recipient.balance (line 223) before db.commit() is called (line 242). If any step raises — including the audit write — the except clause on line 243 calls db.rollback() (line 244) and re-raises, so neither balance change is ever persisted. test_transfer_rolls_back_on_db_error proves this by patching _write_audit to raise a RuntimeError after the debit and asserting both balances are unchanged after the 500 response. test_successful_transfer_debits_sender_credits_recipient proves the happy path commits both sides atomically.

Code evidence:
- `ledgerlite/services.py:220` `try:` — ✘ too_short
- `ledgerlite/services.py:221` `sender.balance -= amount` — ✘ not_found
- `ledgerlite/services.py:223` `recipient.balance += amount` — ✘ not_found
- `ledgerlite/services.py:247` `db.commit()` — ✔ verified
- `ledgerlite/services.py:339` `except Exception:` — ✔ verified
- `ledgerlite/services.py:260` `db.rollback()` — ✔ verified
- `ledgerlite/services.py:245` `raise` — ✘ too_short

Tests:
- `ledgerlite/tests/test_spec4_transfer_atomicity.py` · `test_transfer_rolls_back_on_db_error` — ✘ not found
- `ledgerlite/tests/test_spec4_transfer_atomicity.py` · `test_successful_transfer_debits_sender_credits_recipient` — ✘ not found

Mutations (deliberate sabotage — each must make a test fail):
- REQ-04-M1: commit the debit before the credit (two transactions) — **killed** by `test_failed_credit_rolls_back_the_debit`
- REQ-04-M2: credit the recipient even when the debit failed — **killed** by `test_insufficient_funds_rejected_without_side_effects`

### REQ-05 — Large-transfer pending approval threshold

**Risk:** High · **Change in v2.0:** changed · **Final status:** ⚠️ untested

> A transfer of 5,000.00 or more must be held as pending_approval until a second, different user approves it. (v1.0 threshold was 10,000.00.)

Acceptance criteria:
- A transfer of 5,000.00 is held as pending_approval, not completed immediately.
- The initiator cannot approve their own transfer.

Auditor's reasoning: The v2.0 threshold of 5,000.00 is correctly implemented. Transfers >= 5,000.00 are set to pending_approval; transfers below that are completed immediately. This was fixed from the old v1.0 value of 10,000.00. All four boundary tests pass.

Code evidence:
- `ledgerlite/services.py:20` `_LARGE_TRANSFER_THRESHOLD = Decimal("5000.00")` — ✘ not_found
- `ledgerlite/services.py:217` `large = amount >= _LARGE_TRANSFER_THRESHOLD` — ✘ not_found
- `ledgerlite/services.py:308` `status = "pending_approval" if large else "completed"` — ✔ verified

Tests:
- `ledgerlite/tests/test_spec5_large_transfer_threshold.py` · `test_transfer_below_threshold_completed` — ✘ not found
- `ledgerlite/tests/test_spec5_large_transfer_threshold.py` · `test_transfer_at_threshold_pending` — ✘ not found
- `ledgerlite/tests/test_spec5_large_transfer_threshold.py` · `test_transfer_above_threshold_pending` — ✘ not found
- `ledgerlite/tests/test_spec5_large_transfer_threshold.py` · `test_transfer_just_below_threshold_completed` — ✘ not found

Mutations (deliberate sabotage — each must make a test fail):
- REQ-05-M1: revert to the old v1.0 threshold of 10,000.00 — **killed** by `test_at_or_above_threshold_is_held[5000.00]`
- REQ-05-M2: exactly 5,000.00 completes without approval — **killed** by `test_at_or_above_threshold_is_held[5000.00]`
- REQ-05-M3: let the initiator approve their own transfer — **killed** by `test_initiator_cannot_approve_own_transfer`
- REQ-05-M4: let the recipient approve the transfer — **killed** by `test_recipient_cannot_approve`
- REQ-05-M5: approve without the approver's PIN — **killed** by `test_approver_needs_correct_pin`
- REQ-05-M6: a transfer can be approved twice (recipient credited twice) — **killed** by `test_double_approval_rejected_and_credits_once`
- REQ-05-M7: any customer can approve (approver role not required) — **killed** by `test_customer_without_approver_role_cannot_approve`

### REQ-06 — Audit log for every money movement

**Risk:** High · **Change in v2.0:** none · **Final status:** ⚠️ untested

> Every money movement (deposit, withdrawal, transfer, approval) writes an audit log entry containing actor, action, amount, account(s) and UTC timestamp. Audit entries cannot be edited.

Acceptance criteria:
- Each money-movement operation adds exactly one audit log entry.
- No update endpoint exists for audit entries.

Auditor's reasoning: _write_audit() is called in deposit() (line 141), withdraw() (line 160), create_transfer() (line 234), and approve_transfer() (line 269). No PATCH/DELETE endpoint for audit entries exists. All five criteria are asserted by named tests in test_spec6_audit_log.py.

Code evidence:
- `ledgerlite/services.py:52` `def _write_audit(` — ✔ verified
- `ledgerlite/services.py:246` `_write_audit(db, actor_id=account_id, action="deposit", amount=amount, account_id=account_id)` — ✔ verified
- `ledgerlite/services.py:263` `_write_audit(db, actor_id=account_id, action="withdrawal", amount=amount, account_id=account_id)` — ✔ verified
- `ledgerlite/services.py:284` `_write_audit(` — ✔ verified
- `ledgerlite/main.py:95` `@app.get("/audit", response_model=list[AuditEntryResponse])` — ✘ not_found

Tests:
- `ledgerlite/tests/test_spec6_audit_log.py` · `test_audit_entry_written_on_deposit` — ✘ not found
- `ledgerlite/tests/test_spec6_audit_log.py` · `test_audit_entry_written_on_withdrawal` — ✘ not found
- `ledgerlite/tests/test_spec6_audit_log.py` · `test_audit_entry_written_on_transfer` — ✘ not found
- `ledgerlite/tests/test_spec6_audit_log.py` · `test_no_audit_delete_endpoint` — ✘ not found
- `ledgerlite/tests/test_spec6_audit_log.py` · `test_no_audit_patch_endpoint` — ✘ not found

Mutations (deliberate sabotage — each must make a test fail):
- REQ-06-M1: deposits are not audited — **killed** by `test_deposit_writes_exactly_one_entry`
- REQ-06-M2: withdrawals write two audit entries — **killed** by `test_withdrawal_writes_exactly_one_entry`
- REQ-06-M3: approval entry records the wrong actor — **killed** by `test_approval_writes_exactly_one_entry`
- REQ-06-M4: audit timestamps lose their UTC marker — **killed** by `test_deposit_writes_exactly_one_entry`
- REQ-06-M5: add an endpoint that edits audit entries — **killed** by `test_existing_entry_cannot_be_modified[PATCH]`
- REQ-06-M6: deposit audit entry records the wrong actor — **killed** by `test_deposit_allowed_after_kyc`

### REQ-07 — Account lockout after failed PIN attempts

**Risk:** Medium · **Change in v2.0:** none · **Final status:** ⚠️ untested

> An account is locked after 5 consecutive failed PIN attempts. A locked account cannot move money.

Acceptance criteria:
- The 5th wrong PIN locks the account.
- A correct PIN entered before the 5th failure resets the counter.

Auditor's reasoning: _check_pin() increments failed_pin_attempts on each wrong PIN; on the 5th failure (>= _MAX_FAILED_PINS) it sets account.locked = True and raises HTTP 423. A subsequent correct PIN resets failed_pin_attempts to 0. Both acceptance criteria are asserted by dedicated tests.

Code evidence:
- `ledgerlite/services.py:21` `_MAX_FAILED_PINS = 5` — ✘ not_found
- `ledgerlite/services.py:97` `if account.locked:` — ✔ verified
- `ledgerlite/services.py:98` `raise HTTPException(status_code=423, detail="Account is locked due to too many failed PIN attempts")` — ✔ verified
- `ledgerlite/services.py:73` `if not verify_pin(pin, account.pin_hash):` — ✘ not_found
- `ledgerlite/services.py:102` `account.failed_pin_attempts = 0  # a correct PIN resets the counter` — ✔ verified
- `ledgerlite/services.py:75` `if account.failed_pin_attempts >= _MAX_FAILED_PINS:` — ✘ not_found
- `ledgerlite/services.py:109` `account.locked = True` — ✔ verified
- `ledgerlite/services.py:102` `account.failed_pin_attempts = 0  # a correct PIN resets the counter` — ✔ verified

Tests:
- `ledgerlite/tests/test_spec7_pin_lockout.py` · `test_fifth_wrong_pin_locks_account` — ✘ not found
- `ledgerlite/tests/test_spec7_pin_lockout.py` · `test_correct_pin_resets_counter` — ✘ not found

Mutations (deliberate sabotage — each must make a test fail):
- REQ-07-M1: lock only after 6 failures — **killed** by `test_fifth_wrong_pin_locks_account`
- REQ-07-M2: do not persist the failure counter (the original lockout bug) — **killed** by `test_failed_attempts_are_persisted_between_requests`
- REQ-07-M3: a correct PIN no longer resets the counter — **killed** by `test_correct_pin_resets_counter`
- REQ-07-M4: locked accounts can still move money — **killed** by `test_fifth_wrong_pin_locks_account`
- REQ-07-M5: any PIN is accepted — **killed** by `test_approver_needs_correct_pin`

### REQ-08 — Exact decimal arithmetic

**Risk:** Medium · **Change in v2.0:** none · **Final status:** ⚠️ untested

> All monetary values are stored and calculated as exact decimals (never floating point) and returned with exactly 2 decimal places.

Acceptance criteria:
- 0.10 + 0.20 equals 0.30 exactly.
- The API returns monetary values formatted as strings with exactly 2 decimal places (e.g. "0.30").

Auditor's reasoning: All monetary values are coerced through _to_decimal() (Decimal(str(value))) before arithmetic; the database column is Numeric(12,2); and balance is serialised as a 2dp string via @field_serializer. The critical 0.10+0.20==0.30 criterion is directly asserted by test_point_one_plus_point_two_equals_point_three.

Code evidence:
- `ledgerlite/models.py:24` `balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))` — ✘ not_found
- `ledgerlite/services.py:11` `from decimal import Decimal, InvalidOperation` — ✘ not_found
- `ledgerlite/services.py:91` `def _to_decimal(value) -> Decimal:` — ✘ not_found
- `ledgerlite/services.py:93` `return Decimal(str(value))` — ✘ not_found
- `ledgerlite/schemas.py:122` `@field_serializer("balance")` — ✔ verified
- `ledgerlite/schemas.py:66` `return f"{v:.2f}"` — ✘ not_found

Tests:
- `ledgerlite/tests/test_spec8_decimal_arithmetic.py` · `test_point_one_plus_point_two_equals_point_three` — ✘ not found
- `ledgerlite/tests/test_spec8_decimal_arithmetic.py` · `test_balance_serialised_as_two_decimal_places` — ✘ not found
- `ledgerlite/tests/test_spec2_deposit_limits.py` · `test_multiple_deposits_accumulate` — ✘ not found
- `ledgerlite/tests/test_spec2_deposit_limits.py` · `test_boundary_50000_accepted` — ✘ not found

Mutations (deliberate sabotage — each must make a test fail):
- REQ-08-M1: store money as floating point (REAL) — **killed** by `test_money_is_stored_as_integer_cents_not_real`
- REQ-08-M2: convert money through float — **killed** by `test_classic_float_traps_are_exact`
- REQ-08-M3: silently round amounts with more than 2 decimals — **killed** by `test_sub_cent_amount_cannot_dodge_the_threshold`

### REQ-09 — Daily outgoing transfer cap

**Risk:** High · **Change in v2.0:** new · **Final status:** ⚠️ untested

> Total outgoing transfers per account must not exceed 20,000.00 per UTC calendar day.

Acceptance criteria:
- A transfer that would take the day's total outgoing above 20,000.00 is rejected.

Auditor's reasoning: The implementation introduces a hard cap of 20,000.00 in outgoing transfers per UTC calendar day. The constant _DAILY_TRANSFER_CAP is defined at module level and the check runs inside the transfer service before any balance mutation: it sums all transfers with status 'completed' or 'pending_approval' for the sender since today_start (UTC midnight), converts the aggregate to Decimal, and raises HTTP 400 when daily_total + amount > _DAILY_TRANSFER_CAP. Three dedicated tests cover the boundary exactly (20,000.00 accepted), the first cent over the boundary (20,000.01 rejected), and a three-transfer scenario where the third transfer is blocked.

Code evidence:
- `ledgerlite/services.py:22` `_DAILY_TRANSFER_CAP = Decimal("20000.00")` — ✘ not_found
- `ledgerlite/services.py:198` `today_utc = datetime.datetime.now(timezone.utc).date()` — ✘ not_found
- `ledgerlite/services.py:199` `today_start = datetime.datetime(today_utc.year, today_utc.month, today_utc.day, tzinfo=timezone.utc)` — ✘ not_found
- `ledgerlite/services.py:201` `daily_total_row = (` — ✘ not_found
- `ledgerlite/services.py:210` `daily_total = Decimal(str(daily_total_row[0]))` — ✘ not_found
- `ledgerlite/services.py:211` `if daily_total + amount > _DAILY_TRANSFER_CAP:` — ✘ not_found
- `ledgerlite/services.py:186` `raise HTTPException(status_code=409, detail="Email already registered")` — ✔ verified

Tests:
- `ledgerlite/tests/test_spec9_daily_cap.py` · `test_daily_cap_exact_boundary_accepted` — ✘ not found
- `ledgerlite/tests/test_spec9_daily_cap.py` · `test_daily_cap_exceeded_rejected` — ✘ not found
- `ledgerlite/tests/test_spec9_daily_cap.py` · `test_daily_cap_three_transfers_third_blocked` — ✘ not found

Mutations (deliberate sabotage — each must make a test fail):
- REQ-09-M1: raise the daily cap by one cent — **killed** by `test_one_cent_over_the_cap_rejected`
- REQ-09-M2: pending transfers no longer count toward the cap — **killed** by `test_one_cent_over_the_cap_rejected`
- REQ-09-M3: count yesterday's transfers too — **killed** by `test_yesterdays_transfers_do_not_count`
- REQ-09-M4: stop serialising transactions (concurrent transfers race the cap) — **killed** by `test_concurrent_duplicate_signups_give_one_account`
- REQ-09-M5: drop the UTC-day window (cap becomes all-time) — **killed** by `test_yesterdays_transfers_do_not_count`

### REQ-10 — Sanctions list blocking

**Risk:** High · **Change in v2.0:** new · **Final status:** ⚠️ untested

> Transfers to an account whose country code is on the sanctions list (KP, IR, SY, CU) are blocked and logged.

Acceptance criteria:
- A transfer to a sanctioned country is rejected with reason "sanctions".
- An audit entry is written for the blocked transfer.

Auditor's reasoning: Transfers where the sender or recipient has a country_code in {KP, IR, SY, CU} are rejected with HTTP 400 and detail 'sanctions'. A sanctions_blocked audit entry is written before rejection. All 9 test cases (4 sender-blocked, 4 recipient-blocked, 1 audit-entry) pass.

Code evidence:
- `ledgerlite/services.py:23` `_SANCTIONED_COUNTRIES = {"KP", "IR", "SY", "CU"}` — ✘ not_found
- `ledgerlite/services.py:180` `if sender.country_code in _SANCTIONED_COUNTRIES or recipient.country_code in _SANCTIONED_COUNTRIES:` — ✘ not_found
- `ledgerlite/services.py:287` `action="sanctions_blocked",` — ✔ verified
- `ledgerlite/services.py:294` `raise HTTPException(status_code=400, detail="sanctions")` — ✔ verified

Tests:
- `ledgerlite/tests/test_spec10_sanctions.py` · `test_sanctioned_sender_blocked[KP]` — ✘ not found
- `ledgerlite/tests/test_spec10_sanctions.py` · `test_sanctioned_sender_blocked[IR]` — ✘ not found
- `ledgerlite/tests/test_spec10_sanctions.py` · `test_sanctioned_sender_blocked[SY]` — ✘ not found
- `ledgerlite/tests/test_spec10_sanctions.py` · `test_sanctioned_sender_blocked[CU]` — ✘ not found
- `ledgerlite/tests/test_spec10_sanctions.py` · `test_sanctioned_recipient_blocked[KP]` — ✘ not found
- `ledgerlite/tests/test_spec10_sanctions.py` · `test_sanctioned_recipient_blocked[IR]` — ✘ not found
- `ledgerlite/tests/test_spec10_sanctions.py` · `test_sanctioned_recipient_blocked[SY]` — ✘ not found
- `ledgerlite/tests/test_spec10_sanctions.py` · `test_sanctioned_recipient_blocked[CU]` — ✘ not found
- `ledgerlite/tests/test_spec10_sanctions.py` · `test_audit_entry_written_for_sanctions_block` — ✘ not found

Mutations (deliberate sabotage — each must make a test fail):
- REQ-10-M1: drop CU from the sanctions list — **killed** by `test_transfer_to_sanctioned_recipient_blocked_and_logged[CU]`
- REQ-10-M2: screen only the sender, not the recipient — **killed** by `test_transfer_to_sanctioned_recipient_blocked_and_logged[KP]`
- REQ-10-M3: log blocks under a different action name — **killed** by `test_transfer_to_sanctioned_recipient_blocked_and_logged[KP]`
- REQ-10-M4: block the transfer but lose the audit entry — **killed** by `test_transfer_to_sanctioned_recipient_blocked_and_logged[KP]`

### REQ-11 — Masked account numbers in statements

**Risk:** Medium · **Change in v2.0:** new · **Final status:** ⚠️ untested

> Account statements must mask account numbers, showing only the last 4 digits (e.g. ****1234).

Acceptance criteria:
- No full account number appears in any statement response.
- Account numbers in statements are masked, showing only the last 4 digits.

Auditor's reasoning: StatementAccountResponse overrides the account_number serializer to emit '******' + last-4 digits. The statement route uses StatementResponse (which embeds StatementAccountResponse) as its response_model, so every GET /accounts/{id}/statement response has a masked account number. The detail endpoint continues to use the unmasked AccountResponse. Three tests cover the requirement: pattern format, last-4 preservation, and detail-endpoint passthrough.

Code evidence:
- `ledgerlite/schemas.py:170` `class StatementAccountResponse(AccountResponse):` — ✔ verified
- `ledgerlite/schemas.py:174` `def serialize_account_number(self, v: str) -> str:` — ✔ verified
- `ledgerlite/schemas.py:108` `return "******" + v[-4:]` — ✘ not_found
- `ledgerlite/main.py:111` `@app.get("/accounts/{account_id}/statement", response_model=StatementResponse)` — ✔ verified
- `ledgerlite/main.py:114` `return StatementResponse(account=account, transactions=transactions)` — ✔ verified

Tests:
- `ledgerlite/tests/test_spec11_statement_masking.py` · `test_statement_masks_account_number` — ✘ not found
- `ledgerlite/tests/test_spec11_statement_masking.py` · `test_statement_mask_preserves_last4` — ✘ not found
- `ledgerlite/tests/test_spec11_statement_masking.py` · `test_account_detail_endpoint_not_masked` — ✘ not found

Mutations (deliberate sabotage — each must make a test fail):
- REQ-11-M1: mask with 6 stars instead of the spec's **** — **killed** by `test_statement_masks_account_number_like_the_spec_example`
- REQ-11-M2: statements show the full account number — **killed** by `test_statement_masks_account_number_like_the_spec_example`
- REQ-11-M3: reveal 5 digits instead of 4 — **killed** by `test_statement_masks_account_number_like_the_spec_example`

### REQ-12 — Audit log retention — no deletion

**Risk:** Medium · **Change in v2.0:** none · **Final status:** ⚠️ unverified

> Audit log entries must never be deleted through the API (7-year retention).

Acceptance criteria:
- No delete endpoint exists for audit entries.
- A DELETE request to audit entries returns HTTP 405 or 404.

Auditor's reasoning: No DELETE /audit route is defined in main.py, making audit log deletion impossible at the API level. The GET /audit route at line 95 is the only audit endpoint. Tests confirm that DELETE requests to /audit and /audit/{id} both return 405 Method Not Allowed.

Code evidence:
- `ledgerlite/main.py:95` `@app.get("/audit", response_model=list[AuditEntryResponse])` — ✘ not_found

Tests:
- `ledgerlite/tests/test_spec12_audit_retention.py` · `test_delete_audit_returns_405` — ✘ not found
- `ledgerlite/tests/test_spec12_audit_retention.py` · `test_delete_audit_entry_returns_405` — ✘ not found

Mutations (deliberate sabotage — each must make a test fail):
- REQ-12-M1: add an endpoint that deletes audit entries — **killed** by `test_existing_entry_cannot_be_modified[DELETE]`
- REQ-12-M2: add an endpoint that purges the whole audit log — **killed** by `test_audit_collection_cannot_be_modified[DELETE]`

## 5. Human compliance sign-offs

| When | Where | Statement |
|---|---|---|
| 2026-09-25T21:46:52+05:00 | IBM Bob task03 | Approved — compliance sign-off by Shehar Bano |

## 6. IBM Bob sessions

| Task | What | Started | Minutes | Bobcoins | Parallel subagents |
|---|---|---|---|---|---|
| task01 | Create a new Python project called "solotrace" in this folder with thi | 2026-09-25T20:08:10+05:00 | 71.7 | 15.44 | 12 (in 112.7 s) |
| task02 | Build the SoloTrace CLI (python -m solotrace) in the solotrace package | 2026-09-25T21:26:20+05:00 | 11.8 | 3.14 | — |
| task03 | Stage 3 — FIX. Act as the SoloTrace Auditor and follow .bob/rules-solo | 2026-09-25T21:42:07+05:00 | 15.2 | 5.53 | 12 (in 37.5 s) |
| task04 | Polish SoloTrace and build the public demo dashboard. | 2026-09-25T22:04:12+05:00 | 13.8 | 7.48 | — |

Screenshots of each task's session summary are in `bob_sessions/`.

## 7. Method and limitations

- Verdicts are written by AI subagents (one per requirement). SoloTrace never trusts them blindly: every code citation is re-located in the audited commit (verbatim, re-wrapped or with a stripped comment), citations outside the repository are rejected, and cited tests must exist and pass.
- Mutation testing shows the tests *guard* each requirement; it cannot prove the absence of every possible defect.
- LedgerLite is a deliberately small sample API (SQLite, PIN-based access control, an admin token instead of identity management, a static sanctions list); it is an audit target, not a production banking system.
- Held transfers have no reject/expiry path yet; funds stay reserved until approved.

