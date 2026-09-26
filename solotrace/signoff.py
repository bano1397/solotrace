"""
solotrace signoff — record a human compliance sign-off of an audit result.

The sign-off is bound to exactly what was approved: the audited commit and a SHA-256
of the traceability matrix (ignoring only when the pipeline ran).  If the result changes
afterwards, the report and dashboard show that the sign-off no longer matches it.

    python -m solotrace signoff --by "Jane Doe" --statement "Approved — compliance sign-off by Jane Doe"
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from solotrace.repo import head_commit, repo_root


def result_fingerprint(matrix_path: Path) -> str:
    """SHA-256 of the audit result in *matrix_path*, ignoring only ``audit.audited_at``."""
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    matrix.get("audit", {}).pop("audited_at", None)
    canonical = json.dumps(matrix, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_signoffs(out_dir: Path, bob_sessions: Path = Path("bob_sessions")) -> list[dict[str, Any]]:
    """All sign-offs: those typed into IBM Bob (exported) and those recorded with this command."""
    records: list[dict[str, Any]] = []
    bob = bob_sessions / "signoffs.json"
    if bob.exists():
        for s in json.loads(bob.read_text(encoding="utf-8")).get("signoffs", []):
            records.append({**s, "channel": s.get("channel") or f"IBM Bob {s.get('task', '')}".strip()})
    local = out_dir / "signoffs.json"
    if local.exists():
        records.extend(json.loads(local.read_text(encoding="utf-8")).get("signoffs", []))
    matrix = out_dir / "matrix.json"
    current = result_fingerprint(matrix) if matrix.exists() else None
    for r in records:
        if r.get("result_sha256"):
            r["matches_current_result"] = r["result_sha256"] == current
    return sorted(records, key=lambda r: r.get("approved_at", ""))


def cmd_signoff(out: str, by: str, statement: str, channel: str, scope: str) -> int:
    out_dir = Path(out)
    matrix = out_dir / "matrix.json"
    if not matrix.exists():
        print(f"ERROR: {matrix} not found — run `python -m solotrace run` first, then sign off the result.",
              file=sys.stderr)
        return 1
    path = out_dir / "signoffs.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"signoffs": []}
    record = {
        "approved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "by": by,
        "statement": statement,
        "channel": channel,
        "scope": scope,
        "code_commit": head_commit(repo_root()),
        "result_sha256": result_fingerprint(matrix),
    }
    data["signoffs"].append(record)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Sign-off recorded: {by} at {record['approved_at']} (result {record['result_sha256'][:12]}…)")
    return 0
