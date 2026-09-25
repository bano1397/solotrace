---
name: solotrace-audit
description: >
  Run the SoloTrace Read → Audit → Fix → Report process to prove whether
  every requirement in a spec document is implemented and tested in a codebase.
  Reference the schemas in solotrace/schemas/ as supporting files.
---

# SoloTrace Audit Skill

This skill guides you through the full SoloTrace audit process on any repository
that has a requirements specification document (PDF or Markdown).

## Supporting files

- `requirement.schema.json` — schema for extracted requirement objects
- `verdict.schema.json` — schema for per-requirement audit verdicts
- `audit-checklist.md` — step-by-step checklist for the audit process

---

## Phase 1 — Read: Extract requirements

1. Locate the specification document (e.g. `demo-data/*.pdf` or a Markdown file).
2. For each requirement found, produce a JSON object that validates against
   `solotrace/schemas/requirement.schema.json`:
   - Assign a unique `id` matching `^REQ-\d{2}$` (e.g. `REQ-01`).
   - Extract verbatim `text` from the spec.
   - Derive testable `acceptance_criteria` — at least one per requirement.
   - Classify `risk` as `High`, `Medium`, or `Low`.
   - Set `change` to `none`, `changed`, or `new` relative to the previous version.
3. Write the array to `out/requirements.json`.
4. Validate every object using `solotrace/schemas.py::validate_requirement()`.

## Phase 2 — Audit: Produce verdicts

For each requirement in `out/requirements.json`:

1. Search the codebase for the implementation:
   - Use `grep` to find relevant functions, constants, and conditionals.
   - Read the identified lines; do **not** infer from comments.
2. Search the test suite for assertions covering the acceptance criteria:
   - Look for test functions that assert the exact threshold/behaviour.
   - A test that does not assert the criterion does **not** count.
3. Assign a `status`:
   - `covered` — implementation matches spec **and** ≥1 test asserts the criterion.
   - `untested` — correct implementation, no asserting test exists.
   - `contradicts` — implementation differs from the spec (wrong value, inverted logic, etc.).
   - `missing` — no implementation found.
4. Populate `code_evidence` (file, line, snippet) and `test_evidence` (file, test_name).
5. For non-`covered` verdicts, write a `suggested_fix`.
6. Validate every verdict object using `solotrace/schemas.py::validate_verdict()`.
7. Write one JSON file per verdict to `out/verdicts/REQ-XX.json`.

## Phase 3 — Fix (only after explicit human approval)

For each non-`covered` verdict the human asks you to fix:

1. Write a **failing** test that directly asserts the missing acceptance criterion.
2. Confirm the new test fails; all existing tests must still pass.
3. Implement the fix in the application code.
4. Run the full test suite (`.venv/bin/pytest -q`); all tests must pass.
5. Never weaken, skip, or delete any existing test.

## Phase 4 — Report: Build the traceability matrix

1. Load all verdict files from `out/verdicts/`.
2. Build `out/matrix.json`:
   ```json
   {
     "generated_at": "<ISO-8601 UTC timestamp>",
     "summary": { "covered": N, "untested": N, "contradicts": N, "missing": N },
     "verdicts": [ <verdict objects in REQ-id order> ]
   }
   ```
3. Print a Markdown summary table to the chat with columns:
   `ID | Title | Status | Risk | Evidence`.

## Audit constraints (always active)

- **Never modify application code or tests** during Phases 1 and 2.
- Every verdict must cite at least one `code_evidence` entry (except `missing`).
- Doubt about whether a test covers a criterion → verdict is `untested`, not `covered`.
- All JSON output must pass the stdlib validators in `solotrace/schemas.py` before writing.
