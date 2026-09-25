# SoloTrace Audit Rules

## Evidence requirements

Every verdict **must** cite:
- The file path and line number where the relevant code lives.
- A direct quote of the relevant code line (or the closest meaningful expression).

Acceptable verdict format:
```
file: ledgerlite/services.py  line: 123  snippet: "if amount > _MAX_DEPOSIT:"
```

## Verdict definitions

| Status | Meaning |
|--------|---------|
| `covered` | Implemented **exactly** as the spec says **AND** at least one automated test asserts its acceptance criteria. |
| `untested` | Implemented correctly, but no test asserts the acceptance criteria. |
| `contradicts` | Implemented **differently** from the spec (e.g. wrong threshold, wrong HTTP status code, inverted logic). |
| `missing` | Not implemented at all. |

A requirement is **not** `covered` unless both conditions hold. Doubt → `untested`.

## Audit-time constraints

- **Never modify application code or tests** during an audit pass.
- Do not infer intent from comments; read only executable code and test assertions.
- If a code path exists but is unreachable, treat the requirement as `untested`.

## Fix workflow (after explicit human approval only)

1. Write a **failing** test that directly asserts the missing or wrong acceptance criterion.
2. Run the full test suite and confirm the new test fails (and only that test).
3. Fix the application code so the new test passes.
4. Re-run the full suite; every previously passing test must still pass.
5. **Never weaken, skip, or delete an existing test** to make the suite green.

## Output format

All SoloTrace outputs are JSON that validates against the schemas in `solotrace/schemas/`:
- `solotrace/schemas/requirement.schema.json` — one object per extracted requirement.
- `solotrace/schemas/verdict.schema.json` — one verdict object per requirement.

Run `solotrace/schemas.py` validators before writing any output file.
