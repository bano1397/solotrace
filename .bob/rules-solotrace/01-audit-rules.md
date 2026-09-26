# SoloTrace audit rules

These rules apply in the **SoloTrace Auditor** mode. The deterministic checks behind them
live in the `solotrace` Python package (`python -m solotrace …`), so every rule below is
enforced by code, not by trust.

## 1. Evidence

Every verdict cites code as `{file, line, snippet}` and tests as `{file, test_name}`.

- **Quote verbatim.** Open the file and copy the line character for character. No
  paraphrase, no `...`, no pseudo-code. `solotrace verify` re-finds every quote in the audited
  commit and rejects anything that is not really there.
- A quote may span several consecutive lines, or be a single line of a statement that the file
  wraps over several lines. Trailing `# comments` you add are ignored; code you invent is not.
- Quotes shorter than 8 characters (`try:`, `raise`, `(`) prove nothing and are rejected.
- Paths are repository-relative. Absolute paths and `..` are rejected.
- Test names: `test_x`, `test_x[param]`, `TestClass::test_x` or `TestClass.test_x`. Only cite
  tests that exist and assert the acceptance criterion.

## 2. Verdicts

| Status | Meaning |
|---|---|
| `covered` | Implemented **exactly** as the spec says **and** at least one test asserts its acceptance criteria. |
| `untested` | Implemented, but no test asserts the acceptance criteria. |
| `contradicts` | Implemented **differently** from the spec (wrong threshold, wrong status code, inverted logic). |
| `missing` | Not implemented. |

Doubt means `untested`, never `covered`.

## 3. Evidence scoring (done by `python -m solotrace run`)

The AI verdict alone never makes a requirement *proven*. A requirement is **proven** only if:
the verdict is `covered`, at least one code citation is verified, at least one cited test exists
and passes, and every mutation in `out/mutations/<REQ>.json` is **killed** by the test suite.
Anything else is reported as `weak`, `unverified`, `untested`, `contradicts` or `missing`.

## 4. Mutations (deliberate sabotage)

A mutation is the smallest change that breaks one requirement:
`{"id", "file", "find", "replace", "description"}`, where `find` occurs **exactly once** in the
file. Good mutations change a threshold by one cent, drop one check, skip one audit write or
allow one more PIN attempt. `solotrace prove` applies each one to a private copy and runs the tests.

## 5. Audit-time constraints

- **Never modify application code or tests during an audit.**
- Read executable code and assertions, not comments or docstrings.

## 6. Fixes — only after a human compliance sign-off

1. Show the fix plan and ask: **"Approve these fixes? (compliance sign-off)"** — then wait.
2. Write a test that fails for the gap; confirm it fails.
3. Fix the code; run the full suite (`.venv/bin/pytest -q`); never weaken or delete a test.
4. Re-audit the changed requirements and re-run `python -m solotrace run`.

## 7. Output

All JSON validates with `solotrace/schemas.py` (`validate_requirement`, `validate_verdict`).
Schemas: `solotrace/schemas/requirement.schema.json`, `solotrace/schemas/verdict.schema.json`.
