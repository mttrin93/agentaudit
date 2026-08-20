"""The stored copy of the published agentic list, and the subtraction over it.

The point of `published.py` is that the negative-coverage claim is **derived**, so the
tests that matter are the ones a hand-written list could not pass:

* the subtraction *moves* when the library's families move, so the claim cannot go
  stale while still looking current;
* every family says whether it claims a category, so a family added later cannot
  quietly inherit the old answer;
* the two mistakes that make a gap **disappear** — a claim on an identifier the copy
  does not carry, and a reason left behind for a category somebody has since started
  claiming — are refused rather than absorbed.

The copy itself is asserted as a copy: ten entries, published order, no rewording.
There is nothing here that checks the titles are *correct*, because this repository
cannot check that — the provenance is two agreeing secondary readings and
`published.py` says so.
"""

import pytest

from backend.bench.library import Family
from backend.bench.published import (
    AGENTIC_TOP_10_2026,
    EDITION,
    FAMILY_CATEGORY,
    OUT_OF_REACH,
    UNTESTED_AGENTIC_CATEGORIES,
    AgenticCategory,
    UntestedCategory,
    untested_categories,
)

# --- The copy ----------------------------------------------------------------


def test_the_copy_is_ten_entries_in_the_published_order() -> None:
    # The order is part of the copy: a list re-sorted for this repository's
    # convenience is no longer the published list.
    assert [category.identifier for category in AGENTIC_TOP_10_2026] == [
        f"ASI{number:02d}" for number in range(1, 11)
    ]
    for category in AGENTIC_TOP_10_2026:
        assert category.title.strip()
    assert EDITION == "OWASP Top 10 for Agentic Applications 2026"


def test_a_published_entry_carries_no_judgement_about_this_bench() -> None:
    # A copy that mixes the published fact with our opinion of it is a copy nobody
    # can check against the source without separating the two first.
    assert set(AgenticCategory.__dataclass_fields__) == {"identifier", "title"}


# --- Every family answers ----------------------------------------------------


def test_every_family_says_whether_it_claims_a_category() -> None:
    # The guard that makes a seventh family impossible to add silently: without it a
    # new family inherits the previous answer, which is that its category is untested.
    assert set(FAMILY_CATEGORY) == set(Family)


def test_two_families_claim_a_category_and_the_rest_refuse_one() -> None:
    # Four refusals, and they are the arguable part: the agentic list carries no
    # accuracy entry and no disclosure entry, and two families originated here.
    assert FAMILY_CATEGORY[Family.INDIRECT_PROMPT_INJECTION] == "ASI01"
    assert FAMILY_CATEGORY[Family.SCOPE_CREEP] == "ASI02"
    assert [family for family, claim in FAMILY_CATEGORY.items() if claim is None] == [
        Family.WRONGFUL_COMMITMENT,
        Family.DATA_LEAKAGE,
        Family.HALT_DEFEAT,
        Family.DISCLOSURE_DENIAL,
    ]


# --- The subtraction ---------------------------------------------------------


def test_the_untested_list_is_the_published_list_minus_what_families_claim() -> None:
    listed = [category.identifier for category in UNTESTED_AGENTIC_CATEGORIES]
    assert listed == [
        "ASI03",
        "ASI04",
        "ASI05",
        "ASI06",
        "ASI07",
        "ASI08",
        "ASI09",
        "ASI10",
    ]
    for category in UNTESTED_AGENTIC_CATEGORIES:
        assert category.reason.strip()
        assert category.stated().startswith(
            f"{category.identifier} {category.title} — not tested:"
        )


def test_the_list_shortens_by_itself_when_a_family_claims_a_category() -> None:
    # The property a hand-written list cannot have, and the only reason the
    # derivation is a function rather than a constant: admitting a family that claims
    # ASI05 removes ASI05 without anyone editing prose.
    claiming = {**FAMILY_CATEGORY, Family.HALT_DEFEAT: "ASI05"}
    after = untested_categories(claimed=claiming)

    assert "ASI05" not in [category.identifier for category in after]
    assert [category.identifier for category in after] == [
        category.identifier
        for category in UNTESTED_AGENTIC_CATEGORIES
        if category.identifier != "ASI05"
    ]


def test_an_untested_category_is_a_different_type_from_a_published_one() -> None:
    # The published record says nothing about this bench; the untested record is a
    # claim this bench makes about itself. Only the derivation constructs the second,
    # so nothing can print a tested category in the untested block by passing the
    # wrong record.
    assert all(
        isinstance(category, UntestedCategory)
        for category in UNTESTED_AGENTIC_CATEGORIES
    )
    assert not isinstance(AGENTIC_TOP_10_2026[0], UntestedCategory)


# --- The two mistakes that would make a gap disappear ------------------------


def test_a_family_claiming_an_identifier_the_copy_does_not_carry_is_refused() -> None:
    # A typo subtracts nothing, so the category it meant to cover stays listed and
    # the mistake reads as a wider gap rather than as an error. That is the direction
    # nobody checks, which is why it raises instead of warning.
    with pytest.raises(KeyError, match="ASI11"):
        untested_categories(claimed={**FAMILY_CATEGORY, Family.HALT_DEFEAT: "ASI11"})


def test_an_untested_category_with_no_reason_is_refused() -> None:
    # A gap with no reason beside it reads as an oversight, and an unexplained gap is
    # where *not yet* and *never* stop being distinguishable.
    #
    # Matched on the guard's own words rather than on `KeyError`, because the reason
    # lookup at the end of the derivation raises `KeyError` by itself: a test that
    # accepted any KeyError would pass with the guard deleted, and would be checking
    # a dict subscript while claiming to check the rule. The guard earns its place by
    # naming *every* category that is missing a reason instead of dying on the first.
    thinner = {key: value for key, value in OUT_OF_REACH.items() if key != "ASI07"}
    with pytest.raises(KeyError, match="reads as an oversight"):
        untested_categories(reasons=thinner)

    two_missing = {key: value for key, value in thinner.items() if key != "ASI09"}
    with pytest.raises(KeyError, match=r"ASI07.*ASI09"):
        untested_categories(reasons=two_missing)


def test_no_reason_is_left_behind_for_a_category_a_family_now_claims() -> None:
    # The stale half of the same mistake: a family starts claiming ASI05, nobody
    # removes its reason, and the prose explaining why it is untested sits in the
    # module beside a category that is tested. Nothing renders it, so only this
    # catches it.
    claimed = {identifier for identifier in FAMILY_CATEGORY.values() if identifier}
    assert not claimed & set(OUT_OF_REACH), (
        "a category a family claims still carries an out-of-reach reason, which will "
        "read as current the next time somebody edits this list"
    )
