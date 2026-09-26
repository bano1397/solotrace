# SoloTrace audit checklist

## READ
- [ ] Specification located and read
- [ ] `out/requirements.json` written; every entry passes `validate_requirement()`

## AUDIT (one subagent per requirement)
- [ ] Verdict status decided (doubt → `untested`)
- [ ] Code quoted verbatim with file and line
- [ ] Only real, asserting tests cited
- [ ] `out/verdicts/<ID>.json` passes `validate_verdict()`
- [ ] No application code or tests changed

## PROVE
- [ ] `python -m solotrace run --spec … --auditor "…"` completed
- [ ] Every citation verified (no `not_found`, `too_short`, bad paths)
- [ ] Every cited test exists and passes
- [ ] Every mutation killed; every requirement **proven**

## SIGN-OFF and FIX
- [ ] Fix plan approved: "Approve these fixes? (compliance sign-off)"
- [ ] Failing test written first for every gap
- [ ] Full suite green; no test weakened or deleted
- [ ] Changed requirements re-audited and re-proven
