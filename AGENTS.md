# AGENTS.md

## What is SoloTrace?

SoloTrace is a requirements-traceability auditor for regulated software.
It reads a specification document, searches the codebase for each requirement's
implementation and test coverage, and produces machine-readable verdicts that
prove — or disprove — compliance.

Designed for domains where traceability is mandatory: banking, insurance, healthcare.

---

## Repository layout

```
.
├── solotrace/                  # SoloTrace auditing tool (Python package)
│   ├── __init__.py
│   ├── schemas.py              # stdlib-only validators for requirement/verdict JSON
│   ├── schemas/
│   │   ├── requirement.schema.json   # JSON Schema (draft 2020-12)
│   │   └── verdict.schema.json
│   └── tests/
│       └── test_schemas.py
├── ledgerlite/                 # Sample banking API audited by SoloTrace
│   ├── main.py                 # FastAPI app + routes
│   ├── db.py                   # SQLAlchemy engine / session
│   ├── models.py               # Account, Transfer, AuditEntry
│   ├── schemas.py              # Pydantic I/O models
│   ├── security.py             # PBKDF2-HMAC-SHA256 PIN hashing
│   ├── services.py             # Business logic
│   └── tests/
│       ├── conftest.py
│       ├── test_spec1_accounts_kyc.py
│       ├── test_spec2_deposit_limits.py
│       ├── test_spec3_withdrawals.py
│       └── test_spec4_transfer_atomicity.py
├── demo-data/                  # Specification documents (PDF)
├── out/                        # SoloTrace outputs
│   ├── requirements.json       # Extracted requirements (generated)
│   ├── matrix.json             # Traceability matrix (generated)
│   └── verdicts/               # One JSON file per requirement (generated)
├── docs/                       # Static dashboard (GitHub Pages)
├── bob_sessions/               # PNG screenshots of Bob task session summaries
├── .bob/
│   ├── custom_modes.yaml       # SoloTrace Auditor custom mode
│   ├── rules-solotrace/        # Mode-specific audit rules
│   │   └── 01-audit-rules.md
│   └── skills/
│       └── solotrace-audit/    # Reusable Bob skill
│           ├── SKILL.md
│           ├── requirement.schema.json
│           ├── verdict.schema.json
│           └── audit-checklist.md
├── requirements.txt
├── README.md
├── LICENSE
└── AGENTS.md                   # This file
```

---

## Running the tests

```bash
# All tests (LedgerLite API + SoloTrace schema validators)
.venv/bin/pytest -q

# LedgerLite only
.venv/bin/pytest ledgerlite/tests/ -q

# SoloTrace only
.venv/bin/pytest solotrace/tests/ -q
```

All tests must pass before any commit.

---

## Running LedgerLite

```bash
source .venv/bin/activate
uvicorn ledgerlite.main:app --reload --port 8000
# Docs: http://localhost:8000/docs
```

---

## Audit rules summary

| Rule | Description |
|------|-------------|
| **Cite everything** | Every verdict must include `code_evidence` (file, line, snippet). |
| **Four statuses** | `covered` · `untested` · `contradicts` · `missing` — see definitions in `.bob/rules-solotrace/01-audit-rules.md`. |
| **No audit-time edits** | Application code and tests are read-only during an audit pass. |
| **Fix workflow** | Write failing test → fix code → full suite green → no test weakened. |
| **Validated output** | All JSON output passes `validate_requirement()` / `validate_verdict()` before being written. |

---

## Bob custom mode

Switch to the **SoloTrace Auditor** mode in Bob to activate the audit rules automatically.
The mode slug is `solotrace`; rules are loaded from `.bob/rules-solotrace/`.

To run a full audit, activate the **solotrace-audit** skill.
