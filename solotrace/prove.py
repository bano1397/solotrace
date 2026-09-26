"""
solotrace prove — mutation testing as compliance evidence.

"All tests pass" proves little: a test can pass without checking the requirement.
For every requirement, ``out/mutations/<REQ>.json`` lists small, deliberate breaks
of its implementation (a *mutation*: change 5000.00 to 5000.01, drop the sanctions
check, skip an audit write …).  SoloTrace applies each mutation to a private copy
of the repository and runs the test suite:

* **killed**   — at least one test failed: the tests really guard the requirement;
* **survived** — every test still passed: the requirement is NOT proven by its tests;
* **invalid**  — the mutated code could not even be collected (bad mutation).

A requirement is *proven* only if it has mutations and every one of them is killed.

Mutation file format::

    {"requirement": "REQ-05",
     "mutations": [{"id": "REQ-05-M1", "file": "ledgerlite/services.py",
                    "find": "Decimal(\\"5000.00\\")", "replace": "Decimal(\\"5000.01\\")",
                    "description": "raise the approval threshold by one cent"}]}
"""
from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from solotrace import __version__
from solotrace.repo import SourceReader, UnsafePathError, head_commit, is_dirty, project_files, repo_root

_COPY_IGNORE = shutil.ignore_patterns(
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache", "out", "out-*", "docs",
    "bob_sessions", "*.db", "node_modules", ".mypy_cache",
)
_REQUIRED_KEYS = ("id", "file", "find", "replace", "description")


# ── loading and validation ───────────────────────────────────────────────────

def load_mutations(mutations_dir: Path, reader: SourceReader) -> tuple[list[dict[str, Any]], list[str]]:
    """Load and validate all mutation files. Returns (mutations, errors)."""
    mutations: list[dict[str, Any]] = []
    errors: list[str] = []
    seen_ids: set[str] = set()
    for path in sorted(mutations_dir.glob("REQ-*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            errors.append(f"{path.name}: invalid JSON ({exc})")
            continue
        requirement = data.get("requirement", path.stem) if isinstance(data, dict) else path.stem
        items = data.get("mutations", []) if isinstance(data, dict) else data
        if requirement != path.stem:
            errors.append(f"{path.name}: requirement {requirement!r} does not match the file name")
            continue
        for index, m in enumerate(items):
            where = f"{path.name}[{index}]"
            if not isinstance(m, dict) or any(not isinstance(m.get(k), str) for k in _REQUIRED_KEYS):
                errors.append(f"{where}: needs string fields {', '.join(_REQUIRED_KEYS)}")
                continue
            if m["id"] in seen_ids:
                errors.append(f"{where}: duplicate mutation id {m['id']!r}")
                continue
            try:
                rel = reader.check(m["file"])
                text = reader.text(rel)
            except UnsafePathError as exc:
                errors.append(f"{where}: {exc}")
                continue
            if text is None:
                errors.append(f"{where}: file not found: {m['file']}")
                continue
            count = text.count(m["find"]) if m["find"] else 0
            if count != 1:
                errors.append(f"{where}: 'find' must occur exactly once in {m['file']} (found {count})")
                continue
            if m["find"] == m["replace"]:
                errors.append(f"{where}: 'replace' is identical to 'find'")
                continue
            seen_ids.add(m["id"])
            line = text[: text.index(m["find"])].count("\n") + 1
            mutations.append({**m, "file": rel, "requirement": requirement, "line": line})
    return mutations, errors


# ── execution ────────────────────────────────────────────────────────────────

def _pytest(copy: Path, tests_path: str, timeout: int) -> tuple[str, str | None, float]:
    cmd = [sys.executable, "-m", "pytest", tests_path, "-x", "-q", "-p", "no:cacheprovider", "-o", "addopts="]
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(copy)}
    started = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=copy, capture_output=True, text=True, timeout=timeout, env=env, check=False)
    except subprocess.TimeoutExpired:
        return "timeout", None, time.monotonic() - started
    duration = time.monotonic() - started
    killed_by = next(
        (line[len("FAILED "):].split(" - ", 1)[0] for line in proc.stdout.splitlines() if line.startswith("FAILED ")),
        None,
    )
    if proc.returncode == 0:
        return "survived", None, duration
    if proc.returncode == 1:
        return "killed", killed_by, duration
    return "invalid", None, duration


_SKIP_PREFIXES = ("out/", "out-", "docs/", "bob_sessions/")


def copy_project(root: Path, dest: Path) -> None:
    """Copy the project's own files (tracked or untracked-but-not-ignored) — never venvs or secrets."""
    files = project_files(root)
    if files is None:
        shutil.copytree(root, dest, ignore=_COPY_IGNORE)
        return
    for rel in sorted(files):
        if rel.startswith(_SKIP_PREFIXES):
            continue
        src = root / rel
        if not src.is_file():
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)


def _worker(root: Path, tests_path: str, jobs: "queue.Queue", results: list, timeout: int, lock: threading.Lock) -> None:
    with tempfile.TemporaryDirectory(prefix="solotrace-prove-") as tmp:
        copy = Path(tmp) / "repo"
        copy_project(root, copy)
        while True:
            try:
                mutation = jobs.get_nowait()
            except queue.Empty:
                return
            try:
                target = copy / mutation["file"]
                original = target.read_text(encoding="utf-8")
                target.write_text(original.replace(mutation["find"], mutation["replace"], 1), encoding="utf-8")
                try:
                    outcome, killed_by, duration = _pytest(copy, tests_path, timeout)
                finally:
                    target.write_text(original, encoding="utf-8")
                record = {**mutation, "outcome": outcome, "killed_by": killed_by, "duration_s": round(duration, 2)}
            except Exception as exc:  # never lose a mutation silently
                record = {**mutation, "outcome": "invalid", "killed_by": None, "duration_s": 0.0,
                          "error": f"{type(exc).__name__}: {exc}"}
            with lock:
                results.append(record)


def baseline_passes(root: Path, tests_path: str, timeout: int) -> tuple[bool, float]:
    with tempfile.TemporaryDirectory(prefix="solotrace-prove-") as tmp:
        copy = Path(tmp) / "repo"
        copy_project(root, copy)
        outcome, _, duration = _pytest(copy, tests_path, timeout)
    return outcome == "survived", duration


def run_mutations(root: Path, mutations: list[dict[str, Any]], tests_path: str,
                  workers: int, timeout: int) -> list[dict[str, Any]]:
    jobs: "queue.Queue" = queue.Queue()
    for m in mutations:
        jobs.put(m)
    results: list[dict[str, Any]] = []
    lock = threading.Lock()
    threads = [
        threading.Thread(target=_worker, args=(root, tests_path, jobs, results, timeout, lock), daemon=True)
        for _ in range(max(1, min(workers, len(mutations))))
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if len(results) != len(mutations):
        raise RuntimeError(f"only {len(results)} of {len(mutations)} mutations produced a result")
    order = {m["id"]: i for i, m in enumerate(mutations)}
    return sorted(results, key=lambda r: order[r["id"]])


def summarise(results: list[dict[str, Any]], requirement_ids: list[str]) -> dict[str, Any]:
    per_req: dict[str, dict[str, Any]] = {}
    grouped: dict[str, list] = defaultdict(list)
    for r in results:
        grouped[r["requirement"]].append(r)
    for req in requirement_ids:
        items = grouped.get(req, [])
        killed = sum(1 for r in items if r["outcome"] in ("killed", "timeout"))
        survived = [r for r in items if r["outcome"] == "survived"]
        invalid = sum(1 for r in items if r["outcome"] == "invalid")
        per_req[req] = {
            "tried": len(items),
            "killed": killed,
            "survived": len(survived),
            "invalid": invalid,
            "proven": bool(items) and not survived and not invalid,
            "mutations": [
                {k: r[k] for k in ("id", "description", "file", "line", "outcome", "killed_by", "duration_s")}
                for r in items
            ],
        }
    totals = {
        "mutations": len(results),
        "killed": sum(v["killed"] for v in per_req.values()),
        "survived": sum(v["survived"] for v in per_req.values()),
        "invalid": sum(v["invalid"] for v in per_req.values()),
        "requirements_proven": sum(1 for v in per_req.values() if v["proven"]),
        "requirements": len(requirement_ids),
    }
    return {"totals": totals, "requirements": per_req}


def cmd_prove(out: str, tests_path: str, workers: int = 4, timeout: int = 300) -> int:
    root = repo_root()
    out_dir = Path(out)
    reader = SourceReader(root)
    mutations, errors = load_mutations(out_dir / "mutations", reader)
    if errors:
        print("ERROR: invalid mutation files:\n  " + "\n  ".join(errors), file=sys.stderr)
        return 1
    if not mutations:
        print(f"ERROR: no mutations found in {out_dir / 'mutations'}", file=sys.stderr)
        return 1

    requirements_path = out_dir / "requirements.json"
    requirement_ids = (
        [r["id"] for r in json.loads(requirements_path.read_text(encoding="utf-8"))]
        if requirements_path.exists() else sorted({m["requirement"] for m in mutations})
    )

    started = time.monotonic()
    ok, baseline_s = baseline_passes(root, tests_path, timeout)
    if not ok:
        print("ERROR: the test suite does not pass on the unmutated code; nothing can be proven.", file=sys.stderr)
        return 1
    print(f"Baseline: test suite passes on the unmutated code ({baseline_s:.1f}s). "
          f"Running {len(mutations)} mutations with {workers} workers...")
    results = run_mutations(root, mutations, tests_path, workers, timeout)
    summary = summarise(results, requirement_ids)
    report = {
        "tool": "solotrace prove",
        "version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": head_commit(root),
        "dirty": is_dirty(root),
        "tests": tests_path,
        "workers": workers,
        "duration_s": round(time.monotonic() - started, 1),
        **summary,
    }
    (out_dir / "prove.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"{'Requirement':<12} {'tried':>5} {'killed':>6} {'survived':>8}  result")
    for req, v in summary["requirements"].items():
        verdict = "PROVEN" if v["proven"] else ("no mutations" if not v["tried"] else "NOT PROVEN")
        print(f"{req:<12} {v['tried']:>5} {v['killed']:>6} {v['survived']:>8}  {verdict}")
        for m in v["mutations"]:
            if m["outcome"] != "killed":
                print(f"{'':12}   {m['outcome'].upper()}: {m['id']} — {m['description']}")
    t = summary["totals"]
    print(f"Mutations killed: {t['killed']}/{t['mutations']} · requirements proven: "
          f"{t['requirements_proven']}/{t['requirements']} · {report['duration_s']}s")
    # Exit 0 only if every requirement is proven (a requirement without mutations is not).
    return 0 if t["requirements_proven"] == t["requirements"] else 2
