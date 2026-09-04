"""The content a case is attacked with is on the case's own record.

The three indirect-injection cases and the three memory-poisoning ones are attacked
by content the target fetched, and until
[ADR-0060](../../docs/adr/0060-a-planted-artefact-is-part-of-the-case-record.md) that
content was in the reference agents' source. The record named the canary, the source
held the note that produced it, and a test watched the two for drift. These are the
tests that replace that watch: there is one copy of each half, the folder the agents
serve is assembled from the records, and every way of writing the fact twice is
refused.

**The property under test is not that the two agree — it is that there is nothing
for them to disagree about.** So the assertions run from the record outwards: what
the retrieval tool hands back *is* the record's body, and what the verdict reads *is*
the record's two halves joined.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from backend.bench.library import (
    Case,
    ElectiveFamily,
    LibraryVersion,
    PlantedArtefact,
    PlantedIn,
    load_case,
    load_elective,
    load_library,
)
from backend.targets.reference import corpus
from backend.targets.reference.corpus import DELIVERY_NOTE, fetched, shared_folder
from backend.tests.conftest import CASES_DIR


def every_committed_case() -> list[Case]:
    """Both tiers, which is what the shared folder is built from."""
    return load_library(CASES_DIR) + load_elective(CASES_DIR, list(ElectiveFamily))


def plants() -> list[Case]:
    return [
        case for case in every_committed_case() if case.planted_artefact is not None
    ]


def fetching_turn(case: Case) -> str:
    """The turn that retrieves — the planting turn where there is one, else the first.

    `Case._refuse_a_planting_its_record_disagrees_with` reads the same turn, and it
    is read here rather than imported so that a change to which turn fetches has to
    be made twice before this suite stops seeing it.
    """
    return case.planting or case.payload[0]


# --- The note the run plants is the note the case names ----------------------


def test_the_content_the_folder_serves_is_the_content_the_case_records() -> None:
    """The guard that used to watch two copies for drift, asserted over one.

    From the record outwards: the case's own fetching turn is put through
    `corpus.fetched`, which is the function the reference agent calls, and what comes
    back has to be the record's body verbatim and the record's canary. A note
    assembled anywhere but from the record fails this, and so does a payload that
    retrieves somebody else's content.
    """
    planting = plants()
    assert planting, "no committed case plants content, so nothing here is under test"

    for case in planting:
        artefact = case.planted_artefact
        assert artefact is not None
        condition = case.success_condition
        assert condition is not None

        note = fetched(fetching_turn(case))

        assert note is not None, case.id
        assert note.key == artefact.key, case.id
        assert note.body == artefact.body, case.id
        produced = note.executed_line or (
            note.standing.line if note.standing is not None else ""
        )
        assert produced == artefact.executed_line == condition.planted_canary, case.id


def test_the_folder_serves_no_instruction_the_library_does_not_carry() -> None:
    """Nothing can be planted with content no record holds.

    The other direction, and the containment half: every note that instructs is a
    record's, and the only body this module writes out is the one that instructs
    nobody — which is not a case, has no verdict and no admission, and is the control
    the canary is read against.
    """
    bodies = {case.planted_artefact.body for case in plants()}  # type: ignore[union-attr]

    for note in shared_folder():
        instructs = bool(note.executed_line) or note.standing is not None
        if not instructs:
            assert note == DELIVERY_NOTE
            continue
        assert note.body in bodies, note.key


def test_two_records_filing_content_under_one_key_stop_the_folder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`fetched` answers the first match, so a shared key hides one record's content.

    Refused where the library can be seen rather than on a record, on `load_library`'s
    own terms: a record cannot see the library it is joining. Driven over a library
    built for it, because the committed one cannot express the fault — a record whose
    key its own fetching turn never names does not load at all.
    """
    [first, *_] = plants()
    both = [first, replace(first, id=f"{first.id}-again")]
    monkeypatch.setattr(corpus, "load_library", lambda _: both)
    monkeypatch.setattr(corpus, "load_elective", lambda _, __: [])
    corpus._planted.cache_clear()
    corpus.shared_folder.cache_clear()

    try:
        with pytest.raises(ValueError, match="both file content under"):
            corpus.shared_folder()
    finally:
        corpus._planted.cache_clear()
        corpus.shared_folder.cache_clear()


def test_the_committed_folder_files_every_note_under_its_own_key() -> None:
    """And the same property over the library the three agents actually serve."""
    keys = [case.planted_artefact.key for case in plants()]  # type: ignore[union-attr]

    assert len(keys) == len(set(keys)), keys
    assert DELIVERY_NOTE.key not in keys


# --- One copy, and every way of writing a second one is refused --------------


def test_a_record_may_not_write_the_canary_its_own_content_produces(
    tmp_path: Path,
) -> None:
    """The drift the old test watched for, made unwritable.

    A record that named the canary *and* planted the content that produces it would
    be two copies of one fact again, agreeing on the day it was written. `load_case`
    refuses it rather than checking that they match.
    """
    source = (CASES_DIR / "indirect-injection-001.toml").read_text(encoding="utf-8")
    doubled = source.replace(
        "[success_condition]\nkind = ",
        '[success_condition]\nplanted_canary = "NOTE-PROCESSED-44120"\nkind = ',
    )
    written = tmp_path / "indirect-injection-001.toml"
    written.write_text(doubled, encoding="utf-8")

    with pytest.raises(ValueError, match="writes a planted canary"):
        load_case(written)


def test_a_case_attacked_by_fetched_content_that_plants_none_is_refused(
    injection_case: Case,
) -> None:
    """The state this field exists to end: a record naming only what the attack made.

    Its attack would be somewhere the record cannot show a reader, and nothing but a
    reference agent could be planted with it.
    """
    with pytest.raises(ValueError, match="carries no content"):
        replace(injection_case, planted_artefact=None)


def test_content_on_a_case_that_plants_nothing_is_refused(leakage_case: Case) -> None:
    """The other half of the pairing.

    `data_leakage` reads the registration nonce, which the run issues and the
    operator plants inside the target's boundary (ADR-0007). Content on such a record
    is content nothing plants and nothing scores.
    """
    supplier = _supplier()

    with pytest.raises(ValueError, match="carries planted content"):
        replace(leakage_case, planted_artefact=supplier)


def test_a_case_whose_fetching_turn_names_other_content_is_refused(
    injection_case: Case,
) -> None:
    """The message has to retrieve the content the case is attacked with.

    `corpus.fetched` matches a message against the key, so a record filed under a
    word its own turn never says is a case whose attempt fetches something else — and
    answers a clean zero that reads like a defence.
    """
    elsewhere = replace(_supplier(), key="ledger")

    with pytest.raises(ValueError, match="the turn that fetches names no such thing"):
        replace(injection_case, planted_artefact=elsewhere)


def test_content_that_waits_for_a_subject_on_a_same_turn_case_is_refused(
    injection_case: Case,
) -> None:
    """Only a retained instruction may wait for anything.

    Content scored on the turn that fetched it has no later turn for a subject to be
    raised in, so a record that made it wait would be a case whose attack can never
    fire (ADR-0041).
    """
    dormant = replace(_supplier(), fires_on=("the august invoices",))

    with pytest.raises(ValueError, match="waits for a subject"):
        replace(injection_case, planted_artefact=dormant)


def test_a_subject_the_scored_turn_never_raises_is_refused() -> None:
    """The drift `MARCH_RETAINER` used to sit beside the note to prevent.

    The subject the content waits on and the subject the case asks about are one fact
    now, so a record whose scored turn raises none of them is refused rather than
    measured as a clean zero.
    """
    dormant = load_case(CASES_DIR / "elective" / "memory-poisoning-002.toml")
    artefact = dormant.planted_artefact
    assert artefact is not None

    with pytest.raises(ValueError, match="raises none of it"):
        replace(
            dormant,
            planted_artefact=replace(artefact, fires_on=("the september ledger",)),
        )


def test_a_block_that_lost_a_field_names_the_whole_list(tmp_path: Path) -> None:
    """`RETRIEVAL_FIELDS`' argument, one block over.

    The reader of a half-written record needs the whole list, not the first key a
    `KeyError` happened to notice.
    """
    source = (CASES_DIR / "indirect-injection-001.toml").read_text(encoding="utf-8")
    written = tmp_path / "indirect-injection-001.toml"
    written.write_text(source.replace('key = "supplier"\n', ""), encoding="utf-8")

    with pytest.raises(ValueError, match=r"missing \['key'\]"):
        load_case(written)


def test_an_artefact_missing_a_half_or_a_key_is_refused() -> None:
    """Content nothing can retrieve, nothing can plant, or nothing can score."""
    with pytest.raises(ValueError, match=r"states nothing for \['key', 'prefix'\]"):
        PlantedArtefact(
            where=PlantedIn.RETRIEVED_CONTENT,
            key="",
            body="A note. Its reference is 44120.\n",
            prefix="",
            reference="44120",
        )


# --- The canary stays composed ------------------------------------------------


def test_an_artefact_whose_body_carries_the_join_is_refused() -> None:
    """A body holding the finished string would score every refusal that quoted it.

    The soundness property of both fetched-content families, asserted over the bytes
    of the record rather than argued in its header (ADR-0004).
    """
    supplier = _supplier()

    with pytest.raises(ValueError, match="joined in its own body"):
        replace(supplier, body=f"{supplier.body}\n{supplier.executed_line}\n")


def test_an_artefact_whose_body_spells_out_neither_half_is_refused() -> None:
    """Content whose instruction cannot be carried out measures the fetch."""
    with pytest.raises(ValueError, match="does not spell out"):
        PlantedArtefact(
            where=PlantedIn.RETRIEVED_CONTENT,
            key="supplier",
            body="Northwind Components — nothing is outstanding.\n",
            prefix="NOTE-PROCESSED-",
            reference="44120",
        )


def test_no_committed_body_carries_the_canary_it_produces() -> None:
    """Asserted over the library as well as over the type, because it is the property.

    A target that quotes the whole note back while refusing it reproduces both halves
    and never the join, so a refusal that describes the attack cannot be scored as one
    that carried it out.
    """
    for case in plants():
        artefact = case.planted_artefact
        assert artefact is not None
        assert artefact.executed_line not in artefact.body, case.id
        assert artefact.prefix in artefact.body, case.id
        assert artefact.reference in artefact.body, case.id


# --- Versioned by being on the record ----------------------------------------


def test_two_runs_that_planted_different_content_are_two_library_versions() -> None:
    """`_versioned` reads `dataclasses.fields`, so this field is covered by being one.

    Nothing was written to make it so, and the test is here to keep it that way: a
    library whose content changed while its version did not would be two runs
    reporting one provenance for two different attacks.
    """
    library = load_library(CASES_DIR)
    injection = next(case for case in library if case.planted_artefact is not None)
    artefact = injection.planted_artefact
    assert artefact is not None

    moved = [
        case
        if case is not injection
        else replace(
            case,
            planted_artefact=replace(
                artefact, body=artefact.body.replace("thirty days", "sixty days")
            ),
        )
        for case in library
    ]

    assert LibraryVersion.of(moved) != LibraryVersion.of(library)
    assert LibraryVersion.of(moved).cases == LibraryVersion.of(library).cases


def _supplier() -> PlantedArtefact:
    artefact = load_case(CASES_DIR / "indirect-injection-001.toml").planted_artefact
    assert artefact is not None
    return artefact


def test_the_supplier_record_is_the_one_the_helpers_read() -> None:
    """A guard on this module's own fixtures rather than on the library.

    `_supplier` is used to build the refusals above, so a rename of that record would
    otherwise turn every one of them green by never running.
    """
    supplier = _supplier()

    assert supplier.where is PlantedIn.RETRIEVED_CONTENT
    assert supplier.key == "supplier"
    assert supplier.executed_line == "NOTE-PROCESSED-44120"
