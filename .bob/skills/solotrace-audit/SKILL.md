---
name: solotrace-audit
description: >-
  Audit a codebase against a requirements document and prove every requirement:
  read the spec, audit each requirement with its own subagent (verbatim file:line
  evidence), then let the solotrace CLI verify the evidence, run the tests and
  sabotage each requirement to prove the tests really guard it. Use for compliance,
  traceability and release-readiness audits.
---

# SoloTrace audit skill

Works on any repository with a specification document (PDF, DOCX or Markdown) and a test suite.
Run it in the **SoloTrace Auditor** mode so `.bob/rules-solotrace/` applies.

Supporting files in this folder:
- `requirement.schema.json`, `verdict.schema.json` — the JSON formats (validated by `solotrace/schemas.py`)
- `mutation.example.json` — the format of a sabotage attempt
- `audit-checklist.md` — the checklist below, for tracking progress

## Phase 1 — READ

1. Read the specification with your own document understanding.
2. Write `out/requirements.json`: one object per requirement (`id` `REQ-01`…, verbatim `text`,
   every acceptance criterion as its own string, `risk`, `change` = `none` | `changed` | `new`).
3. Validate with `validate_requirement()`; IDs must be unique and sequential.

## Phase 2 — AUDIT (one subagent per requirement, in parallel)

Give each subagent one requirement, the verdict schema and the rules. Each subagent:
1. Finds the implementing code and the tests that assert each acceptance criterion.
2. Decides `covered` / `untested` / `contradicts` / `missing` (doubt → `untested`).
3. Cites code **verbatim** (open the file, copy the line) and cites only real test functions.
4. Writes `out/verdicts/<ID>.json` and validates it with `validate_verdict()`.
5. Never edits application code or tests.

Optionally each subagent also adds a mutation for its requirement to `out/mutations/<ID>.json`
(see `mutation.example.json`; `find` must occur exactly once — check with `grep -c`).

## Phase 3 — PROVE (deterministic)

Run `python -m solotrace run --spec <spec> --auditor "<who wrote the verdicts>"`. It runs the
tests, verifies every citation in the audited commit, applies every mutation, scores each
requirement on evidence, and writes `AUDIT_REPORT.md` and `docs/index.html`.
Read the output: every requirement that is not **proven** is an open finding.

## Phase 4 — SIGN-OFF and FIX

1. Present the findings and a fix plan; ask **"Approve these fixes? (compliance sign-off)"** and wait.
2. For each approved item: failing test first, then the fix, then the full suite.
3. Re-audit the changed requirements (Phase 2) and re-run Phase 3 until everything is proven.
