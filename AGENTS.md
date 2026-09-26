# AGENTS.md

Loaded automatically by every IBM Bob task in this workspace.

## What this repository is

**SoloTrace** audits a codebase against a requirements document and proves every requirement.
IBM Bob does the judgement work (read the spec, audit each requirement with a subagent, fix after
a human sign-off); the `solotrace` Python package checks everything Bob produces.

**LedgerLite** (`ledgerlite/`) is the audit target: a small FastAPI + SQLite payments API that
must meet `demo-data/LedgerLite-Requirements-v2.0.pdf` (12 requirements, REQ-01 … REQ-12).

## Layout

```
.bob/
  custom_modes.yaml             SoloTrace Auditor mode (slug: solotrace)
  rules-solotrace/              evidence, verdict, mutation and sign-off rules
  skills/solotrace-audit/       reusable skill: READ → AUDIT → PROVE → SIGN-OFF/FIX
ledgerlite/                     the audited payments API
  services.py                   business rules (limits, sanctions, lockout, approvals)
  models.py · schemas.py · db.py · security.py · main.py
  tests/test_reqNN_*.py         one test module per requirement
solotrace/                      the auditor's deterministic engine
  verify.py    evidence verifier (re-finds every quote in the audited commit)
  testrun.py   runs the test suite, records every result
  prove.py     mutation testing (sabotage must be caught by the tests)
  matrix.py    evidence-based scoring        report.py   AUDIT_REPORT.md
  dashboard.py docs/index.html               pipeline.py `python -m solotrace run`
demo-data/                      the requirements PDF
out/          final audit: requirements.json, verdicts/, mutations/, results
out-round1/   round 1 (after Bob's first fixes)     out-before/  baseline audit
bob_sessions/ IBM Bob task session summaries, sessions.json, signoffs.json
scripts/      export_bob_sessions.py, rebuild_history.py
docs/         GitHub Pages dashboard
```

## Commands

```bash
.venv/bin/pytest -q                                   # all tests (LedgerLite + SoloTrace)
.venv/bin/python -m solotrace run --auditor "<who wrote the verdicts>"   # full evidence pipeline
.venv/bin/python -m solotrace verify --out out --check                  # read-only citation check
.venv/bin/python -m solotrace prove --out out                          # mutation testing only
LEDGERLITE_ADMIN_TOKEN=dev .venv/bin/uvicorn ledgerlite.main:app --port 8000   # run the API
```

## Rules for agents

- In an audit, never change application code or tests; quote code verbatim.
- Fix only after the human answers "Approve these fixes? (compliance sign-off)".
- A requirement is done only when `python -m solotrace run` reports it **proven**.
- Test data is synthetic: use `@example.com` emails, no real people or client data.
- Never write credentials into the repository.
