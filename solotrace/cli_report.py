"""
solotrace report  --  Audit Report Generator

Reads:
  --before  directory with requirements.json, verdicts/, matrix.json, timings.json
  --after   directory with requirements.json, verdicts/, matrix.json, timings.json
            (and optionally verification.json)

Writes AUDIT_REPORT.md with:
  - Executive summary
  - Before / after compliance score
  - Full traceability matrix table
  - Gaps (non-covered requirements) with suggested fixes
  - Evidence-verification stats (if verification.json present)
  - Stage timings
  - Generated timestamp
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ── helpers ───────────────────────────────────────────────────────────────────

def _load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _fmt_duration(started: str, finished: str) -> str:
    """Return human-readable duration string from two ISO timestamps."""
    try:
        t0 = datetime.fromisoformat(started.replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(finished.replace("Z", "+00:00"))
        secs = (t1 - t0).total_seconds()
        if secs < 60:
            return f"{secs:.1f}s"
        return f"{secs / 60:.1f}min"
    except Exception:
        return "?"


def _load_matrix(out_dir: Path) -> dict[str, Any] | None:
    """Load matrix.json; build it on-the-fly from verdicts if missing."""
    m = _load_json(out_dir / "matrix.json")
    return m


def _score(matrix: dict[str, Any]) -> float:
    return matrix.get("summary", {}).get("score_percent", 0.0)


def _status_emoji(status: str) -> str:
    return {
        "covered": "✅",
        "untested": "⚠️",
        "contradicts": "❌",
        "missing": "🔴",
    }.get(status, "❓")


# ── report builder ────────────────────────────────────────────────────────────

def cmd_report(before_dir: str, after_dir: str) -> None:
    before = Path(before_dir)
    after = Path(after_dir)

    m_before = _load_matrix(before)
    m_after = _load_matrix(after)

    if m_before is None:
        print(f"ERROR: matrix.json not found in {before_dir}. "
              "Run `python -m solotrace matrix --out {before_dir}` first.",
              file=sys.stderr)
        sys.exit(1)
    if m_after is None:
        print(f"ERROR: matrix.json not found in {after_dir}. "
              "Run `python -m solotrace matrix --out {after_dir}` first.",
              file=sys.stderr)
        sys.exit(1)

    score_before = _score(m_before)
    score_after = _score(m_after)
    delta = round(score_after - score_before, 1)
    delta_str = f"+{delta}%" if delta >= 0 else f"{delta}%"

    summary_after = m_after.get("summary", {})
    summary_before = m_before.get("summary", {})

    # verification stats
    verif = _load_json(after / "verification.json")
    verif_before = _load_json(before / "verification.json")

    # timings
    timings_after = _load_json(after / "timings.json") or {}
    timings_before = _load_json(before / "timings.json") or {}

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines: list[str] = []

    # ── title & meta ──────────────────────────────────────────────────────────
    lines += [
        "# SoloTrace Audit Report",
        "",
        f"**Generated:** {now_str}  ",
        f"**Before audit:** `{before_dir}`  ",
        f"**After audit:** `{after_dir}`  ",
        "",
    ]

    # ── executive summary ─────────────────────────────────────────────────────
    lines += [
        "## Executive Summary",
        "",
        f"| Metric | Before | After | Δ |",
        f"|--------|--------|-------|---|",
        f"| Compliance score | {score_before}% | {score_after}% | {delta_str} |",
        f"| Covered | {summary_before.get('covered', '?')} | {summary_after.get('covered', '?')} | — |",
        f"| Untested | {summary_before.get('untested', '?')} | {summary_after.get('untested', '?')} | — |",
        f"| Contradicts | {summary_before.get('contradicts', '?')} | {summary_after.get('contradicts', '?')} | — |",
        f"| Missing | {summary_before.get('missing', '?')} | {summary_after.get('missing', '?')} | — |",
        f"| Total requirements | {summary_before.get('total', '?')} | {summary_after.get('total', '?')} | — |",
        "",
    ]

    # ── traceability matrix ───────────────────────────────────────────────────
    lines += [
        "## Traceability Matrix (after)",
        "",
        "| ID | Title | Risk | Change | Status | Tests |",
        "|----|-------|------|--------|--------|-------|",
    ]
    for row in m_after.get("rows", []):
        emoji = _status_emoji(row["status"])
        test_list = ", ".join(
            t.split(" (")[0] for t in row.get("tests", [])
        ) or "—"
        # Escape pipe characters in cells
        title = row["title"].replace("|", "\\|")
        lines.append(
            f"| {row['id']} | {title} | {row['risk']} | {row['change']} "
            f"| {emoji} {row['status']} | {test_list} |"
        )
    lines.append("")

    # ── gaps ──────────────────────────────────────────────────────────────────
    gaps = [r for r in m_after.get("rows", []) if r["status"] != "covered"]
    if gaps:
        lines += ["## Gaps and Suggested Fixes", ""]
        for row in gaps:
            emoji = _status_emoji(row["status"])
            lines += [
                f"### {row['id']} — {row['title']}",
                "",
                f"**Status:** {emoji} {row['status']}  ",
                f"**Risk:** {row['risk']}  ",
                "",
                f"**Reason:** {row['reason']}",
                "",
            ]
            # Load the full verdict for suggested_fix
            vf = after / "verdicts" / f"{row['id']}.json"
            v = _load_json(vf)
            if v and v.get("suggested_fix"):
                lines += [
                    "**Suggested fix:**",
                    "",
                    f"```",
                    v["suggested_fix"],
                    f"```",
                    "",
                ]
            if row.get("evidence"):
                lines += ["**Code evidence:**", ""]
                for ev in row["evidence"]:
                    lines.append(f"- `{ev}`")
                lines.append("")
    else:
        lines += ["## Gaps", "", "_No gaps — all requirements covered._", ""]

    # ── evidence verification stats ───────────────────────────────────────────
    def _verif_section(v: dict[str, Any] | None, label: str) -> list[str]:
        if v is None:
            return [f"### {label}", "", "_verification.json not found._", ""]
        t = v.get("totals", {})
        return [
            f"### {label}",
            "",
            f"| Metric | Count |",
            f"|--------|-------|",
            f"| Entries checked | {t.get('checked', '?')} |",
            f"| Verified OK | {t.get('ok', '?')} |",
            f"| Line corrected | {t.get('corrected', '?')} |",
            f"| Snippet replaced (verified=false) | {t.get('replaced', '?')} |",
            f"| File not found | {t.get('no_file', '?')} |",
            f"| Test entries removed | {t.get('tests_removed', '?')} |",
            "",
        ]

    lines += ["## Evidence Verification", ""]
    lines += _verif_section(verif_before, f"Before ({before_dir})")
    lines += _verif_section(verif, f"After ({after_dir})")

    # ── stage timings ─────────────────────────────────────────────────────────
    def _timing_rows(timings: dict[str, Any]) -> list[str]:
        rows = []
        for stage in timings.get("stages", []):
            dur = _fmt_duration(
                stage.get("started_at", ""),
                stage.get("finished_at", ""),
            )
            rows.append(f"| {stage.get('stage', '?')} | {stage.get('started_at', '?')} | {dur} |")
        return rows

    lines += [
        "## Stage Timings",
        "",
        "### Before",
        "",
        "| Stage | Started | Duration |",
        "|-------|---------|----------|",
    ]
    lines += _timing_rows(timings_before)
    lines += [
        "",
        "### After",
        "",
        "| Stage | Started | Duration |",
        "|-------|---------|----------|",
    ]
    lines += _timing_rows(timings_after)
    lines += ["", "---", f"_Report generated by SoloTrace at {now_str}_", ""]

    report_path = Path("AUDIT_REPORT.md")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report written: {report_path}")
    print(f"  Before score : {score_before}%")
    print(f"  After score  : {score_after}%")
    print(f"  Delta        : {delta_str}")
