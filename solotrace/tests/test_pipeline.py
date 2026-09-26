"""The requirements under audit must be exactly the ones in the specification."""
from pathlib import Path

import pytest

from solotrace.extract import load_requirements
from solotrace.pipeline import _spec_info, matches_spec, numbers_in

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "demo-data" / "LedgerLite-Requirements-v2.0.pdf"
REQS = ROOT / "out" / "requirements.json"

pytestmark = pytest.mark.skipif(not SPEC.exists() or not REQS.exists(), reason="demo data not present")


def test_the_real_requirements_match_the_spec():
    info = _spec_info(SPEC, ROOT, load_requirements(REQS))
    assert info["version"] == "2.0" and info["requirements_in_spec"] == 12


def test_dropping_requirements_is_detected():
    with pytest.raises(ValueError, match="missing"):
        _spec_info(SPEC, ROOT, load_requirements(REQS)[:2])


@pytest.mark.parametrize("old,new", [("5,000.00", "50,000.00"), ("second, different user", "manager")])
def test_rewriting_a_requirement_is_detected(old, new):
    reqs = load_requirements(REQS)
    reqs[4] = {**reqs[4], "text": reqs[4]["text"].replace(old, new)}
    with pytest.raises(ValueError, match="differs from the spec"):
        _spec_info(SPEC, ROOT, reqs)


def test_numbers_in():
    assert numbers_in("above 20,000.00 per day, 5 attempts") == {"20000.00", "5"}
    assert matches_spec("a limit of 10.00", "REQ-99 a limit of 10.00 applies")
