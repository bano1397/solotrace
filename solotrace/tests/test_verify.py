"""Evidence Verifier: citations are re-found in the source, never trusted, never rewritten."""
import json
import textwrap
from pathlib import Path

import pytest

from solotrace.repo import SourceReader, UnsafePathError
from solotrace.verify import (
    parse_test_name,
    snippet_lines,
    verify_code_evidence,
    verify_dir,
    verify_test_evidence,
)

SOURCE = textwrap.dedent('''\
    MAX_DEPOSIT = Decimal("50000.00")


    def deposit(db, account_id, *, amount, pin):
        account = get_account_or_404(db, account_id)
        if amount > MAX_DEPOSIT:
            raise HTTPException(status_code=400, detail="too much")
        _write_audit(
            db,
            actor_id=account_id,
            action="deposit",
            amount=amount,
        )
        return account
    ''')

TESTS = textwrap.dedent('''\
    import pytest

    def test_limit():
        assert True

    class TestDeposits:
        def test_zero(self):
            assert True

    @pytest.mark.parametrize("c", ["KP", "IR"])
    def test_sanctions(c):
        assert c
    ''')


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "svc.py").write_text(SOURCE)
    (tmp_path / "app" / "test_svc.py").write_text(TESTS)
    (tmp_path / "secret.txt").write_text("AWS_SECRET_ACCESS_KEY=do-not-leak\n")
    return tmp_path


@pytest.fixture()
def reader(repo: Path) -> SourceReader:
    return SourceReader(repo)


def cite(line: int, snippet: str, file: str = "app/svc.py") -> dict:
    return {"file": file, "line": line, "snippet": snippet}


def test_exact_quote_is_verified(reader):
    r = verify_code_evidence(cite(6, "if amount > MAX_DEPOSIT:"), reader)
    assert r["verified"] and r["match"] == "exact" and r["actual_line"] == 6


def test_stale_line_number_is_relocated_not_rejected(reader):
    r = verify_code_evidence(cite(2, "if amount > MAX_DEPOSIT:"), reader)
    assert r["verified"] and r["match"] == "relocated" and r["actual_line"] == 6
    assert r["line"] == 2  # the auditor's claim is kept


def test_paraphrase_is_rejected_and_claim_kept(reader):
    claim = "deposit() rejects anything above MAX_DEPOSIT"
    r = verify_code_evidence(cite(6, claim), reader)
    assert r["verified"] is False and r["match"] == "not_found"
    assert r["snippet"] == claim


def test_abridged_quote_with_ellipsis_is_rejected(reader):
    r = verify_code_evidence(cite(8, "_write_audit(...)"), reader)
    assert r["verified"] is False


def test_rewrapped_statement_is_verified(reader):
    one_line = '_write_audit(db, actor_id=account_id, action="deposit", amount=amount)'
    r = verify_code_evidence(cite(8, one_line), reader)
    assert r["verified"] and r["actual_line"] == 8


def test_added_comment_does_not_hide_real_code(reader):
    r = verify_code_evidence(cite(1, 'MAX_DEPOSIT = Decimal("50000.00")  # the REQ-02 limit'), reader)
    assert r["verified"]


@pytest.mark.parametrize("snippet", ["(", "raise", "   ", "x"])
def test_trivial_snippets_prove_nothing(reader, snippet):
    r = verify_code_evidence(cite(7, snippet or " "), reader)
    assert r["verified"] is False and r["match"] == "too_short"


def test_multi_line_quote_must_match_consecutive_lines(reader):
    good = "if amount > MAX_DEPOSIT:\n    raise HTTPException(status_code=400, detail=\"too much\")"
    bad = "if amount > MAX_DEPOSIT:\n    raise HTTPException(status_code=500, detail=\"invented\")"
    assert verify_code_evidence(cite(6, good), reader)["verified"]
    assert not verify_code_evidence(cite(6, bad), reader)["verified"]


@pytest.mark.parametrize("path", ["../secret.txt", "/etc/hosts", "app/../../secret.txt", "~/x.py", "C:/x.py"])
def test_paths_outside_the_repo_are_refused(reader, path):
    r = verify_code_evidence(cite(1, "AWS_SECRET_ACCESS_KEY=do-not-leak", file=path), reader)
    assert r["verified"] is False and r["match"] == "invalid_path"
    assert r["actual_snippet"] is None  # nothing from outside the repo is ever copied


def test_symlink_escaping_the_repo_is_refused(repo, reader, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside") / "leak.py"
    outside.write_text("TOKEN = 'secret-value-123'\n")
    (repo / "app" / "link.py").symlink_to(outside)
    with pytest.raises(UnsafePathError):
        reader.lines("app/link.py")


def test_missing_file(reader):
    r = verify_code_evidence(cite(1, "something meaningful", file="app/nope.py"), reader)
    assert r["match"] == "missing_file" and not r["verified"]


@pytest.mark.parametrize("name,expected", [
    ("test_limit", (None, "test_limit")),
    ("test_sanctions[KP]", (None, "test_sanctions")),
    ("TestDeposits::test_zero", ("TestDeposits", "test_zero")),
    ("TestDeposits.test_zero", ("TestDeposits", "test_zero")),
    ("app/test_svc.py::TestDeposits::test_zero", ("TestDeposits", "test_zero")),
    ("test_happy", (None, "test_happy")),
])
def test_parse_test_name(name, expected):
    assert parse_test_name(name) == expected


@pytest.mark.parametrize("name,exists", [
    ("test_limit", True),
    ("test_sanctions[IR]", True),
    ("TestDeposits::test_zero", True),
    ("test_zero", True),
    ("OtherClass::test_zero", False),
    ("test_invented_by_the_ai", False),
])
def test_cited_tests_must_exist(reader, name, exists):
    assert verify_test_evidence({"file": "app/test_svc.py", "test_name": name}, reader)["exists"] is exists


def test_snippet_lines_strip_comments_but_not_strings():
    assert snippet_lines('x = "a # b"  # note\n\n  y = 1') == ['x = "a # b"', "y = 1"]


def _write_verdict(out: Path, rid: str, evidence: list, tests: list, status: str = "covered") -> None:
    (out / "verdicts").mkdir(parents=True, exist_ok=True)
    (out / "verdicts" / f"{rid}.json").write_text(json.dumps({
        "id": rid, "status": status, "reason": "because",
        "code_evidence": evidence, "test_evidence": tests,
    }))


def test_verify_dir_is_idempotent_and_keeps_claims(repo, reader, tmp_path):
    out = tmp_path / "out"
    _write_verdict(out, "REQ-01", [cite(2, "if amount > MAX_DEPOSIT:"), cite(3, "made-up code line here")],
                   [{"file": "app/test_svc.py", "test_name": "test_limit"}])
    first = verify_dir(out, reader)
    snapshot = (out / "verdicts" / "REQ-01.json").read_text()
    second = verify_dir(out, reader)
    assert first["totals"] == second["totals"]
    assert (out / "verdicts" / "REQ-01.json").read_text() == snapshot
    assert first["totals"]["verified"] == 1 and first["totals"]["not_found"] == 1
    saved = json.loads(snapshot)
    assert saved["code_evidence"][1]["snippet"] == "made-up code line here"
    assert saved["code_evidence"][1]["verified"] is False


def test_verify_dir_rejects_mismatched_ids_without_writing(repo, reader, tmp_path):
    out = tmp_path / "out"
    _write_verdict(out, "REQ-01", [cite(6, "if amount > MAX_DEPOSIT:")], [])
    (out / "verdicts" / "REQ-02.json").write_text(json.dumps({
        "id": "REQ-01", "status": "covered", "reason": "x", "code_evidence": [], "test_evidence": []}))
    with pytest.raises(ValueError, match="does not match"):
        verify_dir(out, reader)
    assert not (out / "verification.json").exists()


def test_verification_report_has_no_absolute_paths(repo, reader, tmp_path):
    out = tmp_path / "out"
    _write_verdict(out, "REQ-01", [cite(6, "if amount > MAX_DEPOSIT:")], [])
    verify_dir(out, reader)
    assert str(tmp_path) not in (out / "verification.json").read_text()
