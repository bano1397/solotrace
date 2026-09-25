"""
Tests for solotrace CLI commands: verify, matrix, report.

Uses only stdlib + pytest (no external deps).
"""
from __future__ import annotations

import ast
import json
import os
import textwrap
from pathlib import Path

import pytest

from solotrace.cli_verify import (
    _normalise,
    _snippet_core,
    _line_contains_core,
    _collect_test_names,
    _strip_parametrize_suffix,
    _verify_code_evidence,
    _verify_verdict,
    cmd_verify,
)
from solotrace.cli_matrix import cmd_matrix
from solotrace.cli_report import cmd_report


# ══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture()
def tmp_src(tmp_path: Path) -> Path:
    """Write a small Python source file and return its path."""
    src = tmp_path / "mymodule.py"
    src.write_text(
        textwrap.dedent("""\
        def foo():
            x = 1
            if x > 0:
                return True
            return False

        def bar():
            pass
        """),
        encoding="utf-8",
    )
    return src


@pytest.fixture()
def tmp_test_file(tmp_path: Path) -> Path:
    """Write a small test file and return its path."""
    tf = tmp_path / "test_things.py"
    tf.write_text(
        textwrap.dedent("""\
        def test_alpha():
            assert 1 == 1

        def test_beta():
            assert 2 == 2

        def helper_not_a_test():
            pass
        """),
        encoding="utf-8",
    )
    return tf


def _make_verdict(
    tmp_path: Path,
    req_id: str,
    code_evidence: list,
    test_evidence: list,
    status: str = "covered",
) -> Path:
    """Write a verdict JSON file into tmp_path/verdicts/ and return its path."""
    vdir = tmp_path / "verdicts"
    vdir.mkdir(parents=True, exist_ok=True)
    vf = vdir / f"{req_id}.json"
    data = {
        "id": req_id,
        "status": status,
        "reason": "Test verdict.",
        "code_evidence": code_evidence,
        "test_evidence": test_evidence,
    }
    vf.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return vf


# ══════════════════════════════════════════════════════════════════════════════
# Unit tests: _normalise / _snippet_core / _line_contains_core
# ══════════════════════════════════════════════════════════════════════════════

class TestHelpers:
    def test_normalise_strips_whitespace(self):
        assert _normalise("  hello   world  ") == "hello world"

    def test_normalise_collapses_tabs(self):
        assert _normalise("\tx\t=\t1\t") == "x = 1"

    def test_snippet_core_multiline(self):
        multi = "    if x > 0:\n        return True"
        assert _snippet_core(multi) == "if x > 0:"

    def test_snippet_core_single_line(self):
        assert _snippet_core("    return True") == "return True"

    def test_line_contains_core_match(self):
        assert _line_contains_core("    if x > 0:", "if x > 0:")

    def test_line_contains_core_no_match(self):
        assert not _line_contains_core("    return False", "if x > 0:")


class TestStripParametrizeSuffix:
    def test_strips_single_param(self):
        assert _strip_parametrize_suffix("test_name[KP]") == "test_name"

    def test_strips_multi_param(self):
        assert _strip_parametrize_suffix("test_foo[0-bar-baz]") == "test_foo"

    def test_no_suffix_unchanged(self):
        assert _strip_parametrize_suffix("test_no_params") == "test_no_params"

    def test_empty_brackets(self):
        assert _strip_parametrize_suffix("test_empty[]") == "test_empty"


# ══════════════════════════════════════════════════════════════════════════════
# Unit tests: _verify_code_evidence
# ══════════════════════════════════════════════════════════════════════════════

class TestVerifyCodeEvidence:

    def test_exact_match_returns_ok(self, tmp_src: Path):
        """Snippet matches the cited line exactly → outcome 'ok', verified=True."""
        entry = {
            "file": str(tmp_src),
            "line": 3,   # "    if x > 0:"
            "snippet": "if x > 0:",
        }
        updated, outcome = _verify_code_evidence(entry)
        assert outcome == "ok"
        assert updated["verified"] is True
        assert updated["line"] == 3

    def test_off_by_one_corrected(self, tmp_src: Path):
        """Snippet at wrong line number; found within ±5 → outcome 'corrected', line fixed."""
        # "    if x > 0:" is line 3; cite line 1 (off by 2)
        entry = {
            "file": str(tmp_src),
            "line": 1,
            "snippet": "if x > 0:",
        }
        updated, outcome = _verify_code_evidence(entry)
        assert outcome == "corrected"
        assert updated["verified"] is True
        assert updated["line"] == 3

    def test_paraphrase_snippet_replaced(self, tmp_src: Path):
        """Snippet is a paraphrase that doesn't appear in any ±5 window → outcome 'replaced', verified=False."""
        entry = {
            "file": str(tmp_src),
            "line": 2,
            "snippet": "completely wrong paraphrase that is not in the file at all xyz",
        }
        updated, outcome = _verify_code_evidence(entry)
        assert outcome == "replaced"
        assert updated["verified"] is False

    def test_missing_file_returns_no_file(self, tmp_path: Path):
        """File does not exist → outcome 'no_file', entry unchanged."""
        entry = {
            "file": str(tmp_path / "nonexistent.py"),
            "line": 1,
            "snippet": "anything",
        }
        updated, outcome = _verify_code_evidence(entry)
        assert outcome == "no_file"
        assert updated == entry  # unchanged


# ══════════════════════════════════════════════════════════════════════════════
# Unit tests: _collect_test_names
# ══════════════════════════════════════════════════════════════════════════════

class TestCollectTestNames:

    def test_known_test_functions_found(self, tmp_test_file: Path):
        names = _collect_test_names(str(tmp_test_file))
        assert "test_alpha" in names
        assert "test_beta" in names

    def test_non_test_function_excluded(self, tmp_test_file: Path):
        names = _collect_test_names(str(tmp_test_file))
        assert "helper_not_a_test" not in names

    def test_missing_file_returns_none(self, tmp_path: Path):
        result = _collect_test_names(str(tmp_path / "missing.py"))
        assert result is None


# ══════════════════════════════════════════════════════════════════════════════
# Unit tests: _verify_verdict — phantom test removal
# ══════════════════════════════════════════════════════════════════════════════

class TestVerifyVerdict:

    def test_real_test_kept(self, tmp_test_file: Path):
        verdict = {
            "id": "REQ-01",
            "status": "covered",
            "reason": "ok",
            "code_evidence": [],
            "test_evidence": [
                {"file": str(tmp_test_file), "test_name": "test_alpha"},
            ],
        }
        updated, stats = _verify_verdict(verdict)
        assert len(updated["test_evidence"]) == 1
        assert stats["tests_removed"] == 0

    def test_fake_test_removed(self, tmp_test_file: Path):
        """test_name that does not exist in the file is removed."""
        verdict = {
            "id": "REQ-01",
            "status": "covered",
            "reason": "ok",
            "code_evidence": [],
            "test_evidence": [
                {"file": str(tmp_test_file), "test_name": "test_does_not_exist"},
            ],
        }
        updated, stats = _verify_verdict(verdict)
        assert updated["test_evidence"] == []
        assert stats["tests_removed"] == 1

    def test_missing_test_file_removes_entry(self, tmp_path: Path):
        """File not found → entry removed (treated as phantom)."""
        verdict = {
            "id": "REQ-01",
            "status": "covered",
            "reason": "ok",
            "code_evidence": [],
            "test_evidence": [
                {"file": str(tmp_path / "ghost.py"), "test_name": "test_whatever"},
            ],
        }
        updated, stats = _verify_verdict(verdict)
        assert updated["test_evidence"] == []
        assert stats["tests_removed"] == 1

    def test_parametrized_test_id_kept(self, tmp_test_file: Path):
        """
        pytest parametrized IDs like "test_alpha[KP]" must match the function
        "test_alpha" — the [...] suffix must be stripped before the AST lookup.
        """
        verdict = {
            "id": "REQ-01",
            "status": "covered",
            "reason": "ok",
            "code_evidence": [],
            "test_evidence": [
                {"file": str(tmp_test_file), "test_name": "test_alpha[KP]"},
                {"file": str(tmp_test_file), "test_name": "test_beta[0-foo]"},
            ],
        }
        updated, stats = _verify_verdict(verdict)
        assert len(updated["test_evidence"]) == 2
        assert stats["tests_removed"] == 0

    def test_parametrized_nonexistent_function_removed(self, tmp_test_file: Path):
        """test_name[KP] where test_name does not exist is still removed."""
        verdict = {
            "id": "REQ-01",
            "status": "covered",
            "reason": "ok",
            "code_evidence": [],
            "test_evidence": [
                {"file": str(tmp_test_file), "test_name": "test_ghost[KP]"},
            ],
        }
        updated, stats = _verify_verdict(verdict)
        assert updated["test_evidence"] == []
        assert stats["tests_removed"] == 1


# ══════════════════════════════════════════════════════════════════════════════
# Integration tests: cmd_verify
# ══════════════════════════════════════════════════════════════════════════════

class TestCmdVerify:

    def test_verify_writes_verification_json(self, tmp_path: Path, tmp_src: Path):
        """cmd_verify must produce verification.json."""
        _make_verdict(
            tmp_path,
            "REQ-01",
            code_evidence=[{"file": str(tmp_src), "line": 3, "snippet": "if x > 0:"}],
            test_evidence=[],
        )
        cmd_verify(str(tmp_path))
        verif = json.loads((tmp_path / "verification.json").read_text())
        assert "totals" in verif
        assert verif["totals"]["checked"] == 1

    def test_verify_corrects_off_by_one(self, tmp_path: Path, tmp_src: Path):
        """cmd_verify corrects line numbers that are off within ±5 lines."""
        _make_verdict(
            tmp_path,
            "REQ-01",
            code_evidence=[{"file": str(tmp_src), "line": 1, "snippet": "if x > 0:"}],
            test_evidence=[],
        )
        cmd_verify(str(tmp_path))
        # Read updated verdict
        updated = json.loads((tmp_path / "verdicts" / "REQ-01.json").read_text())
        ce = updated["code_evidence"][0]
        assert ce["line"] == 3
        assert ce["verified"] is True

    def test_verify_marks_paraphrase_false(self, tmp_path: Path, tmp_src: Path):
        """Snippet that matches nothing is marked verified=False."""
        _make_verdict(
            tmp_path,
            "REQ-01",
            code_evidence=[{
                "file": str(tmp_src),
                "line": 2,
                "snippet": "THIS SNIPPET DOES NOT EXIST IN THE FILE ANYWHERE zzzz",
            }],
            test_evidence=[],
        )
        cmd_verify(str(tmp_path))
        updated = json.loads((tmp_path / "verdicts" / "REQ-01.json").read_text())
        ce = updated["code_evidence"][0]
        assert ce["verified"] is False

    def test_verify_removes_phantom_test(self, tmp_path: Path, tmp_src: Path, tmp_test_file: Path):
        """cmd_verify removes test_evidence entries for non-existent test functions."""
        _make_verdict(
            tmp_path,
            "REQ-01",
            code_evidence=[],
            test_evidence=[
                {"file": str(tmp_test_file), "test_name": "test_alpha"},      # real
                {"file": str(tmp_test_file), "test_name": "test_phantom"},    # fake
            ],
        )
        cmd_verify(str(tmp_path))
        updated = json.loads((tmp_path / "verdicts" / "REQ-01.json").read_text())
        kept = [te["test_name"] for te in updated["test_evidence"]]
        assert "test_alpha" in kept
        assert "test_phantom" not in kept

    def test_verify_totals_in_verification_json(self, tmp_path: Path, tmp_src: Path, tmp_test_file: Path):
        """Totals in verification.json count corrected and tests_removed correctly."""
        _make_verdict(
            tmp_path,
            "REQ-01",
            code_evidence=[
                {"file": str(tmp_src), "line": 3, "snippet": "if x > 0:"},  # ok
                {"file": str(tmp_src), "line": 1, "snippet": "if x > 0:"},  # corrected
            ],
            test_evidence=[
                {"file": str(tmp_test_file), "test_name": "test_phantom"},
            ],
        )
        cmd_verify(str(tmp_path))
        verif = json.loads((tmp_path / "verification.json").read_text())
        t = verif["totals"]
        assert t["checked"] == 2
        assert t["ok"] >= 1
        assert t["corrected"] >= 1
        assert t["tests_removed"] == 1


# ══════════════════════════════════════════════════════════════════════════════
# Integration tests: cmd_matrix
# ══════════════════════════════════════════════════════════════════════════════

def _write_requirements(out_dir: Path, reqs: list[dict]) -> None:
    (out_dir / "requirements.json").write_text(json.dumps(reqs), encoding="utf-8")


def _write_verdict_file(out_dir: Path, verdict: dict) -> None:
    vdir = out_dir / "verdicts"
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / f"{verdict['id']}.json").write_text(json.dumps(verdict), encoding="utf-8")


class TestCmdMatrix:

    def _make_req(self, req_id: str, status: str, tmp_path: Path) -> None:
        req = {
            "id": req_id,
            "title": f"Title {req_id}",
            "text": "text",
            "acceptance_criteria": ["AC1"],
            "risk": "High",
            "change": "none",
        }
        verdict = {
            "id": req_id,
            "status": status,
            "reason": f"reason for {req_id}",
            "code_evidence": [],
            "test_evidence": [],
        }
        _write_requirements(tmp_path, [req])
        _write_verdict_file(tmp_path, verdict)

    def test_matrix_written(self, tmp_path: Path):
        self._make_req("REQ-01", "covered", tmp_path)
        cmd_matrix(str(tmp_path))
        assert (tmp_path / "matrix.json").exists()

    def test_matrix_rows_count(self, tmp_path: Path):
        reqs = []
        for i, status in enumerate(["covered", "untested", "missing"], start=1):
            rid = f"REQ-{i:02d}"
            req = {
                "id": rid,
                "title": f"Title {rid}",
                "text": "t",
                "acceptance_criteria": ["AC"],
                "risk": "Low",
                "change": "none",
            }
            reqs.append(req)
            _write_verdict_file(
                tmp_path,
                {"id": rid, "status": status, "reason": "r",
                 "code_evidence": [], "test_evidence": []},
            )
        _write_requirements(tmp_path, reqs)
        cmd_matrix(str(tmp_path))
        matrix = json.loads((tmp_path / "matrix.json").read_text())
        assert len(matrix["rows"]) == 3
        assert matrix["summary"]["total"] == 3

    def test_matrix_score_100_percent(self, tmp_path: Path):
        reqs = []
        for i in range(1, 4):
            rid = f"REQ-{i:02d}"
            reqs.append({
                "id": rid, "title": "T", "text": "t",
                "acceptance_criteria": ["AC"], "risk": "Low", "change": "none",
            })
            _write_verdict_file(
                tmp_path,
                {"id": rid, "status": "covered", "reason": "r",
                 "code_evidence": [], "test_evidence": []},
            )
        _write_requirements(tmp_path, reqs)
        cmd_matrix(str(tmp_path))
        matrix = json.loads((tmp_path / "matrix.json").read_text())
        assert matrix["summary"]["score_percent"] == 100.0
        assert matrix["summary"]["covered"] == 3

    def test_matrix_score_zero_when_all_missing(self, tmp_path: Path):
        rid = "REQ-01"
        _write_requirements(tmp_path, [{
            "id": rid, "title": "T", "text": "t",
            "acceptance_criteria": ["AC"], "risk": "High", "change": "none",
        }])
        _write_verdict_file(
            tmp_path,
            {"id": rid, "status": "missing", "reason": "r",
             "code_evidence": [], "test_evidence": []},
        )
        cmd_matrix(str(tmp_path))
        matrix = json.loads((tmp_path / "matrix.json").read_text())
        assert matrix["summary"]["score_percent"] == 0.0
        assert matrix["summary"]["missing"] == 1

    def test_matrix_summary_keys_present(self, tmp_path: Path):
        self._make_req("REQ-01", "covered", tmp_path)
        cmd_matrix(str(tmp_path))
        matrix = json.loads((tmp_path / "matrix.json").read_text())
        summary = matrix["summary"]
        for key in ("total", "covered", "untested", "contradicts", "missing", "score_percent"):
            assert key in summary, f"Missing key: {key}"


# ══════════════════════════════════════════════════════════════════════════════
# Integration tests: cmd_report
# ══════════════════════════════════════════════════════════════════════════════

def _make_audit_dir(tmp_path: Path, subdir: str, score_covered: int, total: int) -> Path:
    d = tmp_path / subdir
    d.mkdir()
    reqs = []
    for i in range(1, total + 1):
        rid = f"REQ-{i:02d}"
        reqs.append({
            "id": rid, "title": f"T{i}", "text": "t",
            "acceptance_criteria": ["AC"], "risk": "High", "change": "none",
        })
    (d / "requirements.json").write_text(json.dumps(reqs), encoding="utf-8")

    vdir = d / "verdicts"
    vdir.mkdir()
    for i, req in enumerate(reqs):
        status = "covered" if i < score_covered else "missing"
        v = {
            "id": req["id"], "status": status, "reason": "r",
            "code_evidence": [], "test_evidence": [],
        }
        (vdir / f"{req['id']}.json").write_text(json.dumps(v), encoding="utf-8")

    # Write matrix.json
    covered = score_covered
    missing = total - covered
    matrix = {
        "rows": [
            {
                "id": req["id"],
                "title": req["title"],
                "risk": "High",
                "change": "none",
                "status": "covered" if i < score_covered else "missing",
                "reason": "r",
                "evidence": [],
                "tests": [],
            }
            for i, req in enumerate(reqs)
        ],
        "summary": {
            "total": total,
            "covered": covered,
            "untested": 0,
            "contradicts": 0,
            "missing": missing,
            "score_percent": round(covered / total * 100, 1) if total else 0.0,
        },
    }
    (d / "matrix.json").write_text(json.dumps(matrix), encoding="utf-8")

    (d / "timings.json").write_text(json.dumps({"stages": []}), encoding="utf-8")
    return d


class TestCmdReport:

    def test_report_file_created(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        before_dir = _make_audit_dir(tmp_path, "before", score_covered=5, total=10)
        after_dir = _make_audit_dir(tmp_path, "after", score_covered=8, total=10)
        cmd_report(str(before_dir), str(after_dir))
        assert (tmp_path / "AUDIT_REPORT.md").exists()

    def test_report_contains_scores(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        before_dir = _make_audit_dir(tmp_path, "before", score_covered=5, total=10)
        after_dir = _make_audit_dir(tmp_path, "after", score_covered=8, total=10)
        cmd_report(str(before_dir), str(after_dir))
        report = (tmp_path / "AUDIT_REPORT.md").read_text()
        assert "50.0%" in report   # before score
        assert "80.0%" in report   # after score

    def test_report_contains_matrix_table(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        before_dir = _make_audit_dir(tmp_path, "before", score_covered=1, total=2)
        after_dir = _make_audit_dir(tmp_path, "after", score_covered=1, total=2)
        cmd_report(str(before_dir), str(after_dir))
        report = (tmp_path / "AUDIT_REPORT.md").read_text()
        assert "Traceability Matrix" in report
        assert "REQ-01" in report

    def test_report_contains_gaps_section(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        before_dir = _make_audit_dir(tmp_path, "before", score_covered=0, total=2)
        after_dir = _make_audit_dir(tmp_path, "after", score_covered=0, total=2)
        cmd_report(str(before_dir), str(after_dir))
        report = (tmp_path / "AUDIT_REPORT.md").read_text()
        assert "Gaps" in report

    def test_report_includes_generated_timestamp(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        before_dir = _make_audit_dir(tmp_path, "before", score_covered=1, total=1)
        after_dir = _make_audit_dir(tmp_path, "after", score_covered=1, total=1)
        cmd_report(str(before_dir), str(after_dir))
        report = (tmp_path / "AUDIT_REPORT.md").read_text()
        assert "Generated" in report
        assert "UTC" in report


# ══════════════════════════════════════════════════════════════════════════════
# Integration tests: cmd_dashboard
# ══════════════════════════════════════════════════════════════════════════════

from solotrace.cli_dashboard import cmd_dashboard
from solotrace.cli_run import cmd_run


class TestCmdDashboard:

    def test_dashboard_creates_index_html(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """cmd_dashboard must produce docs/index.html."""
        monkeypatch.chdir(tmp_path)
        before_dir = _make_audit_dir(tmp_path, "before", score_covered=4, total=12)
        after_dir  = _make_audit_dir(tmp_path, "after",  score_covered=12, total=12)
        cmd_dashboard(str(before_dir), str(after_dir))
        assert (tmp_path / "docs" / "index.html").exists()

    def test_dashboard_is_self_contained_html(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """The generated HTML must not reference external URLs."""
        monkeypatch.chdir(tmp_path)
        before_dir = _make_audit_dir(tmp_path, "before", score_covered=2, total=4)
        after_dir  = _make_audit_dir(tmp_path, "after",  score_covered=4, total=4)
        cmd_dashboard(str(before_dir), str(after_dir))
        html = (tmp_path / "docs" / "index.html").read_text(encoding="utf-8")
        # Must be a valid HTML document
        assert "<!DOCTYPE html>" in html
        # Must not load external CSS/JS files
        assert "https://cdn" not in html
        assert '<script src="http' not in html
        assert '<link rel="stylesheet" href="http' not in html

    def test_dashboard_contains_scores(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Dashboard must embed the before and after compliance scores."""
        monkeypatch.chdir(tmp_path)
        before_dir = _make_audit_dir(tmp_path, "before", score_covered=4, total=12)
        after_dir  = _make_audit_dir(tmp_path, "after",  score_covered=12, total=12)
        cmd_dashboard(str(before_dir), str(after_dir))
        html = (tmp_path / "docs" / "index.html").read_text(encoding="utf-8")
        assert "33" in html   # before score ≈ 33%
        assert "100" in html  # after score 100%

    def test_dashboard_contains_matrix_data(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Dashboard must embed the traceability matrix JSON."""
        monkeypatch.chdir(tmp_path)
        before_dir = _make_audit_dir(tmp_path, "before", score_covered=1, total=2)
        after_dir  = _make_audit_dir(tmp_path, "after",  score_covered=2, total=2)
        cmd_dashboard(str(before_dir), str(after_dir))
        html = (tmp_path / "docs" / "index.html").read_text(encoding="utf-8")
        assert "REQ-01" in html
        assert "MATRIX_DATA" in html

    def test_dashboard_ibm_branding(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Dashboard must contain IBM Bob branding and the GitHub repo link."""
        monkeypatch.chdir(tmp_path)
        before_dir = _make_audit_dir(tmp_path, "before", score_covered=1, total=1)
        after_dir  = _make_audit_dir(tmp_path, "after",  score_covered=1, total=1)
        cmd_dashboard(str(before_dir), str(after_dir))
        html = (tmp_path / "docs" / "index.html").read_text(encoding="utf-8")
        assert "IBM Bob" in html
        assert "bano1397/solotrace" in html


# ══════════════════════════════════════════════════════════════════════════════
# Integration tests: cmd_run
# ══════════════════════════════════════════════════════════════════════════════

class TestCmdRun:

    def _make_run_dirs(self, tmp_path: Path) -> tuple[Path, Path]:
        """Set up minimal before/after audit dirs suitable for cmd_run."""
        before_dir = _make_audit_dir(tmp_path, "before", score_covered=1, total=2)
        after_dir  = _make_audit_dir(tmp_path, "after",  score_covered=2, total=2)
        return before_dir, after_dir

    def test_run_produces_all_outputs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """cmd_run must produce verification.json, matrix.json, AUDIT_REPORT.md, docs/index.html."""
        monkeypatch.chdir(tmp_path)
        before_dir, after_dir = self._make_run_dirs(tmp_path)
        cmd_run(
            spec="fake-spec.pdf",
            out=str(after_dir),
            before=str(before_dir),
            after=str(after_dir),
        )
        assert (after_dir / "verification.json").exists()
        assert (after_dir / "matrix.json").exists()
        assert (tmp_path / "AUDIT_REPORT.md").exists()
        assert (tmp_path / "docs" / "index.html").exists()

    def test_run_updates_timings(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """cmd_run must write automated stage timings to out/timings.json."""
        monkeypatch.chdir(tmp_path)
        before_dir, after_dir = self._make_run_dirs(tmp_path)
        cmd_run(
            spec="fake.pdf",
            out=str(after_dir),
            before=str(before_dir),
            after=str(after_dir),
        )
        timings = json.loads((after_dir / "timings.json").read_text())
        stage_names = [s["stage"] for s in timings["stages"]]
        assert "verify" in stage_names
        assert "matrix" in stage_names
        assert "report" in stage_names
        assert "dashboard" in stage_names
