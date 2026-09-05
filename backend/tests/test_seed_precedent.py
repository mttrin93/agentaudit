"""What hand-seeded precedent is allowed to be, and what it must never look like.

The store is long-term memory the attacker reads, and this script is the operator
writing into it by hand. The chain that fills it from the scored layer has a caller
since #38 (`bench/filing.py`), so these sentences are no longer the only thing the
store has ever held — and the risk here is unchanged by that: it is that a typed
sentence becomes indistinguishable from a recorded finding, or that the remediation
half reaches the attacker along with the failure half.

The store these tests touch is the one `conftest.precedent_elsewhere` points at a
temporary directory, so nothing here writes to the real database.
"""

import pytest

from backend.bench.adaptive import precedent
from backend.bench.adaptive.blinding import Blinding
from backend.bench.adaptive.precedent import (
    PRECEDENT_NAMESPACE,
    DurablePrecedents,
    Precedent,
    PrecedentDatabase,
)
from backend.bench.adaptive.tools import retrieve_precedent
from backend.bench.library import Family, VerdictClass
from backend.tests.conftest import A_FIX, a_finding, a_target
from scripts.seed_precedent import SEEDS, cleared, held, main, seeded
from scripts.seed_precedent import __doc__ as SEED_DOC


def test_a_seeded_entry_says_it_was_typed_and_not_measured() -> None:
    """A reader of the file can tell a typed sentence from a recorded finding.

    The whole risk of seeding by hand is that the hint becomes evidence. A recorded
    precedent names the case that produced it, so these name the absence of one in
    the same field, where anybody reading the store meets it first.
    """
    store = PrecedentDatabase()

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
    store = PrecedentDatabase()
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
    store = PrecedentDatabase()

    first = seeded(store)
    second = seeded(store)

    assert first == second == len(SEEDS)


def test_clearing_removes_the_seeds_and_leaves_a_recorded_finding_alone() -> None:
    """This script deletes its own entries by key and never empties the file.

    A store with findings in it holds the only record of what earlier runs learned.
    A `--clear` that truncated the file would be this script deleting evidence it
    did not write.
    """
    store = PrecedentDatabase()
    durable = DurablePrecedents(store=store)
    finding = a_finding(family=Family.DATA_LEAKAGE)
    assert finding.verdict_class is VerdictClass.DETERMINISTIC
    recorded = durable.record(finding, A_FIX)
    seeded(store)

    remaining = cleared(store)

    assert remaining == 1
    assert [entry.case_id for entry in held(store)] == [recorded.case_id]


def test_the_script_seeds_and_clears_through_its_own_command_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`--clear` through `main`, because that is the way an operator reaches it.

    The test above calls `cleared` directly, which leaves the argument parsing and
    the exit code untested — and the store the command line builds is not the store
    a test hands it. The three invocations are one sequence on purpose: seeding is
    what gives clearing something to remove.
    """
    store = PrecedentDatabase()

    assert main([]) == 0
    assert len(held(store)) == len(SEEDS)

    assert main(["--clear"]) == 0
    assert held(store) == []

    assert main(["--list"]) == 0
    assert "nothing filed" in capsys.readouterr().out


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


def test_the_document_the_store_used_to_be_is_named_while_it_is_still_there(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """#36 dropped the old store rather than importing it, and this says it aloud.

    A clone that ran the bench before has a `findings.json` holding the sentences
    an operator typed, and nothing reads it any more. The failure mode that makes
    a decision look like an oversight is an operator who runs `--list`, is told
    nothing is filed, and concludes the seeding broke — so the command that would
    print that is the command that names the file it has stopped reading.

    Nothing is imported from it and nothing deletes it: the store was machine-local
    and git-ignored, so re-seeding is the whole migration (ADR-0029).

    Written at the path `conftest.precedent_elsewhere` already redirects, rather than
    patched again here, so this also asserts that the redirection reaches the script:
    it reads the module attribute for exactly that reason, because a `from … import`
    would have bound the real location and asked the engineer's working copy.
    """
    legacy = precedent.LEGACY_STORE_PATH
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text("[]\n", encoding="utf-8")

    assert main(["--list"]) == 0

    printed = capsys.readouterr().out
    assert str(legacy) in printed
    assert "no longer read" in printed
    assert legacy.exists(), "the notice deleted the operator's own file"


def test_the_store_the_script_writes_to_is_the_one_it_names(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The path printed is read off the store rather than off the constant.

    `conftest.precedent_elsewhere` redirects the store and the suite would
    otherwise have been printing the real location while writing to a temporary
    one — a banner that disagrees with the file it describes is worse than none,
    because it is the line an operator checks before believing the rest.
    """
    assert main(["--list"]) == 0

    assert str(PrecedentDatabase().path) in capsys.readouterr().out


def test_the_script_describes_a_chain_that_now_has_a_caller() -> None:
    """The docstring is a claim about the rest of the codebase, so it is asserted.

    It used to say the chain that fills the store from the scored layer "has no
    caller yet", which was true and is the sentence #38 quoted as the statement of
    the bug. A run files now (ADR-0031), so an operator reading this script would
    otherwise be told the store has only ever held their own typed sentences — and
    the one place that mistake matters is the script whose whole purpose is to make
    a typed sentence distinguishable from a recorded finding.
    """
    assert SEED_DOC is not None
    assert "no caller" not in SEED_DOC, (
        "the script still describes the absence #38 closed, so an operator is "
        "told the store holds nothing a run produced"
    )
    assert "bench/filing.py" in SEED_DOC, (
        "the script does not name the module that now fills the store, so a "
        "reader has nowhere to go to check the claim above"
    )
