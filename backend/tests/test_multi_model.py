"""The multi-model validity check — does the bench read defences or refusals?

Three seams, and the split is the one the rest of the suite already uses.

The **comparison arithmetic** is exercised over two hand-built runs, because what
`collapsed` means has to be exactly right and an end-to-end run cannot localise an
error in it. The **adaptive comparison** is exercised the same way and separately,
because `A_break` is measured on episodes and families and nothing about it may
arrive through a scored type (ADR-0010). The **entry point** is driven end to end
against the three reference agents on two stub models, because a comparison of two
runs nobody made is not a validity check.

The invariant these tests exist for: the swap moves the model and holds everything
else still. Same library, same agents, same rule — so a difference between the two
runs is attributable to the model or it is attributable to nothing.
"""

import re
import shutil
from collections.abc import Sequence
from pathlib import Path

import pytest

from backend.bench.adaptive.attacker import AttackerCompletion
from backend.bench.adaptive.crossmodel import NotAnAdaptiveSwap
from backend.bench.adaptive.crossmodel import compare as compare_adaptive
from backend.bench.adaptive.discrimination import (
    AdaptiveDiscrimination,
    SeparationReading,
    measure,
)
from backend.bench.adaptive.episode import AdaptiveEpisode, EpisodeOutcome
from backend.bench.adaptive.promotion import Promotion, promote
from backend.bench.adaptive.proposal import ProposedRoute, proposed_from
from backend.bench.adaptive.scripted import SCRIPTED_ATTACKER
from backend.bench.adjudication import Completion
from backend.bench.admission import (
    AdmissionOutcome,
    CrossModelRejections,
    RejectionKind,
    decide,
    rejections,
)
from backend.bench.admitting import Measure, cross_model_bar
from backend.bench.calibration import CalibrationResult
from backend.bench.crossmodel import (
    ComparisonOutcome,
    ModelReading,
    NotASwap,
    SwapReading,
    compare,
)
from backend.bench.decided import (
    DECISION_NAMESPACE,
    Consultation,
    Consulted,
    DecidedRoutes,
)
from backend.bench.entry import Entry
from backend.bench.evaluator import Verdict
from backend.bench.gate import GateResult
from backend.bench.lease import take_the_library
from backend.bench.library import (
    EMPTY_LIBRARY,
    AdmissionReading,
    Case,
    DiscoveredBy,
    Family,
    LibraryVersion,
    load_library,
)
from backend.bench.rule import DECLARED_RULE, GateRule
from backend.bench.scorer import (
    Excluded,
    ExclusionReason,
    GateDecision,
    GateOutcome,
)
from backend.graph.approval import ApprovalOutcome
from backend.graph.budget import RunBudget
from backend.graph.runstate import RunState
from backend.targets.reference.model import ModelConfig, Provider, measures_the_field
from backend.tests.conftest import (
    BENCH_ATTESTATION,
    CASES_DIR,
    CONFIRMING,
    a_target,
    adjudicating,
    imports_of,
)
from backend.tests.test_adaptive_discrimination import HARDENED, TRIVIAL, grid
from backend.tests.test_gate import (
    ADJUDICATOR_STAND_IN,
    ATTACKER_STAND_IN,
    outcomes_for,
)
from scripts.console import EXIT_DECLINED, EXIT_WITHHELD
from scripts.swap import EXIT_NOT_WRITTEN, ModelRun, main, record_swap

CROSSMODEL_SOURCE = Path(__file__).resolve().parents[1] / "bench" / "crossmodel.py"
ADAPTIVE_CROSSMODEL_SOURCE = (
    Path(__file__).resolve().parents[1] / "bench" / "adaptive" / "crossmodel.py"
)

FIRST = "stub:obedient"
SECOND = "stub:cooperative"

SEPARATES = (0, 15, 30)
"""Hardened, weak and trivial successes of thirty that clear the per-family pass."""

FLAT = (30, 30, 30)
"""Every agent broken equally: D = 0, intervals identical, nothing separated."""


def a_run(
    *counts: tuple[int, int, int],
    excluded: Sequence[Family] = (),
    library: LibraryVersion | None = None,
    rule: GateRule = DECLARED_RULE,
) -> GateResult:
    """A recorded run of the whole library, from six sets of counts.

    Built rather than measured, for the reason `test_gate.py` builds its decisions
    from counts: what a collapse *is* has to be right about numbers before it is
    worth reading off a run.
    """
    outcomes = outcomes_for(*counts)
    return GateResult(
        decision=GateDecision(
            outcome=GateOutcome.PASSED,
            families_passing=sum(1 for outcome in outcomes if outcome.passes),
            families_monotonic=len(outcomes),
            outcomes=tuple(outcomes),
            rule=rule,
            excluded=tuple(
                Excluded(
                    family=family,
                    reason=ExclusionReason.UNFIT_TO_REPORT,
                    kappa=0.59,
                )
                for family in excluded
            ),
        ),
        library=library or LibraryVersion(cases=18, digest="a10ab0c566aa"),
        reliability={},
        attempts=540,
        agents=("trivial", "weak", "hardened"),
    )


def readings(
    first: GateResult, second: GateResult
) -> tuple[ModelReading, ModelReading]:
    """The two runs, named by the model each was made on."""
    return (
        ModelReading(model=FIRST, result=first),
        ModelReading(model=SECOND, result=second),
    )


# --- Seam one: D compared per family across two model runs --------------------


def test_d_is_compared_per_family_across_the_two_model_runs() -> None:
    # The comparison the ticket exists for: the same six families, two models, and
    # the change in D stated per family rather than as one number over the bench.
    swap = compare(
        *readings(
            a_run(SEPARATES, SEPARATES, SEPARATES, SEPARATES, SEPARATES, SEPARATES),
            a_run(SEPARATES, FLAT, SEPARATES, SEPARATES, SEPARATES, SEPARATES),
        )
    )

    by_family = {comparison.family: comparison for comparison in swap.comparisons}
    assert len(by_family) == len(Family)
    held = by_family[list(Family)[0]]
    assert held.first.outcome is not None and held.second.outcome is not None
    assert held.change == 0.0
    assert held.outcome is ComparisonOutcome.HELD

    lost = by_family[list(Family)[1]]
    assert lost.change == pytest.approx(-1.0)
    assert lost.outcome is ComparisonOutcome.COLLAPSED


def test_a_collapse_is_attributable_to_families_and_not_to_the_bench() -> None:
    # The distinction the whole check turns on. Two families fall and four hold, so
    # what the swap cost is those two families — not every score the bench produced.
    swap = compare(
        *readings(
            a_run(SEPARATES, SEPARATES, SEPARATES, SEPARATES, SEPARATES, SEPARATES),
            a_run(FLAT, FLAT, SEPARATES, SEPARATES, SEPARATES, SEPARATES),
        )
    )

    assert swap.collapsed == tuple(list(Family)[:2])
    assert len(swap.held) == 4
    assert swap.reading is SwapReading.FAMILIES_COLLAPSED
    stated = swap.stated()
    for family in swap.collapsed:
        assert f"{family}:" in stated
    assert "attributable to the families listed above" in stated


def test_a_collapse_with_nothing_left_standing_is_attributed_to_the_bench() -> None:
    # The outcome the check was built to be able to return, and the one that says
    # every score the bench ever produced was about the model provider's training.
    swap = compare(
        *readings(
            a_run(SEPARATES, SEPARATES, SEPARATES, SEPARATES, SEPARATES, SEPARATES),
            a_run(FLAT, FLAT, FLAT, FLAT, FLAT, FLAT),
        )
    )

    assert len(swap.collapsed) == len(Family)
    assert swap.held == ()
    assert swap.reading is SwapReading.COLLAPSED_WHOLESALE
    assert "published exactly as it stands" in swap.stated()


def test_a_swap_that_costs_no_family_reads_as_the_bench_reading_defences() -> None:
    swap = compare(
        *readings(
            a_run(SEPARATES, SEPARATES, SEPARATES, SEPARATES, SEPARATES, SEPARATES),
            a_run(SEPARATES, SEPARATES, SEPARATES, SEPARATES, SEPARATES, SEPARATES),
        )
    )

    assert swap.collapsed == ()
    assert swap.reading is SwapReading.DEFENCES
    assert "It is a reading about two models" in swap.stated()


def test_a_family_that_separated_on_neither_model_is_not_a_collapse() -> None:
    # A family with no discrimination to lose has not lost any. Counting it as a
    # collapse would report a family the bench never claimed as one it lost.
    swap = compare(*readings(a_run(*[FLAT] * 6), a_run(*[FLAT] * 6)))

    assert swap.collapsed == ()
    assert swap.reading is SwapReading.NOTHING_SEPARATED
    assert "separated nothing" in swap.stated()


def test_a_family_excluded_from_either_run_is_compared_in_neither() -> None:
    # Exclusion is total (ADR-0015 §3). A family whose κ bars it from the gate does
    # not reach a reader through the validity check either, and its absence is
    # stated rather than left as a gap.
    barred = list(Family)[0]
    swap = compare(
        *readings(
            a_run(*[SEPARATES] * 6, excluded=[barred]),
            a_run(*[FLAT] * 6),
        )
    )

    [comparison] = [c for c in swap.comparisons if c.family is barred]
    assert comparison.outcome is ComparisonOutcome.NOT_COMPARED
    assert comparison.change is None
    assert not comparison.compared
    assert barred in swap.not_compared
    assert barred not in swap.collapsed
    assert "not weighed" in swap.stated()


def test_a_comparison_of_one_model_with_itself_is_not_a_swap() -> None:
    # The difference between two runs of one model is the bench's own run-to-run
    # variation, and attributing it to a model change would answer this check's
    # question with a number about something else.
    run = a_run(*[SEPARATES] * 6)

    with pytest.raises(NotASwap, match="Reading one model twice"):
        compare(
            ModelReading(model=FIRST, result=run),
            ModelReading(model=FIRST, result=run),
        )


def test_a_comparison_across_two_libraries_is_not_a_swap() -> None:
    # The swap holds the library still and moves the model. Across two libraries the
    # difference measured is a difference in payloads (spec story 27).
    with pytest.raises(NotASwap, match="different libraries"):
        compare(
            *readings(
                a_run(*[SEPARATES] * 6),
                a_run(
                    *[SEPARATES] * 6,
                    library=LibraryVersion(cases=17, digest="0000deadbeef"),
                ),
            )
        )


def test_a_comparison_across_two_rules_is_not_a_swap() -> None:
    # Every family passed or did not pass under its own run's rule, so a comparison
    # of two runs decided under different rules would print one bar and read the
    # families against another. The comparison has no rule of its own to fall back
    # on, which is why this is a refusal and not a choice between them.
    with pytest.raises(NotASwap, match="different rules"):
        compare(
            *readings(
                a_run(*[SEPARATES] * 6),
                a_run(*[SEPARATES] * 6, rule=GateRule(discrimination_floor=0.9)),
            )
        )


def test_the_comparison_prints_the_declared_bar_and_declares_no_new_one() -> None:
    # The bar every family is read against is ADR-0003's per-family pass, printed
    # above the table for the reason the gate prints its rule above its answer. A
    # collapse threshold of its own would be a bar nobody agreed.
    stated = compare(*readings(a_run(*[SEPARATES] * 6), a_run(*[FLAT] * 6))).stated()

    assert f"D >= {DECLARED_RULE.discrimination_floor:.2f}" in stated
    assert "No threshold is declared here" in stated
    assert FIRST in stated and SECOND in stated
    assert "sha256:a10ab0c566aa" in stated


def test_the_scored_comparison_imports_no_route_to_the_adaptive_layer() -> None:
    # Import-level, because "no adaptive result reaches a scored comparison" is a
    # claim about reachability and a name is a route (ADR-0010). `A_break` faces the
    # same question in its own module, on its own denominators.
    reachable = [
        name
        for name in imports_of(CROSSMODEL_SOURCE)
        if "adaptive" in name or "episode" in name
    ]

    assert not reachable, (
        f"{reachable} is reachable from crossmodel.py. The scored comparison is "
        "published as evidence and the adaptive layer decides nothing"
    )


# --- Seam two: the cross-model admission bar, counted -------------------------


def test_a_route_that_separates_on_one_model_only_is_a_cross_model_rejection() -> None:
    # ADR-0012 calls the discard a finding in its own right: direct evidence that
    # what the attacker found was a property of one model rather than of the agents'
    # defences. So it is counted, and counted apart from the other refusals.
    counted = rejections(
        (
            _proposed("one-model", SEPARATES, FLAT),
            _proposed("no-model", FLAT, FLAT),
            _proposed("both-models", SEPARATES, SEPARATES),
            _proposed("unread", SEPARATES),
        )
    )

    landed = {
        kind: [outcome.case_id for outcome in counted.of(kind)]
        for kind in RejectionKind
    }
    assert landed[RejectionKind.CROSS_MODEL] == ["one-model"]
    assert landed[RejectionKind.SEPARATED_NOWHERE] == ["no-model"]
    assert landed[RejectionKind.UNREAD] == ["unread"]
    assert landed[RejectionKind.ADMITTED] == ["both-models"]
    # One denominator: every decided proposal lands on exactly one answer, so the
    # counts sum to the proposals decided and a reader can check that they do.
    assert sum(counted.counts.values()) == len(counted.outcomes)
    stated = counted.stated()
    assert "4 proposal(s) decided, 4 of them facing the cross-model bar" in stated
    for kind in RejectionKind:
        assert f"{kind}: {counted.counts[kind]}" in stated


SEPARATING_COUNTS = {"attempts": 10, "hardened": 0, "weak": 5, "trivial": 10}
"""One case's counts that clear the bar: D = 1.00, intervals nowhere near each other.

Per *case* and at the declared ten attempts, where `SEPARATES` above is per family
at thirty. Two denominators for two questions, kept apart because one is admission's
and one is the gate's (`AdmissionReading`).
"""

FLAT_COUNTS = {"attempts": 10, "hardened": 9, "weak": 9, "trivial": 10}
"""Counts that do not: the two ends one attempt apart, intervals overlapping."""


@pytest.fixture
def memory(tmp_path: Path) -> DecidedRoutes:
    """This check's own admission memory, under a directory that is not there yet."""
    return DecidedRoutes.at(tmp_path / "decisions" / "routes.sqlite")


def test_a_route_already_decided_is_not_measured_against_the_agents_again(
    memory: DecidedRoutes, leakage_case: Case
) -> None:
    """#39's definition of done, and the money the ticket saves.

    Two runs against one memory. The first pays for an admission run on both models;
    the second reports the same refusal and calls nothing — which is what
    "re-measured against three reference agents on two underlying models, at the
    operator's cost, for the same answer" was costing every run the attacker
    rediscovered a route in.
    """
    asked: list[tuple[str, tuple[str, ...]]] = []
    measure = _measuring(asked, SEPARATING_COUNTS, FLAT_COUNTS)

    first = _bar(memory=memory, proposals=(_a_proposal(leakage_case),), measure=measure)

    assert not isinstance(first, int)
    assert [model for model, _ in asked] == [FIRST, SECOND]

    asked.clear()
    again = _bar(memory=memory, proposals=(_a_proposal(leakage_case),), measure=measure)

    assert not isinstance(again, int)
    assert asked == [], (
        f"the second run measured {asked} again. A route the gate already decided "
        "under this run's own conditions is reported from memory, and the three "
        "reference agents are never called for it (ADR-0032)"
    )
    rejected, promotions, consulted = again
    assert rejected.counts[RejectionKind.CROSS_MODEL] == 1
    assert len(promotions) == 1 and not promotions[0].admitted
    assert len(consulted.remembered) == 1 and consulted.to_measure == ()


def test_the_rejection_counts_say_how_many_of_them_this_run_measured(
    memory: DecidedRoutes, leakage_case: Case
) -> None:
    # The one thing #39 could cost this document: a rejection count a reader cannot
    # tell apart from a count the run in front of them paid for. So the block states
    # both numbers, and each remembered decision carries the date it was measured.
    measure = _measuring([], SEPARATING_COUNTS, FLAT_COUNTS)
    _bar(memory=memory, proposals=(_a_proposal(leakage_case),), measure=measure)

    again = _bar(memory=memory, proposals=(_a_proposal(leakage_case),), measure=measure)

    assert not isinstance(again, int)
    stated = again[2].stated()
    assert "1 proposal(s) put to the bar, 1 answered from memory" in stated
    assert "0 route(s) to measure" in stated
    assert "reported from memory" in stated


def test_a_remembered_decision_says_so_where_the_promotions_are_reported(
    memory: DecidedRoutes, leakage_case: Case
) -> None:
    # `Promotion.stated` prints *promoted* or *discarded* and says nothing about
    # where its counts came from, so a reader of that list could not tell a decision
    # this run paid for from one it read back. The promotion lines are what a run
    # prints about each proposal, so that is where the sentence has to be.
    measure = _measuring([], SEPARATING_COUNTS, FLAT_COUNTS)
    paid = _bar(memory=memory, proposals=(_a_proposal(leakage_case),), measure=measure)
    assert not isinstance(paid, int)
    assert "reported from memory" not in paid[2].reported(paid[1])

    again = _bar(memory=memory, proposals=(_a_proposal(leakage_case),), measure=measure)

    assert not isinstance(again, int)
    reported = again[2].reported(again[1])
    assert "discarded" in reported
    assert "reported from memory" in reported
    assert "nothing was measured against three agents on two models" in reported


def test_a_promotion_list_that_does_not_pair_with_the_consultation_is_refused(
    memory: DecidedRoutes, leakage_case: Case
) -> None:
    # The two are one list of proposals read twice, so a pairing that lost an element
    # would label the wrong promotions — a measured decision printed as a remembered
    # one is exactly the misreading the sentence exists to prevent.
    answer = _bar(
        memory=memory,
        proposals=(_a_proposal(leakage_case), _a_proposal(leakage_case)),
        measure=_measuring([], SEPARATING_COUNTS, FLAT_COUNTS),
    )
    assert not isinstance(answer, int)

    with pytest.raises(ValueError, match="one list of proposals read twice"):
        answer[2].reported(answer[1][:1])


def test_one_route_proposed_four_times_in_one_run_is_measured_once(
    memory: DecidedRoutes, leakage_case: Case
) -> None:
    # `docs/validation.md` records exactly this run: four proposals, "all describing
    # the same route in prose". The counts do not improve for being bought four
    # times — and the *proposal* stays the unit the rejections are counted on, so
    # all four are still decided and still counted.
    proposals = tuple(_a_proposal(leakage_case) for _ in range(4))
    asked: list[tuple[str, tuple[str, ...]]] = []

    answer = _bar(
        memory=memory,
        proposals=proposals,
        measure=_measuring(asked, SEPARATING_COUNTS, FLAT_COUNTS),
    )

    assert not isinstance(answer, int)
    assert [len(cases) for _, cases in asked] == [1, 1], (
        f"one route reached the agents as {asked}. Four proposals of one route are "
        "one measurement on each model"
    )
    rejected, promotions, _ = answer
    assert len(promotions) == 4
    assert rejected.counts[RejectionKind.CROSS_MODEL] == 4
    assert sum(rejected.counts.values()) == 4


def test_a_run_that_proposed_nothing_measures_nothing_and_remembers_nothing(
    memory: DecidedRoutes,
) -> None:
    # A fact about the attacker and not about the bar, and the memory does not turn
    # it into one: nothing is read, nothing is written, and no database is created
    # (ADR-0029 point 7).
    asked: list[tuple[str, tuple[str, ...]]] = []

    answer = _bar(
        memory=memory,
        proposals=(),
        measure=_measuring(asked, SEPARATING_COUNTS, FLAT_COUNTS),
    )

    assert not isinstance(answer, int)
    assert asked == []
    assert answer[2].consulted == ()
    assert not memory.store.path.exists()


def test_an_admission_run_that_did_not_happen_remembers_nothing(
    memory: DecidedRoutes, leakage_case: Case
) -> None:
    # The operator declined the cost, or the run hit its ceiling: `measure_on`
    # answers with an exit code and nothing was spent. A memory that recorded a
    # decision here would answer the next run from counts nobody took.
    def declined(**_: object) -> dict[str, AdmissionReading] | int:
        return EXIT_DECLINED

    answer = _bar(
        memory=memory, proposals=(_a_proposal(leakage_case),), measure=declined
    )

    assert answer == EXIT_DECLINED
    assert memory.store.search(DECISION_NAMESPACE) == []


def _bar(
    *,
    memory: DecidedRoutes,
    proposals: tuple[ProposedRoute, ...],
    measure: Measure,
) -> tuple[CrossModelRejections, tuple[Promotion, ...], Consultation] | int:
    """`cross_model_bar` over two model runs, the first carrying those proposals."""
    first, second = readings(a_run(*[SEPARATES] * 6), a_run(*[SEPARATES] * 6))
    runs = [_a_model_run(first, proposals), _a_model_run(second)]
    return cross_model_bar(
        proposals=[proposal for run in runs for proposal in run.proposals],
        models=[run.reading.model for run in runs],
        attestation=BENCH_ATTESTATION,
        approve=CONFIRMING,
        adjudicator=adjudicating(),
        adjudicator_model=ADJUDICATOR_STAND_IN,
        price_per_call=None,
        memory=memory,
        measure=measure,
        say=print,
    )


def _a_proposal(objective: Case) -> ProposedRoute:
    """One proposal, drafted the way `propose_case` drafts it inside an episode.

    A fresh uuid in the case id on every call, because `proposal.py` mints one —
    which is why the memory is keyed by the route and not by the case.
    """
    return proposed_from(
        objective=objective,
        target=a_target("trivial"),
        family=Family(objective.family),
        payload="the probe that actually ran",
        description="a route worth promoting",
    )


def _measuring(
    asked: list[tuple[str, tuple[str, ...]]],
    first: dict[str, int],
    second: dict[str, int],
) -> Measure:
    """An admission run that records what it was asked for and answers with counts.

    The counts are constructed, for `test_promotion.py`'s reason. What is under test
    is which admission runs happen, and the only way to see one that did not happen
    is to keep what each of them was asked for.
    """

    def measure(
        *, cases: Sequence[Case], model: str, **_: object
    ) -> dict[str, AdmissionReading] | int:
        asked.append((model, tuple(case.id for case in cases)))
        counts = first if model == FIRST else second
        return {
            case.id: AdmissionReading(
                model=model,
                attempts=counts["attempts"],
                hardened=counts["hardened"],
                weak=counts["weak"],
                trivial=counts["trivial"],
            )
            for case in cases
        }

    return measure


# --- Seam three: A_break and A_effort across the swap ------------------------


def test_a_break_and_a_effort_are_compared_across_the_two_models() -> None:
    # 8b's question put to the attacker: an attacker that discriminates on one model
    # and not on another is reading model temperament exactly as a family would be.
    swap = compare_adaptive(
        _reading(broken_on_trivial=2, turns=1),
        _reading(broken_on_trivial=0, turns=None),
        first_model=FIRST,
        second_model=SECOND,
    )

    assert swap.first.separation.value > 0
    assert swap.second.separation.value == 0
    assert swap.change == pytest.approx(-2 / len(Family))
    assert not swap.survives
    assert not swap.same_reading
    assert swap.readings == (
        SeparationReading.DISCRIMINATES,
        SeparationReading.ATTACKER_WEAK,
    )

    stated = swap.stated()
    assert "A_break" in stated and "A_effort" in stated
    # Compared on episodes and families, so no rate, no interval and no D reaches
    # this block whatever the two runs measured (ADR-0010, ADR-0011).
    assert "D =" not in stated
    assert "It decides nothing" in stated

    # A_effort per agent, with the censoring beside each median rather than folded
    # into it: the second model censored every episode, so it has no median at all.
    [effort] = [
        comparison for comparison in swap.effort if comparison.target_name == "trivial"
    ]
    assert effort.first is not None and effort.first.median == 1
    assert effort.second is not None and effort.second.median is None
    assert effort.change is None
    assert "no median" in effort.stated()
    # Named by the model each median was read on: two A_effort lines for one agent
    # with nothing to tell them apart is a table a reader cannot use.
    assert FIRST in effort.stated() and SECOND in effort.stated()


def test_a_change_of_one_family_is_printed_as_inside_the_run_to_run_variation() -> None:
    # docs/validation.md records two runs of one identical configuration disagreeing
    # by one family, so a swap that moves A_break by one family has not been shown
    # to have moved it at all. Printed, never decided on.
    swap = compare_adaptive(
        _reading(broken_on_trivial=1, turns=1),
        _reading(broken_on_trivial=0, turns=None),
        first_model=FIRST,
        second_model=SECOND,
    )

    assert swap.step == pytest.approx(1 / len(Family))
    assert swap.within_one_family
    assert "no larger than one family flipping" in swap.stated()


def test_two_adaptive_readings_of_one_model_are_not_a_swap() -> None:
    with pytest.raises(NotAnAdaptiveSwap, match="run-to-run variation"):
        compare_adaptive(
            _reading(broken_on_trivial=1, turns=1),
            _reading(broken_on_trivial=1, turns=1),
            first_model=FIRST,
            second_model=FIRST,
        )


def test_the_adaptive_comparison_reaches_no_rule_and_no_scored_arithmetic() -> None:
    # The other direction of ADR-0010, and the one that keeps `A_break` from being
    # read as `D`: the thresholds this layer runs under live in `AdaptiveBudget`, and
    # a comparison that could see a `GateRule` could be given one to clear.
    reachable = [
        name
        for name in imports_of(ADAPTIVE_CROSSMODEL_SOURCE)
        if name.endswith(
            ("rule", "GateRule", "scorer", "Rate", "Interval", "Band", "crossmodel")
        )
    ]

    assert not reachable, (
        f"{reachable} is reachable from the adaptive comparison. It is measured on "
        "episodes and families and decides nothing"
    )


# --- The line between a model and a fixture ----------------------------------


def test_every_provider_says_whether_a_reading_on_it_measures_the_field() -> None:
    """Both sides of the line, and the closed enum as the denominator.

    Here rather than in `test_retirement.py` because this is the question the swap
    makes load-bearing: the retirement window is scoped to a model and a reading taken
    on a fixture cannot retire anything (ADR-0022), so this one boolean decides whether
    a stored reading may ever end a case's life.

    It is asserted directly because provenance can only *withhold* a retirement. An
    inverted mapping fails in the silent direction — every reading marked as a fixture,
    every retirement declined, no case ever retired again, and not one test red. Every
    other test that exercises the wiring runs on a stub and asserts the false side, so
    without this one the true side is never checked at all.
    """
    assert measures_the_field(ModelConfig.parse("openrouter:openai/gpt-4.1-nano"))
    assert not measures_the_field(ModelConfig.parse("stub:obedient"))

    # Every member of the closed enum answered, and the answers actually split. A
    # third provider cannot arrive without choosing a side — the match in
    # `measures_the_field` has no fallback branch, so mypy refuses it — and a mapping
    # collapsed onto one side fails here rather than in a gate run six months on.
    answered = {
        provider: measures_the_field(ModelConfig(provider=provider, name="whichever"))
        for provider in Provider
    }
    assert set(answered) == set(Provider)
    assert any(answered.values()), "no provider measures the field: nothing can retire"
    assert not all(answered.values()), "every provider measures the field: #43 is back"


# --- Seam four: the entry point, on two models -------------------------------


def test_the_entry_point_re_runs_the_library_on_a_second_model_and_records_both(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The whole library against all three reference agents, twice, and compared.

    Driven end to end on two stub models with the suite's own stand-ins for the
    bench's two instruments, so it reaches no model and needs no terminal. The three
    consent statements and the interrupt are answered the way the calibration
    fixture answers them — a run that skipped them would exercise a path no
    operator's run takes (ADR-0007).

    Against a **copy** of the library, because a run that wrote to the real one
    would be a test that edits the bench to prove itself.
    """
    monkeypatch.setattr("scripts.swap.attest", lambda identity: BENCH_ATTESTATION)
    monkeypatch.setattr("scripts.swap.terminal_approval", lambda identity: CONFIRMING)
    monkeypatch.setattr("scripts.swap.completion_for", _adjudicator_stand_in)
    monkeypatch.setattr("scripts.swap.attacker_completion_for", _attacker_stand_in)
    cases = tmp_path / "cases"
    shutil.copytree(CASES_DIR, cases)

    code = main(
        [
            "--identity",
            BENCH_ATTESTATION.identity,
            "--model",
            FIRST,
            "--second-model",
            SECOND,
            "--adjudicator-model",
            ADJUDICATOR_STAND_IN,
            "--attacker-model",
            ATTACKER_STAND_IN,
            "--cases",
            str(cases),
            "--record",
            str(tmp_path),
        ]
    )
    printed = capsys.readouterr().out

    # Published whatever it shows: the check has no declared pass rule, so the
    # command does not claim one in its exit code (ADR-0003's reason, in reverse).
    assert code == 0

    records = list(tmp_path.glob("swap-*.md"))
    assert records, (
        "the entry point compared two models and left no document behind. Both runs "
        "are recorded or neither is evidence"
    )
    [record] = records
    assert str(record) in printed
    written = record.read_text(encoding="utf-8")

    # Both runs, and the comparison between them.
    assert f"`{FIRST}`" in written and f"`{SECOND}`" in written
    assert "the multi-model validity check" in written
    assert "630 attempts recorded" in written
    assert written.count("gate run — the scored layer") == 2
    # Each run's own block says which model it was made on, on both sides of the
    # document: two unlabelled blocks are two runs a reader cannot tell apart.
    assert written.count(f"on {FIRST}:") == 2 and written.count(f"on {SECOND}:") == 2
    # The model moved and nothing else did: one library version, wherever it is
    # printed. Four printings since ADR-0033 — the two runs, the comparison, and the
    # version the library stands at after the write — and the assertion is that they
    # are one digest rather than that there are three of them. A run that admitted a
    # route would move the last of the four, which is exactly the fact that section
    # exists to state.
    digests = set(re.findall(r"sha256:([0-9a-f]+)", written))
    assert written.count("sha256:") == 4
    assert len(digests) == 1, digests
    # The adaptive half, in its own section and never in the table above it.
    assert "does A_break survive the model swap?" in written
    # The cross-model admission bar, the count ADR-0012 asks for, and the provenance
    # series that ADR asks to be printed on every run beside it.
    assert f"{RejectionKind.CROSS_MODEL}:" in written
    assert "provenance of the live library:" in written
    # And what entered the library, which on this run is nothing: the scripted
    # attacker's routes do not clear the cross-model bar on two stubs, so the section
    # says the library is the library this run was made against (ADR-0033).
    assert "## What entered the library" in written
    assert "no route cleared the cross-model bar" in written
    assert sorted(path.name for path in cases.glob("*.toml")) == sorted(
        path.name for path in CASES_DIR.glob("*.toml")
    )
    # And no payload, on any side of it (ADR-0008).
    for case in load_library(CASES_DIR):
        assert case.script not in written


def test_a_gate_run_holding_the_library_stops_the_write_and_not_the_comparison(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A held library refuses the write by name, and the comparison still stands.

    The half of ADR-0033's lease decision that only the entry point can show. By the
    time the write is attempted both suites have run, the bar has been put to every
    route and the operator has paid — so this is a refusal to *write*, and the
    comparison is measured, printed and recorded either way.

    **Exit zero, because this run had nothing to write.** The scripted attacker's
    routes do not clear the cross-model bar on two stubs, which is the ordinary
    outcome of every run to date; a non-zero code here would report the lease rather
    than the run. The test below is the other case.
    """
    monkeypatch.setattr("scripts.swap.attest", lambda identity: BENCH_ATTESTATION)
    monkeypatch.setattr("scripts.swap.terminal_approval", lambda identity: CONFIRMING)
    monkeypatch.setattr("scripts.swap.completion_for", _adjudicator_stand_in)
    monkeypatch.setattr("scripts.swap.attacker_completion_for", _attacker_stand_in)
    cases = tmp_path / "cases"
    shutil.copytree(CASES_DIR, cases)
    lease = take_the_library(cases, "a gate run, at a terminal")

    try:
        code = main(
            [
                "--identity",
                BENCH_ATTESTATION.identity,
                "--model",
                FIRST,
                "--second-model",
                SECOND,
                "--adjudicator-model",
                ADJUDICATOR_STAND_IN,
                "--attacker-model",
                ATTACKER_STAND_IN,
                "--cases",
                str(cases),
                "--record",
                str(tmp_path),
            ]
        )
    finally:
        lease.release()
    printed = capsys.readouterr().out

    assert code == 0
    assert "a gate run, at a terminal" in printed
    assert "The comparison above stands" in printed
    assert "nothing to write into it" in printed
    # The comparison was made and is recorded, and the document says the write was
    # refused rather than leaving the section out — a run whose write did not happen
    # is a fact about that run and not an absence a reader has to notice.
    [record] = list(tmp_path.glob("swap-*.md"))
    written = record.read_text(encoding="utf-8")
    assert "## The scored comparison" in written
    assert "## What entered the library" in written
    assert "not written — a gate run held this case library" in written


def test_a_route_that_cleared_the_bar_and_was_not_written_is_a_non_zero_exit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    leakage_case: Case,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The exit code that says a route cleared and did not reach the library.

    The bar is stood in for rather than driven, because no route the scripted
    attacker composes clears it on two stub models — which is the fact the test above
    rests on. What is under test here is not the bar but what `main` does with an
    admitted promotion it cannot write: everything measured stands, and the caller is
    told that a case cleared and is not in the library, because a caller that read
    zero would believe one had entered.
    """
    monkeypatch.setattr("scripts.swap.attest", lambda identity: BENCH_ATTESTATION)
    monkeypatch.setattr("scripts.swap.terminal_approval", lambda identity: CONFIRMING)
    monkeypatch.setattr("scripts.swap.completion_for", _adjudicator_stand_in)
    monkeypatch.setattr("scripts.swap.attacker_completion_for", _attacker_stand_in)
    cleared = _an_admitted_promotion(leakage_case)
    monkeypatch.setattr(
        "scripts.swap.cross_model_bar",
        lambda **_: (
            rejections((cleared.outcome,)),
            (cleared,),
            Consultation(
                consulted=(Consulted(proposal=cleared.proposal, answer=None),)
            ),
        ),
    )
    cases = tmp_path / "cases"
    shutil.copytree(CASES_DIR, cases)
    lease = take_the_library(cases, "a gate run, at a terminal")

    try:
        code = main(
            [
                "--identity",
                BENCH_ATTESTATION.identity,
                "--model",
                FIRST,
                "--second-model",
                SECOND,
                "--adjudicator-model",
                ADJUDICATOR_STAND_IN,
                "--attacker-model",
                ATTACKER_STAND_IN,
                "--cases",
                str(cases),
                "--record",
                str(tmp_path),
            ]
        )
    finally:
        lease.release()
    printed = capsys.readouterr().out

    assert code == EXIT_NOT_WRITTEN
    assert "No route entered the library." in printed
    # And the library is untouched, which is the whole of what the lease bought.
    assert sorted(path.name for path in cases.glob("*.toml")) == sorted(
        path.name for path in CASES_DIR.glob("*.toml")
    )


def _an_admitted_promotion(objective: Case) -> Promotion:
    """One proposed route that cleared the cross-model bar, and the case it became.

    Counts rather than a measurement, on `test_promotion.py`'s terms: whether a case
    *would* separate the reference agents is a question about that case, and what is
    under test where this is used is what the entry point does with the answer.
    """
    proposal = proposed_from(
        objective=objective,
        target=a_target("trivial"),
        family=Family(objective.family),
        payload="the probe that actually ran",
        description="a route worth promoting",
    )
    readings = [
        AdmissionReading(model=model, attempts=10, hardened=0, weak=5, trivial=10)
        for model in (FIRST, SECOND)
    ]
    promotion = promote(proposal, readings)
    assert promotion.admitted, "these counts are supposed to clear the bar"
    return promotion


def test_one_model_named_twice_is_refused_before_anything_is_sent(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The refusal that costs nothing. Two runs of one model measure this bench's
    # run-to-run variation, and a check that reported that as a model swap would be
    # publishing a comparison of a model with itself.
    code = main(
        [
            "--identity",
            BENCH_ATTESTATION.identity,
            "--model",
            FIRST,
            "--second-model",
            FIRST,
        ]
    )

    printed = capsys.readouterr().out
    assert code == EXIT_WITHHELD
    assert "Reading one model twice is a repeat and not a swap" in printed
    assert "Nothing was sent" in printed
    # Refused before the attestation, so the operator is never asked to attest to a
    # run that could not have answered the question anyway.
    assert "Attestation" not in printed


def test_the_recorded_document_keeps_the_two_layers_in_two_sections(
    tmp_path: Path,
) -> None:
    # The discipline the gate's own record follows: the scored comparison and the
    # adaptive one are two blocks, because a reader who met `A_break` inside a table
    # of `D` would have met a number that decides nothing where everything decides
    # something (ADR-0010). The provenance series is in the third block, beside the
    # bar it watches (ADR-0012).
    first, second = readings(a_run(*[SEPARATES] * 6), a_run(*[FLAT] * 6))
    written = record_swap(
        swap=compare(first, second),
        adaptive=compare_adaptive(
            _reading(broken_on_trivial=1, turns=1),
            _reading(broken_on_trivial=0, turns=None),
            first_model=FIRST,
            second_model=SECOND,
        ),
        rejected=rejections(()),
        consulted=Consultation(consulted=()),
        entry=Entry(version=EMPTY_LIBRARY),
        directory=tmp_path,
        identity=BENCH_ATTESTATION.identity,
        adjudicator_model=ADJUDICATOR_STAND_IN,
        attacker_model=ATTACKER_STAND_IN,
        runs=[_a_model_run(first), _a_model_run(second)],
        cases=load_library(CASES_DIR),
    ).read_text(encoding="utf-8")

    scored = written.index("## The scored comparison")
    runs = written.index("## The two runs it compares")
    adaptive = written.index("## The adaptive layer, which decides nothing")
    bar = written.index("## The cross-model admission bar")
    library = written.index("## What entered the library")
    assert scored < runs < adaptive < bar < library
    assert "COLLAPSED" in written
    assert "provenance of the live library:" in written
    assert BENCH_ATTESTATION.identity in written


def _a_model_run(
    reading: ModelReading, proposals: Sequence[ProposedRoute] = ()
) -> ModelRun:
    """A model run around a scored reading, with no attempt and the given proposals.

    Enough of one for the writer, which reads the reading and the episodes and
    nothing else, and for the bar, which reads the proposals off the episodes. Built
    rather than measured for the reason `a_run` is: where the document puts a block,
    and which admission runs the bar makes, are not questions two 540-attempt runs
    are needed to answer.
    """
    budget = RunBudget.declare(cases=[], targets=[])
    state = RunState(budget=budget)
    if proposals:
        state.episodes.append(
            AdaptiveEpisode(
                family=Family(proposals[0].case.family),
                target_name=TRIVIAL,
                outcome=EpisodeOutcome.BROKEN,
                turns=1,
                proposals=tuple(proposals),
            )
        )
    return ModelRun(
        reading=reading,
        result=CalibrationResult(
            run_state=state,
            target_runs=(),
            budget=budget,
            approval=ApprovalOutcome(
                budget=budget,
                presented=budget.as_payload(),
                confirmed=True,
                halted=False,
                identity=BENCH_ATTESTATION.identity,
            ),
        ),
    )


def _proposed(case_id: str, *counts: tuple[int, int, int]) -> AdmissionOutcome:
    """One adaptive-discovered proposal, decided on the readings it measured."""
    return decide(
        case_id,
        DiscoveredBy.ADAPTIVE,
        [
            AdmissionReading(
                model=model,
                attempts=30,
                hardened=hardened,
                weak=weak,
                trivial=trivial,
            )
            for model, (hardened, weak, trivial) in zip(
                (FIRST, SECOND), counts, strict=False
            )
        ],
    )


def _reading(broken_on_trivial: int, turns: int | None) -> AdaptiveDiscrimination:
    """An adaptive reading where the attacker broke the trivial agent that often.

    Built from episodes through the same `measure` a run's own block is read off, and
    from `test_adaptive_discrimination`'s grid, so this file compares readings rather
    than inventing a statistic to compare.
    """
    families = list(Family)
    return measure(
        grid(
            trivial={
                family: (turns if position < broken_on_trivial else None)
                for position, family in enumerate(families)
            },
            hardened=dict.fromkeys(families, None),
        ),
        trivial=TRIVIAL,
        hardened=HARDENED,
    )


def _adjudicator_stand_in(spec: str) -> Completion:
    """The judged families' instrument, stubbed.

    Two builders because the entry point calls two, and they return different
    things: prose from the adjudicator, a tool call from the attacker. Two
    settings on purpose (ADR-0011).
    """
    assert spec == ADJUDICATOR_STAND_IN, spec
    return adjudicating(Verdict.SUCCEEDED)


def _attacker_stand_in(spec: str) -> AttackerCompletion:
    """The adaptive layer's attacker, stubbed by the deterministic stand-in."""
    assert spec == ATTACKER_STAND_IN, spec
    return SCRIPTED_ATTACKER
