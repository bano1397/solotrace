"""
solotrace test — run the audited project's test suite and record every result.

A requirement can only count as proven if the tests cited for it actually *pass*
(not merely exist).  This command runs pytest with a JUnit report and stores one
outcome per test case in ``<out>/tests.json``.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from solotrace import __version__
from solotrace.repo import head_commit, is_dirty, repo_root
from solotrace.verify import parse_test_name


def _module_to_file(root: Path, classname: str) -> tuple[str, str | None]:
    """``pkg.tests.test_mod.TestX`` -> ("pkg/tests/test_mod.py", "TestX")."""
    parts = classname.split(".")
    for cut in range(len(parts), 0, -1):
        candidate = "/".join(parts[:cut]) + ".py"
        if (root / candidate).is_file():
            rest = parts[cut:]
            return candidate, (rest[0] if rest else None)
    return "/".join(parts) + ".py", None


def parse_junit(xml_text: str, root: Path) -> list[dict[str, Any]]:
    cases = []
    for case in ET.fromstring(xml_text).iter("testcase"):
        file, cls = _module_to_file(root, case.get("classname", ""))
        if case.find("failure") is not None or case.find("error") is not None:
            outcome = "failed"
        elif case.find("skipped") is not None:
            outcome = "skipped"
        else:
            outcome = "passed"
        name = case.get("name", "")
        cases.append({
            "file": file,
            "class": cls,
            "name": name,
            "base": name.split("[", 1)[0],
            "outcome": outcome,
            "time": float(case.get("time") or 0),
        })
    return cases


def run_tests(root: Path, tests_path: str, junit_path: Path, timeout: int = 1200) -> dict[str, Any]:
    cmd = [
        sys.executable, "-m", "pytest", tests_path, "-q",
        "-p", "no:cacheprovider", f"--junitxml={junit_path}", "-o", "junit_family=xunit2",
    ]
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    started = time.monotonic()
    proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=timeout, env=env, check=False)
    duration = time.monotonic() - started
    cases = parse_junit(junit_path.read_text(encoding="utf-8"), root) if junit_path.exists() else []
    counts = {k: sum(1 for c in cases if c["outcome"] == k) for k in ("passed", "failed", "skipped")}
    return {
        "tool": "solotrace test",
        "version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": head_commit(root),
        "dirty": is_dirty(root),
        "command": "python -m pytest " + tests_path,
        "exit_code": proc.returncode,
        "duration_s": round(duration, 2),
        "total": len(cases),
        **counts,
        "tail": proc.stdout.strip().splitlines()[-1:] if proc.stdout.strip() else [],
        "cases": cases,
    }


def lookup(cases: list[dict[str, Any]], file: str, test_name: str) -> bool | None:
    """True if every run case of the cited test passed, False if any failed, None if never run."""
    cls, func = parse_test_name(test_name)
    wanted_param = test_name.split("[", 1)[1] if "[" in test_name else None
    hits = [
        c for c in cases
        if c["file"] == file and c["base"] == func and (cls is None or c["class"] == cls)
        and (wanted_param is None or c["name"] == f"{func}[{wanted_param}")
    ]
    if not hits:
        return None
    return all(c["outcome"] == "passed" for c in hits)


def cmd_test(out: str, tests_path: str) -> int:
    root = repo_root()
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    junit = out_dir / "junit.xml"
    result = run_tests(root, tests_path, junit)
    (out_dir / "tests.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    junit.unlink(missing_ok=True)
    print(f"Test run of {tests_path}: {result['passed']} passed, {result['failed']} failed, "
          f"{result['skipped']} skipped in {result['duration_s']}s (exit {result['exit_code']})")
    return 0 if result["exit_code"] == 0 else 1
