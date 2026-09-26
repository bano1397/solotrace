"""
solotrace matrix — build the traceability matrix, scored on evidence.

Inputs (in the audit directory):
  requirements.json   extracted requirements
  verdicts/REQ-*.json AI auditor verdicts (after ``solotrace verify``)
  tests.json          test results from ``solotrace test`` (optional)
  prove.json          mutation results from ``solotrace prove`` (optional)

The AI's opinion alone never makes a requirement "proven":

  final status   meaning
  ------------   ---------------------------------------------------------------
  proven         AI says covered, ≥1 verified code citation, ≥1 cited test that
                 exists and passed, and every mutation of the requirement is killed
  covered        as above, but no mutation testing was run
  weak           covered, but at least one mutation survived (tests don't guard it)
  unverified     AI says covered, but no code citation survived verification
  untested       no cited test exists and passes (or the AI said "untested")
  contradicts    implemented differently from the spec (AI verdict)
  missing        not implemented (AI verdict, or no verdict at all)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from solotrace import __version__
from solotrace.extract import load_requirements
from solotrace.repo import SourceReader, repo_root
from solotrace.schemas import validate_verdict
from solotrace.testrun import lookup
from solotrace.verify import verify_code_evidence, verify_test_evidence

FINAL_STATUSES = ("proven", "covered", "weak", "unverified", "untested", "contradicts", "missing")


def _load_json(path: Path) -> Any | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def load_verdicts(verdicts_dir: Path, requirement_ids: list[str]) -> dict[str, dict[str, Any]]:
    verdicts: dict[str, dict[str, Any]] = {}
    for path in sorted(verdicts_dir.glob("REQ-*.json")):
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        validate_verdict(data)
        if data["id"] != path.stem:
            raise ValueError(f"{path.name}: id {data['id']!r} does not match the file name")
        if data["id"] not in requirement_ids:
            raise ValueError(f"{path.name}: {data['id']} is not a requirement in requirements.json")
        verdicts[data["id"]] = data
    return verdicts


def build_row(req: dict[str, Any], verdict: dict[str, Any] | None,
              tests: dict[str, Any] | None, prove: dict[str, Any] | None) -> dict[str, Any]:
    verdict = verdict or {"status": "missing", "reason": "no verdict was produced",
                          "code_evidence": [], "test_evidence": [], "suggested_fix": ""}
    ai_status = verdict["status"]

    evidence = []
    for e in verdict["code_evidence"]:
        verified = e.get("verified")
        evidence.append({
            "file": e["file"],
            "line": e.get("actual_line") or e["line"],
            "claimed_line": e["line"],
            "snippet": e.get("actual_snippet") if verified else e["snippet"],
            "claimed_snippet": e["snippet"],
            "verified": verified,
            "match": e.get("match"),
        })

    cited_tests = []
    for t in verdict["test_evidence"]:
        passed = lookup(tests["cases"], t["file"], t["test_name"]) if tests else None
        cited_tests.append({"file": t["file"], "test_name": t["test_name"],
                            "exists": t.get("exists"), "passed": passed})

    n_verified = sum(1 for e in evidence if e["verified"])
    n_passing = sum(1 for t in cited_tests if t["exists"] is not False and t["passed"] is True)
    mutation = None
    if prove is not None:
        m = prove["requirements"].get(req["id"], {"tried": 0, "killed": 0, "survived": 0, "proven": False})
        mutation = {"tried": m["tried"], "killed": m["killed"], "survived": m["survived"], "proven": m["proven"]}

    if ai_status != "covered":
        final = ai_status
    elif n_verified == 0:
        final = "unverified"
    elif tests is not None and n_passing == 0:
        final = "untested"
    elif mutation is not None and not mutation["proven"]:
        final = "weak"
    elif mutation is not None:
        final = "proven"
    else:
        final = "covered"

    return {
        "id": req["id"],
        "title": req["title"],
        "text": req["text"],
        "acceptance_criteria": req["acceptance_criteria"],
        "risk": req["risk"],
        "change": req["change"],
        "ai_status": ai_status,
        "status": final,
        "reason": verdict["reason"],
        "suggested_fix": verdict.get("suggested_fix") or "",
        "evidence": evidence,
        "tests": cited_tests,
        "checks": {
            "citations_verified": n_verified,
            "citations_total": len(evidence),
            "tests_passing": n_passing,
            "tests_cited": len(cited_tests),
            "mutations": mutation,
        },
    }


def build_matrix(out_dir: Path) -> dict[str, Any]:
    requirements = load_requirements(out_dir / "requirements.json")
    ids = [r["id"] for r in requirements]
    verdicts = load_verdicts(out_dir / "verdicts", ids)
    tests = _load_json(out_dir / "tests.json")
    prove = _load_json(out_dir / "prove.json")
    meta = _load_json(out_dir / "audit.json") or {}

    # Evidence is always re-checked here against the audited code; "verified" flags that
    # happen to be present in a verdict file are ignored.
    commit = meta.get("code_commit") if meta.get("code_commit") and not meta.get("dirty") else None
    reader = SourceReader(repo_root(), commit=commit)
    for v in verdicts.values():
        v["code_evidence"] = [verify_code_evidence(e, reader) for e in v["code_evidence"]]
        v["test_evidence"] = [verify_test_evidence(t, reader) for t in v["test_evidence"]]

    rows = [build_row(r, verdicts.get(r["id"]), tests, prove) for r in requirements]
    total = len(rows)
    counts = {s: sum(1 for r in rows if r["status"] == s) for s in FINAL_STATUSES}
    ai_counts = {s: sum(1 for r in rows if r["ai_status"] == s) for s in ("covered", "untested", "contradicts", "missing")}
    evidence_ok = counts["proven"] + counts["covered"]

    def pct(n: int) -> float:
        return round(n / total * 100, 1) if total else 0.0

    summary = {
        "total": total,
        "ai": {**ai_counts, "score_percent": pct(ai_counts["covered"])},
        "statuses": counts,
        "evidence_score_percent": pct(evidence_ok),
        "proven_percent": pct(counts["proven"]) if prove is not None else None,
        "citations_verified": sum(r["checks"]["citations_verified"] for r in rows),
        "citations_total": sum(r["checks"]["citations_total"] for r in rows),
        "mutation_testing": bool(prove),
        "mutations_killed": prove["totals"]["killed"] if prove else None,
        "mutations_total": prove["totals"]["mutations"] if prove else None,
        "tests_run": {k: tests[k] for k in ("total", "passed", "failed", "skipped", "commit")} if tests else None,
    }
    return {"tool": "solotrace matrix", "version": __version__, "audit": meta, "summary": summary, "rows": rows}


def cmd_matrix(out: str) -> int:
    out_dir = Path(out)
    try:
        matrix = build_matrix(out_dir)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    (out_dir / "matrix.json").write_text(json.dumps(matrix, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    s = matrix["summary"]
    print(f"Traceability matrix: {out_dir}/matrix.json")
    print(f"  AI verdicts   : {s['ai']['covered']}/{s['total']} covered ({s['ai']['score_percent']}%)")
    print(f"  Evidence score: {s['evidence_score_percent']}%  "
          f"(citations verified {s['citations_verified']}/{s['citations_total']})")
    if s["mutation_testing"]:
        print(f"  Proven        : {s['statuses']['proven']}/{s['total']} ({s['proven_percent']}%), "
              f"mutations killed {s['mutations_killed']}/{s['mutations_total']}")
    for status in FINAL_STATUSES:
        if s["statuses"][status]:
            print(f"    {status:<12}: {s['statuses'][status]}")
    return 0
