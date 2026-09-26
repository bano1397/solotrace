"""
solotrace run — the deterministic half of an audit, in one command.

IBM Bob does the judgement work (READ the spec, AUDIT with one subagent per
requirement, FIX after human sign-off).  This command then checks everything
Bob produced, with real timings:

  1. requirements  validate out/requirements.json against the spec PDF (+ SHA-256)
  2. test          run the test suite, record every result
  3. verify        re-find every code citation in the audited commit
  4. prove         sabotage each requirement; its tests must catch every attempt
  5. matrix        score each requirement on evidence, not on the AI's word
  6. report        AUDIT_REPORT.md
  7. dashboard     docs/index.html
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from solotrace.extract import load_requirements, pdf_to_text
from solotrace.matrix import build_matrix
from solotrace.prove import baseline_passes, load_mutations, run_mutations, summarise
from solotrace.repo import SourceReader, head_commit, is_dirty, relative_display, repo_root, sha256_file
from solotrace.testrun import run_tests
from solotrace.verify import verify_dir


def _spec_info(spec: Path, root: Path, requirement_ids: list[str]) -> dict[str, Any]:
    text = pdf_to_text(spec)
    missing = [rid for rid in requirement_ids if rid not in text]
    if missing:
        raise ValueError(f"requirements not found in the spec text: {', '.join(missing)}")
    version = re.search(r"Version\s+([0-9]+(?:\.[0-9]+)*)", text)
    return {
        "path": relative_display(spec, root),
        "sha256": sha256_file(spec),
        "version": version.group(1) if version else None,
        "requirements_in_spec": len(requirement_ids),
    }


def _verdicts_written_at(out_dir: Path) -> str | None:
    """When the auditor wrote the verdicts (newest verdict file), as ISO-8601 UTC."""
    stamps = [p.stat().st_mtime for p in (out_dir / "verdicts").glob("REQ-*.json")]
    if not stamps:
        return None
    return datetime.fromtimestamp(max(stamps), timezone.utc).isoformat(timespec="seconds")


def cmd_run(spec: str, out: str, before: str | None, round1: str | None, tests_path: str,
            prove: bool = True, workers: int = 4, auditor: str | None = None,
            bob_task: str | None = None, video_url: str | None = None, strict: bool = False) -> int:
    from solotrace.dashboard import cmd_dashboard
    from solotrace.report import cmd_report

    root = repo_root()
    out_dir = Path(out)
    timings: list[tuple[str, float, str]] = []
    context: dict[str, Any] = {}

    def stage(name: str, fn: Callable[[], str]) -> None:
        print(f"── {len(timings) + 1}. {name}")
        started = time.monotonic()
        note = fn()
        elapsed = time.monotonic() - started
        timings.append((name, elapsed, note))
        print(f"   {note}  ({elapsed:.1f}s)")

    def do_requirements() -> str:
        reqs = load_requirements(out_dir / "requirements.json")
        ids = [r["id"] for r in reqs]
        info = _spec_info(Path(spec), root, ids)
        previous = json.loads((out_dir / "audit.json").read_text()) if (out_dir / "audit.json").exists() else {}
        meta = {
            "label": previous.get("label", "Round 2 — final"),
            "description": previous.get("description", "Final audit of LedgerLite against spec v2.0."),
            "auditor": auditor or previous.get("auditor", "IBM Bob 2.0 — SoloTrace Auditor mode"),
            "bob_task": bob_task or previous.get("bob_task"),
            "audited_at": _verdicts_written_at(out_dir),
            "code_commit": head_commit(root),
            "dirty": is_dirty(root),
            "spec": info,
        }
        (out_dir / "audit.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        context["ids"] = ids
        return f"{len(ids)} requirements, all present in {info['path']} (v{info['version']}, sha256 {info['sha256'][:12]}…)"

    def do_test() -> str:
        junit = out_dir / "junit.xml"
        result = run_tests(root, tests_path, junit)
        junit.unlink(missing_ok=True)
        (out_dir / "tests.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        if result["exit_code"] not in (0, 1):
            raise RuntimeError(f"pytest could not run (exit {result['exit_code']})")
        return f"{result['passed']} passed, {result['failed']} failed, {result['skipped']} skipped"

    def do_verify() -> str:
        t = verify_dir(out_dir, SourceReader(root))["totals"]
        return (f"{t['verified']}/{t['checked']} code citations verified "
                f"({t['not_found']} not found, {t['too_short']} too short, "
                f"{t['invalid_path'] + t['missing_file']} bad paths); "
                f"{t['tests_checked'] - t['tests_missing']}/{t['tests_checked']} cited tests exist")

    def do_prove() -> str:
        mutations, errors = load_mutations(out_dir / "mutations", SourceReader(root))
        if errors:
            raise ValueError("invalid mutation files:\n  " + "\n  ".join(errors))
        ok, _ = baseline_passes(root, tests_path, 300)
        if not ok:
            raise RuntimeError("the test suite fails on the unmutated code; nothing can be proven")
        results = run_mutations(root, mutations, tests_path, workers, 300)
        summary = summarise(results, context["ids"])
        report = {"tool": "solotrace prove", "commit": head_commit(root), "dirty": is_dirty(root),
                  "tests": tests_path, "workers": workers,
                  "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **summary}
        (out_dir / "prove.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        t = summary["totals"]
        return f"{t['killed']}/{t['mutations']} sabotage attempts caught; {t['requirements_proven']}/{t['requirements']} requirements proven"

    def do_matrix() -> str:
        matrix = build_matrix(out_dir)
        (out_dir / "matrix.json").write_text(json.dumps(matrix, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        s = matrix["summary"]
        context["summary"] = s
        proven = f"{s['statuses']['proven']}/{s['total']} proven" if s["mutation_testing"] else "no mutation testing"
        return f"AI says {s['ai']['covered']}/{s['total']} covered; evidence score {s['evidence_score_percent']}%; {proven}"

    def do_report() -> str:
        if cmd_report(before, round1, out) != 0:
            raise RuntimeError("report failed")
        return "AUDIT_REPORT.md written"

    def do_dashboard() -> str:
        if cmd_dashboard(before or out, round1 or out, out, video_url=video_url) != 0:
            raise RuntimeError("dashboard failed")
        return "docs/index.html written"

    print("SoloTrace — evidence pipeline (IBM Bob's verdicts are checked, never trusted blindly)")
    try:
        stage("requirements", do_requirements)
        stage("test", do_test)
        stage("verify", do_verify)
        if prove:
            stage("prove", do_prove)
        stage("matrix", do_matrix)
        stage("report", do_report)
        stage("dashboard", do_dashboard)
    except (FileNotFoundError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    total = sum(t for _, t, _ in timings)
    print(f"Done in {total:.1f}s.")
    s = context["summary"]
    if strict and s["statuses"]["proven"] != s["total"]:
        return 2
    return 0
