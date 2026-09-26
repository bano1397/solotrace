"""
solotrace report — write an auditor-grade AUDIT_REPORT.md.

The report states exactly what was audited (spec hash, code commit, test run),
what each requirement's evidence is (verified file:line quotes, passing tests,
killed mutations), how the result changed across audit rounds, and who signed
off.  Every path is repository-relative; nothing machine-specific is written.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from solotrace import __version__
from solotrace.signoff import load_signoffs

ICON: dict[Any, str] = {
    "proven": "✅ proven",
    "covered": "☑️ covered",
    "weak": "🟠 weak",
    "unverified": "⚠️ unverified",
    "untested": "⚠️ untested",
    "contradicts": "❌ contradicts",
    "missing": "⛔ missing",
    None: "—",
}


def _load(path: Path) -> Any | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _md(text: Any) -> str:
    """Untrusted text (written by an AI auditor) made inert: one line, no HTML, no table breaks."""
    text = " ".join(str(text).split())
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return text.replace("|", "\\|").replace("`", "'")


def _code(text: Any) -> str:
    """Inline code span that cannot be broken out of (code spans render HTML literally)."""
    text = " ".join(str(text).split())
    fence = "``" if "`" in text else "`"
    return f"{fence} {text} {fence}" if fence == "``" else f"`{text}`"


def _pct(n: int, d: int) -> str:
    return f"{n}/{d} ({round(n / d * 100) if d else 0}%)"


def _stage_line(name: str, m: dict[str, Any] | None) -> str | None:
    if not m:
        return None
    s = m["summary"]
    proven = f"{s['statuses']['proven']}/{s['total']}" if s["mutation_testing"] else "not tested"
    mutations = f"{s['mutations_killed']}/{s['mutations_total']}" if s["mutation_testing"] else "—"
    tests = s["tests_run"]
    tests_txt = f"{tests['passed']} passed / {tests['failed']} failed" if tests else "—"
    return (f"| {name} | `{(m['audit'].get('code_commit') or '')[:7]}` | {s['ai']['covered']}/{s['total']} "
            f"| {s['citations_verified']}/{s['citations_total']} | {tests_txt} | {mutations} | {proven} |")


def build_report(before: dict | None, round1: dict | None, after: dict, extras: dict[str, Any]) -> str:
    s = after["summary"]
    audit = after.get("audit", {})
    spec = audit.get("spec", {})
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    total = s["total"]
    proven = s["statuses"]["proven"]
    lines: list[str] = []
    add = lines.append

    add(f"# SoloTrace audit report — {audit.get('project', 'audited project')}")
    add("")
    add(f"*Generated {now} by SoloTrace {__version__} · verdicts by {audit.get('auditor', 'the AI auditor')}.*")
    add("")
    add("> **Result:** " + (
        f"{proven} of {total} requirements are **proven**: implemented, cited with verified file:line evidence, "
        f"covered by passing tests, and every deliberate sabotage of them was caught by the tests."
        if s["mutation_testing"] else
        f"{s['statuses']['covered']} of {total} requirements are covered with verified evidence (no mutation testing)."
    ))
    add("")

    add("## 1. Scope")
    add("")
    add("| Item | Value |")
    add("|---|---|")
    add(f"| Specification | `{spec.get('path', 'n/a')}` (version {spec.get('version', 'n/a')}) |")
    add(f"| Specification SHA-256 | `{spec.get('sha256', 'n/a')}` |")
    add(f"| Code audited | commit `{audit.get('code_commit', 'n/a')}`{' (uncommitted changes present)' if audit.get('dirty') else ''} |")
    if s["tests_run"]:
        t = s["tests_run"]
        add(f"| Test suite | `ledgerlite/tests`: {t['passed']} passed, {t['failed']} failed, {t['skipped']} skipped |")
    add(f"| Evidence verification | {s['citations_verified']}/{s['citations_total']} code citations verified against the audited commit |")
    if s["mutation_testing"]:
        add(f"| Mutation testing | {s['mutations_killed']}/{s['mutations_total']} mutations killed |")
    add(f"| Auditor | {audit.get('auditor', 'n/a')} |")
    add(f"| Audited at | {audit.get('audited_at', 'n/a')} |")
    add("")

    add("## 2. Results across audit rounds")
    add("")
    add("| Round | Code | AI says covered | Citations verified | Tests | Mutations killed | Proven |")
    add("|---|---|---|---|---|---|---|")
    for name, m in (("Baseline (IBM Bob task 1)", before), ("Round 1 (after Bob's fixes, task 3)", round1),
                    ("Round 2 (final)", after)):
        row = _stage_line(name, m)
        if row:
            add(row)
    add("")
    add("*Proven* = the AI verdict is `covered`, at least one code citation is verified verbatim, at least one "
        "cited test exists and passed, and every mutation of the requirement was killed by the test suite.")
    add("")

    add("## 3. Traceability matrix")
    add("")
    add("| Req | Requirement | Risk | Change | Baseline | Round 1 | Final | Evidence | Tests | Mutations |")
    add("|---|---|---|---|---|---|---|---|---|---|")
    by_id = {name: {r["id"]: r for r in (m or {}).get("rows", [])} for name, m in (("b", before), ("r", round1))}
    for r in after["rows"]:
        c = r["checks"]
        mut = c["mutations"]
        mut_txt = "{}/{}".format(mut["killed"], mut["tried"]) if mut else "—"
        base_status = by_id["b"].get(r["id"], {}).get("status")
        round1_status = by_id["r"].get(r["id"], {}).get("status")
        add(f"| {_md(r['id'])} | {_md(r['title'])} | {_md(r['risk'])} | {_md(r['change'])} "
            f"| {ICON.get(base_status, '—')} | {ICON.get(round1_status, '—')} | {ICON.get(r['status'], _md(r['status']))} "
            f"| {c['citations_verified']}/{c['citations_total']} | {c['tests_passing']}/{c['tests_cited']} | {mut_txt} |")
    add("")

    add("## 4. Requirement detail")
    add("")
    for r in after["rows"]:
        add(f"### {_md(r['id'])} — {_md(r['title'])}")
        add("")
        add(f"**Risk:** {_md(r['risk'])} · **Change in v2.0:** {_md(r['change'])} · **Final status:** {ICON.get(r['status'], _md(r['status']))}")
        add("")
        add(f"> {_md(r['text'])}")
        add("")
        add("Acceptance criteria:")
        for ac in r["acceptance_criteria"]:
            add(f"- {_md(ac)}")
        add("")
        add(f"Auditor's reasoning: {_md(r['reason'])}")
        add("")
        if r["evidence"]:
            add("Code evidence:")
            for e in r["evidence"]:
                mark = "✔ verified" if e["verified"] else f"✘ {e['match'] or 'unverified'}"
                add(f"- {_code(str(e['file']) + ':' + str(e['line']))} {_code(e['snippet'])} — {mark}")
            add("")
        if r["tests"]:
            add("Tests:")
            for t in r["tests"]:
                state = "✔ passed" if t["passed"] else ("✘ not found" if t["exists"] is False else "✘ failed or not run")
                add(f"- {_code(t['file'])} · {_code(t['test_name'])} — {state}")
            add("")
        muts = extras.get("prove", {}).get("requirements", {}).get(r["id"], {}).get("mutations", [])
        if muts:
            add("Mutations (deliberate sabotage — each must make a test fail):")
            for m in muts:
                killer = f" by {_code(m['killed_by'].split('::')[-1])}" if m.get("killed_by") else ""
                add(f"- {_md(m['id'])}: {_md(m['description'])} — **{_md(m['outcome'])}**{killer}")
            add("")

    signoffs = extras.get("signoffs") or []
    add("## 5. Human compliance sign-offs")
    add("")
    if signoffs:
        add("| When | Where | Scope | Statement |")
        add("|---|---|---|---|")
        for so in signoffs:
            scope = _md(so.get("scope", "fix plan (round 1)"))
            if so.get("matches_current_result") is False:
                scope += " — ⚠️ result changed since"
            add(f"| {_md(so['approved_at'])} | {_md(so.get('channel', ''))} | {scope} | {_md(so['statement'])} |")
    else:
        add("No sign-off records found.")
    add("")

    sessions = extras.get("sessions") or []
    if sessions:
        add("## 6. IBM Bob sessions")
        add("")
        add("| Task | What | Started | Minutes | Bobcoins | Parallel subagents |")
        add("|---|---|---|---|---|---|")
        for se in sessions:
            sub = se["subagents"]
            par = f"{sub['count']} (in {sub['parallel_wall_clock_s']} s)" if sub["count"] else "—"
            add(f"| {se['task']} | {_md(se['title'][:70])} | {se['started_at']} | {se['duration_min']} | {se['bobcoins']} | {par} |")
        add("")
        add("Screenshots of each task's session summary are in `bob_sessions/`.")
        add("")

    add("## 7. Method and limitations")
    add("")
    add("- Verdicts are written by AI subagents (one per requirement). SoloTrace never trusts them blindly: every "
        "code citation is re-located in the audited commit (verbatim, re-wrapped or with a stripped comment), citations "
        "outside the repository are rejected, and cited tests must exist and pass.")
    add("- Mutation testing shows the tests *guard* each requirement; it cannot prove the absence of every possible defect.")
    for note in audit.get("limitations", []):
        add(f"- {note}")
    add("")
    return "\n".join(lines) + "\n"


def cmd_report(before: str | None, round1: str | None, after: str, output: str = "AUDIT_REPORT.md") -> int:
    after_dir = Path(after)
    m_after = _load(after_dir / "matrix.json")
    if m_after is None:
        print(f"ERROR: {after_dir}/matrix.json not found — run `python -m solotrace matrix --out {after}` first.")
        return 1
    m_before = _load(Path(before) / "matrix.json") if before else None
    m_round1 = _load(Path(round1) / "matrix.json") if round1 else None
    extras = {
        "prove": _load(after_dir / "prove.json") or {},
        "signoffs": load_signoffs(after_dir),
        "sessions": (_load(Path("bob_sessions") / "sessions.json") or {}).get("sessions", []),
    }
    Path(output).write_text(build_report(m_before, m_round1, m_after, extras), encoding="utf-8")
    print(f"Audit report written: {output}")
    return 0
