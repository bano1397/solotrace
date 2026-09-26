"""
Lightweight stdlib-only validators for SoloTrace JSON schemas.

No external dependencies — uses only Python builtins.
"""
from __future__ import annotations

import re
from typing import Any

_REQ_ID_RE = re.compile(r"^REQ-\d{2}$")
_RISK_VALUES = {"High", "Medium", "Low"}
_CHANGE_VALUES = {"none", "changed", "new"}
_STATUS_VALUES = {"covered", "untested", "contradicts", "missing"}
_MATCH_VALUES = {"exact", "relocated", "not_found", "ambiguous", "too_short", "invalid_path", "missing_file"}
# Fields written by the AI auditor, plus optional fields added by `solotrace verify`.
_CODE_EVIDENCE_KEYS = {"file", "line", "snippet", "verified", "match", "actual_line", "actual_snippet"}
_TEST_EVIDENCE_KEYS = {"file", "test_name", "exists", "passed"}


# ── internal helpers ──────────────────────────────────────────────────────────

def _require_keys(obj: dict, keys: list[str], context: str) -> None:
    for key in keys:
        if key not in obj:
            raise ValueError(f"{context}: missing required field '{key}'")


def _require_str(obj: dict, field: str, context: str, min_len: int = 1) -> None:
    if not isinstance(obj.get(field), str):
        raise ValueError(f"{context}: field '{field}' must be a string")
    if len(obj[field]) < min_len:
        raise ValueError(f"{context}: field '{field}' must not be empty")


def _require_enum(obj: dict, field: str, allowed: set[str], context: str) -> None:
    if obj.get(field) not in allowed:
        raise ValueError(
            f"{context}: field '{field}' must be one of {sorted(allowed)!r}, "
            f"got {obj.get(field)!r}"
        )


# ── public API ────────────────────────────────────────────────────────────────

def validate_requirement(data: Any) -> None:
    """
    Validate *data* against requirement.schema.json.

    Raises :class:`ValueError` with a descriptive message on the first violation.
    Does nothing if *data* is valid.
    """
    if not isinstance(data, dict):
        raise ValueError("requirement: must be a JSON object (dict)")

    ctx = "requirement"
    _require_keys(data, ["id", "title", "text", "acceptance_criteria", "risk", "change"], ctx)

    # id
    if not isinstance(data["id"], str) or not _REQ_ID_RE.match(data["id"]):
        raise ValueError(
            f"{ctx}: 'id' must match pattern ^REQ-\\d{{2}}$, got {data['id']!r}"
        )

    # title / text
    _require_str(data, "title", ctx)
    _require_str(data, "text", ctx)

    # acceptance_criteria
    ac = data["acceptance_criteria"]
    if not isinstance(ac, list) or len(ac) == 0:
        raise ValueError(f"{ctx}: 'acceptance_criteria' must be a non-empty array")
    for i, item in enumerate(ac):
        if not isinstance(item, str) or not item:
            raise ValueError(
                f"{ctx}: 'acceptance_criteria[{i}]' must be a non-empty string"
            )

    # enums
    _require_enum(data, "risk", _RISK_VALUES, ctx)
    _require_enum(data, "change", _CHANGE_VALUES, ctx)

    # no extra keys
    allowed = {"id", "title", "text", "acceptance_criteria", "risk", "change"}
    extra = set(data.keys()) - allowed
    if extra:
        raise ValueError(f"{ctx}: unexpected fields: {sorted(extra)!r}")


def validate_verdict(data: Any) -> None:
    """
    Validate *data* against verdict.schema.json.

    Raises :class:`ValueError` with a descriptive message on the first violation.
    Does nothing if *data* is valid.
    """
    if not isinstance(data, dict):
        raise ValueError("verdict: must be a JSON object (dict)")

    ctx = "verdict"
    _require_keys(data, ["id", "status", "reason", "code_evidence", "test_evidence"], ctx)

    # id
    if not isinstance(data["id"], str) or not _REQ_ID_RE.match(data["id"]):
        raise ValueError(
            f"{ctx}: 'id' must match pattern ^REQ-\\d{{2}}$, got {data['id']!r}"
        )

    _require_enum(data, "status", _STATUS_VALUES, ctx)
    _require_str(data, "reason", ctx)

    # code_evidence
    ce = data["code_evidence"]
    if not isinstance(ce, list):
        raise ValueError(f"{ctx}: 'code_evidence' must be an array")
    for i, item in enumerate(ce):
        ectx = f"{ctx}.code_evidence[{i}]"
        if not isinstance(item, dict):
            raise ValueError(f"{ectx}: must be an object")
        _require_keys(item, ["file", "line", "snippet"], ectx)
        _require_str(item, "file", ectx)
        _require_str(item, "snippet", ectx)
        if not isinstance(item["line"], int) or isinstance(item["line"], bool):
            raise ValueError(f"{ectx}: 'line' must be an integer")
        if item["line"] < 1:
            raise ValueError(f"{ectx}: 'line' must be >= 1")
        extra = set(item.keys()) - _CODE_EVIDENCE_KEYS
        if extra:
            raise ValueError(f"{ectx}: unexpected fields: {sorted(extra)!r}")
        if "verified" in item and not isinstance(item["verified"], bool):
            raise ValueError(f"{ectx}: 'verified' must be a boolean if present")
        if "match" in item and item["match"] not in _MATCH_VALUES:
            raise ValueError(f"{ectx}: 'match' must be one of {sorted(_MATCH_VALUES)!r}")
        if item.get("actual_line") is not None and (
            not isinstance(item["actual_line"], int) or isinstance(item["actual_line"], bool)
        ):
            raise ValueError(f"{ectx}: 'actual_line' must be an integer or null")
        if item.get("actual_snippet") is not None and not isinstance(item["actual_snippet"], str):
            raise ValueError(f"{ectx}: 'actual_snippet' must be a string or null")

    # test_evidence
    te = data["test_evidence"]
    if not isinstance(te, list):
        raise ValueError(f"{ctx}: 'test_evidence' must be an array")
    for i, item in enumerate(te):
        tctx = f"{ctx}.test_evidence[{i}]"
        if not isinstance(item, dict):
            raise ValueError(f"{tctx}: must be an object")
        _require_keys(item, ["file", "test_name"], tctx)
        _require_str(item, "file", tctx)
        _require_str(item, "test_name", tctx)
        extra = set(item.keys()) - _TEST_EVIDENCE_KEYS
        if extra:
            raise ValueError(f"{tctx}: unexpected fields: {sorted(extra)!r}")
        for flag in ("exists", "passed"):
            if item.get(flag) is not None and not isinstance(item[flag], bool):
                raise ValueError(f"{tctx}: '{flag}' must be a boolean or null")

    # optional suggested_fix
    if "suggested_fix" in data and not isinstance(data["suggested_fix"], str):
        raise ValueError(f"{ctx}: 'suggested_fix' must be a string if present")

    # no extra keys
    # "verified" is not a top-level field; it lives inside code_evidence items
    allowed = {"id", "status", "reason", "code_evidence", "test_evidence", "suggested_fix"}
    extra = set(data.keys()) - allowed
    if extra:
        raise ValueError(f"{ctx}: unexpected fields: {sorted(extra)!r}")
