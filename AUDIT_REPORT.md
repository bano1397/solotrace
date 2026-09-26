# SoloTrace audit report — LedgerLite Payments API

*Generated 2026-09-26T02:10:27+00:00 by SoloTrace 2.0.0 · verdicts by IBM Bob 2.0 — task 5 (SoloTrace Auditor mode, 12 parallel subagents; 11 finished before the 40-Bobcoin budget ran out, the REQ-12 verdict was reformatted to the schema unchanged, and this pipeline was run locally).*

> **Result:** 11 of 12 requirements are **proven**: implemented, cited with verified file:line evidence, covered by passing tests, and every deliberate sabotage of them was caught by the tests.

## 1. Scope

| Item | Value |
|---|---|
| Specification | `demo-data/LedgerLite-Requirements-v2.0.pdf` (version 2.0) |
| Specification SHA-256 | `cf06e0a2c238e7806ae6692702a6d4a713816333b83e22a8b2e7ff14007f9250` |
| Code audited | commit `08a08b04147ec6935476a4d41752a69cd80887c4` |
| Test suite | `ledgerlite/tests`: 161 passed, 0 failed, 0 skipped |
| Evidence verification | 82/85 code citations verified against the audited commit |
| Mutation testing | 98/99 mutations killed |
| Auditor | IBM Bob 2.0 — task 5 (SoloTrace Auditor mode, 12 parallel subagents; 11 finished before the 40-Bobcoin budget ran out, the REQ-12 verdict was reformatted to the schema unchanged, and this pipeline was run locally) |
| Audited at | 2026-09-26T02:07:02+00:00 |

## 2. Results across audit rounds

| Round | Code | AI says covered | Citations verified | Tests | Mutations killed | Proven |
|---|---|---|---|---|---|---|
| Baseline (IBM Bob task 1) | `b52c5e4` | 4/12 | 27/36 | 28 passed / 0 failed | — | not tested |
| Round 1 (after Bob's fixes, task 3) | `149d409` | 12/12 | 55/57 | 58 passed / 0 failed | 23/34 | 6/12 |
| Round 2 (final) | `08a08b0` | 12/12 | 82/85 | 161 passed / 0 failed | 98/99 | 11/12 |

*Proven* = the AI verdict is `covered`, at least one code citation is verified verbatim, at least one cited test exists and passed, and every mutation of the requirement was killed by the test suite.

## 3. Traceability matrix

| Req | Requirement | Risk | Change | Baseline | Round 1 | Final | Evidence | Tests | Mutations |
|---|---|---|---|---|---|---|---|---|---|
| REQ-01 | Unique email and KYC gating | High | none | ☑️ covered | ✅ proven | ✅ proven | 6/6 | 6/6 | 8/8 |
| REQ-02 | Deposit amount limits | Medium | none | ☑️ covered | ✅ proven | ✅ proven | 6/6 | 5/5 | 8/8 |
| REQ-03 | Withdrawal floor — no negative balance | High | none | ☑️ covered | ✅ proven | ✅ proven | 5/5 | 6/6 | 7/7 |
| REQ-04 | Atomic transfers | High | none | ⚠️ unverified | 🟠 weak | 🟠 weak | 9/11 | 4/4 | 6/7 |
| REQ-05 | Large-transfer pending approval threshold | High | changed | ❌ contradicts | 🟠 weak | ✅ proven | 5/5 | 2/2 | 11/11 |
| REQ-06 | Audit log for every money movement | High | none | ⚠️ untested | 🟠 weak | ✅ proven | 10/10 | 10/10 | 11/11 |
| REQ-07 | Account lockout after failed PIN attempts | Medium | none | ⚠️ untested | ✅ proven | ✅ proven | 9/9 | 7/7 | 9/9 |
| REQ-08 | Exact decimal arithmetic | Medium | none | ⚠️ untested | 🟠 weak | ✅ proven | 7/7 | 9/9 | 7/7 |
| REQ-09 | Daily outgoing transfer cap | High | new | ⛔ missing | 🟠 weak | ✅ proven | 9/9 | 9/9 | 10/10 |
| REQ-10 | Sanctions list blocking | High | new | ⛔ missing | ✅ proven | ✅ proven | 6/6 | 14/14 | 9/9 |
| REQ-11 | Masked account numbers in statements | Medium | new | ⛔ missing | ✅ proven | ✅ proven | 9/9 | 5/5 | 7/7 |
| REQ-12 | Audit log retention — no deletion | Medium | none | ⚠️ untested | 🟠 weak | ✅ proven | 1/2 | 6/6 | 5/5 |

## 4. Requirement detail

### REQ-01 — Unique email and KYC gating

**Risk:** High · **Change in v2.0:** none · **Final status:** ✅ proven

> An account can only be created with a unique email address. An account may not send or receive money until its KYC status is verified.

Acceptance criteria:
- Duplicate email is rejected.
- Any money movement on an unverified account is rejected.

Auditor's reasoning: Both acceptance criteria are fully guarded by production code and exercised by dedicated tests. AC1 (duplicate email rejected): services.py normalises the email to lowercase (line 167) then queries for an existing account with that email (line 168) and raises HTTP 409 if found (line 169); tests assert the 409 for an exact-duplicate and for a case-variant. AC2 (money movement blocked until KYC verified): _require_kyc (lines 118-119) raises HTTP 403 for any account whose kyc_status is not 'verified'; it is called before every deposit (lines 238-239), withdrawal (line 256), and on both sender and recipient for transfers (lines 297-298); tests cover deposit, withdrawal, sender-unverified transfer, recipient-unverified transfer, and the held-transfer path.

Code evidence:
- `ledgerlite/services.py:167` `email = email.strip().lower()` — ✔ verified
- `ledgerlite/services.py:168` `if db.scalar(select(Account.id).where(Account.email == email)) is not None:` — ✔ verified
- `ledgerlite/services.py:169` `raise HTTPException(status_code=409, detail="Email already registered")` — ✔ verified
- `ledgerlite/services.py:118` `if account.kyc_status != "verified":` — ✔ verified
- `ledgerlite/services.py:119` `raise HTTPException(status_code=403, detail=f"{role} KYC is not verified")` — ✔ verified
- `ledgerlite/services.py:296` `_require_kyc(sender, "Sender")` — ✔ verified

Tests:
- `ledgerlite/tests/test_req01_accounts_kyc.py` · `test_duplicate_email_rejected` — ✔ passed
- `ledgerlite/tests/test_req01_accounts_kyc.py` · `test_duplicate_email_is_case_insensitive` — ✔ passed
- `ledgerlite/tests/test_req01_accounts_kyc.py` · `test_deposit_blocked_before_kyc` — ✔ passed
- `ledgerlite/tests/test_req01_accounts_kyc.py` · `test_withdraw_blocked_before_kyc` — ✔ passed
- `ledgerlite/tests/test_req01_accounts_kyc.py` · `test_transfer_sender_blocked_before_kyc` — ✔ passed
- `ledgerlite/tests/test_req01_accounts_kyc.py` · `test_transfer_recipient_blocked_before_kyc` — ✔ passed

Mutations (deliberate sabotage — each must make a test fail):
- REQ-01-M1: KYC gate never fires (unverified accounts can move money) — **killed** by `test_deposit_blocked_before_kyc`
- REQ-01-M2: skip the recipient KYC check on transfers — **killed** by `test_transfer_recipient_blocked_before_kyc`
- REQ-01-M3: make the unique-email check case-sensitive — **killed** by `test_duplicate_email_is_case_insensitive`
- REQ-01-X1: [independent QA R2-01a] recipient KYC skipped for held (&gt;=5,000) transfers; approval later credits an unverified account — **killed** by `test_held_transfer_to_unverified_recipient_is_rejected`
- REQ-01-X2: [independent QA R2-01c] new accounts are born KYC-verified — **killed** by `test_create_account_success`
- REQ-01-X3: [independent QA R2-01d] verify-kyc endpoint no longer requires the admin token (self-verification) — **killed** by `test_kyc_verification_requires_admin_token`
- REQ-01-X4: [independent QA R2-01b] KYC only enforced for deposits above 1,000.00 (AML-style threshold) — **killed** by `test_deposit_blocked_before_kyc`
- REQ-01-B1: sender KYC check is disabled; an unverified sender can initiate transfers — **killed** by `test_transfer_sender_blocked_before_kyc`

### REQ-02 — Deposit amount limits

**Risk:** Medium · **Change in v2.0:** none · **Final status:** ✅ proven

> A deposit amount must be greater than 0 and at most 50,000.00 per transaction.

Acceptance criteria:
- Deposits of 0 are rejected.
- Negative deposit amounts are rejected.
- A deposit of 50,000.01 is rejected.
- A deposit of 50,000.00 is accepted.

Auditor's reasoning: All four acceptance criteria are exercised by dedicated tests. (1) Deposits of 0 are rejected: test_zero_and_negative_rejected is parametrized over '0' and '0.00', asserting HTTP 400 with 'greater than 0'. (2) Negative deposits are rejected: same parametrized test covers '-0.00' and '-1.00'. (3) A deposit of 50,000.01 is rejected: test_boundary_50000_01_rejected asserts HTTP 400 and balance unchanged. (4) A deposit of 50,000.00 is accepted: test_boundary_50000_accepted asserts HTTP 200 and correct balance. Enforcement is backed by _require_positive (lines 122-124) checking amount &lt;= 0, and the MAX_DEPOSIT guard (lines 242-243) checking amount &gt; MAX_DEPOSIT where MAX_DEPOSIT = Decimal('50000.00') (line 28).

Code evidence:
- `ledgerlite/services.py:28` `MAX_DEPOSIT = Decimal("50000.00") # REQ-02` — ✔ verified
- `ledgerlite/services.py:122` `def _require_positive(amount: Decimal, what: str) -> None:` — ✔ verified
- `ledgerlite/services.py:123` `if amount <= Decimal("0"):` — ✔ verified
- `ledgerlite/services.py:241` `_require_positive(amount, "Deposit")` — ✔ verified
- `ledgerlite/services.py:242` `if amount > MAX_DEPOSIT:` — ✔ verified
- `ledgerlite/services.py:243` `raise HTTPException(status_code=400, detail=f"Deposit amount must not exceed {MAX_DEPOSIT}")` — ✔ verified

Tests:
- `ledgerlite/tests/test_req02_deposit_limits.py` · `test_positive_amount_accepted` — ✔ passed
- `ledgerlite/tests/test_req02_deposit_limits.py` · `test_zero_and_negative_rejected` — ✔ passed
- `ledgerlite/tests/test_req02_deposit_limits.py` · `test_boundary_50000_accepted` — ✔ passed
- `ledgerlite/tests/test_req02_deposit_limits.py` · `test_boundary_50000_01_rejected` — ✔ passed
- `ledgerlite/tests/test_req02_deposit_limits.py` · `test_limit_is_per_transaction_not_per_balance` — ✔ passed

Mutations (deliberate sabotage — each must make a test fail):
- REQ-02-M1: lower the deposit maximum by one cent — **killed** by `test_boundary_50000_accepted`
- REQ-02-M2: allow a deposit of 50,000.01 — **killed** by `test_boundary_50000_01_rejected`
- REQ-02-M3: accept zero and negative deposits — **killed** by `test_zero_and_negative_rejected[0]`
- REQ-02-X1: [independent QA R2-02a] upper bound off-by-one: 50,000.00 rejected (&gt;=) — **killed** by `test_boundary_50000_accepted`
- REQ-02-X2: [independent QA R2-02b] per-transaction limit misread as a balance cap (balance + amount &gt; 50,000.00) — **killed** by `test_limit_is_per_transaction_not_per_balance`
- REQ-02-X3: [independent QA R2-02c] limit compares only whole dollars (int(amount)) — **killed** by `test_boundary_50000_01_rejected`
- REQ-02-X4: [independent QA R2-02d] lower bound off-by-one on the deposit path only: 0.00 accepted — **killed** by `test_zero_and_negative_rejected[0]`
- REQ-02-B1: changes &lt;= to &lt;, so a zero deposit passes the positive check and is accepted instead of rejected — **killed** by `test_zero_and_negative_rejected[0]`

### REQ-03 — Withdrawal floor — no negative balance

**Risk:** High · **Change in v2.0:** none · **Final status:** ✅ proven

> A withdrawal must never make the account balance negative.

Acceptance criteria:
- Withdrawing more than the balance is rejected.
- The balance is unchanged after a rejected withdrawal.

Auditor's reasoning: The withdrawal floor is enforced atomically in _debit() (services.py:131) via a SQL WHERE clause that requires Account.balance &gt;= amount before subtracting; if the row does not match (balance too low) rowcount is 0 and the function returns False (line 135). The withdraw() caller at line 259 treats a False return as an error: it rolls back the transaction and raises HTTP 400 'Insufficient funds' (lines 260-261), leaving the balance unchanged. Both acceptance criteria are exercised: test_overdraft_rejected_and_balance_unchanged confirms a withdrawal above the balance is rejected with 400 and the balance is unchanged; test_balance_never_goes_negative confirms the balance cannot go below zero; test_withdrawal_exact_balance_allowed confirms equality is permitted; and test_concurrent_withdrawals_cannot_overdraw proves the atomic WHERE guard holds under concurrency.

Code evidence:
- `ledgerlite/services.py:131` `.where(Account.id == account_id, Account.balance >= amount)` — ✔ verified
- `ledgerlite/services.py:135` `return result.rowcount == 1` — ✔ verified
- `ledgerlite/services.py:259` `if not _debit(db, account_id, amount): # REQ-03: never below zero, even under concurrency` — ✔ verified
- `ledgerlite/services.py:260` `db.rollback()` — ✔ verified
- `ledgerlite/services.py:261` `raise HTTPException(status_code=400, detail="Insufficient funds")` — ✔ verified

Tests:
- `ledgerlite/tests/test_req03_withdrawals.py` · `test_overdraft_rejected_and_balance_unchanged` — ✔ passed
- `ledgerlite/tests/test_req03_withdrawals.py` · `test_balance_never_goes_negative` — ✔ passed
- `ledgerlite/tests/test_req03_withdrawals.py` · `test_withdrawal_exact_balance_allowed` — ✔ passed
- `ledgerlite/tests/test_req03_withdrawals.py` · `test_concurrent_withdrawals_cannot_overdraw` — ✔ passed
- `ledgerlite/tests/test_req03_withdrawals.py` · `test_withdrawal_reduces_balance` — ✔ passed
- `ledgerlite/tests/test_req03_withdrawals.py` · `test_zero_and_negative_withdrawals_rejected` — ✔ passed

Mutations (deliberate sabotage — each must make a test fail):
- REQ-03-M1: debit without checking the balance — **killed** by `test_overdraft_rejected_and_balance_unchanged`
- REQ-03-M2: accept negative withdrawals (which increase the balance) — **killed** by `test_zero_and_negative_withdrawals_rejected`
- REQ-03-X1: [independent QA R2-03a] debit guard off-by-one: withdrawing the exact balance rejected — **killed** by `test_withdrawal_exact_balance_allowed`
- REQ-03-X2: [independent QA R2-03b] 1-cent overdraft tolerance in the debit guard — **killed** by `test_overdraft_rejected_and_balance_unchanged`
- REQ-03-X3: [independent QA R2-03c] transfer path debits without the balance guard (sender can go negative) — **killed** by `test_insufficient_funds_rejected_without_side_effects`
- REQ-03-X4: [independent QA R2-03d] rejected withdrawal still pays out what is available (balance changes on rejection) — **killed** by `test_overdraft_rejected_and_balance_unchanged`
- REQ-03-B1: always report the debit as successful regardless of whether the balance guard matched, allowing overdrafts to proceed — **killed** by `test_overdraft_rejected_and_balance_unchanged`

### REQ-04 — Atomic transfers

**Risk:** High · **Change in v2.0:** none · **Final status:** 🟠 weak

> A transfer between two accounts is atomic: either both the debit and the credit happen, or neither does.

Acceptance criteria:
- If the credit fails, the debit is rolled back.

Auditor's reasoning: The create_transfer function in services.py (lines 310-341) wraps all mutations — debit, credit, Transfer row insert, flush, and audit write — inside a single try/except block. db.commit() is called only after every step succeeds (line 336). If any step raises (including a credit failure), the except Exception handler at line 339 calls db.rollback() (line 340) and re-raises, guaranteeing no partial state is persisted. The approve_transfer function (lines 368-394) applies the same pattern for the large-transfer approval path: the status update, credit, and audit write are all covered by the same rollback-on-exception guard (lines 392-394). Four dedicated test functions in test_req04_transfer_atomicity.py exercise both the happy path and every failure mode: credit failure rolls back the debit (test_failed_credit_rolls_back_the_debit), audit-write failure rolls back both balance changes (test_failed_audit_write_rolls_back_everything), and approval-time credit failure leaves the transfer in pending_approval state (test_failed_credit_during_approval_rolls_back).

Code evidence:
- `ledgerlite/services.py:310` `try:` — ✘ too_short
- `ledgerlite/services.py:311` `# REQ-04: debit, credit, transfer row and audit entry commit together or not at all.` — ✘ too_short
- `ledgerlite/services.py:312` `if not _debit(db, sender_id, amount):` — ✔ verified
- `ledgerlite/services.py:313` `db.rollback()` — ✔ verified
- `ledgerlite/services.py:316` `_credit(db, recipient_id, amount)` — ✔ verified
- `ledgerlite/services.py:336` `db.commit()` — ✔ verified
- `ledgerlite/services.py:339` `except Exception:` — ✔ verified
- `ledgerlite/services.py:340` `db.rollback()` — ✔ verified
- `ledgerlite/services.py:379` `_credit(db, transfer.recipient_id, transfer.amount)` — ✔ verified
- `ledgerlite/services.py:389` `db.commit()` — ✔ verified
- `ledgerlite/services.py:393` `db.rollback()` — ✔ verified

Tests:
- `ledgerlite/tests/test_req04_transfer_atomicity.py` · `test_successful_transfer_debits_sender_and_credits_recipient` — ✔ passed
- `ledgerlite/tests/test_req04_transfer_atomicity.py` · `test_failed_credit_rolls_back_the_debit` — ✔ passed
- `ledgerlite/tests/test_req04_transfer_atomicity.py` · `test_failed_audit_write_rolls_back_everything` — ✔ passed
- `ledgerlite/tests/test_req04_transfer_atomicity.py` · `test_failed_credit_during_approval_rolls_back` — ✔ passed

Mutations (deliberate sabotage — each must make a test fail):
- REQ-04-M1: commit the debit before the credit (two transactions) — **killed** by `test_failed_credit_rolls_back_the_debit`
- REQ-04-M2: credit the recipient even when the debit failed — **killed** by `test_insufficient_funds_rejected_without_side_effects`
- REQ-04-X1: [independent QA R2-04a] credit errors swallowed (debit kept, transfer 'completed') — **killed** by `test_failed_credit_rolls_back_the_debit`
- REQ-04-X2: [independent QA R2-04b] approval commits 'completed' BEFORE crediting (credit failure on approval = debit without credit) — **killed** by `test_failed_credit_during_approval_rolls_back`
- REQ-04-X3: [independent QA R2-04c] create_transfer commits (not rolls back) on unexpected errors — **killed** by `test_failed_credit_rolls_back_the_debit`
- REQ-04-X4: [independent QA R2-04d] transfer row + balances committed before the audit write — **killed** by `test_failed_audit_write_rolls_back_everything`
- REQ-04-B1: Remove db.rollback() from approve_transfer's exception handler so a credit failure during approval leaves the balance change uncommitted but not rolled back, violating atomicity on the approval path. — **survived**

### REQ-05 — Large-transfer pending approval threshold

**Risk:** High · **Change in v2.0:** changed · **Final status:** ✅ proven

> A transfer of 5,000.00 or more must be held as pending_approval until a second, different user approves it. (v1.0 threshold was 10,000.00.)

Acceptance criteria:
- A transfer of 5,000.00 is held as pending_approval, not completed immediately.
- The initiator cannot approve their own transfer.

Auditor's reasoning: Both acceptance criteria are fully implemented and tested. AC1: the threshold constant is set to 5,000.00 (services.py:29), the comparison uses &gt;= so exactly 5,000.00 triggers pending_approval (services.py:307-308), and test_at_or_above_threshold_is_held parametrises over ["5000.00", "5000.01", "10000.00"] asserting status == "pending_approval" and recipient balance unchanged. AC2: the initiator-cannot-approve guard is present at services.py:355-356, and test_initiator_cannot_approve_own_transfer grants the initiator the approver role then asserts a 403 with "Initiator" in the detail and recipient balance still 0.00.

Code evidence:
- `ledgerlite/services.py:29` `LARGE_TRANSFER_THRESHOLD = Decimal("5000.00") # REQ-05 (v2.0; was 10,000.00 in v1.0)` — ✔ verified
- `ledgerlite/services.py:307` `large = amount >= LARGE_TRANSFER_THRESHOLD # REQ-05` — ✔ verified
- `ledgerlite/services.py:308` `status = "pending_approval" if large else "completed"` — ✔ verified
- `ledgerlite/services.py:355` `if approver_id == transfer.sender_id:` — ✔ verified
- `ledgerlite/services.py:356` `raise HTTPException(status_code=403, detail="Initiator cannot approve their own transfer")` — ✔ verified

Tests:
- `ledgerlite/tests/test_req05_large_transfer_approval.py` · `test_at_or_above_threshold_is_held` — ✔ passed
- `ledgerlite/tests/test_req05_large_transfer_approval.py` · `test_initiator_cannot_approve_own_transfer` — ✔ passed

Mutations (deliberate sabotage — each must make a test fail):
- REQ-05-M1: revert to the old v1.0 threshold of 10,000.00 — **killed** by `test_failed_credit_during_approval_rolls_back`
- REQ-05-M2: exactly 5,000.00 completes without approval — **killed** by `test_failed_credit_during_approval_rolls_back`
- REQ-05-M3: let the initiator approve their own transfer — **killed** by `test_initiator_cannot_approve_own_transfer`
- REQ-05-M4: let the recipient approve the transfer — **killed** by `test_recipient_cannot_approve`
- REQ-05-M5: approve without the approver's PIN — **killed** by `test_approver_needs_correct_pin`
- REQ-05-M6: a transfer can be approved twice (recipient credited twice) — **killed** by `test_double_approval_rejected_and_credits_once`
- REQ-05-M7: any customer can approve (approver role not required) — **killed** by `test_customer_without_approver_role_cannot_approve`
- REQ-05-X1: [independent QA R2-05a] approval authorised with the INITIATOR's PIN (initiator can self-approve by naming any approver_id) — **killed** by `test_approval_needs_the_approvers_own_pin`
- REQ-05-X2: [independent QA R2-05b] held transfers still credit the recipient at creation — **killed** by `test_failed_credit_during_approval_rolls_back`
- REQ-05-X3: [independent QA R2-05c] approval records the initiator as approver — **killed** by `test_second_user_approval_completes_and_credits_once`
- REQ-05-B1: large transfers are marked completed immediately instead of pending_approval — **killed** by `test_failed_credit_during_approval_rolls_back`

### REQ-06 — Audit log for every money movement

**Risk:** High · **Change in v2.0:** none · **Final status:** ✅ proven

> Every money movement (deposit, withdrawal, transfer, approval) writes an audit log entry containing actor, action, amount, account(s) and UTC timestamp. Audit entries cannot be edited.

Acceptance criteria:
- Each money-movement operation adds exactly one audit log entry.
- No update endpoint exists for audit entries.

Auditor's reasoning: Every money-movement operation calls _write_audit (services.py:52-73) which appends exactly one AuditEntry carrying actor_id, action, amount, account_id/related_account_id and a UTC timestamp from _now(). Deposit calls it at line 246, withdrawal at line 263, create_transfer at lines 327-335 (action=transfer_initiated), and approve_transfer at lines 380-388 (action=transfer_approved). The only audit HTTP route is GET /audit (main.py:149); no PUT/PATCH/POST/DELETE route exists, asserted directly by test_no_route_can_change_audit_entries. Both acceptance criteria are guarded by dedicated tests.

Code evidence:
- `ledgerlite/services.py:52` `def _write_audit(` — ✔ verified
- `ledgerlite/services.py:62` `"""Append one audit entry (REQ-06). Entries are never updated or deleted."""` — ✔ verified
- `ledgerlite/services.py:39` `return datetime.datetime.now(datetime.timezone.utc)` — ✔ verified
- `ledgerlite/services.py:246` `_write_audit(db, actor_id=account_id, action="deposit", amount=amount, account_id=account_id)` — ✔ verified
- `ledgerlite/services.py:263` `_write_audit(db, actor_id=account_id, action="withdrawal", amount=amount, account_id=account_id)` — ✔ verified
- `ledgerlite/services.py:327` `_write_audit(` — ✔ verified
- `ledgerlite/services.py:330` `action="transfer_initiated",` — ✔ verified
- `ledgerlite/services.py:380` `_write_audit(` — ✔ verified
- `ledgerlite/services.py:383` `action="transfer_approved",` — ✔ verified
- `ledgerlite/main.py:149` `@app.get("/audit", response_model=list[AuditEntryResponse], dependencies=[Depends(require_admin)])` — ✔ verified

Tests:
- `ledgerlite/tests/test_req06_audit_log.py` · `test_deposit_writes_exactly_one_entry` — ✔ passed
- `ledgerlite/tests/test_req06_audit_log.py` · `test_withdrawal_writes_exactly_one_entry` — ✔ passed
- `ledgerlite/tests/test_req06_audit_log.py` · `test_transfer_writes_exactly_one_entry` — ✔ passed
- `ledgerlite/tests/test_req06_audit_log.py` · `test_approval_writes_exactly_one_entry` — ✔ passed
- `ledgerlite/tests/test_req06_audit_log.py` · `test_held_transfer_writes_exactly_one_entry` — ✔ passed
- `ledgerlite/tests/test_req06_audit_log.py` · `test_audit_collection_cannot_be_modified` — ✔ passed
- `ledgerlite/tests/test_req06_audit_log.py` · `test_existing_entry_cannot_be_modified` — ✔ passed
- `ledgerlite/tests/test_req06_audit_log.py` · `test_no_route_can_change_audit_entries` — ✔ passed
- `ledgerlite/tests/test_req06_audit_log.py` · `test_audit_timestamps_are_real_utc_even_on_a_non_utc_server` — ✔ passed
- `ledgerlite/tests/test_req06_audit_log.py` · `test_rejected_operations_write_no_money_movement_entry` — ✔ passed

Mutations (deliberate sabotage — each must make a test fail):
- REQ-06-M1: deposits are not audited — **killed** by `test_deposit_writes_exactly_one_entry`
- REQ-06-M2: withdrawals write two audit entries — **killed** by `test_withdrawal_writes_exactly_one_entry`
- REQ-06-M3: approval entry records the wrong actor — **killed** by `test_approval_writes_exactly_one_entry`
- REQ-06-M4: audit timestamps lose their UTC marker — **killed** by `test_deposit_writes_exactly_one_entry`
- REQ-06-M5: add an endpoint that edits audit entries — **killed** by `test_existing_entry_cannot_be_modified[PATCH]`
- REQ-06-M6: deposit audit entry records the wrong actor — **killed** by `test_deposit_allowed_after_kyc`
- REQ-06-M7: approvals are not audited — **killed** by `test_approval_writes_exactly_one_entry`
- REQ-06-X1: [independent QA R2-06a] audit timestamp is naive server-local time, serialised with a 'Z' (UTC+5 here -&gt; 5h wrong) — **killed** by `test_audit_timestamps_are_real_utc_even_on_a_non_utc_server`
- REQ-06-X2: [independent QA R2-06b] PATCH /admin/audit/{id} lets compliance edit an audit entry — **killed** by `test_route_inventory_is_exactly_the_reviewed_set`
- REQ-06-X3: [independent QA R2-06c] held (&gt;=5,000) transfers write TWO audit entries — **killed** by `test_held_transfer_writes_exactly_one_entry`
- REQ-06-B1: transfer audit entry records wrong action name; test_transfer_writes_exactly_one_entry asserts action == 'transfer_initiated' — **killed** by `test_failed_audit_write_rolls_back_everything`

### REQ-07 — Account lockout after failed PIN attempts

**Risk:** Medium · **Change in v2.0:** none · **Final status:** ✅ proven

> An account is locked after 5 consecutive failed PIN attempts. A locked account cannot move money.

Acceptance criteria:
- The 5th wrong PIN locks the account.
- A correct PIN entered before the 5th failure resets the counter.

Auditor's reasoning: The implementation in _check_pin() (services.py:95-114) enforces all acceptance criteria. On each failed PIN attempt the counter is incremented and committed immediately (lines 106, 111); on the 5th failure (&gt;= MAX_FAILED_PINS=5, line 107) account.locked is set to True and HTTP 423 is raised (lines 108-113). A correct PIN resets failed_pin_attempts to 0 and commits (lines 101-103). Every call site routes through _check_pin so a locked account always receives HTTP 423 before any money movement occurs. The test suite covers AC1 (test_fifth_wrong_pin_locks_account), AC2 (test_correct_pin_resets_counter), persistence across requests, brute-force stopping, and all four PIN-protected endpoints.

Code evidence:
- `ledgerlite/services.py:30` `MAX_FAILED_PINS = 5 # REQ-07` — ✔ verified
- `ledgerlite/services.py:97` `if account.locked:` — ✔ verified
- `ledgerlite/services.py:98` `raise HTTPException(status_code=423, detail="Account is locked due to too many failed PIN attempts")` — ✔ verified
- `ledgerlite/services.py:102` `account.failed_pin_attempts = 0 # a correct PIN resets the counter` — ✔ verified
- `ledgerlite/services.py:106` `account.failed_pin_attempts += 1` — ✔ verified
- `ledgerlite/services.py:107` `locked_now = account.failed_pin_attempts >= MAX_FAILED_PINS` — ✔ verified
- `ledgerlite/services.py:109` `account.locked = True` — ✔ verified
- `ledgerlite/services.py:111` `db.commit() # persist the counter / lock even though the request fails` — ✔ verified
- `ledgerlite/services.py:113` `raise HTTPException(status_code=423, detail="Account locked after too many failed PIN attempts")` — ✔ verified

Tests:
- `ledgerlite/tests/test_req07_pin_lockout.py` · `test_failed_attempts_are_persisted_between_requests` — ✔ passed
- `ledgerlite/tests/test_req07_pin_lockout.py` · `test_fifth_wrong_pin_locks_account` — ✔ passed
- `ledgerlite/tests/test_req07_pin_lockout.py` · `test_locked_account_cannot_move_money_anywhere` — ✔ passed
- `ledgerlite/tests/test_req07_pin_lockout.py` · `test_correct_pin_resets_counter` — ✔ passed
- `ledgerlite/tests/test_req07_pin_lockout.py` · `test_brute_force_is_stopped` — ✔ passed
- `ledgerlite/tests/test_req07_pin_lockout.py` · `test_fifth_wrong_pin_locks_on_every_endpoint` — ✔ passed
- `ledgerlite/tests/test_req07_pin_lockout.py` · `test_correct_pin_on_every_endpoint_resets_the_counter` — ✔ passed

Mutations (deliberate sabotage — each must make a test fail):
- REQ-07-M1: lock only after 6 failures — **killed** by `test_fifth_wrong_pin_locks_account`
- REQ-07-M2: do not persist the failure counter (the original lockout bug) — **killed** by `test_failed_attempts_are_persisted_between_requests`
- REQ-07-M3: a correct PIN no longer resets the counter — **killed** by `test_correct_pin_resets_counter`
- REQ-07-M4: locked accounts can still move money — **killed** by `test_fifth_wrong_pin_locks_account`
- REQ-07-M5: any PIN is accepted — **killed** by `test_approver_needs_correct_pin`
- REQ-07-X1: [independent QA R2-07a] POST /transfers checks the PIN without counting failures — **killed** by `test_fifth_wrong_pin_locks_on_every_endpoint[transfer]`
- REQ-07-X2: [independent QA R2-07b] withdraw checks the PIN without counting failures — **killed** by `test_fifth_wrong_pin_locks_on_every_endpoint[withdraw]`
- REQ-07-X3: [independent QA R2-07c] GET /accounts/{id} and /statement check the PIN without counting failures — **killed** by `test_fifth_wrong_pin_locks_on_every_endpoint[read]`
- REQ-07-B1: counter never increments — lockout can never be reached — **killed** by `test_failed_attempts_are_persisted_between_requests`

### REQ-08 — Exact decimal arithmetic

**Risk:** Medium · **Change in v2.0:** none · **Final status:** ✅ proven

> All monetary values are stored and calculated as exact decimals (never floating point) and returned with exactly 2 decimal places.

Acceptance criteria:
- 0.10 + 0.20 equals 0.30 exactly.
- The API returns monetary values formatted as strings with exactly 2 decimal places (e.g. "0.30").

Auditor's reasoning: Exact decimal arithmetic is enforced end-to-end by three interlocking mechanisms. (1) Storage: the custom Money TypeDecorator (models.py:13-34) stores every monetary value as an INTEGER count of cents (impl = Integer), converting on write via Decimal * 100 and on read via Decimal(int(value)) / 100 with an explicit .quantize(CENT) — floating-point representation is structurally impossible at the DB layer. (2) Input validation: _validate_amount (schemas.py:29-37) rejects any Decimal whose precision exceeds 2 places with a ValueError rather than silently rounding, and the Amount annotated type gates every API amount field. (3) Serialisation: _money_str (schemas.py:55-56) formats every outgoing monetary Decimal with f'{value:.2f}', and AccountResponse, TransferResponse and AuditEntryResponse each apply it via @field_serializer. The canonical AC (0.10 + 0.20 = 0.30) is directly asserted by test_point_one_plus_point_two_equals_point_three; 2-decimal string output is asserted by test_amounts_are_returned_with_exactly_two_decimals and test_transfer_amount_is_returned_as_a_two_decimal_string; integer-only DB storage is verified by test_money_is_stored_as_integer_cents_not_real; and ORM round-trip exactness is confirmed by test_values_read_back_from_the_database_are_exact_decimals.

Code evidence:
- `ledgerlite/models.py:13` `class Money(TypeDecorator):` — ✔ verified
- `ledgerlite/models.py:29` `return int((value * 100).to_integral_value(rounding=ROUND_HALF_EVEN))` — ✔ verified
- `ledgerlite/models.py:34` `return (Decimal(int(value)) / 100).quantize(CENT)` — ✔ verified
- `ledgerlite/schemas.py:9` `CENT = Decimal("0.01")` — ✔ verified
- `ledgerlite/schemas.py:35` `if value != value.quantize(CENT):` — ✔ verified
- `ledgerlite/schemas.py:55` `def _money_str(value: Decimal | None) -> str | None:` — ✔ verified
- `ledgerlite/schemas.py:122` `@field_serializer("balance")` — ✔ verified

Tests:
- `ledgerlite/tests/test_req08_exact_decimals.py` · `test_point_one_plus_point_two_equals_point_three` — ✔ passed
- `ledgerlite/tests/test_req08_exact_decimals.py` · `test_amounts_are_returned_with_exactly_two_decimals` — ✔ passed
- `ledgerlite/tests/test_req08_exact_decimals.py` · `test_money_is_stored_as_integer_cents_not_real` — ✔ passed
- `ledgerlite/tests/test_req08_exact_decimals.py` · `test_more_than_two_decimals_is_rejected_not_rounded` — ✔ passed
- `ledgerlite/tests/test_req08_exact_decimals.py` · `test_classic_float_traps_are_exact` — ✔ passed
- `ledgerlite/tests/test_req08_exact_decimals.py` · `test_many_small_amounts_add_up_exactly` — ✔ passed
- `ledgerlite/tests/test_req08_exact_decimals.py` · `test_transfer_amount_is_returned_as_a_two_decimal_string` — ✔ passed
- `ledgerlite/tests/test_req08_exact_decimals.py` · `test_values_read_back_from_the_database_are_exact_decimals` — ✔ passed
- `ledgerlite/tests/test_req08_exact_decimals.py` · `test_daily_total_arithmetic_is_exact` — ✔ passed

Mutations (deliberate sabotage — each must make a test fail):
- REQ-08-M1: store money as floating point (REAL) — **killed** by `test_money_is_stored_as_integer_cents_not_real`
- REQ-08-M2: convert money through float — **killed** by `test_classic_float_traps_are_exact`
- REQ-08-M3: silently round amounts with more than 2 decimals — **killed** by `test_sub_cent_amount_cannot_dodge_the_threshold`
- REQ-08-X1: [independent QA R2-08a] TransferResponse.amount returned as a JSON float (100.0) — **killed** by `test_transfer_amount_is_returned_as_a_two_decimal_string`
- REQ-08-X2: [independent QA R2-08b] money read back from the DB through float division (cents / 100) — **killed** by `test_values_read_back_from_the_database_are_exact_decimals`
- REQ-08-X3: [independent QA R2-08c] daily outgoing total converted through float — **killed** by `test_daily_total_arithmetic_is_exact`
- REQ-08-B1: AccountResponse.balance serialised as a JSON float instead of a 2-decimal string — **killed** by `test_create_account_success`

### REQ-09 — Daily outgoing transfer cap

**Risk:** High · **Change in v2.0:** new · **Final status:** ✅ proven

> Total outgoing transfers per account must not exceed 20,000.00 per UTC calendar day.

Acceptance criteria:
- A transfer that would take the day's total outgoing above 20,000.00 is rejected.

Auditor's reasoning: The implementation enforces a hard daily outgoing transfer cap of 20,000.00 per UTC calendar day. DAILY_TRANSFER_CAP is defined as Decimal('20000.00') at module level (services.py:31). The helper outgoing_total_today() (services.py:152-161) sums all transfers by the sender with status 'completed' or 'pending_approval' (the _COUNTED_STATUSES tuple at line 34) since the UTC midnight boundary computed by _utc_day_start() (services.py:147-149). In the transfer service (services.py:301), the guard raises HTTP 400 before any balance mutation when outgoing_total_today + amount &gt; DAILY_TRANSFER_CAP. Nine dedicated tests in test_req09_daily_cap.py exercise: exact boundary acceptance (20,000.00), one-cent overage rejection, three-transfer block, per-sender isolation, rejected transfers not counting, yesterday's transfers not counting, midnight boundary precision, UTC day (not server-local day), and concurrent transfer serialisation.

Code evidence:
- `ledgerlite/services.py:31` `DAILY_TRANSFER_CAP = Decimal("20000.00") # REQ-09` — ✔ verified
- `ledgerlite/services.py:34` `_COUNTED_STATUSES = ("completed", "pending_approval")` — ✔ verified
- `ledgerlite/services.py:147` `def _utc_day_start(moment: datetime.datetime) -> datetime.datetime:` — ✔ verified
- `ledgerlite/services.py:148` `day = moment.astimezone(datetime.timezone.utc).date()` — ✔ verified
- `ledgerlite/services.py:149` `return datetime.datetime(day.year, day.month, day.day, tzinfo=datetime.timezone.utc)` — ✔ verified
- `ledgerlite/services.py:152` `def outgoing_total_today(db: Session, sender_id: int, now: datetime.datetime) -> Decimal:` — ✔ verified
- `ledgerlite/services.py:157` `Transfer.status.in_(_COUNTED_STATUSES),` — ✔ verified
- `ledgerlite/services.py:158` `Transfer.created_at >= _utc_day_start(now),` — ✔ verified
- `ledgerlite/services.py:301` `if outgoing_total_today(db, sender_id, now) + amount > DAILY_TRANSFER_CAP:` — ✔ verified

Tests:
- `ledgerlite/tests/test_req09_daily_cap.py` · `test_exactly_20000_accepted` — ✔ passed
- `ledgerlite/tests/test_req09_daily_cap.py` · `test_one_cent_over_the_cap_rejected` — ✔ passed
- `ledgerlite/tests/test_req09_daily_cap.py` · `test_third_of_three_7000_transfers_blocked` — ✔ passed
- `ledgerlite/tests/test_req09_daily_cap.py` · `test_cap_is_per_sender` — ✔ passed
- `ledgerlite/tests/test_req09_daily_cap.py` · `test_rejected_transfers_do_not_count` — ✔ passed
- `ledgerlite/tests/test_req09_daily_cap.py` · `test_yesterdays_transfers_do_not_count` — ✔ passed
- `ledgerlite/tests/test_req09_daily_cap.py` · `test_concurrent_transfers_cannot_exceed_the_cap` — ✔ passed
- `ledgerlite/tests/test_req09_daily_cap.py` · `test_transfer_just_after_midnight_counts_for_the_whole_day` — ✔ passed
- `ledgerlite/tests/test_req09_daily_cap.py` · `test_the_day_is_the_utc_day_not_the_server_local_day` — ✔ passed

Mutations (deliberate sabotage — each must make a test fail):
- REQ-09-M1: raise the daily cap by one cent — **killed** by `test_one_cent_over_the_cap_rejected`
- REQ-09-M2: pending transfers no longer count toward the cap — **killed** by `test_one_cent_over_the_cap_rejected`
- REQ-09-M3: count yesterday's transfers too — **killed** by `test_yesterdays_transfers_do_not_count`
- REQ-09-M4: stop serialising transactions (concurrent transfers race the cap) — **killed** by `test_concurrent_duplicate_signups_give_one_account`
- REQ-09-M5: drop the UTC-day window (cap becomes all-time) — **killed** by `test_yesterdays_transfers_do_not_count`
- REQ-09-X1: [independent QA R2-09a] UTC day start keeps the current microseconds (transfers in the first instant after midnight not counted) — **killed** by `test_transfer_just_after_midnight_counts_for_the_whole_day`
- REQ-09-X2: [independent QA R2-09b] day boundary uses the server-local date (UTC+5: cap disabled 19:00-24:00 UTC) — **killed** by `test_the_day_is_the_utc_day_not_the_server_local_day`
- REQ-09-X3: [independent QA R2-09c] held (&gt;=5,000) transfers exempt from the daily cap — **killed** by `test_third_of_three_7000_transfers_blocked`
- REQ-09-X4: [independent QA R2-09d] cap check ignores the new transfer's own amount — **killed** by `test_third_of_three_7000_transfers_blocked`
- REQ-09-B1: outgoing_total_today always returns zero so the cap check never accumulates and every transfer is allowed regardless of the day's running total — **killed** by `test_one_cent_over_the_cap_rejected`

### REQ-10 — Sanctions list blocking

**Risk:** High · **Change in v2.0:** new · **Final status:** ✅ proven

> Transfers to an account whose country code is on the sanctions list (KP, IR, SY, CU) are blocked and logged.

Acceptance criteria:
- A transfer to a sanctioned country is rejected with reason "sanctions".
- An audit entry is written for the blocked transfer.

Auditor's reasoning: The implementation at services.py:279-294 performs sanctions screening before any other business logic (KYC, daily cap). It checks both sender and recipient country codes against SANCTIONED_COUNTRIES = frozenset({"KP", "IR", "SY", "CU"}) defined at line 32. On a hit it writes a 'sanctions_blocked' audit entry recording actor_id (sender), amount, account_id, related_account_id, and the matching country code(s) in detail, then commits and raises HTTPException(400, detail="sanctions"). AC1 (rejected with reason "sanctions") is satisfied by line 294; AC2 (audit entry written for blocked transfer) is satisfied by lines 284-293. The test suite covers all four sanctioned codes for both sender-side and recipient-side screening, lower-case normalization, screening before KYC, screening before daily cap, that large transfers are blocked not held, that the sender is the recorded actor, and that clean countries are not blocked.

Code evidence:
- `ledgerlite/services.py:32` `SANCTIONED_COUNTRIES = frozenset({"KP", "IR", "SY", "CU"}) # REQ-10` — ✔ verified
- `ledgerlite/services.py:280` `blocked = sorted(` — ✔ verified
- `ledgerlite/services.py:281` `{c for c in (sender.country_code, recipient.country_code) if c in SANCTIONED_COUNTRIES}` — ✔ verified
- `ledgerlite/services.py:284` `_write_audit(` — ✔ verified
- `ledgerlite/services.py:287` `action="sanctions_blocked",` — ✔ verified
- `ledgerlite/services.py:294` `raise HTTPException(status_code=400, detail="sanctions")` — ✔ verified

Tests:
- `ledgerlite/tests/test_req10_sanctions.py` · `test_transfer_to_sanctioned_recipient_blocked_and_logged[KP]` — ✔ passed
- `ledgerlite/tests/test_req10_sanctions.py` · `test_transfer_to_sanctioned_recipient_blocked_and_logged[IR]` — ✔ passed
- `ledgerlite/tests/test_req10_sanctions.py` · `test_transfer_to_sanctioned_recipient_blocked_and_logged[SY]` — ✔ passed
- `ledgerlite/tests/test_req10_sanctions.py` · `test_transfer_to_sanctioned_recipient_blocked_and_logged[CU]` — ✔ passed
- `ledgerlite/tests/test_req10_sanctions.py` · `test_transfer_from_sanctioned_sender_blocked_and_logged[KP]` — ✔ passed
- `ledgerlite/tests/test_req10_sanctions.py` · `test_transfer_from_sanctioned_sender_blocked_and_logged[IR]` — ✔ passed
- `ledgerlite/tests/test_req10_sanctions.py` · `test_transfer_from_sanctioned_sender_blocked_and_logged[SY]` — ✔ passed
- `ledgerlite/tests/test_req10_sanctions.py` · `test_transfer_from_sanctioned_sender_blocked_and_logged[CU]` — ✔ passed
- `ledgerlite/tests/test_req10_sanctions.py` · `test_lower_case_country_code_is_still_screened` — ✔ passed
- `ledgerlite/tests/test_req10_sanctions.py` · `test_sanctions_hit_is_logged_even_before_kyc` — ✔ passed
- `ledgerlite/tests/test_req10_sanctions.py` · `test_clean_countries_are_not_blocked` — ✔ passed
- `ledgerlite/tests/test_req10_sanctions.py` · `test_large_transfer_to_sanctioned_country_is_blocked_not_held` — ✔ passed
- `ledgerlite/tests/test_req10_sanctions.py` · `test_sanctions_entry_records_the_sender_as_actor` — ✔ passed
- `ledgerlite/tests/test_req10_sanctions.py` · `test_screening_happens_before_the_daily_cap` — ✔ passed

Mutations (deliberate sabotage — each must make a test fail):
- REQ-10-M1: drop CU from the sanctions list — **killed** by `test_transfer_to_sanctioned_recipient_blocked_and_logged[CU]`
- REQ-10-M2: screen only the sender, not the recipient — **killed** by `test_transfer_to_sanctioned_recipient_blocked_and_logged[KP]`
- REQ-10-M3: log blocks under a different action name — **killed** by `test_transfer_to_sanctioned_recipient_blocked_and_logged[KP]`
- REQ-10-M4: block the transfer but lose the audit entry — **killed** by `test_transfer_to_sanctioned_recipient_blocked_and_logged[KP]`
- REQ-10-X1: [independent QA R2-10a] held (&gt;=5,000) transfers skip sanctions screening (approval never re-screens) — **killed** by `test_large_transfer_to_sanctioned_country_is_blocked_not_held`
- REQ-10-X2: [independent QA R2-10b] insufficient-funds pre-check before screening: unfunded attempts to KP/IR/SY/CU are not logged — **killed** by `test_transfer_sender_blocked_before_kyc`
- REQ-10-X3: [independent QA R2-10d] daily-cap (velocity) check moved before screening: capped senders' KP/IR/SY/CU attempts are not logged — **killed** by `test_screening_happens_before_the_daily_cap`
- REQ-10-X4: [independent QA R2-10c] sanctions audit entry names the recipient as actor — **killed** by `test_sanctions_entry_records_the_sender_as_actor`
- REQ-10-B1: change rejection detail from 'sanctions' to 'blocked' so callers cannot distinguish a sanctions block from a generic block — **killed** by `test_transfer_to_sanctioned_recipient_blocked_and_logged[KP]`

### REQ-11 — Masked account numbers in statements

**Risk:** Medium · **Change in v2.0:** new · **Final status:** ✅ proven

> Account statements must mask account numbers, showing only the last 4 digits (e.g. ****1234).

Acceptance criteria:
- No full account number appears in any statement response.
- Account numbers in statements are masked, showing only the last 4 digits.

Auditor's reasoning: The implementation provides a dedicated mask_account_number helper (schemas.py:66-68) that replaces all but the last 4 digits with '****'. A specialised StatementAccountResponse subclass (schemas.py:170-175) overrides the account_number field serialiser to call that helper, ensuring every statement response automatically masks the number. The /accounts/{id}/statement endpoint (main.py:111-114) is bound exclusively to StatementResponse, which requires a StatementAccountResponse for its account field (schemas.py:178-180), so the masking is structural and cannot be bypassed. Five dedicated tests confirm: (1) the masked value matches ****DDDD and preserves the last 4 digits; (2) no full account number (including counterparty numbers) appears anywhere in the statement body; (3) no full account number appears in response headers; (4) the non-statement owner endpoint still returns the full number; and (5) the endpoint requires a valid PIN. All acceptance criteria are satisfied.

Code evidence:
- `ledgerlite/schemas.py:66` `def mask_account_number(number: str) -> str:` — ✔ verified
- `ledgerlite/schemas.py:68` `return "****" + number[-4:]` — ✔ verified
- `ledgerlite/schemas.py:170` `class StatementAccountResponse(AccountResponse):` — ✔ verified
- `ledgerlite/schemas.py:173` `@field_serializer("account_number")` — ✔ verified
- `ledgerlite/schemas.py:175` `return mask_account_number(v)` — ✔ verified
- `ledgerlite/schemas.py:178` `class StatementResponse(BaseModel):` — ✔ verified
- `ledgerlite/schemas.py:179` `account: StatementAccountResponse` — ✔ verified
- `ledgerlite/main.py:111` `@app.get("/accounts/{account_id}/statement", response_model=StatementResponse)` — ✔ verified
- `ledgerlite/main.py:114` `return StatementResponse(account=account, transactions=transactions)` — ✔ verified

Tests:
- `ledgerlite/tests/test_req11_statement_masking.py` · `test_statement_masks_account_number_like_the_spec_example` — ✔ passed
- `ledgerlite/tests/test_req11_statement_masking.py` · `test_no_full_account_number_anywhere_in_a_statement` — ✔ passed
- `ledgerlite/tests/test_req11_statement_masking.py` · `test_no_full_account_number_in_statement_headers_either` — ✔ passed
- `ledgerlite/tests/test_req11_statement_masking.py` · `test_owner_account_view_is_not_a_statement` — ✔ passed
- `ledgerlite/tests/test_req11_statement_masking.py` · `test_statement_requires_the_account_pin` — ✔ passed

Mutations (deliberate sabotage — each must make a test fail):
- REQ-11-M1: mask with 6 stars instead of the spec's **** — **killed** by `test_statement_masks_account_number_like_the_spec_example`
- REQ-11-M2: statements show the full account number — **killed** by `test_statement_masks_account_number_like_the_spec_example`
- REQ-11-M3: reveal 5 digits instead of 4 — **killed** by `test_statement_masks_account_number_like_the_spec_example`
- REQ-11-X1: [independent QA R2-11a] mask shows the FIRST 4 digits — **killed** by `test_statement_masks_account_number_like_the_spec_example`
- REQ-11-X2: [independent QA R2-11b] statement lines embed the counterparty's full account record — **killed** by `test_no_full_account_number_anywhere_in_a_statement`
- REQ-11-X3: [independent QA R2-11c] statement response carries the full account number in a Content-Disposition filename — **killed** by `test_no_full_account_number_in_statement_headers_either`
- REQ-11-B1: bypass masking entirely — serialize_account_number returns the raw account number — **killed** by `test_statement_masks_account_number_like_the_spec_example`

### REQ-12 — Audit log retention — no deletion

**Risk:** Medium · **Change in v2.0:** none · **Final status:** ✅ proven

> Audit log entries must never be deleted through the API (7-year retention).

Acceptance criteria:
- No delete endpoint exists for audit entries.
- A DELETE request to audit entries returns HTTP 405 or 404.

Auditor's reasoning: No DELETE route exists for audit entries anywhere in the API. ledgerlite/main.py line 147 explicitly documents this design intent ('read-only by design: no update or delete route exists — REQ-06, REQ-12'), and the only audit endpoint defined is GET /audit (line 149). Six tests in test_req12_audit_retention.py collectively verify: (1) DELETE /audit returns 405, (2) DELETE /audit/{id} returns 404 or 405, (3) no DELETE route is registered on any audit path, (4) the full route inventory matches the approved read-only-audit set exactly, (5) deleting an account cannot remove its audit trail, and (6) known purge paths (/admin/audit/purge, /audit/purge) return 404 or 405. All acceptance criteria are satisfied.

Code evidence:
- `ledgerlite/main.py:147` `# ── audit (read-only by design: no update or delete route exists — REQ-06, REQ-12) ──` — ✘ too_short
- `ledgerlite/main.py:149` `@app.get("/audit", response_model=list[AuditEntryResponse], dependencies=[Depends(require_admin)])` — ✔ verified

Tests:
- `ledgerlite/tests/test_req12_audit_retention.py` · `test_delete_audit_collection_returns_405` — ✔ passed
- `ledgerlite/tests/test_req12_audit_retention.py` · `test_delete_existing_audit_entry_is_refused_and_entry_survives` — ✔ passed
- `ledgerlite/tests/test_req12_audit_retention.py` · `test_no_delete_route_exists_for_audit_entries` — ✔ passed
- `ledgerlite/tests/test_req12_audit_retention.py` · `test_route_inventory_is_exactly_the_reviewed_set` — ✔ passed
- `ledgerlite/tests/test_req12_audit_retention.py` · `test_deleting_an_account_cannot_remove_its_audit_trail` — ✔ passed
- `ledgerlite/tests/test_req12_audit_retention.py` · `test_no_purge_action_removes_audit_entries` — ✔ passed

Mutations (deliberate sabotage — each must make a test fail):
- REQ-12-M1: add an endpoint that deletes audit entries — **killed** by `test_existing_entry_cannot_be_modified[DELETE]`
- REQ-12-M2: add an endpoint that purges the whole audit log — **killed** by `test_audit_collection_cannot_be_modified[DELETE]`
- REQ-12-X1: [independent QA R2-12a] DELETE /accounts/{id} (account closure) deletes that account's audit entries — **killed** by `test_route_inventory_is_exactly_the_reviewed_set`
- REQ-12-X2: [independent QA R2-12b] POST /admin/audit/purge?older_than_days=N deletes audit entries — **killed** by `test_route_inventory_is_exactly_the_reviewed_set`
- REQ-12-X3: [independent QA R2-12c] DELETE /admin/audit/{id} — **killed** by `test_no_delete_route_exists_for_audit_entries`

## 5. Human compliance sign-offs

| When | Where | Scope | Statement |
|---|---|---|---|
| 2026-09-25T21:46:52+05:00 | IBM Bob task03 | fix plan (round 1) | Approved — compliance sign-off by Shehar Bano |

## 6. IBM Bob sessions

| Task | What | Started | Minutes | Bobcoins | Parallel subagents |
|---|---|---|---|---|---|
| task01 | Create a new Python project called "solotrace" in this folder with thi | 2026-09-25T20:08:10+05:00 | 71.7 | 15.44 | 12 (in 112.7 s) |
| task02 | Build the SoloTrace CLI (python -m solotrace) in the solotrace package | 2026-09-25T21:26:20+05:00 | 11.8 | 3.14 | — |
| task03 | Stage 3 — FIX. Act as the SoloTrace Auditor and follow .bob/rules-solo | 2026-09-25T21:42:07+05:00 | 15.2 | 5.53 | 12 (in 37.5 s) |
| task04 | Polish SoloTrace and build the public demo dashboard. | 2026-09-25T22:04:12+05:00 | 13.8 | 7.48 | — |
| task05 | Final audit — task 5. Use the solotrace-audit skill and follow .bob/ru | 2026-09-26T06:23:09+05:00 | 36.3 | 7.75 | 12 (in 2053.3 s) |

Screenshots of each task's session summary are in `bob_sessions/`.

## 7. Method and limitations

- Verdicts are written by AI subagents (one per requirement). SoloTrace never trusts them blindly: every code citation is re-located in the audited commit (verbatim, re-wrapped or with a stripped comment), citations outside the repository are rejected, and cited tests must exist and pass.
- Mutation testing shows the tests *guard* each requirement; it cannot prove the absence of every possible defect.
- LedgerLite is a deliberately small sample API (SQLite, PIN-based access control, an admin token instead of identity management, a static sanctions list); it is an audit target, not a production banking system.
- Held transfers have no reject/expiry path yet; funds stay reserved until approved.

