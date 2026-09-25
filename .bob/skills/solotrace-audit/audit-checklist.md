# SoloTrace Audit Checklist

Use this checklist to track progress through an audit session.

## Phase 1 — Read

- [ ] Specification document located
- [ ] All requirements extracted to `out/requirements.json`
- [ ] Each requirement validated with `validate_requirement()`
- [ ] IDs are sequential (`REQ-01`, `REQ-02`, …)

## Phase 2 — Audit

For each requirement:

- [ ] Implementation searched with grep + read
- [ ] Test coverage searched for each acceptance criterion
- [ ] Status assigned (`covered` / `untested` / `contradicts` / `missing`)
- [ ] `code_evidence` populated (skip only for `missing`)
- [ ] `test_evidence` populated (skip only for `missing` / `untested`)
- [ ] `suggested_fix` written for non-`covered` verdicts
- [ ] Verdict validated with `validate_verdict()`
- [ ] Written to `out/verdicts/REQ-XX.json`

## Phase 3 — Fix (human-approved only)

- [ ] Failing test written for each gap
- [ ] New test confirmed to fail in isolation
- [ ] Application code fixed
- [ ] Full suite passes (`.venv/bin/pytest -q`)
- [ ] No existing tests weakened or deleted

## Phase 4 — Report

- [ ] `out/matrix.json` built
- [ ] Markdown summary table posted to chat
