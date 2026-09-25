"""
solotrace run  --  Full audit pipeline

Runs the following stages in order, printing each with wall-clock timing:

  1. extract-check — validate out/requirements.json (extracted by IBM Bob)
  2. verify        — evidence anti-hallucination guard
  3. matrix        — build traceability matrix
  4. report        — write AUDIT_REPORT.md
  5. dashboard     — write docs/index.html

The READ (document understanding), AUDIT (parallel subagents), and FIX stages
are NOT automated here — they run inside IBM Bob (SoloTrace Auditor mode +
solotrace-audit skill).  This command picks up after the verdicts have been
written and validates / reports on them.

Usage
-----
    python -m solotrace run --spec demo-data/LedgerLite-Requirements-v2.0.pdf
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from solotrace.cli_verify import cmd_verify
from solotrace.cli_matrix import cmd_matrix
from solotrace.cli_report import cmd_report
from solotrace.cli_dashboard import cmd_dashboard


# ── timing helpers ────────────────────────────────────────────────────────────

class _Timer:
    def __init__(self) -> None:
        self._t0: float = 0.0

    def start(self) -> str:
        self._t0 = time.monotonic()
        return datetime.now(timezone.utc).isoformat()

    def elapsed(self) -> float:
        return time.monotonic() - self._t0


def _banner(stage: str, width: int = 60) -> str:
    pad = (width - len(stage) - 2) // 2
    return f"{'─' * pad} {stage} {'─' * (width - pad - len(stage) - 2)}"


# ── extract-check stage ───────────────────────────────────────────────────────

def _stage_extract_check(out_dir: Path) -> None:
    """
    Validate out/requirements.json against the JSON schema.

    The actual PDF extraction and requirement drafting happen inside IBM Bob
    (SoloTrace Auditor mode + solotrace-audit skill).  This stage only confirms
    that the file is present and schema-valid.
    """
    from solotrace.extract import load_requirements

    req_path = out_dir / "requirements.json"
    reqs = load_requirements(req_path)
    print(f"  requirements.json: {len(reqs)} requirements validated ✓")


# ── public command ────────────────────────────────────────────────────────────

def cmd_run(spec: str, out: str, before: str, after: str) -> None:
    """
    Run all post-audit pipeline stages and record timings.

    Parameters
    ----------
    spec:
        Path to the PDF specification (used only for display / documentation).
    out:
        Directory containing requirements.json and verdicts/ (default: out).
    before:
        Pre-fix audit directory (default: out-before).
    after:
        Post-fix audit directory = same as *out* (default: out).
    """
    out_dir = Path(out)

    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║           SoloTrace — automated compliance pipeline          ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print("  Spec  :", spec)
    print("  Out   :", out)
    print()
    print("  NOTE: READ (document understanding), AUDIT (12 parallel subagents),")
    print("        HUMAN SIGN-OFF, and FIX (Agent mode) stages run inside IBM Bob")
    print("        (SoloTrace Auditor mode + solotrace-audit skill).")
    print("        This command runs the post-fix verification and reporting stages.")
    print()

    stages: list[dict] = []
    timer = _Timer()

    # ── Stage 1: extract-check ────────────────────────────────────────────────
    print(_banner("1 / 5  extract-check"))
    started = timer.start()
    try:
        _stage_extract_check(out_dir)
    except Exception as exc:
        print(f"  ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    elapsed = timer.elapsed()
    stages.append({"stage": "extract-check", "started_at": started,
                   "finished_at": datetime.now(timezone.utc).isoformat()})
    print(f"  ✓  {elapsed:.2f}s\n")

    # ── Stage 2: verify ───────────────────────────────────────────────────────
    print(_banner("2 / 5  verify"))
    started = timer.start()
    cmd_verify(out)
    elapsed = timer.elapsed()
    stages.append({"stage": "verify", "started_at": started,
                   "finished_at": datetime.now(timezone.utc).isoformat()})
    print(f"  ✓  {elapsed:.2f}s\n")

    # ── Stage 3: matrix ───────────────────────────────────────────────────────
    print(_banner("3 / 5  matrix"))
    started = timer.start()
    cmd_matrix(out)
    elapsed = timer.elapsed()
    stages.append({"stage": "matrix", "started_at": started,
                   "finished_at": datetime.now(timezone.utc).isoformat()})
    print(f"  ✓  {elapsed:.2f}s\n")

    # ── Stage 4: report ───────────────────────────────────────────────────────
    print(_banner("4 / 5  report"))
    started = timer.start()
    cmd_report(before, after)
    elapsed = timer.elapsed()
    stages.append({"stage": "report", "started_at": started,
                   "finished_at": datetime.now(timezone.utc).isoformat()})
    print(f"  ✓  {elapsed:.2f}s\n")

    # ── Stage 5: dashboard ────────────────────────────────────────────────────
    print(_banner("5 / 5  dashboard"))
    started = timer.start()
    cmd_dashboard(before, after)
    elapsed = timer.elapsed()
    stages.append({"stage": "dashboard", "started_at": started,
                   "finished_at": datetime.now(timezone.utc).isoformat()})
    print(f"  ✓  {elapsed:.2f}s\n")

    # ── Write timings.json ────────────────────────────────────────────────────
    timings_path = out_dir / "timings.json"
    existing_timings: dict = {}
    if timings_path.exists():
        try:
            existing_timings = json.loads(timings_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    existing_stages = existing_timings.get("stages", [])
    # Preserve human-run stages (read, audit, fix, re-audit) and append our automated stages
    automated_names = {s["stage"] for s in stages}
    preserved = [s for s in existing_stages if s.get("stage") not in automated_names]
    timings_path.write_text(
        json.dumps({"stages": preserved + stages}, indent=2),
        encoding="utf-8",
    )

    print("══════════════════════════════════════════════════════════════")
    print("  Pipeline complete.")
    print(f"  Timings written : {timings_path}")
    print(f"  Report          : AUDIT_REPORT.md")
    print(f"  Dashboard       : docs/index.html")
    print("══════════════════════════════════════════════════════════════")
    print()
