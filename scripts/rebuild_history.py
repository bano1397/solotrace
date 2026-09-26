"""Rebuild the historical audit stages with today's SoloTrace, from git history.

Every number SoloTrace shows for the earlier stages can be reproduced:

  out-before/  Baseline — IBM Bob's first audit (task 1) of LedgerLite as built
               from spec v1.0, commit b52c5e4.
  out-round1/  Round 1 — IBM Bob's re-audit (task 3) after Bob's own fixes,
               commit 149d409.  Mutations in out-round1/mutations come from an
               independent QA pass and are replayed with ``solotrace prove``.

For each stage this script checks out the audited commit into a temporary git
worktree, restores the verdicts IBM Bob wrote at that commit, runs the test
suite there, verifies every citation against that commit's source, optionally
runs the mutations, and writes the traceability matrix.

    python scripts/rebuild_history.py            # both stages
    python scripts/rebuild_history.py round1     # one stage
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from solotrace.matrix import build_matrix  # noqa: E402
from solotrace.prove import baseline_passes, load_mutations, run_mutations, summarise  # noqa: E402
from solotrace.repo import SourceReader  # noqa: E402
from solotrace.testrun import run_tests  # noqa: E402
from solotrace.verify import verify_dir  # noqa: E402

SESSIONS = json.loads((ROOT / "bob_sessions" / "sessions.json").read_text())["sessions"]
TASK = {s["task"]: s for s in SESSIONS}

STAGES = {
    "baseline": {
        "dir": "out-before",
        "commit": "b52c5e4",
        "label": "Baseline audit",
        "description": "Spec v2.0 against LedgerLite as built from spec v1.0.",
        "auditor": "IBM Bob 2.0 — task 1 (Agent mode, 12 parallel subagents)",
        "bob_task": "task01",
        "audited_at": TASK["task01"]["subagents"]["started_at"],
        "prove": False,
    },
    "round1": {
        "dir": "out-round1",
        "commit": "149d409",
        "label": "Round 1 — after Bob's fixes",
        "description": "IBM Bob fixed the 8 gaps after a human compliance sign-off, then re-audited.",
        "auditor": "IBM Bob 2.0 — task 3 (SoloTrace Auditor mode, 12 parallel subagents)",
        "bob_task": "task03",
        "audited_at": TASK["task03"]["subagents"]["started_at"],
        "prove": True,
    },
}


def git(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def restore_bob_outputs(stage_dir: Path, commit: str) -> None:
    """Put back the requirements and verdicts exactly as IBM Bob wrote them at *commit*."""
    (stage_dir / "verdicts").mkdir(parents=True, exist_ok=True)
    for stale in (stage_dir / "verdicts").glob("REQ-*.json"):
        stale.unlink()
    (stage_dir / "requirements.json").write_text(git("show", f"{commit}:out/requirements.json"))
    names = git("ls-tree", "--name-only", f"{commit}:out/verdicts").split()
    for name in names:
        if name.startswith("REQ-") and name.endswith(".json"):
            (stage_dir / "verdicts" / name).write_text(git("show", f"{commit}:out/verdicts/{name}"))


def rebuild(key: str) -> None:
    cfg = STAGES[key]
    stage_dir = ROOT / cfg["dir"]
    full_commit = git("rev-parse", cfg["commit"]).strip()
    print(f"== {cfg['label']} ({cfg['dir']}, commit {cfg['commit']})")
    restore_bob_outputs(stage_dir, full_commit)

    with tempfile.TemporaryDirectory(prefix="solotrace-history-") as tmp:
        worktree = Path(tmp) / "wt"
        git("worktree", "add", "--detach", str(worktree), full_commit)
        try:
            junit = Path(tmp) / "junit.xml"
            tests = run_tests(worktree, "ledgerlite/tests", junit)
            (stage_dir / "tests.json").write_text(json.dumps(tests, indent=2) + "\n")
            print(f"   tests: {tests['passed']} passed, {tests['failed']} failed")

            report = verify_dir(stage_dir, SourceReader(ROOT, commit=full_commit))
            t = report["totals"]
            print(f"   citations: {t['verified']}/{t['checked']} verified "
                  f"(exact {t['exact']}, relocated {t['relocated']}, not found {t['not_found']})")

            prove_path = stage_dir / "prove.json"
            if cfg["prove"]:
                mutations, errors = load_mutations(stage_dir / "mutations", SourceReader(worktree), "ledgerlite/tests")
                if errors:
                    raise SystemExit("mutation errors:\n" + "\n".join(errors))
                ok, _ = baseline_passes(worktree, "ledgerlite/tests", 300)
                if not ok:
                    raise SystemExit("baseline tests fail in the worktree")
                results = run_mutations(worktree, mutations, "ledgerlite/tests", workers=6, timeout=300)
                reqs = [r["id"] for r in json.loads((stage_dir / "requirements.json").read_text())]
                summary = summarise(results, reqs)
                prove_path.write_text(json.dumps({"tool": "solotrace prove", "commit": full_commit,
                                                  "tests": "ledgerlite/tests", **summary}, indent=2) + "\n")
                s = summary["totals"]
                print(f"   mutations: {s['killed']}/{s['mutations']} killed, "
                      f"{s['requirements_proven']}/{s['requirements']} requirements proven")
            elif prove_path.exists():
                prove_path.unlink()
        finally:
            git("worktree", "remove", "--force", str(worktree))

    meta = {"project": "LedgerLite Payments API", **{k: cfg[k] for k in ("label", "description", "auditor", "bob_task", "audited_at")}}
    meta["code_commit"] = full_commit
    (stage_dir / "audit.json").write_text(json.dumps(meta, indent=2) + "\n")
    matrix = build_matrix(stage_dir)
    (stage_dir / "matrix.json").write_text(json.dumps(matrix, indent=2, ensure_ascii=False) + "\n")
    s = matrix["summary"]
    print(f"   AI verdicts {s['ai']['covered']}/{s['total']} covered · evidence score "
          f"{s['evidence_score_percent']}% · statuses {s['statuses']}")


if __name__ == "__main__":
    for key in (sys.argv[1:] or list(STAGES)):
        rebuild(key)
