"""Export an index of IBM Bob task sessions for this project (read-only).

Reads Bob's local task database (~/.bob/db/bob.db) in read-only mode and writes
bob_sessions/sessions.json: one entry per Bob task with its start/end time,
Bobcoin cost, context size and the subagents it spawned.  Only timestamps,
titles, costs and counts are exported — never message contents or settings.

    python scripts/export_bob_sessions.py
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
from pathlib import Path

DB = Path.home() / ".bob" / "db" / "bob.db"
OUT = Path(__file__).resolve().parents[1] / "bob_sessions" / "sessions.json"
PKT = dt.timezone(dt.timedelta(hours=5), "PKT")

# Screenshot evidence captured for each top-level task (see bob_sessions/).
SCREENSHOTS = {
    "Create a new Python project": "solotrace_task01_summary_P0-P4_setup_app_mode_read_audit.png",
    "Build the SoloTrace CLI": "solotrace_task02_summary_P5_cli_evidence_verifier.png",
    "Stage 3 — FIX": "solotrace_task03_summary_P6_fix_and_reaudit.png",
    "Polish SoloTrace": "solotrace_task04_summary_P7_dashboard_pages.png",
}


def _iso(ms: int) -> str:
    return dt.datetime.fromtimestamp(ms / 1000, PKT).isoformat(timespec="seconds")


def main() -> None:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = con.execute(
        "select id, parent_id, title, task_type, created_at, updated_at, costs from tasks order by created_at"
    ).fetchall()
    tasks = {r[0]: r for r in rows}
    children: dict[str, list] = {}
    for r in rows:
        if r[1]:
            children.setdefault(r[1], []).append(r)

    sessions = []
    number = 0
    for tid, parent, title, ttype, created, updated, costs in rows:
        if parent or ttype != "normal" or not (title or "").strip():
            continue
        cost = json.loads(costs or "{}")
        if cost.get("cost", 0) < 1:  # skip an aborted 0.09-coin attempt in the wrong folder
            continue
        number += 1
        subs = children.get(tid, [])
        sub_start = min((s[4] for s in subs), default=None)
        sub_end = max((s[5] for s in subs), default=None)
        first_line = title.strip().splitlines()[0]
        sessions.append({
            "task": f"task{number:02d}",
            "task_id": tid,
            "title": first_line[:120],
            "started_at": _iso(created),
            "finished_at": _iso(updated),
            "duration_min": round((updated - created) / 60000, 1),
            "bobcoins": round(cost.get("cost", 0), 2),
            "context_tokens": cost.get("contextTokens"),
            "subagents": {
                "count": len(subs),
                "parallel_wall_clock_s": round((sub_end - sub_start) / 1000, 1) if subs else None,
                "sum_of_durations_s": round(sum(s[5] - s[4] for s in subs) / 1000, 1) if subs else None,
                "bobcoins": round(sum(json.loads(s[6] or "{}").get("cost", 0) for s in subs), 2),
                "started_at": _iso(sub_start) if subs else None,
            },
            "screenshot": next((v for k, v in SCREENSHOTS.items() if first_line.startswith(k)), None),
        })
    # Human compliance sign-offs typed into Bob (only the approval line and its time).
    signoffs = []
    task_numbers = {s["task_id"]: s["task"] for s in sessions}
    for task_id, data, created in con.execute(
        "select task_id, data, created_at from messages where role = 'user' order by created_at"
    ):
        if task_id not in task_numbers:
            continue
        text = data if isinstance(data, str) else str(data)
        marker = text.find("Approved")
        if marker == -1 or "compliance sign-off" not in text[marker:marker + 200]:
            continue
        line = text[marker:].split("\"", 1)[0].split("\\n", 1)[0].strip()
        signoffs.append({"task": task_numbers[task_id], "approved_at": _iso(created), "statement": line})
    (OUT.parent / "signoffs.json").write_text(json.dumps({"source": "IBM Bob IDE task history (read-only export)",
                                                         "signoffs": signoffs}, indent=2) + "\n", encoding="utf-8")

    total = round(sum(s["bobcoins"] for s in sessions), 2)
    OUT.write_text(json.dumps({"source": "IBM Bob IDE local task history (read-only export)",
                               "timezone": "PKT (UTC+05:00)", "total_bobcoins": total,
                               "sessions": sessions}, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(sessions)} tasks, {total} Bobcoins)")


if __name__ == "__main__":
    main()
