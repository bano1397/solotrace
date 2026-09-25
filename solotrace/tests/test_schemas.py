"""
Tests for solotrace/schemas.py — validate_requirement() and validate_verdict().

Covers:
- Happy-path valid objects.
- Every required-field missing case.
- Type errors (wrong types for each field).
- Enum violations (risk, change, status).
- Pattern violations (id).
- Boundary / edge cases (empty lists, line < 1, extra keys).
"""
import pytest
from solotrace.schemas import validate_requirement, validate_verdict


# ── helpers ───────────────────────────────────────────────────────────────────

def _valid_req(**overrides):
    base = {
        "id": "REQ-01",
        "title": "Deposit limit",
        "text": "Deposit amount must be > 0 and <= 50000.00.",
        "acceptance_criteria": [
            "Deposits of 0 are rejected.",
            "Deposits of 50000.00 are accepted.",
            "Deposits of 50000.01 are rejected.",
        ],
        "risk": "High",
        "change": "none",
    }
    base.update(overrides)
    return base


def _valid_verdict(**overrides):
    base = {
        "id": "REQ-01",
        "status": "covered",
        "reason": "Implemented and tested.",
        "code_evidence": [
            {"file": "ledgerlite/services.py", "line": 123, "snippet": "if amount > _MAX_DEPOSIT:"}
        ],
        "test_evidence": [
            {"file": "ledgerlite/tests/test_spec2_deposit_limits.py", "test_name": "test_boundary_50000_01_rejected"}
        ],
    }
    base.update(overrides)
    return base


# ══════════════════════════════════════════════════════════════════════════════
# validate_requirement
# ══════════════════════════════════════════════════════════════════════════════

class TestValidateRequirement:

    # ── happy path ────────────────────────────────────────────────────────────

    def test_valid_requirement_passes(self):
        validate_requirement(_valid_req())

    def test_all_risk_values_accepted(self):
        for risk in ("High", "Medium", "Low"):
            validate_requirement(_valid_req(risk=risk))

    def test_all_change_values_accepted(self):
        for change in ("none", "changed", "new"):
            validate_requirement(_valid_req(change=change))

    def test_id_boundary_two_digits(self):
        validate_requirement(_valid_req(id="REQ-99"))

    def test_id_zero_padded(self):
        validate_requirement(_valid_req(id="REQ-00"))

    def test_multiple_acceptance_criteria(self):
        validate_requirement(_valid_req(acceptance_criteria=["AC1", "AC2", "AC3"]))

    # ── not a dict ────────────────────────────────────────────────────────────

    def test_non_dict_raises(self):
        with pytest.raises(ValueError, match="must be a JSON object"):
            validate_requirement(["REQ-01"])

    def test_none_raises(self):
        with pytest.raises(ValueError):
            validate_requirement(None)

    # ── missing required fields ───────────────────────────────────────────────

    @pytest.mark.parametrize("field", ["id", "title", "text", "acceptance_criteria", "risk", "change"])
    def test_missing_field_raises(self, field):
        req = _valid_req()
        del req[field]
        with pytest.raises(ValueError, match=f"missing required field '{field}'"):
            validate_requirement(req)

    # ── id pattern ────────────────────────────────────────────────────────────

    def test_id_wrong_prefix_raises(self):
        with pytest.raises(ValueError, match="'id' must match"):
            validate_requirement(_valid_req(id="REQ-1"))

    def test_id_three_digits_raises(self):
        with pytest.raises(ValueError, match="'id' must match"):
            validate_requirement(_valid_req(id="REQ-001"))

    def test_id_no_prefix_raises(self):
        with pytest.raises(ValueError, match="'id' must match"):
            validate_requirement(_valid_req(id="01"))

    def test_id_not_string_raises(self):
        with pytest.raises(ValueError, match="'id' must match"):
            validate_requirement(_valid_req(id=1))

    # ── title / text types ────────────────────────────────────────────────────

    def test_title_not_string_raises(self):
        with pytest.raises(ValueError, match="'title' must be a string"):
            validate_requirement(_valid_req(title=123))

    def test_text_not_string_raises(self):
        with pytest.raises(ValueError, match="'text' must be a string"):
            validate_requirement(_valid_req(text=None))

    # ── acceptance_criteria ───────────────────────────────────────────────────

    def test_acceptance_criteria_empty_list_raises(self):
        with pytest.raises(ValueError, match="non-empty array"):
            validate_requirement(_valid_req(acceptance_criteria=[]))

    def test_acceptance_criteria_not_list_raises(self):
        with pytest.raises(ValueError, match="non-empty array"):
            validate_requirement(_valid_req(acceptance_criteria="single string"))

    def test_acceptance_criteria_item_not_string_raises(self):
        with pytest.raises(ValueError, match="acceptance_criteria\\[0\\]"):
            validate_requirement(_valid_req(acceptance_criteria=[42]))

    def test_acceptance_criteria_empty_string_raises(self):
        with pytest.raises(ValueError, match="acceptance_criteria\\[0\\]"):
            validate_requirement(_valid_req(acceptance_criteria=[""]))

    # ── enum violations ───────────────────────────────────────────────────────

    def test_invalid_risk_raises(self):
        with pytest.raises(ValueError, match="'risk'"):
            validate_requirement(_valid_req(risk="Critical"))

    def test_invalid_change_raises(self):
        with pytest.raises(ValueError, match="'change'"):
            validate_requirement(_valid_req(change="updated"))

    # ── extra keys ────────────────────────────────────────────────────────────

    def test_extra_key_raises(self):
        req = _valid_req()
        req["priority"] = "P1"
        with pytest.raises(ValueError, match="unexpected fields"):
            validate_requirement(req)


# ══════════════════════════════════════════════════════════════════════════════
# validate_verdict
# ══════════════════════════════════════════════════════════════════════════════

class TestValidateVerdict:

    # ── happy path ────────────────────────────────────────────────────────────

    def test_valid_verdict_passes(self):
        validate_verdict(_valid_verdict())

    def test_all_status_values_accepted(self):
        for status in ("covered", "untested", "contradicts", "missing"):
            validate_verdict(_valid_verdict(status=status))

    def test_empty_evidence_arrays_accepted(self):
        validate_verdict(_valid_verdict(code_evidence=[], test_evidence=[]))

    def test_optional_suggested_fix_accepted(self):
        validate_verdict(_valid_verdict(suggested_fix="Add a test for boundary X."))

    def test_multiple_evidence_entries(self):
        validate_verdict(_valid_verdict(
            code_evidence=[
                {"file": "a.py", "line": 1, "snippet": "x"},
                {"file": "b.py", "line": 2, "snippet": "y"},
            ],
            test_evidence=[
                {"file": "t.py", "test_name": "test_a"},
                {"file": "t.py", "test_name": "test_b"},
            ],
        ))

    # ── not a dict ────────────────────────────────────────────────────────────

    def test_non_dict_raises(self):
        with pytest.raises(ValueError, match="must be a JSON object"):
            validate_verdict("covered")

    # ── missing required fields ───────────────────────────────────────────────

    @pytest.mark.parametrize("field", ["id", "status", "reason", "code_evidence", "test_evidence"])
    def test_missing_field_raises(self, field):
        v = _valid_verdict()
        del v[field]
        with pytest.raises(ValueError, match=f"missing required field '{field}'"):
            validate_verdict(v)

    # ── id pattern ────────────────────────────────────────────────────────────

    def test_id_invalid_raises(self):
        with pytest.raises(ValueError, match="'id' must match"):
            validate_verdict(_valid_verdict(id="REQ-1"))

    # ── status enum ──────────────────────────────────────────────────────────

    def test_invalid_status_raises(self):
        with pytest.raises(ValueError, match="'status'"):
            validate_verdict(_valid_verdict(status="partial"))

    # ── reason ────────────────────────────────────────────────────────────────

    def test_reason_not_string_raises(self):
        with pytest.raises(ValueError, match="'reason' must be a string"):
            validate_verdict(_valid_verdict(reason=42))

    # ── code_evidence items ───────────────────────────────────────────────────

    def test_code_evidence_not_list_raises(self):
        with pytest.raises(ValueError, match="'code_evidence' must be an array"):
            validate_verdict(_valid_verdict(code_evidence="not a list"))

    def test_code_evidence_item_missing_file_raises(self):
        with pytest.raises(ValueError, match="missing required field 'file'"):
            validate_verdict(_valid_verdict(code_evidence=[{"line": 1, "snippet": "x"}]))

    def test_code_evidence_item_missing_line_raises(self):
        with pytest.raises(ValueError, match="missing required field 'line'"):
            validate_verdict(_valid_verdict(code_evidence=[{"file": "a.py", "snippet": "x"}]))

    def test_code_evidence_item_missing_snippet_raises(self):
        with pytest.raises(ValueError, match="missing required field 'snippet'"):
            validate_verdict(_valid_verdict(code_evidence=[{"file": "a.py", "line": 1}]))

    def test_code_evidence_line_not_int_raises(self):
        with pytest.raises(ValueError, match="'line' must be an integer"):
            validate_verdict(_valid_verdict(
                code_evidence=[{"file": "a.py", "line": "10", "snippet": "x"}]
            ))

    def test_code_evidence_line_zero_raises(self):
        with pytest.raises(ValueError, match="'line' must be >= 1"):
            validate_verdict(_valid_verdict(
                code_evidence=[{"file": "a.py", "line": 0, "snippet": "x"}]
            ))

    def test_code_evidence_line_negative_raises(self):
        with pytest.raises(ValueError, match="'line' must be >= 1"):
            validate_verdict(_valid_verdict(
                code_evidence=[{"file": "a.py", "line": -5, "snippet": "x"}]
            ))

    def test_code_evidence_extra_key_raises(self):
        with pytest.raises(ValueError, match="unexpected fields"):
            validate_verdict(_valid_verdict(
                code_evidence=[{"file": "a.py", "line": 1, "snippet": "x", "extra": "bad"}]
            ))

    # ── test_evidence items ───────────────────────────────────────────────────

    def test_test_evidence_not_list_raises(self):
        with pytest.raises(ValueError, match="'test_evidence' must be an array"):
            validate_verdict(_valid_verdict(test_evidence={}))

    def test_test_evidence_item_missing_file_raises(self):
        with pytest.raises(ValueError, match="missing required field 'file'"):
            validate_verdict(_valid_verdict(test_evidence=[{"test_name": "test_x"}]))

    def test_test_evidence_item_missing_test_name_raises(self):
        with pytest.raises(ValueError, match="missing required field 'test_name'"):
            validate_verdict(_valid_verdict(test_evidence=[{"file": "t.py"}]))

    def test_test_evidence_extra_key_raises(self):
        with pytest.raises(ValueError, match="unexpected fields"):
            validate_verdict(_valid_verdict(
                test_evidence=[{"file": "t.py", "test_name": "t", "extra": "bad"}]
            ))

    # ── suggested_fix ────────────────────────────────────────────────────────

    def test_suggested_fix_not_string_raises(self):
        with pytest.raises(ValueError, match="'suggested_fix' must be a string"):
            validate_verdict(_valid_verdict(suggested_fix=123))

    # ── extra top-level keys ──────────────────────────────────────────────────

    def test_extra_top_level_key_raises(self):
        v = _valid_verdict()
        v["reviewer"] = "alice"
        with pytest.raises(ValueError, match="unexpected fields"):
            validate_verdict(v)
