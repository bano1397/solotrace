"""
solotrace verify  --  Evidence Verifier (anti-hallucination guard)

For every out/verdicts/*.json
  • code_evidence: check each entry against the real source file.
      - If the snippet (whitespace-normalised) matches the cited line  →  verified=True, keep.
      - Else search ±5 lines; if found  →  correct line number, verified=True.
      - Else replace snippet with the actual source line, verified=False.
  • test_evidence: remove entries whose test_name is not a function/method
    defined in the cited file (uses ast).

Writes out/verification.json and prints a human-readable report.
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from solotrace.schemas import validate_verdict


# ── helpers ───────────────────────────────────────────────────────────────────

def _load_source_lines(filepath: str) -> list[str] | None:
    """Return 1-indexed list (index 0 == line 1). None if file not found."""
    p = Path(filepath)
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8", errors="replace").splitlines()


def _normalise(text: str) -> str:
    """Strip leading/trailing whitespace and collapse internal whitespace."""
    return re.sub(r"\s+", " ", text.strip())


def _snippet_core(snippet: str) -> str:
    """
    For multi-line or synthetic snippets, return only the first non-empty line
    after whitespace-normalisation.  Used as a search token for the ±5 window.
    """
    for line in snippet.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return _normalise(snippet)


def _line_contains_core(source_line: str, core: str) -> bool:
    """True if core (whitespace-normalised) is a substring of source_line (normalised)."""
    return _normalise(core) in _normalise(source_line)


def _collect_test_names(filepath: str) -> set[str] | None:
    """
    Parse *filepath* with ast and return the set of all function/method names
    whose name starts with 'test'.  Returns None if the file cannot be parsed.
    """
    p = Path(filepath)
    if not p.exists():
        return None
    try:
        tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"), filename=filepath)
    except SyntaxError:
        return None
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test"):
                names.add(node.name)
    return names


# ── core verification logic ───────────────────────────────────────────────────

def _verify_code_evidence(entry: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """
    Verify one code_evidence entry.

    Returns (updated_entry, outcome) where outcome is one of:
      'ok'        — snippet matched the cited line exactly (whitespace-insensitive)
      'corrected' — line number was wrong; corrected within ±5 window
      'replaced'  — snippet did not match anything; replaced with real source line
      'no_file'   — source file not found; entry left as-is
    """
    file_path = entry["file"]
    cited_line = entry["line"]
    snippet = entry["snippet"]

    lines = _load_source_lines(file_path)
    if lines is None:
        return entry, "no_file"

    # Exact match at cited line (1-based → index cited_line-1)
    idx = cited_line - 1
    if 0 <= idx < len(lines):
        if _normalise(lines[idx]) == _normalise(_snippet_core(snippet)):
            updated = dict(entry, snippet=lines[idx], verified=True)
            return updated, "ok"
        # Also accept if the snippet first-line is a substring of the source line
        if _line_contains_core(lines[idx], _snippet_core(snippet)):
            updated = dict(entry, snippet=lines[idx], verified=True)
            return updated, "ok"

    # Search ±5 lines
    core = _snippet_core(snippet)
    search_start = max(0, cited_line - 1 - 5)
    search_end = min(len(lines), cited_line - 1 + 6)  # exclusive
    for i in range(search_start, search_end):
        if _line_contains_core(lines[i], core):
            updated = dict(entry, line=i + 1, snippet=lines[i], verified=True)
            return updated, "corrected"

    # Replacement: use the real source line at cited position (best effort).
    # Skip blank lines — scan outward from idx to find a non-blank line.
    real_line = ""
    if 0 <= idx < len(lines):
        for offset in range(0, min(5, len(lines))):
            for sign in (0, 1, -1):
                candidate_idx = idx + sign * offset
                if 0 <= candidate_idx < len(lines):
                    candidate = lines[candidate_idx].rstrip("\r\n")
                    if candidate.strip():
                        real_line = candidate
                        break
            if real_line:
                break
    if not real_line and lines:
        # last resort: first non-blank line in the file
        for ln in lines:
            if ln.strip():
                real_line = ln.rstrip("\r\n")
                break
    if not real_line:
        real_line = "# (source line unavailable)"
    updated = dict(entry, snippet=real_line, verified=False)
    return updated, "replaced"


def _verify_verdict(verdict: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Verify all evidence in one verdict dict.

    Returns (updated_verdict, stats_dict).
    """
    stats = {"ok": 0, "corrected": 0, "replaced": 0, "no_file": 0, "tests_removed": 0}
    updated_ce = []
    for entry in verdict.get("code_evidence", []):
        updated_entry, outcome = _verify_code_evidence(entry)
        updated_ce.append(updated_entry)
        stats[outcome] += 1

    # test_evidence — remove phantom functions
    kept_te = []
    for te in verdict.get("test_evidence", []):
        known = _collect_test_names(te["file"])
        if known is None:
            # file missing — remove entry (treat as phantom)
            stats["tests_removed"] += 1
            continue
        if te["test_name"] not in known:
            stats["tests_removed"] += 1
            continue
        kept_te.append(te)

    updated_verdict = dict(verdict, code_evidence=updated_ce, test_evidence=kept_te)
    return updated_verdict, stats


# ── public command ────────────────────────────────────────────────────────────

def cmd_verify(out_dir: str) -> None:
    """Run evidence verification on all verdicts in *out_dir*/verdicts/."""
    verdicts_dir = Path(out_dir) / "verdicts"
    if not verdicts_dir.exists():
        print(f"ERROR: directory not found: {verdicts_dir}", file=sys.stderr)
        sys.exit(1)

    verdict_files = sorted(verdicts_dir.glob("REQ-*.json"))
    if not verdict_files:
        print(f"No REQ-*.json files found in {verdicts_dir}", file=sys.stderr)
        sys.exit(1)

    totals = {"checked": 0, "ok": 0, "corrected": 0, "replaced": 0,
              "no_file": 0, "tests_removed": 0}
    results: list[dict[str, Any]] = []

    for vf in verdict_files:
        raw = json.loads(vf.read_text(encoding="utf-8"))
        updated, stats = _verify_verdict(raw)

        # Persist corrected verdict back to file
        # Validate before writing (tolerate extra 'verified' field)
        validate_verdict(updated)
        vf.write_text(json.dumps(updated, indent=2), encoding="utf-8")

        n_ce = len(updated["code_evidence"])
        totals["checked"] += n_ce
        for k in ("ok", "corrected", "replaced", "no_file"):
            totals[k] += stats[k]
        totals["tests_removed"] += stats["tests_removed"]

        results.append({
            "file": str(vf),
            "id": updated["id"],
            "code_evidence_count": n_ce,
            "stats": stats,
        })

    # Write verification.json
    verification = {
        "out_dir": str(Path(out_dir).resolve()),
        "totals": totals,
        "verdicts": results,
    }
    out_path = Path(out_dir) / "verification.json"
    out_path.write_text(json.dumps(verification, indent=2), encoding="utf-8")

    # Human-readable report
    n = totals["checked"]
    corrected = totals["corrected"]
    rejected = totals["replaced"]
    no_file = totals["no_file"]
    tests_rm = totals["tests_removed"]

    print(f"Evidence verification: {out_dir}/verdicts/")
    print(f"  Entries checked  : {n}")
    print(f"  Verified OK      : {totals['ok']}")
    print(f"  Line corrected   : {corrected}")
    print(f"  Snippet replaced : {rejected}  (verified=false)")
    print(f"  File not found   : {no_file}")
    print(f"  Tests removed    : {tests_rm}")
    print(f"  Written          : {out_path}")
