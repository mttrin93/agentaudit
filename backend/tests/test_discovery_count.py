"""The adaptive layer beside a scored rate: a count of episodes, and a summand of
nothing.

#77 puts an adaptive number next to a scored rate in the same row, which is the place
a reader is most likely to add the two. What forbids the addition is the types and the
layout rather than a caption
([ADR-0056](../../docs/adr/0056-a-discovery-count-shares-a-row-with-a-rate-and-is-a-summand-of-nothing.md)),
and this file is the executable half of that claim.

Four hazards, one test each.

**The two numbers have different denominators, and one of them has none.** A rate is
successes over attempts; a discovery count is a count of episodes, and CONTEXT.md says
why an episode has none — *its length varies with what the attacker decides to do*. So
the row may print no fraction, no percentage and no shared heading, and the censored
count travels beside the broken one because an attacker that ran out of turns is not a
target that held.

**A family the search never worked in has no discovery count, and not a count of
zero.** The same refusal a family with no attempts makes by having no rate at all: an
attacker that never worked in a family must stay distinguishable from one that worked
there and found nothing.

**The two readings may disagree, and no code may reconcile them.** A family measured
`holds` with two adaptive discoveries is the reading the bench exists to be able to
produce (PLAN §3, trigger 2). Asserted as *nothing else on the page moves*: the two
documents differ by the lines about the search and by nothing else.

**The count exists only as a sentence.** No type on either surface carries it as a
number, so `entry.rate.successes + <the count>` is a type error rather than a
judgement call. The other half of that claim is in `test_payload.py`, which fails when
a field for one is added to `FamilyEntry`.
"""

import re
from dataclasses import fields, replace

import pytest

from backend.bench.adaptive.episode import EpisodeOutcome
from backend.bench.assembler import AdaptiveSection, ReportedEpisode
from backend.bench.library import Family
from backend.bench.payload import TargetPayload
from backend.bench.rendering import render
from backend.bench.rendering._measured import Discoveries
from backend.tests.test_payload import a_payload, a_result, an_episode
from backend.tests.test_rendering import _block


def _searching(*episodes: ReportedEpisode, successes: int = 30) -> TargetPayload:
    """One deterministic family, and the search this run recorded against it.

    One family and no judged entry, so the block under `### data_leakage` is the only
    place either reading can appear.
    """
    return a_payload(
        result=a_result(
            families=(Family.DATA_LEAKAGE,),
            successes=successes,
            judged=(),
            adaptive=AdaptiveSection(episodes=episodes),
        )
    )


def test_a_familys_block_prints_what_the_search_found_beside_what_it_measured() -> None:
    # Two readings of one family in one block: the rate over attempts, and the count
    # of episodes. Both present, and neither derived from the other.
    payload = _searching(
        an_episode(Family.DATA_LEAKAGE),
        an_episode(Family.DATA_LEAKAGE),
        an_episode(Family.DATA_LEAKAGE, EpisodeOutcome.CENSORED),
    )
    block = _block(render(payload), "data_leakage")

    measured = [line for line in block if "attempts succeeded**" in line]
    found = [line for line in block if "episodes broke this family" in line]
    assert len(measured) == 1, "the rate line is not in this family's block"
    assert len(found) == 1, "the discovery count is not in this family's block"

    # Separate lines, and neither readable as a continuation of the other: the rate
    # line names attempts and the discovery line names episodes.
    [rate_line] = measured
    [found_line] = found
    assert "30 of 30 attempts succeeded" in rate_line
    assert "2 episodes broke this family" in found_line
    assert "1 stopped out of turns" in found_line, (
        "the censored count is not beside the broken one, so an attacker that ran "
        "out of turns reads as a target that held"
    )

    # The word is **discoveries**, matching CONTEXT.md's **adaptive finding**: not
    # breaks, not successes, and never an adaptive rate. `rate` appears in the line
    # only in the clause that says the count is not one.
    assert found_line.startswith("- **Discoveries")
    for wrong in ("success", "adaptive rate", "discovery rate"):
        assert wrong not in found_line, f"{found_line} calls the count a {wrong}"

    # And no denominator, in any of the three forms one could arrive in.
    assert "attempt" not in found_line
    assert "%" not in found_line
    assert not re.search(r"\d\s*/\s*\d", found_line), f"{found_line} prints a fraction"
    assert "no denominator" in found_line


def test_a_family_the_search_never_worked_in_has_no_count_and_not_a_zero() -> None:
    # The same refusal a family with no attempts makes by having no rate: the number
    # is absent and the absence is stated in words, rather than printed as zero.
    block = _block(render(_searching()), "data_leakage")

    [found_line] = [line for line in block if "adaptive attacker" in line]

    assert "no episode" in found_line
    assert "not a count of zero" in found_line
    assert not re.search(r"\b0\b", found_line), f"{found_line} prints a count of zero"


def test_a_family_that_holds_with_a_discovery_against_it_is_left_as_it_reads() -> None:
    # The reading the bench exists to be able to produce (PLAN §3, trigger 2), and the
    # assertion is that no code reconciles it: the band, the rate, the interval and
    # every other line are the lines of the same run with no search recorded.
    searched = render(
        _searching(
            an_episode(Family.DATA_LEAKAGE),
            an_episode(Family.DATA_LEAKAGE),
            successes=0,
        )
    )
    unsearched = render(_searching(successes=0))

    row = _block(searched, "data_leakage")
    assert "**Band — holds**" in "\n".join(row)
    assert "2 episodes broke this family" in "\n".join(row)

    # And every other line of that row is byte-identical to the row of the same run
    # with no search recorded: nothing here resolves the disagreement, marks it, or
    # reads one reading against the other.
    unmoved = [line for line in row if "adaptive attacker" not in line]
    assert unmoved == [
        line
        for line in _block(unsearched, "data_leakage")
        if "adaptive attacker" not in line
    ]
    assert len(row) == len(unmoved) + 1


def test_the_discovery_count_is_a_sentence_and_no_type_holds_it_as_a_number() -> None:
    """The type-level half: there is no number for anybody to add.

    `Discoveries` carries the row's sentence and nothing arithmetical, so the count
    cannot be lifted off it and added to a rate — under `mypy --strict` the addition
    is an error at the call site rather than a line that type-checks and means
    nothing (ADR-0010, ADR-0056).
    """
    assert [(one.name, one.type) for one in fields(Discoveries)] == [("stated", "str")]

    # And it is built from the episodes rather than set by a caller, so a row cannot
    # be handed a count that no episode supports.
    one = Discoveries.of(
        (
            {"family": "data_leakage", "outcome": EpisodeOutcome.BROKEN.value},
            {"family": "data_leakage", "outcome": EpisodeOutcome.CENSORED.value},
        )
    )
    assert "1 episode broke this family" in one.stated

    # And no episodes at all is refused rather than worded, so the absence has one
    # representation — the family missing from the mapping — and not two.
    with pytest.raises(ValueError, match="never worked in"):
        Discoveries.of(())


def test_a_family_with_no_figure_still_carries_what_the_search_found() -> None:
    # The join is the family and never the figure. A family whose rate is withheld
    # and a family whose precondition was unmet are both families an attacker may
    # have broken, and a document silent about the count there would be silent about
    # the only reading it has.
    text = render(
        a_payload(
            result=replace(
                a_result(),
                adaptive=AdaptiveSection(
                    episodes=(an_episode(Family.WRONGFUL_COMMITMENT),)
                ),
            )
        )
    )

    barred = [line for line in text.splitlines() if "wrongful_commitment" in line]
    assert barred
    assert any("1 episode broke this family" in line for line in barred)
