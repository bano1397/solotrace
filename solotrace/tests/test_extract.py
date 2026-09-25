"""
Tests for solotrace/extract.py.

Covers:
- pdf_to_text: returns a non-empty string containing all 12 REQ-xx IDs.
- load_requirements: happy path loads and validates 12 entries.
- load_requirements: raises ValueError on duplicate IDs.
- load_requirements: raises ValueError on non-sequential IDs.
- load_requirements: raises ValueError when an entry fails schema validation.
- load_requirements: raises FileNotFoundError on missing file.
"""
import json
import re
import tempfile
from pathlib import Path

import pytest

from solotrace.extract import load_requirements, pdf_to_text

_PDF_PATH = Path("demo-data/LedgerLite-Requirements-v2.0.pdf")
_REQUIREMENTS_PATH = Path("out/requirements.json")
_REQ_ID_PATTERN = re.compile(r"REQ-\d{2}")


# ── pdf_to_text ───────────────────────────────────────────────────────────────

class TestPdfToText:

    def test_returns_non_empty_string(self):
        text = pdf_to_text(_PDF_PATH)
        assert isinstance(text, str)
        assert len(text) > 100

    def test_contains_all_12_req_ids(self):
        text = pdf_to_text(_PDF_PATH)
        found_ids = set(_REQ_ID_PATTERN.findall(text))
        expected = {f"REQ-{i:02d}" for i in range(1, 13)}
        assert expected.issubset(found_ids), (
            f"Missing IDs in extracted text: {expected - found_ids}"
        )

    def test_contains_spec_title(self):
        text = pdf_to_text(_PDF_PATH)
        assert "LedgerLite" in text

    def test_path_as_string_accepted(self):
        text = pdf_to_text(str(_PDF_PATH))
        assert "REQ-01" in text

    def test_missing_pdf_raises(self):
        with pytest.raises(Exception):
            pdf_to_text("demo-data/does_not_exist.pdf")


# ── load_requirements ─────────────────────────────────────────────────────────

class TestLoadRequirements:

    def test_loads_12_requirements(self):
        reqs = load_requirements(_REQUIREMENTS_PATH)
        assert len(reqs) == 12

    def test_all_ids_sequential(self):
        reqs = load_requirements(_REQUIREMENTS_PATH)
        ids = [r["id"] for r in reqs]
        expected = [f"REQ-{i:02d}" for i in range(1, 13)]
        assert ids == expected

    def test_all_entries_pass_schema_validation(self):
        """load_requirements calls validate_requirement internally; if this
        returns without raising, all 12 entries are schema-valid."""
        reqs = load_requirements(_REQUIREMENTS_PATH)
        assert all(isinstance(r, dict) for r in reqs)

    def test_change_counts(self):
        reqs = load_requirements(_REQUIREMENTS_PATH)
        change_counts = {}
        for r in reqs:
            change_counts[r["change"]] = change_counts.get(r["change"], 0) + 1
        assert change_counts.get("changed", 0) == 1, "Expected exactly 1 CHANGED requirement"
        assert change_counts.get("new", 0) == 3, "Expected exactly 3 NEW requirements"
        assert change_counts.get("none", 0) == 8, "Expected exactly 8 unchanged requirements"

    def test_req05_is_changed(self):
        reqs = load_requirements(_REQUIREMENTS_PATH)
        req05 = next(r for r in reqs if r["id"] == "REQ-05")
        assert req05["change"] == "changed"

    def test_new_requirements_are_09_10_11(self):
        reqs = load_requirements(_REQUIREMENTS_PATH)
        new_ids = sorted(r["id"] for r in reqs if r["change"] == "new")
        assert new_ids == ["REQ-09", "REQ-10", "REQ-11"]

    def test_missing_file_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_requirements("out/does_not_exist.json")

    def test_duplicate_id_raises_value_error(self):
        reqs = load_requirements(_REQUIREMENTS_PATH)
        # Duplicate REQ-01
        dup = [reqs[0].copy()] + list(reqs)
        dup[1] = {**dup[1], "id": "REQ-01"}  # second entry also REQ-01
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(dup, f)
            tmp_path = f.name
        with pytest.raises(ValueError, match="duplicate"):
            load_requirements(tmp_path)

    def test_non_sequential_id_raises_value_error(self):
        reqs = load_requirements(_REQUIREMENTS_PATH)
        # Swap the id of the second entry so it breaks sequence
        bad = [r.copy() for r in reqs]
        bad[1] = {**bad[1], "id": "REQ-99"}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(bad, f)
            tmp_path = f.name
        with pytest.raises(ValueError, match="sequential"):
            load_requirements(tmp_path)

    def test_invalid_entry_raises_value_error(self):
        reqs = load_requirements(_REQUIREMENTS_PATH)
        bad = [r.copy() for r in reqs]
        bad[0] = {**bad[0], "risk": "Critical"}  # invalid enum
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(bad, f)
            tmp_path = f.name
        with pytest.raises(ValueError):
            load_requirements(tmp_path)

    def test_not_a_list_raises_value_error(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump({"id": "REQ-01"}, f)
            tmp_path = f.name
        with pytest.raises(ValueError, match="JSON array"):
            load_requirements(tmp_path)
