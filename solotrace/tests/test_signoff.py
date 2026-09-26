import json
from pathlib import Path

from solotrace import signoff
from solotrace.signoff import cmd_signoff, load_signoffs


def _matrix(out: Path, proven: int, audited_at: str = "2026-09-26T00:00:00+00:00") -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "matrix.json").write_text(json.dumps(
        {"audit": {"audited_at": audited_at}, "summary": {"proven": proven}, "rows": []}))


def test_signoff_is_bound_to_the_result_it_approves(tmp_path, monkeypatch):
    monkeypatch.setattr(signoff, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(signoff, "head_commit", lambda root: "abc123")
    out, no_bob = tmp_path / "out", tmp_path / "no-bob-sessions"
    _matrix(out, 12)
    assert cmd_signoff(str(out), "A Reviewer", "Approved", "chat", "final audit result") == 0
    [record] = load_signoffs(out, no_bob)
    assert record["by"] == "A Reviewer" and record["code_commit"] == "abc123"
    assert record["matches_current_result"] is True
    _matrix(out, 12, audited_at="2026-09-27T00:00:00+00:00")  # re-run, same result
    assert load_signoffs(out, no_bob)[0]["matches_current_result"] is True
    _matrix(out, 11)  # the result changed after the sign-off
    assert load_signoffs(out, no_bob)[0]["matches_current_result"] is False


def test_signoff_needs_a_result_first(tmp_path):
    assert cmd_signoff(str(tmp_path / "out"), "A Reviewer", "Approved", "chat", "final") == 1


def test_bob_and_local_signoffs_are_merged_in_time_order(tmp_path):
    bob, out = tmp_path / "bob_sessions", tmp_path / "out"
    bob.mkdir()
    out.mkdir()
    (bob / "signoffs.json").write_text(json.dumps({"signoffs": [
        {"approved_at": "2026-09-25T21:46:52+05:00", "task": "task03", "statement": "Approved"}]}))
    (out / "signoffs.json").write_text(json.dumps({"signoffs": [
        {"approved_at": "2026-09-26T09:00:00+05:00", "statement": "Approved final", "channel": "chat"}]}))
    records = load_signoffs(out, bob)
    assert [r["channel"] for r in records] == ["IBM Bob task03", "chat"]
    assert "matches_current_result" not in records[0]
