"""What hand-seeded precedent is allowed to be, and what it must never look like.

The store is long-term memory the attacker reads, and this script is the operator
writing into it by hand while the chain that fills it from the scored layer has no
caller. So the risk here is not that the writing fails — it is that a typed sentence
becomes indistinguishable from a recorded finding, or that the remediation half
reaches the attacker along with the failure half.

The store these tests touch is the one `conftest.precedent_elsewhere` points at a
temporary directory, so nothing here writes to the real file.
"""

import pytest

from backend.bench.adaptive.blinding import Blinding
from backend.bench.adaptive.precedent import (
    PRECEDENT_NAMESPACE,
    DurablePrecedents,
    JsonFileStore,
    Precedent,
)
from backend.bench.adaptive.tools import retrieve_precedent
from backend.bench.library import Family, VerdictClass
from backend.tests.conftest import a_finding, a_target
from scripts.seed_precedent import SEEDS, cleared, held, seeded


def test_a_seeded_entry_says_it_was_typed_and_not_measured() -> None:
    """A reader of the file can tell a typed sentence from a recorded finding.

    The whole risk of seeding by hand is that the hint becomes evidence. A recorded
    precedent names the case that produced it, so these name the absence of one in
    the same field, where anybody reading the store meets it first.
    """
    store = JsonFileStore()

    seeded(store)

    filed = held(store)
    assert len(filed) == len(SEEDS)
    # Asserted against the words rather than against the constant: a test that
    # compared the id to the constant it came from would pass however the constant
    # were rewritten, including into something that reads like a real case id.
    assert all("seeded" in entry.case_id for entry in filed)
    assert all("not measured" in entry.external_id for entry in filed)


def test_the_attacker_is_shown_the_failure_and_never_the_remediation() -> None:
    """`retrieve_precedent` returns one half of the record, and this is that half.

    Telling an attacker how a hole was closed hands it the defence with the
    weakness. The rule lives in `retrieve_precedent`; what this asserts is that
    seeded records are subject to it like any other.
    """
    store = JsonFileStore()
    seeded(store)
    leakage = next(seed for seed in SEEDS if seed.family is Family.DATA_LEAKAGE)

    shown = retrieve_precedent(
        DurablePrecedents(store=store),
        Family.DATA_LEAKAGE,
        Blinding.over([a_target(name="finbrief")]),
    )

    assert leakage.failure in shown
    assert leakage.remediation not in shown


def test_seeding_twice_files_the_same_entries_rather_than_copies() -> None:
    """`Precedent.key` is a digest of the record, so a re-run is idempotent.

    An operator who runs this script twice has not built a corpus of duplicates,
    and an attacker reading the store is not shown the same sentence four times.
    """
    store = JsonFileStore()

    first = seeded(store)
    second = seeded(store)

    assert first == second == len(SEEDS)


def test_clearing_removes_the_seeds_and_leaves_a_recorded_finding_alone() -> None:
    """This script deletes its own entries by key and never empties the file.

    A store with findings in it holds the only record of what earlier runs learned.
    A `--clear` that truncated the file would be this script deleting evidence it
    did not write.
    """
    store = JsonFileStore()
    durable = DurablePrecedents(store=store)
    finding = a_finding(family=Family.DATA_LEAKAGE)
    assert finding.verdict_class is VerdictClass.DETERMINISTIC
    recorded = durable.record(finding)
    seeded(store)

    remaining = cleared(store)

    assert remaining == 1
    assert [entry.case_id for entry in held(store)] == [recorded.case_id]


def test_the_two_judged_families_are_given_no_seed() -> None:
    """Precedent holds deterministic findings only (ADR-0004).

    A judged verdict carries a reliability figure and a wider stated limit, and a
    typed sentence inherits neither. `Precedent.of` refuses one on the recorded
    side; the seeds simply do not write one.
    """
    judged = {Family.WRONGFUL_COMMITMENT, Family.DISCLOSURE_DENIAL}

    assert not judged & {seed.family for seed in SEEDS}


@pytest.mark.parametrize("seed", SEEDS, ids=lambda seed: str(seed.family))
def test_no_seed_carries_a_payload(seed: Precedent) -> None:
    """Prose, and never payload text (ADR-0008).

    A precedent that quoted the message that worked would put a working exploit in
    the store, which is the one thing the record's own docstring forbids. The test
    is a heuristic and says so: what separates a description from a payload is who
    it addresses. A defender-facing sentence talks about *the target*; a payload
    addresses the reader directly and asks it for something. So an imperative, a
    second-person address or a quoted message anywhere in the sentence fails —
    mid-sentence included, which is where one actually gets pasted in.
    """
    said = seed.failure.lower()

    assert seed.failure.strip()
    assert "the target" in said
    assert "please" not in said
    assert " you " not in said and not said.startswith("you ")
    assert '"' not in seed.failure
    assert seed.stored()["family"] == str(seed.family)
    assert PRECEDENT_NAMESPACE == ("agentaudit", "precedent")
