"""Scoring on evidence, the audit report and the dashboard's safety properties."""
import json

import pytest

from solotrace.dashboard import render
from solotrace.matrix import build_row
from solotrace.report import build_report
from solotrace.testrun import lookup, parse_junit

REQ = {"id": "REQ-01", "title": "Limit", "text": "Deposits are capped.", "acceptance_criteria": ["cap holds"],
       "risk": "High", "change": "none"}
CASES = [
    {"file": "t/test_a.py", "class": None, "name": "test_cap", "base": "test_cap", "outcome": "passed", "time": 0},
    {"file": "t/test_a.py", "class": None, "name": "test_bad", "base": "test_bad", "outcome": "failed", "time": 0},
    {"file": "t/test_a.py", "class": "TestX", "name": "test_p[KP]", "base": "test_p", "outcome": "passed", "time": 0},
    {"file": "t/test_a.py", "class": "TestX", "name": "test_p[IR]", "base": "test_p", "outcome": "failed", "time": 0},
]
TESTS = {"cases": CASES, "total": 4, "passed": 2, "failed": 2, "skipped": 0, "commit": "abc"}


def verdict(status="covered", verified=True, test="test_cap", exists=True):
    return {"id": "REQ-01", "status": status, "reason": "r", "suggested_fix": "",
            "code_evidence": [{"file": "a.py", "line": 3, "snippet": "LIMIT = 5", "verified": verified,
                               "match": "exact" if verified else "not_found", "actual_line": 3 if verified else None,
                               "actual_snippet": "LIMIT = 5" if verified else None}],
            "test_evidence": [{"file": "t/test_a.py", "test_name": test, "exists": exists}]}


def prove(proven: bool):
    return {"requirements": {"REQ-01": {"tried": 2, "killed": 2 if proven else 1,
                                        "survived": 0 if proven else 1, "proven": proven}}}


@pytest.mark.parametrize("v,tests,prove_data,expected", [
    (verdict(), TESTS, prove(True), "proven"),
    (verdict(), TESTS, prove(False), "weak"),
    (verdict(), TESTS, None, "covered"),
    (verdict(verified=False), TESTS, prove(True), "unverified"),
    (verdict(test="test_bad"), TESTS, prove(True), "untested"),
    (verdict(exists=False), TESTS, prove(True), "untested"),
    (verdict(status="contradicts"), TESTS, prove(True), "contradicts"),
    (None, TESTS, prove(True), "missing"),
])
def test_final_status_needs_evidence_not_just_the_ai(v, tests, prove_data, expected):
    assert build_row(REQ, v, tests, prove_data)["status"] == expected


def test_lookup_handles_parametrized_and_class_tests():
    assert lookup(CASES, "t/test_a.py", "test_cap") is True
    assert lookup(CASES, "t/test_a.py", "test_bad") is False
    assert lookup(CASES, "t/test_a.py", "TestX::test_p[KP]") is True
    assert lookup(CASES, "t/test_a.py", "TestX::test_p") is False  # one parameter failed
    assert lookup(CASES, "t/test_a.py", "test_never_ran") is None


def test_parse_junit(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "test_m.py").write_text("")
    xml = ('<testsuites><testsuite>'
           '<testcase classname="pkg.test_m.TestK" name="test_a" time="0.1"/>'
           '<testcase classname="pkg.test_m" name="test_b[x]" time="0.1"><failure message="boom"/></testcase>'
           '<testcase classname="pkg.test_m" name="test_c" time="0"><skipped/></testcase>'
           '</testsuite></testsuites>')
    cases = parse_junit(xml, tmp_path)
    assert [(c["file"], c["class"], c["base"], c["outcome"]) for c in cases] == [
        ("pkg/test_m.py", "TestK", "test_a", "passed"),
        ("pkg/test_m.py", None, "test_b", "failed"),
        ("pkg/test_m.py", None, "test_c", "skipped"),
    ]


def _matrix(row):
    return {"audit": {"code_commit": "abc1234", "spec": {"path": "spec.pdf", "sha256": "f" * 64, "version": "2.0"}},
            "rows": [row],
            "summary": {"total": 1, "ai": {"covered": 1, "score_percent": 100.0},
                        "statuses": {"proven": 1, "covered": 0, "weak": 0, "unverified": 0, "untested": 0,
                                     "contradicts": 0, "missing": 0},
                        "evidence_score_percent": 100.0, "proven_percent": 100.0, "citations_verified": 1,
                        "citations_total": 1, "mutation_testing": True, "mutations_killed": 2,
                        "mutations_total": 2, "tests_run": TESTS}}


def test_report_states_scope_and_evidence():
    row = build_row(REQ, verdict(), TESTS, prove(True))
    text = build_report(None, None, _matrix(row), {"signoffs": [
        {"task": "task03", "approved_at": "2026-09-25T21:46:52+05:00", "statement": "Approved"}]})
    assert "f" * 64 in text and "abc1234" in text
    assert "`a.py:3`" in text and "✔ verified" in text
    assert "1 of 1 requirements are **proven**" in text
    assert "2026-09-25T21:46:52+05:00" in text


def test_dashboard_embeds_data_without_breaking_out_of_the_script_tag():
    evil = "</script><img src=x onerror=alert(1)>"
    data = {"version": "2.0.0", "pages_url": "https://example.test/", "title": evil}
    html = render(data)
    payload = html.split('<script id="data" type="application/json">', 1)[1].split("</script>", 1)[0]
    assert "</script>" not in payload and "<img" not in payload
    assert json.loads(payload)["title"] == evil  # the JSON still round-trips exactly


def test_matrix_rechecks_evidence_instead_of_trusting_flags(tmp_path, monkeypatch):
    """A verdict file that claims verified:true for invented code must not score."""
    from solotrace.matrix import build_matrix

    monkeypatch.chdir(tmp_path)
    (tmp_path / "app.py").write_text("LIMIT = 50000\n")
    out = tmp_path / "out"
    (out / "verdicts").mkdir(parents=True)
    req = {**REQ, "id": "REQ-01"}
    (out / "requirements.json").write_text(json.dumps([req]))
    fake = {"id": "REQ-01", "status": "covered", "reason": "trust me",
            "code_evidence": [{"file": "app.py", "line": 1, "snippet": "enforce_limit(amount, LIMIT)", "verified": True,
                               "match": "exact", "actual_line": 1, "actual_snippet": "enforce_limit(amount, LIMIT)"}],
            "test_evidence": [{"file": "tests/test_app.py", "test_name": "test_limit", "exists": True}]}
    (out / "verdicts" / "REQ-01.json").write_text(json.dumps(fake))
    matrix = build_matrix(out)
    row = matrix["rows"][0]
    assert row["checks"]["citations_verified"] == 0
    assert row["status"] == "unverified"
