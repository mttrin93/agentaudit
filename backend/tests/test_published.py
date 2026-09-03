"""The subtractions over the two stored copies, and the mistakes they refuse.

The point of `published.py` is that the negative-coverage claim is **derived**, so the
tests that matter are the ones a hand-written list could not pass:

* the subtraction *moves* when the library's families move, so the claim cannot go
  stale while still looking current;
* every family says whether it claims a category on each list, so a family added
  later cannot quietly inherit the old answer;
* the two mistakes that make a gap **disappear** — a claim on an identifier the copy
  does not carry, and a reason left behind for a category somebody has since started
  claiming — are refused rather than absorbed.

**The copies are asserted where the copies live.** Both agentic and LLM entries are
`editions.py`'s since ADR-0036, and so are the assertions that each is ten entries in
the published order carrying no judgement about this bench — `test_editions.py`. What
stays here reads a copy and never checks one.
"""

import pytest

from backend.bench.editions import (
    AGENTIC_TOP_10_2026,
    LLM_TOP_10_2026,
    ORIGINATED_HERE,
)
from backend.bench.labels import ELECTIVE_LABELS
from backend.bench.library import ElectiveFamily, Family, load_library
from backend.bench.published import (
    AGENTIC_CLAIMS,
    CLAIMED_IN_PART,
    LLM_CLAIMS,
    NOT_REACHED_WITHIN,
    OUT_OF_REACH,
    UNTESTED_CATEGORIES,
    UntestedCategory,
    claimed_in_part,
    untested_categories,
)
from backend.tests.conftest import CASES_DIR

# --- Every family answers ----------------------------------------------------


def test_every_family_says_whether_it_claims_a_category_on_each_list() -> None:
    # The guard that makes a seventh family impossible to add silently: without it a
    # new family inherits the previous answer, which is that its category is untested.
    # Both views are read off one label record, so a family missing from either is a
    # family missing from `labels.LABELS` and the module does not load (ADR-0039).
    assert set(AGENTIC_CLAIMS) == set(Family)
    assert set(LLM_CLAIMS) == set(Family)


def test_five_families_claim_an_agentic_category_and_data_leakage_refuses_one() -> None:
    # One refusal left, and it is the one the file argued for rather than the one it
    # was read as arguing: ASI03 is about privileges being abused and data leakage is
    # about material escaping, so data leakage still does not claim it (ADR-0037).
    assert AGENTIC_CLAIMS[Family.INDIRECT_PROMPT_INJECTION] == ("ASI01:2026",)
    assert AGENTIC_CLAIMS[Family.SCOPE_CREEP] == ("ASI02:2026",)
    assert AGENTIC_CLAIMS[Family.WRONGFUL_COMMITMENT] == ("ASI03:2026",)
    assert AGENTIC_CLAIMS[Family.DISCLOSURE_DENIAL] == ("ASI09:2026",)
    assert AGENTIC_CLAIMS[Family.HALT_DEFEAT] == ("ASI10:2026",)
    assert [family for family, claim in AGENTIC_CLAIMS.items() if not claim] == [
        Family.DATA_LEAKAGE
    ]


def test_the_llm_column_is_plan_4s_and_two_families_claim_nothing_on_it() -> None:
    # PLAN §4's external column in the 2026 numbering, and the mirror of the refusal
    # above: halt defeat and disclosure denial originated here and claim nothing on
    # this list, which is the *no LLM equivalent* that sentence in the plan means.
    assert LLM_CLAIMS[Family.INDIRECT_PROMPT_INJECTION] == ("LLM01:2026",)
    assert LLM_CLAIMS[Family.SCOPE_CREEP] == ("LLM03:2026",)
    assert LLM_CLAIMS[Family.WRONGFUL_COMMITMENT] == ("LLM07:2026",)
    assert LLM_CLAIMS[Family.DATA_LEAKAGE] == ("LLM02:2026", "LLM08:2026")
    assert [family for family, claim in LLM_CLAIMS.items() if not claim] == [
        Family.HALT_DEFEAT,
        Family.DISCLOSURE_DENIAL,
    ]


def test_the_three_categories_issue_47_claimed_left_the_untested_list() -> None:
    # Which three, named: the untested block shrank by exactly these, each to the
    # family #42 read it onto, and each carrying the half of the category that family
    # does not reach in place of the out-of-reach reason it no longer has.
    listed = {category.identifier for category in UNTESTED_CATEGORIES}
    for identifier, family in (
        ("ASI03", Family.WRONGFUL_COMMITMENT),
        ("ASI09", Family.DISCLOSURE_DENIAL),
        ("ASI10", Family.HALT_DEFEAT),
    ):
        assert AGENTIC_CLAIMS[family] == (f"{identifier}:2026",)
        assert f"{identifier}:2026" not in listed
        assert f"{identifier}:2026" not in OUT_OF_REACH


# --- The subtraction ---------------------------------------------------------


def test_the_untested_list_is_both_published_lists_minus_what_families_claim() -> None:
    # Two subtractions concatenated, agentic first, and every entry naming its
    # edition: this block carries two lists since #45 and the same number is a
    # different entry in a different edition of one of them.
    listed = [category.identifier for category in UNTESTED_CATEGORIES]
    assert listed == [
        "ASI04:2026",
        "ASI05:2026",
        "ASI06:2026",
        "ASI07:2026",
        "ASI08:2026",
        "LLM04:2026",
        "LLM05:2026",
        "LLM06:2026",
        "LLM09:2026",
        "LLM10:2026",
    ]
    for category in UNTESTED_CATEGORIES:
        assert category.reason.strip()
        assert category.stated().startswith(
            f"{category.identifier} {category.title} — not tested:"
        )
    assert {category.edition for category in UNTESTED_CATEGORIES} == {
        AGENTIC_TOP_10_2026.edition,
        LLM_TOP_10_2026.edition,
    }


def test_an_elective_familys_label_does_not_shorten_the_untested_list() -> None:
    # `ASI06` is on an elective family's label and is still listed as untested, with
    # a reason that says why. The tier's families have no cases on disk, so a
    # subtraction that read `ELECTIVE_LABELS` would shorten a printed coverage claim
    # for a family nothing has ever run — the widening direction nobody checks, from
    # the one place ADR-0035 says the type has to keep closed.
    assert ELECTIVE_LABELS[ElectiveFamily.MEMORY_POISONING].agentic == ("ASI06:2026",)
    # Both halves on the tagged identifier, because that is the only form either
    # tuple carries: a bare `ASI06` is in neither, so an assertion written that way
    # would go on passing with the elective labels feeding the subtraction.
    assert "ASI06:2026" in [category.identifier for category in UNTESTED_CATEGORIES]
    assert "ASI06:2026" not in [claim.identifier for claim in CLAIMED_IN_PART]


def test_the_list_shortens_by_itself_when_a_family_claims_a_category() -> None:
    # The property a hand-written list cannot have, and the only reason the
    # derivation is a function rather than a constant: admitting a family that claims
    # ASI05 removes ASI05 without anyone editing prose.
    claiming = {**AGENTIC_CLAIMS, Family.DATA_LEAKAGE: ("ASI05:2026",)}
    after = untested_categories(claimed=claiming)

    assert "ASI05:2026" not in [category.identifier for category in after]
    assert [category.identifier for category in after] == [
        category.identifier
        for category in UNTESTED_CATEGORIES
        if category.identifier.startswith("ASI") and category.identifier != "ASI05:2026"
    ]


def test_an_untested_category_is_a_different_type_from_a_published_one() -> None:
    # The published record says nothing about this bench; the untested record is a
    # claim this bench makes about itself. Only the derivation constructs the second,
    # so nothing can print a tested category in the untested block by passing the
    # wrong record.
    assert all(
        isinstance(category, UntestedCategory) for category in UNTESTED_CATEGORIES
    )
    assert not isinstance(AGENTIC_TOP_10_2026.entries[0], UntestedCategory)


# --- The two mistakes that would make a gap disappear ------------------------


def test_a_family_claiming_an_identifier_the_copy_does_not_carry_is_refused() -> None:
    # A typo subtracts nothing, so the category it meant to cover stays listed and
    # the mistake reads as a wider gap rather than as an error. That is the direction
    # nobody checks, which is why it raises instead of warning.
    with pytest.raises(KeyError, match="ASI11"):
        untested_categories(
            claimed={**AGENTIC_CLAIMS, Family.DATA_LEAKAGE: ("ASI11:2026",)}
        )


def test_a_claim_on_the_other_published_list_is_refused_by_the_subtraction() -> None:
    # The mistake the two-list shape makes possible: an LLM identifier written into
    # the agentic half of a label. It is in *a* stored copy, so nothing on the record
    # itself refuses it — and it subtracts nothing from the list it was handed to,
    # which is the same disappearing gap a typo makes.
    with pytest.raises(KeyError, match="LLM01:2026"):
        untested_categories(
            claimed={**AGENTIC_CLAIMS, Family.DATA_LEAKAGE: ("LLM01:2026",)}
        )


def test_a_claim_under_a_superseded_numbering_is_refused_by_the_subtraction() -> None:
    # The drift `editions.py` exists to catch, arriving at the subtraction: `LLM07`
    # is Misinformation in the stored edition and was System Prompt Leakage in the
    # one before it. A claim that named no edition would go on meaning whichever the
    # copy last said, so the tag is compared against the copy's own.
    with pytest.raises(KeyError, match="LLM07:2025"):
        untested_categories(
            copy=LLM_TOP_10_2026,
            claimed={**LLM_CLAIMS, Family.HALT_DEFEAT: ("LLM07:2025",)},
        )


def test_an_untested_category_with_no_reason_is_refused() -> None:
    # A gap with no reason beside it reads as an oversight, and an unexplained gap is
    # where *not yet* and *never* stop being distinguishable.
    #
    # Matched on the guard's own words rather than on `KeyError`, because the reason
    # lookup at the end of the derivation raises `KeyError` by itself: a test that
    # accepted any KeyError would pass with the guard deleted, and would be checking
    # a dict subscript while claiming to check the rule. The guard earns its place by
    # naming *every* category that is missing a reason instead of dying on the first.
    thinner = {key: value for key, value in OUT_OF_REACH.items() if key != "ASI07:2026"}
    with pytest.raises(KeyError, match="reads as an oversight"):
        untested_categories(reasons=thinner)

    two_missing = {key: value for key, value in thinner.items() if key != "ASI08:2026"}
    with pytest.raises(KeyError, match=r"ASI07.*ASI08"):
        untested_categories(reasons=two_missing)


def test_no_reason_is_left_behind_for_a_category_a_family_now_claims() -> None:
    # The stale half of the same mistake: a family starts claiming ASI05, nobody
    # removes its reason, and the prose explaining why it is untested sits in the
    # module beside a category that is tested. Nothing renders it, so only this
    # catches it.
    claimed = {
        identifier
        for claims in (*AGENTIC_CLAIMS.values(), *LLM_CLAIMS.values())
        for identifier in claims
    }
    assert not claimed & set(OUT_OF_REACH), (
        "a category a family claims still carries an out-of-reach reason, which will "
        "read as current the next time somebody edits this list"
    )


# --- What a claim does not reach ---------------------------------------------


def test_every_claim_names_its_families_and_the_half_it_does_not_reach() -> None:
    # The five claims, each printing the boundary of what it claims. A category that
    # left the untested block without this would be a coverage claim that got wider
    # and said nothing — which is the move #47 exists to make expensive.
    #
    # One record per category and not per claim, so each holds the families that
    # reach it: ten singletons today, and the shape that keeps one printed line when
    # two families claim one category (#42's `LLM01`, once direct prompt injection
    # has cases and is claimed by more than an elective label).
    assert [(one.identifier, one.families) for one in CLAIMED_IN_PART] == [
        ("ASI01:2026", (Family.INDIRECT_PROMPT_INJECTION,)),
        ("ASI02:2026", (Family.SCOPE_CREEP,)),
        ("ASI03:2026", (Family.WRONGFUL_COMMITMENT,)),
        ("ASI09:2026", (Family.DISCLOSURE_DENIAL,)),
        ("ASI10:2026", (Family.HALT_DEFEAT,)),
        ("LLM01:2026", (Family.INDIRECT_PROMPT_INJECTION,)),
        ("LLM02:2026", (Family.DATA_LEAKAGE,)),
        ("LLM03:2026", (Family.SCOPE_CREEP,)),
        ("LLM07:2026", (Family.WRONGFUL_COMMITMENT,)),
        ("LLM08:2026", (Family.DATA_LEAKAGE,)),
    ]
    for one in CLAIMED_IN_PART:
        assert one.not_reached.strip()
        assert one.stated() == (
            f"{one.identifier} {one.title} — tested in part; not tested within it: "
            f"{one.not_reached}"
        )
        # And the line names no family. The block is derived over the library's
        # families and prints in a report a run may have measured two of them for, so
        # a family named here would read as one this target was tested on (ADR-0018).
        assert not [family for family in Family if family.value in one.stated()]


def test_the_two_blocks_partition_the_published_list_at_any_claim() -> None:
    # Ten entries, each either untested with a reason or claimed with a limit, never
    # both and never neither. The two blocks print in the same section, so a category
    # reaching both would be named as a gap and as a claim in one document, and one
    # reaching neither would leave the section quietly short.
    #
    # Driven with a *moved* mapping rather than the declared one, so what it asserts
    # is the invariant and not a second copy of the two rosters above: those are
    # literals and go stale together, and both derivations read one `_claims`
    # precisely so that they cannot disagree about an entry at a claim nobody has
    # made yet.
    moved = {**AGENTIC_CLAIMS, Family.DATA_LEAKAGE: ("ASI04:2026",)}
    reasons = {key: value for key, value in OUT_OF_REACH.items() if key != "ASI04:2026"}
    limits = {
        **NOT_REACHED_WITHIN,
        "ASI04:2026": "the connectors it is assembled from",
    }

    untested = [
        category.identifier
        for category in untested_categories(claimed=moved, reasons=reasons)
    ]
    claimed = [one.identifier for one in claimed_in_part(claimed=moved, limits=limits)]

    assert not set(untested) & set(claimed)
    assert sorted(untested + claimed) == [
        f"{category.identifier}:{AGENTIC_TOP_10_2026.tag}"
        for category in AGENTIC_TOP_10_2026.entries
    ]
    # A concatenation and not a union of sets: `claimed_in_part` holds one record per
    # category rather than per claim, so a duplicate here would be a category printed
    # twice in one block and the length has to be read.


def test_the_two_blocks_partition_each_stored_copy_as_declared() -> None:
    # The same invariant as above, over the declared data and over both copies:
    # twenty entries, each either untested with a reason or claimed with a limit. A
    # second list subtracted with the first would be the place for an entry to fall
    # through both blocks, so it is asserted per copy rather than over the two
    # concatenated tuples the report prints.
    for copy, claims in (
        (AGENTIC_TOP_10_2026, AGENTIC_CLAIMS),
        (LLM_TOP_10_2026, LLM_CLAIMS),
    ):
        untested = [
            one.identifier for one in untested_categories(copy=copy, claimed=claims)
        ]
        claimed = [one.identifier for one in claimed_in_part(copy=copy, claimed=claims)]

        assert not set(untested) & set(claimed)
        assert sorted(untested + claimed) == [
            f"{entry.identifier}:{copy.tag}" for entry in copy.entries
        ]


def test_the_llm_subtraction_refuses_the_same_two_mistakes_as_the_agentic_one() -> None:
    # One derivation, driven twice, so the second list cannot acquire a weaker guard
    # than the first by being added later. A gap with no reason and a claim with no
    # limit are the two ways this section's coverage statement widens quietly.
    thinner = {key: value for key, value in OUT_OF_REACH.items() if key != "LLM06:2026"}
    with pytest.raises(KeyError, match="reads as an oversight"):
        untested_categories(copy=LLM_TOP_10_2026, claimed=LLM_CLAIMS, reasons=thinner)

    fewer = {
        key: value for key, value in NOT_REACHED_WITHIN.items() if key != "LLM08:2026"
    }
    with pytest.raises(KeyError, match="says nothing about what it does not reach"):
        claimed_in_part(copy=LLM_TOP_10_2026, claimed=LLM_CLAIMS, limits=fewer)


def test_two_families_claiming_one_category_are_one_record_and_one_line() -> None:
    # The shape #42 says the LLM list will carry, driven here on the agentic copy:
    # `LLM01` is claimed by indirect and direct prompt injection once the second
    # exists. The limit is declared per identifier, so a record per *claim* would
    # print the same line twice, and a record that kept one claim would drop the
    # other from the pairing #45 reads.
    both = {**AGENTIC_CLAIMS, Family.DATA_LEAKAGE: ("ASI01:2026",)}
    [claim] = [
        one for one in claimed_in_part(claimed=both) if one.identifier == "ASI01:2026"
    ]

    assert claim.families == (Family.INDIRECT_PROMPT_INJECTION, Family.DATA_LEAKAGE)
    assert [one.identifier for one in claimed_in_part(claimed=both)].count(
        "ASI01:2026"
    ) == 1


def test_a_claim_with_no_limit_beside_it_is_refused() -> None:
    # The mirror of the missing out-of-reach reason, and it guards the opposite
    # direction: this one refuses a claim that shortens the untested list without
    # saying what it leaves out.
    #
    # Matched on the guard's own words rather than on `KeyError`, because the limit
    # lookup at the end of the derivation raises `KeyError` by itself — a test that
    # accepted any KeyError would pass with the guard deleted. The guard earns its
    # place by naming every claim that is missing a limit instead of dying on the
    # first.
    thinner = {
        key: value for key, value in NOT_REACHED_WITHIN.items() if key != "ASI02:2026"
    }
    with pytest.raises(KeyError, match="says nothing about what it does not reach"):
        claimed_in_part(limits=thinner)

    two_missing = {key: value for key, value in thinner.items() if key != "ASI09:2026"}
    with pytest.raises(KeyError, match=r"ASI02.*ASI09"):
        claimed_in_part(limits=two_missing)


def test_no_limit_is_left_behind_for_a_category_no_family_claims() -> None:
    # The stale half, and the same failure `test_no_reason_is_left_behind_...` catches
    # at the other end: a family stops claiming a category, nobody removes the limit,
    # and prose about the boundary of a claim nobody makes sits in the module reading
    # as current. Nothing renders it, so only this catches it.
    claimed = {
        identifier
        for claims in (*AGENTIC_CLAIMS.values(), *LLM_CLAIMS.values())
        for identifier in claims
    }
    assert set(NOT_REACHED_WITHIN) <= claimed, (
        "a category no family claims still carries a not-reached-within limit, which "
        "describes the boundary of a claim this bench does not make"
    )


def test_a_claimed_identifier_the_copy_does_not_carry_is_refused_by_both_blocks() -> (
    None
):
    # One check of a claim against the copy, read by both derivations. A claim that
    # resolved for one and not the other would put a category in both blocks or in
    # neither, and both readings print in the same section of the same document.
    typo = {**AGENTIC_CLAIMS, Family.DATA_LEAKAGE: ("ASI11:2026",)}

    with pytest.raises(KeyError, match="ASI11"):
        untested_categories(claimed=typo)
    with pytest.raises(KeyError, match="ASI11"):
        claimed_in_part(claimed=typo)


# --- The library's own prose, against the claims -----------------------------


def test_no_identifier_a_live_case_claims_is_printed_as_untested() -> None:
    # The cross-section invariant #47 was opened for, arriving from the other list.
    # Section 4 prints "Tests one case within `LLM02:2026`" beside a family's figures;
    # if the coverage section then listed `LLM02:2026` as a category no family
    # reaches, one document would say both things two sections apart.
    #
    # It is why `data_leakage`'s label carries `LLM02:2026` as well as `LLM08:2026`
    # rather than only the one #42's table selected: three case records already claim
    # the first, and a family label that dropped it would put the contradiction into
    # every report. What the family does *not* reach inside it — a third party's
    # personal data — is stated beside the claim instead (ADR-0037).
    untested = {category.identifier for category in UNTESTED_CATEGORIES}
    claimed = {claim.identifier for claim in CLAIMED_IN_PART}

    for case in load_library(CASES_DIR):
        identifier = case.external_id.identifier
        if identifier == ORIGINATED_HERE:
            continue
        assert identifier not in untested, (
            f"{case.id} says it tests one case within {identifier}, and the coverage "
            "section of the same report says no family reaches it"
        )
        assert identifier in claimed


def test_a_case_of_a_claiming_family_does_not_deny_a_published_equivalent() -> None:
    # `halt_defeat` and `disclosure_denial` claim ASI10 and ASI09 at family level, and
    # every one of their case records opened by saying the published lists carry no
    # equivalent entry. That became false the moment the claims landed, and it renders
    # into section 4 of every report — beside a coverage section naming those two
    # categories as claimed. A document that contradicts itself across two sections is
    # the failure #47 was opened for, arriving one section further down.
    #
    # Asserted on the clause that replaced it rather than on the absence of the old
    # wording: an absence assertion pinned to prose goes quietly true the next time
    # somebody rewords the prose (#44's own re-cut).
    for family, article in (
        (Family.HALT_DEFEAT, "Article 14(4)(e)"),
        (Family.DISCLOSURE_DENIAL, "Article 50"),
    ):
        assert AGENTIC_CLAIMS[family]
        cases = [case for case in load_library(CASES_DIR) if case.family is family]

        # Every case of the family, however many there are: the admission gate can
        # grow a family (ADR-0033), so a count pinned here would fail on the run that
        # grew one rather than on the prose this is about.
        assert cases
        for case in cases:
            # The case still claims no published identifier of its own: a family's
            # secondary label and a case's identifier are two different claims, which
            # is why `ORIGINATED_HERE` keeps its meaning and its users (ADR-0037).
            assert case.external_id.identifier == ORIGINATED_HERE
            # Whitespace-normalised, because the record is hard-wrapped TOML and the
            # clause straddles a line break — matching the raw text would be pinning
            # this assertion to where the wrap happens to fall.
            prose = " ".join(case.external_id.not_tested.split())
            assert (
                f"written from {article} rather than from a published risk category"
                in prose
            )
