"""
solotrace matrix  --  Traceability Matrix Builder

Reads requirements.json + verdicts/*.json from *out_dir* and writes
out_dir/matrix.json with:

  rows    — one per requirement: id, title, risk, change, status,
             reason, evidence (code refs), tests (test names)
  summary — total, covered, untested, contradicts, missing, score_percent
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def cmd_matrix(out_dir: str) -> None:
    out = Path(out_dir)

    req_path = out / "requirements.json"
    if not req_path.exists():
        print(f"ERROR: {req_path} not found", file=sys.stderr)
        sys.exit(1)

    requirements: list[dict[str, Any]] = json.loads(req_path.read_text(encoding="utf-8"))

    verdicts_dir = out / "verdicts"
    if not verdicts_dir.exists():
        print(f"ERROR: {verdicts_dir} not found", file=sys.stderr)
        sys.exit(1)

    # Index verdicts by id
    verdict_map: dict[str, dict[str, Any]] = {}
    for vf in verdicts_dir.glob("REQ-*.json"):
        v = json.loads(vf.read_text(encoding="utf-8"))
        verdict_map[v["id"]] = v

    # Build rows
    rows: list[dict[str, Any]] = []
    counts: dict[str, int] = {"covered": 0, "untested": 0, "contradicts": 0, "missing": 0}

    for req in requirements:
        req_id = req["id"]
        v = verdict_map.get(req_id, {})
        status = v.get("status", "missing")

        # code evidence: compact refs  "file:line  snippet"
        evidence = [
            f"{ce['file']}:{ce['line']}  {ce['snippet']}"
            for ce in v.get("code_evidence", [])
        ]
        # test evidence: test_name (file)
        tests = [
            f"{te['test_name']} ({te['file']})"
            for te in v.get("test_evidence", [])
        ]

        rows.append({
            "id": req_id,
            "title": req.get("title", ""),
            "risk": req.get("risk", ""),
            "change": req.get("change", ""),
            "status": status,
            "reason": v.get("reason", ""),
            "evidence": evidence,
            "tests": tests,
        })

        if status in counts:
            counts[status] += 1
        else:
            counts["missing"] += 1

    total = len(rows)
    score = round(counts["covered"] / total * 100, 1) if total else 0.0

    summary = {
        "total": total,
        "covered": counts["covered"],
        "untested": counts["untested"],
        "contradicts": counts["contradicts"],
        "missing": counts["missing"],
        "score_percent": score,
    }

    matrix = {"rows": rows, "summary": summary}
    out_path = out / "matrix.json"
    out_path.write_text(json.dumps(matrix, indent=2), encoding="utf-8")

    print(f"Matrix written: {out_path}")
    print(f"  Total        : {total}")
    print(f"  Covered      : {counts['covered']}  ({score}%)")
    print(f"  Untested     : {counts['untested']}")
    print(f"  Contradicts  : {counts['contradicts']}")
    print(f"  Missing      : {counts['missing']}")
