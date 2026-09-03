"""The stored copies of the published lists, and what resolves against them.

Two lists are cited by this repository and until #44 one of them was stored. The
tests here are about the half a copy makes possible and a memory does not: an
identifier on a case record is *looked up* rather than believed, and a number written
in a superseded edition's numbering is named as such rather than silently accepted.

The copies themselves are asserted as copies — ten entries, published order, no
rewording — and nothing here checks that the titles are *right*, because this
repository cannot check that. Each copy carries its own provenance, they are not the
same strength, and `editions.py` says so on the copy rather than in one blanket
sentence covering both.
"""

import tomllib
from dataclasses import replace
from pathlib import Path

import pytest

from backend.bench.editions import (
    AGENTIC_TOP_10_2026,
    CURRENT,
    LLM_TOP_10_2025,
    LLM_TOP_10_2026,
    ORIGINATED_HERE,
    RETITLED,
    STORED_COPIES,
    PublishedCategory,
    refusal,
    renumbering,
    resolves,
)
from backend.bench.library import load_case
from backend.tests.conftest import CASES_DIR

# --- The copy ----------------------------------------------------------------


def test_the_llm_copy_is_ten_entries_in_the_published_order() -> None:
    # The order is the copy: a list re-sorted for this repository's convenience is no
    # longer the published list, and the whole point of the numbering is that the
    # position *is* the identifier.
    assert [entry.identifier for entry in LLM_TOP_10_2026.entries] == [
        f"LLM{number:02d}" for number in range(1, 11)
    ]
    for entry in LLM_TOP_10_2026.entries:
        assert entry.title.strip()
    assert LLM_TOP_10_2026.edition == "OWASP GenAI LLM Top 10 2026"
    assert LLM_TOP_10_2026.tag == "2026"


def test_the_agentic_copy_is_ten_entries_in_the_published_order() -> None:
    # Moved here with the copy itself (ADR-0036), and asserted on the same terms as
    # the list beside it: two copies checked one way, rather than each checked in the
    # file of whichever module happened to read it.
    assert [entry.identifier for entry in AGENTIC_TOP_10_2026.entries] == [
        f"ASI{number:02d}" for number in range(1, 11)
    ]
    for entry in AGENTIC_TOP_10_2026.entries:
        assert entry.title.strip()
    assert AGENTIC_TOP_10_2026.edition == "OWASP Top 10 for Agentic Applications 2026"
    assert AGENTIC_TOP_10_2026.tag == "2026"


def test_a_published_entry_carries_no_judgement_about_this_bench() -> None:
    # A copy that mixes the published fact with our opinion of it is a copy nobody
    # can check against the source without separating the two first — which is why
    # `UntestedCategory`, the record that does carry an opinion, is a different type
    # in a different module.
    assert set(PublishedCategory.__dataclass_fields__) == {"identifier", "title"}


def test_the_superseded_copy_is_stored_and_is_not_the_current_one() -> None:
    # Kept in the tree for one job — diagnosing a claim written in its numbering —
    # and excluded from the lookup, which is what makes keeping it safe.
    assert LLM_TOP_10_2025.superseded_by is LLM_TOP_10_2026
    assert LLM_TOP_10_2025 not in CURRENT
    assert set(CURRENT) == {AGENTIC_TOP_10_2026, LLM_TOP_10_2026}


# --- The lookup --------------------------------------------------------------


def test_an_identifier_resolves_to_the_entry_the_stored_copy_carries() -> None:
    # The four identifiers the case records claim, and the titles are the reason the
    # claims are checkable at all: a reader holding the record can see that scope
    # creep's LLM03 is Excessive Agency and not Supply Chain.
    assert resolves("LLM01:2026") == PublishedCategory("LLM01", "Prompt Injection")
    assert resolves("LLM02:2026") == PublishedCategory(
        "LLM02", "Sensitive Information Disclosure"
    )
    assert resolves("LLM03:2026") == PublishedCategory("LLM03", "Excessive Agency")
    assert resolves("LLM07:2026") == PublishedCategory("LLM07", "Misinformation")
    # Both lists, one lookup: the agentic identifiers resolve on the same terms.
    assert resolves("ASI01") == PublishedCategory("ASI01", "Agent Goal Hijack")


def test_an_identifier_naming_a_superseded_edition_does_not_resolve() -> None:
    # The whole anti-drift device. `LLM07` is carried by both editions and means two
    # different things in them, so an identifier that names 2025 must not be answered
    # out of the 2026 copy — that is the silent renumbering #44 exists about.
    assert resolves("LLM07:2025") is None
    assert resolves("LLM06:2025") is None


def test_a_refusal_names_the_renumbering_rather_than_calling_it_a_typo() -> None:
    # Two shapes of wrongness need two sentences, because they need different fixes.
    # A superseded number is a real published entry at the wrong number, and the
    # reader needs the current one.
    superseded = refusal("LLM06:2025")
    assert superseded is not None
    assert "Excessive Agency" in superseded
    assert "LLM03:2026" in superseded

    unknown = refusal("LLM11:2026")
    assert unknown is not None
    assert "none of the editions this repository stores" in unknown
    assert "LLM03:2026" not in unknown


def test_an_identifier_that_resolves_has_no_refusal() -> None:
    assert refusal("LLM03:2026") is None
    assert refusal("ASI06") is None


# --- The renumbering, and the three disagreements it settles -----------------


def test_the_renumbering_is_derived_from_the_two_copies_and_is_total() -> None:
    # Ten entries in, ten out, every one landing on an identifier the current copy
    # carries. Derived by title from the copies, so the mapping cannot say something
    # neither copy says — the property a second hand-written mapping would not have.
    moved = renumbering()
    assert set(moved) == {f"LLM{number:02d}:2025" for number in range(1, 11)}
    assert sorted(moved.values()) == [
        f"LLM{number:02d}:2026" for number in range(1, 11)
    ]
    for identifier in moved.values():
        assert resolves(identifier) is not None


def test_two_of_the_three_disagreements_are_the_2025_numbering() -> None:
    # #42's table and PLAN §4 disagree on three rows, and nothing in the repository
    # could adjudicate that before there was a copy to read the titles off. Two of
    # the three are the same published entry under the superseded numbering, and this
    # is the lookup that says so rather than an opinion about which reading is better.
    #
    # Scope creep: #42 selected LLM06, PLAN §4 carries LLM03:2026. One entry.
    assert renumbering()["LLM06:2025"] == "LLM03:2026"
    assert LLM_TOP_10_2025.entry("LLM06") == PublishedCategory(
        "LLM06", "Excessive Agency"
    )
    # Data leakage: #42 selected LLM07, PLAN §4 carries LLM02:2026 / LLM08:2026, and
    # LLM07:2025 System Prompt Leakage is the second of that pair, renamed.
    assert renumbering()["LLM07:2025"] == "LLM08:2026"


def test_the_third_disagreement_is_a_refusal_and_not_a_renumbering() -> None:
    # Wrongful commitment: PLAN §4 carries LLM07:2026 and #42 selected no LLM
    # identifier at all, so there is no number to renumber. What the copy can say is
    # that the entry PLAN §4 names exists and what it is called; whether the *family*
    # claims it is the label record's decision (#45) and the identifier claims (#47),
    # and this ticket deliberately makes no coverage claim of its own.
    assert resolves("LLM07:2026") == PublishedCategory("LLM07", "Misinformation")
    # Had #42 been numbering that entry against 2025 it would have written LLM09.
    assert renumbering()["LLM09:2025"] == "LLM07:2026"


def test_an_entry_the_current_copy_cannot_be_matched_to_is_refused() -> None:
    # A copy half-updated to a new edition, or garbled by a reading that paraphrased
    # a title, arrives in exactly this shape. It must not arrive as a mapping that is
    # quietly one pair shorter, because the pair it drops is the claim nobody checks.
    dropped = replace(
        LLM_TOP_10_2025,
        entries=(
            *LLM_TOP_10_2025.entries[:5],
            PublishedCategory("LLM06", "Excessive Autonomy"),
            *LLM_TOP_10_2025.entries[6:],
        ),
    )
    with pytest.raises(ValueError, match="neither"):
        renumbering(dropped)


def test_a_declared_rename_is_only_for_a_pair_no_title_can_match() -> None:
    # The stale half: an entry gets its old title back, or the reading that said it
    # was renamed turns out to be wrong, and a declared pair now overrides a title
    # match instead of standing in for a missing one. Nothing renders RETITLED, so
    # only this catches it.
    for pair, into in RETITLED.items():
        number, _, tag = pair.partition(":")
        superseded = next(
            copy
            for copy in STORED_COPIES
            if copy.tag == tag and copy.superseded_by is not None
        )
        entry = superseded.entry(number)
        assert entry is not None, f"{pair} names no entry of any stored copy"
        assert resolves(into) is not None, f"{pair} is renamed into {into}, unstored"
        current = superseded.superseded_by
        assert current is not None
        assert entry.title not in [carried.title for carried in current.entries], (
            f"{pair} is declared renamed and its title is still carried by the "
            "current copy, so the declaration is overriding a pair the copies "
            "already agree on"
        )


# --- What a case record may claim --------------------------------------------


def test_every_identifier_on_a_case_record_resolves_to_a_stored_copy() -> None:
    # The claim #44 was opened for. Every case record either names an entry a stored
    # copy carries or says, in the one declared form, that the published lists have
    # no equivalent — and there is no third answer, because a claim about an external
    # standard that nothing can check is the failure this ticket is about.
    #
    # Read out of the records themselves rather than through `load_library`, which
    # would now raise on the way in: a test that could only fail as an import-time
    # error would be asserting that the loader guard exists, and this one is about
    # what is on disk. It fails with the refusal, which names the fix.
    claimed = {
        tomllib.loads(record.read_text(encoding="utf-8"))["external_id"]["identifier"]
        for record in sorted(CASES_DIR.glob("*.toml"))
    }
    for identifier in claimed - {ORIGINATED_HERE}:
        assert resolves(identifier) is not None, refusal(identifier)

    # The roster, so that a case arriving with a fifth identifier is a decision
    # somebody makes rather than one that lands. Every entry here was checked against
    # the stored copy: LLM03:2026 is Excessive Agency and LLM07:2026 is
    # Misinformation, which is what settled #42's disagreement with PLAN §4.
    assert claimed == {
        "LLM01:2026",
        "LLM02:2026",
        "LLM03:2026",
        "LLM07:2026",
        ORIGINATED_HERE,
    }, (
        "a case record claims an identifier this roster does not name. It resolves, "
        "or the assertion above would have failed first — what is left is to read "
        "the entry it resolves to and check that it is the one the case is about"
    )


def test_a_case_claiming_an_identifier_no_copy_carries_does_not_load(
    tmp_path: Path,
) -> None:
    # A mistyped identifier is the shape of the mistake `untested_categories` already
    # refuses on the agentic side, arriving from the other end: there it subtracts
    # nothing, here it prints a published number that is not published. It fails at
    # the record rather than in the report, so nothing can be run against it and
    # nothing can be signed carrying it.
    record = (CASES_DIR / "scope-creep-001.toml").read_text(encoding="utf-8")
    mistyped = tmp_path / "scope-creep-001.toml"
    mistyped.write_text(
        record.replace('identifier = "LLM03:2026"', 'identifier = "LLM3:2026"'),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="none of the editions"):
        load_case(mistyped)


def test_a_case_claiming_a_superseded_number_does_not_load(tmp_path: Path) -> None:
    # The drift, at the place it enters: someone reads #42's table and writes LLM06
    # for scope creep. Tagged `:2025` it names the entry the family really tests —
    # Excessive Agency — under the numbering of an edition this repository does not
    # stand behind, which is a claim no reading of the stored copies supports. The
    # refusal hands back the current number rather than calling it a typo.
    record = (CASES_DIR / "scope-creep-001.toml").read_text(encoding="utf-8")
    stale = tmp_path / "scope-creep-001.toml"
    stale.write_text(
        record.replace('identifier = "LLM03:2026"', 'identifier = "LLM06:2025"'),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="LLM03:2026"):
        load_case(stale)


def test_a_case_may_not_claim_an_identifier_that_names_no_edition(
    tmp_path: Path,
) -> None:
    # The wildcard the edition tag exists to close, and it is the only route by which
    # the drift could still have entered. `LLM06` untagged *resolves* — one current
    # copy per list carries that number, so the lookup has an unambiguous answer —
    # and as a claim it means Excessive Agency in the numbering #42's table was
    # written in and Unbounded Consumption in the copy stored today. A record allowed
    # to omit the edition is a record whose claim changes meaning underneath it the
    # next time a copy is updated.
    assert resolves("LLM06") == PublishedCategory("LLM06", "Unbounded Consumption")

    record = (CASES_DIR / "scope-creep-001.toml").read_text(encoding="utf-8")
    untagged = tmp_path / "scope-creep-001.toml"
    untagged.write_text(
        record.replace('identifier = "LLM03:2026"', 'identifier = "LLM06"'),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="names no edition"):
        load_case(untagged)


def test_the_declared_no_claim_form_is_the_only_thing_that_claims_nothing(
    tmp_path: Path,
) -> None:
    # Halt defeat and disclosure denial originated here and claim no published
    # identifier (ADR-0002). That has to be a sentence a reader can find rather than
    # a blank a typo could imitate, so the empty string and two near misses are
    # refused while the declared form loads.
    record = (CASES_DIR / "halt-defeat-001.toml").read_text(encoding="utf-8")
    assert f'identifier = "{ORIGINATED_HERE}"' in record
    assert load_case(CASES_DIR / "halt-defeat-001.toml").external_id.identifier == (
        ORIGINATED_HERE
    )

    for imitation in ("", "none", "n/a — originated here"):
        near = tmp_path / f"halt-defeat-{len(imitation)}.toml"
        near.write_text(
            record.replace(
                f'identifier = "{ORIGINATED_HERE}"', f'identifier = "{imitation}"'
            ),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="names no edition"):
            load_case(near)
