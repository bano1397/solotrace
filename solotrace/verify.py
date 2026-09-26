"""
solotrace verify — Evidence Verifier (the anti-hallucination guard).

AI auditors cite code as ``{file, line, snippet}`` and tests as ``{file, test_name}``.
This command checks every citation against the real source:

* ``exact``        the snippet is at the cited line
* ``relocated``    the snippet exists in the file, but at another line (stale line number)
* ``not_found``    the snippet does not exist in the file (paraphrase or invention)
* ``too_short``    the snippet is too short to prove anything (e.g. ``"("``)
* ``invalid_path`` the path is absolute, contains ``..`` or escapes the repository
* ``missing_file`` the file does not exist

The auditor's claim (``line``, ``snippet``) is never overwritten.  The verifier only
adds ``verified``, ``match``, ``actual_line`` and ``actual_snippet``, so running it
twice gives the same answer and a paraphrase stays flagged forever.

Tests are checked with ``ast``: ``exists`` is added to every test citation.
Accepted forms: ``test_x``, ``test_x[param]``, ``TestClass::test_x``, ``TestClass.test_x``.
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from solotrace import __version__
from solotrace.repo import SourceReader, UnsafePathError, relative_display, repo_root
from solotrace.schemas import validate_verdict

MIN_SNIPPET_CHARS = 8        # a citation shorter than this proves nothing
MIN_PARTIAL_QUOTE = 16       # a partial quote of a long line must be at least this long
_WS = re.compile(r"\s+")


# ── snippet matching ─────────────────────────────────────────────────────────

MAX_REFLOW_LINES = 8          # a one-line quote may cover a statement wrapped over this many lines


def normalise(text: str) -> str:
    return _WS.sub(" ", text.strip())


def _strip_comment(line: str) -> str:
    """Drop a trailing ``# comment`` that is not inside a string literal."""
    in_quote: str | None = None
    for i, ch in enumerate(line):
        if in_quote:
            if ch == in_quote and line[i - 1] != "\\":
                in_quote = None
        elif ch in "'\"":
            in_quote = ch
        elif ch == "#" and (i == 0 or line[i - 1].isspace()):
            return line[:i].rstrip()
    return line


def snippet_lines(snippet: str) -> list[str]:
    """Quoted code lines, whitespace-normalised, with commentary comments removed."""
    lines = []
    for raw in snippet.splitlines():
        code = normalise(_strip_comment(raw))
        if code:
            lines.append(code)
    return lines


def compact(text: str) -> str:
    """Whitespace-free form, tolerant of trailing commas added when code is re-wrapped."""
    squeezed = _WS.sub("", text)
    for closer in ")]}":
        squeezed = squeezed.replace("," + closer, closer)
    return squeezed


def is_meaningful(lines: list[str]) -> bool:
    joined = "".join(lines)
    return len(joined) >= MIN_SNIPPET_CHARS and len(re.sub(r"\W", "", joined)) >= 4


def line_matches(source_line: str, quoted: str) -> bool:
    src = normalise(_strip_comment(source_line))
    if not src:
        return False
    if quoted == src:
        return True
    return len(quoted) >= MIN_PARTIAL_QUOTE and quoted in src


def _reflow_span(source: list[str], i: int, quoted: str) -> int:
    """Number of source lines (from index i) that a re-wrapped one-line quote covers, or 0."""
    target = compact(quoted)
    if len(target) < MIN_PARTIAL_QUOTE or not source[i].strip():
        return 0
    first = compact(_strip_comment(source[i]))
    if not first or not target.startswith(first[: min(len(first), 12)]):
        return 0
    raw = ""
    for k in range(i, min(len(source), i + MAX_REFLOW_LINES)):
        raw += " " + _strip_comment(source[k])
        joined = compact(raw)
        if k > i and (joined == target or target in joined):
            return k - i + 1
        if len(joined) > len(target) + 40:
            break
    return 0


def _is_code(line: str) -> bool:
    """A line that contains code (not blank, not a comment-only line)."""
    stripped = line.strip()
    return bool(stripped) and not stripped.startswith("#")


def match_at(source: list[str], start: int, quoted: list[str]) -> bool:
    """Do the quoted lines match the source starting at index *start*?

    Blank and comment-only source lines between quoted lines are skipped, because
    ``snippet_lines`` drops them from the quote as well.
    """
    i = start
    for q in quoted:
        while i < len(source) and not _is_code(source[i]):
            i += 1
        if i >= len(source):
            return False
        if line_matches(source[i], q):
            i += 1
            continue
        span = _reflow_span(source, i, q)
        if not span:
            return False
        i += span
    return True


def locate(source: list[str], cited_line: int, quoted: list[str]) -> int | None:
    """0-based index where the quote starts, preferring the cited line, else the nearest."""
    cited = cited_line - 1
    if 0 <= cited < len(source) and match_at(source, cited, quoted):
        return cited
    hits = [i for i in range(len(source)) if _is_code(source[i]) and match_at(source, i, quoted)]
    if not hits:
        return None
    return min(hits, key=lambda i: (abs(i - cited), i))


def verify_code_evidence(entry: dict[str, Any], reader: SourceReader) -> dict[str, Any]:
    """Return *entry* plus verifier fields. The claimed file/line/snippet are kept as-is."""
    result = {k: entry[k] for k in ("file", "line", "snippet")}
    try:
        source = reader.lines(entry["file"])
    except UnsafePathError:
        return {**result, "verified": False, "match": "invalid_path", "actual_line": None, "actual_snippet": None}
    if source is None:
        return {**result, "verified": False, "match": "missing_file", "actual_line": None, "actual_snippet": None}

    quoted = snippet_lines(entry["snippet"])
    # Unverified citations never get a copy of real file content (nothing leaks into outputs).
    if not is_meaningful(quoted):
        return {**result, "verified": False, "match": "too_short", "actual_line": None, "actual_snippet": None}

    index = locate(source, entry["line"], quoted)
    if index is None:
        return {**result, "verified": False, "match": "not_found", "actual_line": None, "actual_snippet": None}
    return {
        **result,
        "verified": True,
        "match": "exact" if index == entry["line"] - 1 else "relocated",
        "actual_line": index + 1,
        "actual_snippet": source[index],
    }


# ── test citations ───────────────────────────────────────────────────────────

def parse_test_name(name: str) -> tuple[str | None, str]:
    """``TestX::test_y[p]`` -> ("TestX", "test_y"); ``file.py::test_y`` -> (None, "test_y")."""
    base = name.split("[", 1)[0].strip()
    parts = [p for p in re.split(r"::|\.", base) if p and p != "py"]
    if not parts:
        return None, base
    func = parts[-1]
    cls = parts[-2] if len(parts) >= 2 and parts[-2][:1].isupper() else None
    return cls, func


def defined_tests(source_text: str) -> set[tuple[str | None, str]]:
    """All (class, function) pairs for test functions defined in a test module."""
    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        return set()
    found: set[tuple[str | None, str]] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            found.add((None, node.name))
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith("test"):
                    found.add((node.name, item.name))
    return found


def verify_test_evidence(entry: dict[str, Any], reader: SourceReader) -> dict[str, Any]:
    result = {"file": entry["file"], "test_name": entry["test_name"]}
    if "passed" in entry:
        result["passed"] = entry["passed"]
    try:
        text = reader.text(entry["file"])
    except UnsafePathError:
        return {**result, "exists": False}
    if text is None:
        return {**result, "exists": False}
    cls, func = parse_test_name(entry["test_name"])
    tests = defined_tests(text)
    exists = (cls, func) in tests if cls else any(name == func for _, name in tests)
    return {**result, "exists": exists}


# ── command ──────────────────────────────────────────────────────────────────

def _load_verdicts(verdicts_dir: Path) -> tuple[list[tuple[Path, dict]], list[str]]:
    loaded, errors = [], []
    for path in sorted(verdicts_dir.glob("REQ-*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            validate_verdict(data)
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        if data["id"] != path.stem:
            errors.append(f"{path.name}: id {data['id']!r} does not match the file name")
            continue
        loaded.append((path, data))
    return loaded, errors


def _write_json(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def verify_dir(out_dir: Path, reader: SourceReader, write: bool = True) -> dict[str, Any]:
    verdicts_dir = out_dir / "verdicts"
    if not verdicts_dir.is_dir():
        raise FileNotFoundError(f"directory not found: {verdicts_dir}")
    loaded, errors = _load_verdicts(verdicts_dir)
    if errors:
        raise ValueError("invalid verdict files:\n  " + "\n  ".join(errors))
    if not loaded:
        raise ValueError(f"no REQ-*.json verdicts in {verdicts_dir}")

    totals: Counter = Counter()
    per_verdict = []
    updated_files = []
    for path, verdict in loaded:
        code = [verify_code_evidence(e, reader) for e in verdict["code_evidence"]]
        tests = [verify_test_evidence(e, reader) for e in verdict["test_evidence"]]
        stats = Counter(e["match"] for e in code)
        stats["tests_checked"] = len(tests)
        stats["tests_missing"] = sum(1 for t in tests if not t["exists"])
        totals.update(stats)
        totals["checked"] += len(code)
        per_verdict.append({"id": verdict["id"], "code_evidence": len(code), "stats": dict(sorted(stats.items()))})
        updated = {**verdict, "code_evidence": code, "test_evidence": tests}
        validate_verdict(updated)
        updated_files.append((path, updated))

    report = {
        "tool": "solotrace verify",
        "version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": reader.describe(),
        "totals": {
            "checked": totals["checked"],
            "verified": totals["exact"] + totals["relocated"],
            "exact": totals["exact"],
            "relocated": totals["relocated"],
            "not_found": totals["not_found"],
            "too_short": totals["too_short"],
            "invalid_path": totals["invalid_path"],
            "missing_file": totals["missing_file"],
            "tests_checked": totals["tests_checked"],
            "tests_missing": totals["tests_missing"],
        },
        "verdicts": per_verdict,
    }
    if write:
        for path, updated in updated_files:
            _write_json(path, updated)
        _write_json(out_dir / "verification.json", report)
    return report


def cmd_verify(out: str, source_commit: str | None = None, check: bool = False) -> int:
    root = repo_root()
    out_dir = Path(out)
    reader = SourceReader(root, commit=source_commit)
    try:
        report = verify_dir(out_dir, reader, write=not check)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    t = report["totals"]
    src = report["source"]
    where = f"commit {src['commit'][:10]}" if src["kind"] == "commit" else "working tree"
    print(f"Evidence verification of {relative_display(out_dir, root)}/verdicts against the {where}")
    print(f"  Code citations checked : {t['checked']}")
    print(f"  Verified               : {t['verified']}  (exact {t['exact']}, relocated {t['relocated']})")
    print(f"  Not found (paraphrase) : {t['not_found']}")
    print(f"  Too short to prove     : {t['too_short']}")
    print(f"  Unsafe or missing path : {t['invalid_path'] + t['missing_file']}")
    print(f"  Test citations         : {t['tests_checked']}  ({t['tests_missing']} do not exist)")
    if check:
        unverified = t["checked"] - t["verified"]
        return 1 if unverified or t["tests_missing"] else 0
    return 0
