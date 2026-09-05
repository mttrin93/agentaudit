"""The suite's own tripwire: adding a case record must not move an unrelated test.

A test about transport, or about a namespace being dropped on every exit path, is
not a test about the library. When `data-leakage-001-scripted_crescendo` was
admitted it turned 112 tests red across 37 files, because most of them reached the
committed library for a case and assumed whatever came back was plain, single-turn
and one of eighteen (#150). Nothing in the suite said that was an assumption, so
nothing caught it until a variant was written to disk.

Local to this file: the two guards below are the statement that was missing. The
first pins what the per-family fixtures hand out; the second names the modules
entitled to read `backend/cases/` at all, so a new dependence on library contents
arrives as a failure here rather than as ninety failures elsewhere.
"""

from __future__ import annotations

import pytest

from backend.bench.library import Case, Family, Transform


@pytest.mark.parametrize("family", list(Family))
def test_every_family_fixture_is_a_plain_single_turn_case(
    family: Family, request: pytest.FixtureRequest
) -> None:
    case: Case = request.getfixturevalue(FIXTURE_NAMES[family])
    assert case.family is family
    assert case.transform is Transform.PLAIN
    assert case.derived_from is None
    assert len(case.payload) == 1


FIXTURE_NAMES = {
    Family.DATA_LEAKAGE: "leakage_case",
    Family.INDIRECT_PROMPT_INJECTION: "injection_case",
    Family.SCOPE_CREEP: "scope_creep_case",
    Family.HALT_DEFEAT: "halt_defeat_case",
    Family.WRONGFUL_COMMITMENT: "wrongful_commitment_case",
    Family.DISCLOSURE_DENIAL: "disclosure_denial_case",
}
