"""
solotrace/extract.py — PDF text extraction and requirement loading.

Dependencies: pypdf (already in requirements.txt), standard library only otherwise.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pypdf

from solotrace.schemas import validate_requirement

_REQ_ID_RE = re.compile(r"REQ-\d{2}")


# ── PDF extraction ────────────────────────────────────────────────────────────

def pdf_to_text(pdf_path: str | Path) -> str:
    """
    Extract all text from *pdf_path* and return it as a single string.

    Pages are separated by a form-feed character (``\\f``) so callers can
    split on page boundaries if needed.
    """
    reader = pypdf.PdfReader(str(pdf_path))
    pages: list[str] = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\f".join(pages)


# ── requirement loading ───────────────────────────────────────────────────────

def load_requirements(path: str | Path = "out/requirements.json") -> list[dict[str, Any]]:
    """
    Load, validate and return the requirements list from *path*.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If any entry fails schema validation, if IDs are not unique, or if
        they are not sequential starting from REQ-01.
    """
    path = Path(path)
    with path.open() as fh:
        data = json.load(fh)

    if not isinstance(data, list):
        raise ValueError("requirements.json must be a JSON array")

    # Validate each entry
    for i, entry in enumerate(data):
        try:
            validate_requirement(entry)
        except ValueError as exc:
            raise ValueError(f"entry {i}: {exc}") from exc

    # Uniqueness check
    ids = [entry["id"] for entry in data]
    if len(ids) != len(set(ids)):
        seen: set[str] = set()
        for req_id in ids:
            if req_id in seen:
                raise ValueError(f"duplicate requirement id: {req_id!r}")
            seen.add(req_id)

    # Sequential check (REQ-01, REQ-02, …, REQ-N)
    for i, req_id in enumerate(ids, start=1):
        expected = f"REQ-{i:02d}"
        if req_id != expected:
            raise ValueError(
                f"requirements are not sequential: expected {expected!r} at "
                f"position {i - 1}, got {req_id!r}"
            )

    return data
