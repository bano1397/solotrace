"""Mutation testing: sabotage must be caught by the tests, or the requirement is not proven."""
import json
import textwrap
from pathlib import Path

import pytest

from solotrace.prove import baseline_passes, load_mutations, run_mutations, summarise
from solotrace.repo import SourceReader

CODE = textwrap.dedent('''\
    LIMIT = 100


    def allowed(amount):
        return 0 < amount <= LIMIT


    def fee(amount):
        return 1
    ''')

TESTS = textwrap.dedent('''\
    from calc import allowed


    def test_limit_boundary():
        assert allowed(100)
        assert not allowed(101)
        assert not allowed(0)
    ''')


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    (tmp_path / "calc.py").write_text(CODE)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_calc.py").write_text(TESTS)
    return tmp_path


def write_mutations(out: Path, req: str, mutations: list[dict]) -> None:
    (out / "mutations").mkdir(parents=True, exist_ok=True)
    (out / "mutations" / f"{req}.json").write_text(json.dumps({"requirement": req, "mutations": mutations}))


def m(mid, find, replace, desc="sabotage"):
    return {"id": mid, "file": "calc.py", "find": find, "replace": replace, "description": desc}


def test_guarded_requirement_is_proven_and_unguarded_one_is_not(project, tmp_path):
    out = tmp_path / "out"
    write_mutations(out, "REQ-01", [m("REQ-01-M1", "LIMIT = 100", "LIMIT = 101"),
                                    m("REQ-01-M2", "0 < amount", "0 <= amount")])
    write_mutations(out, "REQ-02", [m("REQ-02-M1", "return 1", "return 2")])
    mutations, errors = load_mutations(out / "mutations", SourceReader(project))
    assert errors == []
    ok, _ = baseline_passes(project, "tests", timeout=120)
    assert ok
    results = run_mutations(project, mutations, "tests", workers=2, timeout=120)
    summary = summarise(results, ["REQ-01", "REQ-02"])
    assert summary["requirements"]["REQ-01"]["proven"] is True
    assert summary["requirements"]["REQ-01"]["killed"] == 2
    assert summary["requirements"]["REQ-02"]["proven"] is False  # nothing tests the fee
    assert summary["requirements"]["REQ-02"]["survived"] == 1
    assert summary["totals"]["requirements_proven"] == 1
    assert (project / "calc.py").read_text() == CODE  # the real repository is never modified


def test_killed_by_names_the_failing_test(project, tmp_path):
    out = tmp_path / "out"
    write_mutations(out, "REQ-01", [m("REQ-01-M1", "LIMIT = 100", "LIMIT = 99")])
    mutations, _ = load_mutations(out / "mutations", SourceReader(project))
    [result] = run_mutations(project, mutations, "tests", workers=1, timeout=120)
    assert result["outcome"] == "killed"
    assert result["killed_by"].endswith("test_limit_boundary")


def test_broken_mutation_is_invalid_not_killed(project, tmp_path):
    out = tmp_path / "out"
    write_mutations(out, "REQ-01", [m("REQ-01-M1", "LIMIT = 100", "LIMIT = = 100")])
    mutations, _ = load_mutations(out / "mutations", SourceReader(project))
    [result] = run_mutations(project, mutations, "tests", workers=1, timeout=120)
    assert result["outcome"] == "invalid"


@pytest.mark.parametrize("bad,message", [
    (m("REQ-01-M1", "not in the file", "x"), "exactly once"),
    (m("REQ-01-M1", "LIMIT = 100", "LIMIT = 100"), "identical"),
    ({**m("REQ-01-M1", "LIMIT = 100", "LIMIT = 1"), "file": "../calc.py"}, "parent-directory"),
    ({"id": "REQ-01-M1"}, "needs string fields"),
])
def test_invalid_mutation_specs_are_reported(project, tmp_path, bad, message):
    out = tmp_path / "out"
    write_mutations(out, "REQ-01", [bad])
    mutations, errors = load_mutations(out / "mutations", SourceReader(project))
    assert mutations == []
    assert any(message in e for e in errors), errors


def test_ambiguous_find_is_rejected(project, tmp_path):
    out = tmp_path / "out"
    write_mutations(out, "REQ-01", [m("REQ-01-M1", "amount", "x")])
    _, errors = load_mutations(out / "mutations", SourceReader(project))
    assert any("exactly once" in e for e in errors)


def test_file_name_must_match_requirement(project, tmp_path):
    out = tmp_path / "out"
    (out / "mutations").mkdir(parents=True)
    (out / "mutations" / "REQ-01.json").write_text(json.dumps({"requirement": "REQ-02", "mutations": []}))
    _, errors = load_mutations(out / "mutations", SourceReader(project))
    assert errors and "does not match" in errors[0]


def test_requirement_without_mutations_is_not_proven():
    summary = summarise([], ["REQ-01"])
    assert summary["requirements"]["REQ-01"]["proven"] is False
