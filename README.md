# SoloTrace — every requirement, proven

**SoloTrace turns IBM Bob 2.0 into a compliance auditor.** It reads a requirements document,
proves each requirement in code and tests with verified `file:line` evidence, and does not trust
green tests until they catch deliberate sabotage.

[**Live dashboard**](https://bano1397.github.io/solotrace/) ·
[**Audit report**](AUDIT_REPORT.md) ·
[Requirements spec (PDF)](demo-data/LedgerLite-Requirements-v2.0.pdf) ·
[IBM Bob sessions](bob_sessions/) ·
[How Bob is configured](.bob/)

Built solo for the lablab.ai **IBM Bob 2.0 Hackathon** (September 2026).

---

## The problem

Banks, insurers and healthcare companies must show auditors that every written requirement is
implemented **and** tested before each release — EU DORA Art. 9(4)(e) asks for ICT changes to be
"recorded, tested, assessed, approved, implemented and verified", PCI DSS 4.0.1 Req. 6.5.1 asks for
changes to be tested before deployment, and FDA software-validation guidance asks to verify that each
design element "has been implemented in code". Today that traceability check is spreadsheet work,
and when a regulation changes the spec, nobody knows which parts of the code still comply.

AI coding assistants make the gap worse in a new way: **tests pass, the AI says "done", and the
requirement is still not met.** In this repository's own history, IBM Bob's first fix round was
reported as 12/12 covered — SoloTrace later proved only 6/12.

## What SoloTrace does

| # | Stage | Who | What happens |
|---|---|---|---|
| 1 | **READ** | IBM Bob | Reads the spec PDF; extracts each requirement, its acceptance criteria and risk |
| 2 | **AUDIT** | IBM Bob | One subagent per requirement, in parallel, each citing verbatim `file:line` evidence |
| 3 | **VERIFY** | SoloTrace | Re-finds every quote in the audited commit; rejects paraphrases, trivial snippets and paths outside the repo |
| 4 | **SIGN-OFF** | Human | A compliance officer approves the fix plan before any code changes |
| 5 | **FIX** | IBM Bob | Failing test first, then the fix, then the whole suite |
| 6 | **PROVE** | SoloTrace | Each requirement is sabotaged on purpose (e.g. 5000.00 → 5000.01, drop the sanctions check); its tests must catch every attempt |
| 7 | **REPORT** | SoloTrace | Traceability matrix, [AUDIT_REPORT.md](AUDIT_REPORT.md), and the [dashboard](https://bano1397.github.io/solotrace/) |

A requirement counts as **proven** only when the AI verdict is *covered*, a code citation is verified,
a cited test exists and **passes**, and **every** mutation of that requirement is killed.

## Results on the demo (LedgerLite payments API, spec v2.0)

The demo target is LedgerLite, a small FastAPI + SQLite payments API that was built from spec v1.0
and then audited against spec v2.0 (a regulation update: lower approval threshold, a daily transfer
cap, sanctions screening, account-number masking).

| Round | Who fixed | AI verdicts "covered" | Code citations verified | Sabotage caught | **Proven** |
|---|---|---|---|---|---|
| Baseline — [IBM Bob task 1](bob_sessions/) | — | 4/12 (33%) | 27/36 (9 were not real code) | not run | — |
| Round 1 — [IBM Bob task 3](bob_sessions/) | IBM Bob, after human sign-off | 12/12 (100%) | 55/57 | 23/34 | **6/12** |
| Round 2 — final, [IBM Bob task 5](bob_sessions/) | see below | 12/12 | 82/85 (0 invented; 3 too short to count) | **99/99** | **12/12** |

What round 2 exposed and fixed (all now covered by tests): the PIN lockout never persisted (unlimited
PIN guessing), money was stored as floating point, concurrent withdrawals could overdraw an account,
anyone — even the recipient, without a PIN — could approve a held transfer, and several requirements
had tests that could not fail.

**The final sabotage set is not home-made.** 46 mutations were written alongside the fixes; then an
independent adversarial auditor wrote **42 more** without seeing the tests, and 21 of them initially
slipped through (for example: the lockout enforced on only one endpoint, the UTC day computed in
server-local time, a hidden audit-purge route). The tests were strengthened until all **88/88** are
caught. The [mutation files](out/mutations/) mark every independent one as `[independent QA …]`.

**Bob's final audit found one more gap.** In task 5, Bob's 12 subagents re-audited everything and each
wrote one new sabotage. One of them (REQ-04-B1: drop the rollback when an approval fails) slipped past
all 161 tests, so REQ-04 was marked *weak* (11/12 proven). A test was added, and the re-run proved
12/12 with 99/99 sabotage caught. The final result was then signed off by a human
([`out/signoffs.json`](out/signoffs.json)).

Every number above is reproducible: `python scripts/rebuild_history.py` re-runs the baseline and
round-1 audits from git history with the same tool.

## How IBM Bob is used

- **Custom mode** [`SoloTrace Auditor`](.bob/custom_modes.yaml) with its own [rules](.bob/rules-solotrace/01-audit-rules.md)
  (verbatim evidence, four verdicts, no edits during an audit, fixes only after sign-off).
- **Skill** [`solotrace-audit`](.bob/skills/solotrace-audit/SKILL.md): READ → AUDIT → PROVE → SIGN-OFF/FIX, reusable on any repo.
- **Parallel subagents**: one per requirement — 12 at a time; task 1 ran 12 audits in 113 s of wall-clock time (1,021 s of combined work).
- **Human-in-the-loop**: Bob stops and asks *"Approve these fixes? (compliance sign-off)"*; the approval is recorded in [`bob_sessions/signoffs.json`](bob_sessions/signoffs.json).
- **Agent mode** fixed code test-first; **document understanding** read the spec PDF.
- **Evidence of every session**: [`bob_sessions/`](bob_sessions/) holds the task session summaries, and
  [`sessions.json`](bob_sessions/sessions.json) lists each task's times, Bobcoins and subagents (exported read-only from Bob's task history).

## Run it

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q                          # LedgerLite + SoloTrace test suites
.venv/bin/python -m solotrace run                      # test → verify → prove → matrix → report → dashboard
.venv/bin/python -m solotrace verify --out out --check # read-only gate: no invented citation or missing test
.venv/bin/python -m solotrace signoff --by "<reviewer>" --statement "<approval>"  # human sign-off, bound to this result
LEDGERLITE_ADMIN_TOKEN=dev .venv/bin/uvicorn ledgerlite.main:app --port 8000   # the API (docs at /docs)
```

To audit your own project, open it in IBM Bob, switch to the **SoloTrace Auditor** mode, run the
**solotrace-audit** skill on your spec, then `python -m solotrace run --spec <your spec>`.

## Repository map

See [AGENTS.md](AGENTS.md) (it is also what every Bob task loads). In short: `ledgerlite/` is the
audited API, `solotrace/` is the evidence engine, `out*/` hold the three audit rounds, `docs/` is the
dashboard, `bob_sessions/` is the Bob evidence.

## Limitations (honest)

- Verdicts are written by AI subagents; SoloTrace verifies their evidence and the tests, but a
  mutation score shows the tests *guard* a requirement — it cannot prove the absence of every defect.
- LedgerLite is a deliberately small sample: SQLite, PIN-based access control, a static sanctions list,
  an admin token instead of real identity management. It is an audit target, not a bank.
- The demo data is synthetic (`@example.com` addresses only; no real people or client data).

## Credits

Product code was built with **IBM Bob 2.0** (tasks 1–4 and the final audit, see `bob_sessions/`).
Round-2 hardening, the SoloTrace v2 engine and the presentation were built with help from
Claude Code (commits co-authored by Claude). Planning and prompts: Shehar Bano.

MIT licence — see [LICENSE](LICENSE).
