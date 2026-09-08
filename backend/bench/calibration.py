"""The one calibration entry point. No web layer, and the tests drive this.

Everything in the pre-web scope is reached from here: the case library, the
attestation, the approval interrupt and its budget, registration and the nonce
protocol, the applicability and precondition checks, the attempt, and the verdict.
Ten attempts per case (#4), the judge (`narration.py`) and the gate decision
(`gate.py`, which reads what this returns and decides nothing else) extend this
callable rather than adding a second way in.

`narrator` is the pair that explains what the run finds: for every succeeded
attempt the judge writes the narrative and `suggest_remediation` writes the fix,
and the two records travel on `TargetRun.narrations` (ADR-0030). It defaults to
`None`, which is a run that measured what it measured and explained none of it —
a stated absence rather than an empty result, and what every gate run is.

`precedent` is the long-term memory, and this is the one function in the bench that
holds it as something able to write: the deterministic findings are filed at the end
of the run, once every instrument in it has read (`filing.py`, ADR-0031). The
annotation is the concrete `DurablePrecedents` for that reason, and everything below
here — `_run_target`, the narrative pass, the adaptive layer — takes the read-only
protocol instead, so nothing inside a run can write what the run is still reading.

The order below is the order ADR-0007 requires and is not an implementation
detail: attestation, then the estimate, then the halt, and only then anything that
reaches an endpoint. The approval interrupt sits ahead of registration as well as
ahead of the first attempt, because the nonce echo probe is itself a call on the
operator's endpoint — a run that had already spent something by the time it asked
would be asking about a decision it had partly taken.

`plant_nonce` stands in for the human who edits their target's system prompt when
the bench issues a nonce. A user does that by hand — hence the default of `None`,
which is the production case — and the reference agents have a test-equipment
route for it, so the nonce protocol is exercised on every gate run. It is handed the
run's namespace beside the nonce, and `drop_namespace` drops that namespace when the
run ends however it ends (ADR-0063).

`adjudicator` is the model that decides the two judged families (#9). It defaults
to `None` because a library of deterministic cases needs none, and a run given judged
cases without one is refused before the estimate and before anything reaches an
endpoint, rather than partway through: an attempt nothing can score is the operator's
money spent with no measurement behind it, and a partial suite is void rather than
smaller (ADR-0007).

**A run has two layers, and the second one runs here, last.** Once the fixed suite
has finished against every target, `run_adaptive_layer` attacks the ones that
registered by a route of its own choosing (#16). Nothing it produces is scored: it
records `AdaptiveEpisode`s in a field of their own, spends against its own ceiling,
and reaches the scored side through exactly one edge — `propose_case`, which the
admission gate decides (ADR-0010). `attacker` defaults to the deterministic
stand-in of `adaptive/scripted.py` so that the layer always runs; the entry point
in `scripts/calibrate.py` names a configured model instead, on the same terms as
the adjudicator.
"""

from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final, TypeGuard

from backend.bench.adaptive.attacker import AttackerCompletion
from backend.bench.adaptive.budget import DECLARED_ADAPTIVE_BUDGET, AdaptiveBudget
from backend.bench.adaptive.layer import AttackableTarget, run_adaptive_layer
from backend.bench.adaptive.precedent import (
    DURABLE_PRECEDENT,
    DurablePrecedents,
    PrecedentStore,
)
from backend.bench.adaptive.scripted import SCRIPTED_ATTACKER
from backend.bench.adjudication import Completion, NoAdjudicator
from backend.bench.applicability import SkippedCase, applicable, skipped_cases
from backend.bench.attacker import run_case
from backend.bench.contract import TargetConfig, TargetUnreachable
from backend.bench.evaluator import Verdict
from backend.bench.filing import Filing, file_precedent
from backend.bench.judge import Disagreement, Finding
from backend.bench.library import (
    AnyFamily,
    Case,
    ElectiveFamily,
    Family,
    LibraryVersion,
    Transform,
    VerdictClass,
    one_of_the_six,
)
from backend.bench.measurability import (
    NotMeasurable,
    contradicted_by_the_reply,
    not_measurable_elective_families,
    not_measurable_families,
    runnable,
)
from backend.bench.narration import (
    Narration,
    Narrations,
    NarrativeFailure,
    Narrator,
    disagreements_in,
    findings_in,
    narrate_successes,
)
from backend.bench.nonce import issue_nonce
from backend.bench.planting import (
    DropNamespace as _DropNamespace,
)
from backend.bench.planting import (
    PlantCheck,
    Planter,
    Planting,
    Teardown,
    anonymous_run_id,
    checked,
    namespace_for,
    plant,
    refuse_a_canary_the_run_did_not_issue,
    teardown_all,
)
from backend.bench.planting import (
    drop_namespace as _drop_namespace,
)
from backend.bench.registration import (
    Attestation,
    Registration,
    endpoint_hash,
    register,
)
from backend.bench.rule import DECLARED_RULE, GateRule
from backend.bench.scorer import (
    IN_TRANSFORM_ORDER,
    Rate,
    VariantBreakdown,
    VariantCounts,
)
from backend.bench.selection import EVERY_CONSTRUCTION, AttackSelection
from backend.bench.usage import LayerTotals, UsageLedger
from backend.graph.approval import ApprovalOutcome, Approve, run_under_approval
from backend.graph.budget import Layer, RunBudget
from backend.graph.runstate import Attempt, RunState
from backend.observability import (
    Field,
    Span,
    TracedRun,
    Value,
    disable_inherited_tracing,
    flush,
    traced,
)

PlantNonce = Callable[[TargetConfig, str, str], None]
"""The operator's hand, as a callable: plant this nonce for this target, in this run.

The third argument is the run's namespace, and it is an **argument** rather than a
value the planter was built with, for the reason the shim's hooks take one: a planter
holding a namespace between the plant and the drop is a planter whose drop can run
against a later run's namespace
([ADR-0063](../../docs/adr/0063-one-run-scoped-namespace-dropped-wholesale.md) §1).
"""

DropNamespace = _DropNamespace
"""The other half of `PlantNonce`: drop everything that hand planted, wholesale.

Defined in `planting.py` beside `teardown`, because the two are one contract, and
named here because this is where a caller meets it. `None` for the operator who
plants by hand: a person who pasted a nonce into a system prompt takes it out the
same way, and there is no call the bench can make on their behalf.
"""


@dataclass(frozen=True)
class TargetRun:
    """One target's part of a calibration run. No attempts unless registration
    completed."""

    target: TargetConfig
    registration: Registration
    attempts: tuple[Attempt, ...]
    rule: GateRule
    """The rule the attempts were run under, so the rate carries the confidence
    it was measured at."""

    not_measurable: Mapping[Family, NotMeasurable] = field(default_factory=dict)
    """The families this target could not be measured on, and why.

    A separate field from `rates` rather than a third value inside it, so that a
    consumer reading rates cannot read a refusal as a number. Empty for a target
    that met every precondition its library asked for.
    """

    elective_not_measurable: Mapping[ElectiveFamily, NotMeasurable] = field(
        default_factory=dict
    )
    """The elective families this target could not be measured on, and why.

    A second mapping beside the one above, which is the split ADR-0035 asks for at
    every site keyed by family: `not_measurable` is what `gate.family_rates` reads
    when it decides which of the six were withdrawn, and an elective family in it
    would be an elective family in the gate's reasoning about its own denominator.

    This is where memory poisoning lands against a target that keeps no session
    state, and it is the outcome rather than a rate of zero
    ([ADR-0041](../../docs/adr/0041-the-persistence-canary-is-read-over-two-turns.md)).
    """

    plantings: tuple[Planting, ...] = ()
    """What was put in place before this target was registered, and never counted.

    **The record ADR-0007 asks for, kept beside the attempts and summable into
    none of them.** A `Planting` carries the planting, the record that asked for it
    and the attestation that authorised it, and carries no `Layer`, no `sends` and
    no `Transcript` — so a reporting surface that reached for this tuple would find
    nothing a rate could be denominated on
    ([ADR-0062](../../docs/adr/0062-planting-is-a-pre-run-step-off-every-counter.md)).

    Empty for every target that is a URL: its operator plants by hand and the run
    performed no act of its own, which is a fact and not a missing field.
    """

    not_applicable: tuple[SkippedCase, ...] = ()
    """The cases this target was never sent, because they were not written for it.

    A third field rather than a third value in either of the two above, and the
    reason is the same reason `not_measurable` is not a rate of zero: these are
    three different answers. A rate says what was measured, `not_measurable` says
    the target cannot answer the question, and this says the bench never asked —
    the library has no case for this agent type, which is the bench's gap and not
    the target's (`applicability.py`).

    Per case rather than per family, because a family can have some cases that
    apply and some that do not, and the rate over the ones that ran is a real
    number that a family-level skip would have to overwrite.
    """

    narrations: Narrations = None
    """This target's succeeded attempts explained, or which of the three reasons
    there is nothing here.

    A fourth field beside the three above and, like them, not a fifth value inside
    `rates`: a finding is a verdict *plus* its narrative and a rate is a count of
    verdicts, so a consumer reading one may not reach the other (CONTEXT.md,
    ADR-0030).

    **Four readings, and no two of them are the same fact.** `None` is a run made
    with no narrative instrument — it explained nothing, and reading that as
    *nothing to explain* would report a bench that did not look as a target that
    held. `()` is the two instruments having run against a target that succeeded at
    nothing, which is a measurement. A tuple is every succeeded attempt of the six
    explained. A `NarrativeFailure` is the instruments having run and failed, which
    is none of the other three
    ([ADR-0050](../../docs/adr/0050-a-run-whose-narrative-instruments-broke-is-measured-explained-nowhere-and-signable.md)).
    Same distinction `budget.NOT_PRICED` draws about money and `not_measurable`
    draws about a family, one arm wider.
    """

    def __post_init__(self) -> None:
        # A planting that never went through the read-back, on a record of a run that
        # is over. `plant` makes these before the registration probe and `checked`
        # fills the reading in from what the probe answered, so an `UNCHECKED` one
        # here is a harness that planted and did not look — and the block it reaches
        # in the artefact is the one whose strongest claim has to be earned
        # ([ADR-0064](../../docs/adr/0064-the-harness-reads-its-own-canary-back.md)).
        unchecked = sorted(
            str(performed.plant)
            for performed in self.plantings
            if performed.check is PlantCheck.UNCHECKED
        )
        if unchecked:
            raise ValueError(
                f"the {unchecked} planting(s) of target {self.target.name!r} reached "
                "this record without being checked. The bench generated the value "
                "and planted it, so whether it is in place is a reading this run "
                "takes rather than a declaration it repeats: `planting.checked` is "
                "what takes it, off the registration probe"
            )

        attempted_families = {attempt.family for attempt in self.attempts}
        both = (
            set(self.not_measurable) | set(self.elective_not_measurable)
        ) & attempted_families
        if both:
            raise ValueError(
                f"{sorted(both)} were reported not measurable and also attempted "
                "against this target. Not measurable is a distinct outcome from "
                "pass and from fail, and a family cannot hold two of the three"
            )

        attempted = {attempt.case_id for attempt in self.attempts}
        sent_anyway = sorted(
            skipped.case_id
            for skipped in self.not_applicable
            if skipped.case_id in attempted
        )
        if sent_anyway:
            raise ValueError(
                f"{sent_anyway} were reported as not written for this target and "
                "were also run against it. A case that does not apply is skipped "
                "explicitly, and a skip that spent an attempt is a verdict counted "
                "for a payload the case never claimed would land"
            )

        classes: dict[AnyFamily, set[VerdictClass]] = defaultdict(set)
        for attempt in self.attempts:
            classes[attempt.family].add(attempt.verdict_class)
        mixed = sorted(family for family, seen in classes.items() if len(seen) > 1)
        if mixed:
            raise ValueError(
                f"{mixed} were attempted under both verdict classes. A family is "
                "deterministic or judged, and one whose cases disagree would put a "
                "judged rate in the deterministic section — which is the one place "
                "the two must never meet (ADR-0004)"
            )

        if isinstance(self.narrations, NarrativeFailure):
            # The fourth reading is checked against the run's own attempts for the
            # reason the tuple below is: a count of successes that disagreed with
            # the attempts would be a figure about a population this run did not
            # measure (ADR-0050).
            successes = sum(
                1
                for attempt in self.attempts
                if attempt.verdict is Verdict.SUCCEEDED
                and one_of_the_six(attempt.family)
            )
            if self.narrations.successes != successes:
                raise ValueError(
                    f"the narrative pass reports {self.narrations.successes} "
                    f"success(es) to explain and this run made {successes}. The "
                    "reading says how far the instruments got over this target's "
                    "own successes, and one counted over anything else is not that"
                )
        elif self.narrations is not None:
            explained = sorted(
                narration.finding.case_id for narration in self.narrations
            )
            # The six's successes. An elective family's success reaches no finding
            # at all and says so where the decision is taken
            # (`narration.narrate_successes`, ADR-0035), so counting one here would
            # make every run that requested the tier fail this check for holding the
            # absence it was designed to hold.
            succeeded = sorted(
                attempt.case_id
                for attempt in self.attempts
                if attempt.verdict is Verdict.SUCCEEDED
                and one_of_the_six(attempt.family)
            )
            if explained != succeeded:
                raise ValueError(
                    f"{len(explained)} finding(s) were carried for "
                    f"{len(succeeded)} succeeded attempt(s). A run that explained "
                    "some of its successes reports a subset nobody chose, and one "
                    "that explained an attempt it did not make reports a failure "
                    "that was never measured. Findings are all of them or the "
                    "stated absence of all of them (ADR-0030) — all of them being "
                    "the six's, because the tier's are explained nowhere"
                )

    @property
    def findings(self) -> tuple[Finding, ...] | None:
        """The findings this target run produced, or `None` for a run that produced
        none.

        The record CONTEXT.md names, for the consumers that want it without the
        fix beside it — the precedent writer, and a report. `None` carries through
        from a `narrations` of `None` rather than flattening to `()`, because those
        two are the two facts that field exists to keep apart: `()` here is a
        measured *nothing to file*.

        **The fourth reading arrives here as `None`, and that is not the collapse
        ADR-0050 exists against.** A projection into `Finding` has nothing to say
        about why there is no `Finding`, and the reason is one attribute away on the
        same object; what a caller must never get is a `()` it could file or print
        as *this target succeeded at nothing*. Carrying the record through the two
        projections instead was considered and rejected in ADR-0050.
        """
        return findings_in(self.narrations) if _explained(self.narrations) else None

    @property
    def disagreements(self) -> tuple[Disagreement, ...] | None:
        """The review queue for this target: the transcripts the two instruments
        read differently, or `None` for a run with no findings to read it over.

        Read off the findings rather than accumulated during the run, so it cannot
        disagree with them, and it decides nothing: the verdict stands, the reading
        stands, and a human is handed the list (ADR-0004, PLAN §3).
        """
        return (
            disagreements_in(self.narrations) if _explained(self.narrations) else None
        )

    @property
    def rates(self) -> dict[Family, Rate]:
        """This target's failure rate for each family it was attempted on.

        Per family and never pooled across them: the six families measure six
        different failures, an average over them is not a quantity, and a family
        with no attempts is absent rather than reported as a rate of zero. No
        attempts is not a failure rate of zero — a target the bench never
        measured has to stay distinguishable from one that resisted everything.

        Both classes appear here, because `D` and monotonicity are read per family
        and are read the same way whichever route the verdict took. What is
        reported to a reader is the two sections below, never this mapping: they
        carry different evidentiary strength, and the deterministic families carry
        the report's weight (ADR-0004).
        """
        return self._rates(self.attempts)

    @property
    def deterministic_rates(self) -> dict[Family, Rate]:
        """The families whose verdicts came from a success condition.

        The report's own section, and the one that carries its weight: every
        verdict behind these rates is re-derivable by a reader holding the case
        record and the transcript (ADR-0004).
        """
        return self._rates_under(VerdictClass.DETERMINISTIC)

    @property
    def judged_rates(self) -> dict[Family, Rate]:
        """The families whose verdicts came from adjudication.

        Reported apart from the deterministic families and never added to them.
        There is deliberately no property here that returns the two together as one
        collection, and none that totals either: a judged rate carries a wider
        stated limit and a κ figure beside it (#11), and a figure combining one with
        a deterministic rate would be a number whose evidentiary strength nobody
        could state. That is the same prohibition ADR-0005 puts on a composite
        score, applied one level down.
        """
        return self._rates_under(VerdictClass.JUDGED)

    def _rates_under(self, verdict_class: VerdictClass) -> dict[Family, Rate]:
        """The rates of the families decided by one route.

        Selected on `Attempt.verdict_class`, which was copied off the case record
        when the attempt was made — never on the family name (spec story 18).
        """
        return self._rates(
            attempt
            for attempt in self.attempts
            if attempt.verdict_class is verdict_class
        )

    @property
    def elective_rates(self) -> dict[ElectiveFamily, Rate]:
        """This target's failure rate for each **elective** family it was attempted on.

        A second mapping beside `rates` and never a wider key on it, which is the
        split ADR-0035 asks for at every site that groups attempts by family
        ([ADR-0035](../../docs/adr/0035-the-elective-family-tier-is-never-gate-deciding.md)).
        `gate.family_rates`
        reads `rates`, so a mapping keyed over both tiers would be an elective family
        in the gate's denominator — and the arithmetic below is the same arithmetic,
        because *selectable is not ungated*.

        There is deliberately no property returning the two together, on the terms
        `judged_rates` states: a collection holding both would be the one place a
        figure that decides nothing could be read beside figures that decide.

        **Pooled from the breakdown below, exactly as the six's are** (ADR-0055,
        ADR-0088). Two independent walks over the same attempts would be two figures
        that could drift, and `assembler.ElectiveEntry` would then be refusing a
        breakdown this module had already built.
        """
        return {
            family: breakdown.pooled(self.rule)
            for family, breakdown in self.elective_variant_counts.items()
        }

    @property
    def elective_variant_counts(self) -> dict[ElectiveFamily, VariantBreakdown]:
        """Each elective family's attempts split by the transform that made them.

        The counts that take the tier's rate apart again, keyed as `elective_rates` is
        and never in the same mapping as the six's — the split ADR-0035 §2 asks for at
        every site that groups attempts by family.

        Every record in the tier is `plain` today, so every breakdown here holds one
        line. It is built and printed anyway rather than assumed: a family that grows
        a variant grows a second line here with no further edit, and the signed
        document may not be the surface that says less than the payload it is a view
        of (ADR-0055).
        """
        return {
            family: breakdown
            for family, breakdown in self._split(self.attempts).items()
            if isinstance(family, ElectiveFamily)
        }

    @property
    def variant_counts(self) -> dict[Family, VariantBreakdown]:
        """Each family's attempts split by the transform that made them.

        The counts that take this target's per-family rate apart again, keyed exactly
        as `rates` is: one family, one breakdown, and no container holding two
        families' variants together — the breakdown sits one level *below* a rate, so
        ADR-0005's refusal to reach across families reaches it too.

        A family absent from `rates` is absent here, and for the same reason: no
        attempts is not a failure rate of zero, and an empty breakdown printed for a
        family the run never touched would be a denominator nobody measured.

        **Counts and no rate.** Pooling them is `VariantBreakdown.pooled`, and it
        returns the same figure `rates` already does — asserted rather than assumed,
        by `FamilyEntry` and by `verification.py`
        ([ADR-0055](../../docs/adr/0055-a-family-pools-its-variants-and-publishes-the-counts.md)).
        """
        return self._variants(self.attempts)

    @property
    def deterministic_variant_counts(self) -> dict[Family, VariantBreakdown]:
        """The variant counts of the families decided by a success condition.

        Split by verdict class on the same terms as `deterministic_rates`, because a
        breakdown printed beside a rate has to be the breakdown *of* that rate: a
        collection over both routes would put counts under a rate they are not the
        denominator of the moment a family holds cases of both classes.
        """
        return self._variants_under(VerdictClass.DETERMINISTIC)

    @property
    def judged_variant_counts(self) -> dict[Family, VariantBreakdown]:
        """The variant counts of the families decided by adjudication."""
        return self._variants_under(VerdictClass.JUDGED)

    def _variants_under(
        self, verdict_class: VerdictClass
    ) -> dict[Family, VariantBreakdown]:
        """The variant counts of the families decided by one route."""
        return self._variants(
            attempt
            for attempt in self.attempts
            if attempt.verdict_class is verdict_class
        )

    def _variants(self, attempts: Iterable[Attempt]) -> dict[Family, VariantBreakdown]:
        """The six's breakdowns, off the one walk below.

        The narrowing is here and not in `_split`, which is the shape ADR-0035 §2
        asks for: one walk so the two tiers are counted the same way and cannot
        drift, and two projections so the containers stay parted by the type. What
        `gate.family_rates` reads is what this returns.
        """
        return {
            family: breakdown
            for family, breakdown in self._split(attempts).items()
            if isinstance(family, Family)
        }

    def _split(self, attempts: Iterable[Attempt]) -> dict[AnyFamily, VariantBreakdown]:
        """Group attempts by family and then by transform. The one place they split.

        The inner order is `IN_TRANSFORM_ORDER` — the enumeration's, so `PLAIN` comes
        first and two targets' breakdowns line up entry for entry — and never the
        order the run happened to attempt in.

        Over **both** tiers, and the projections above are what keep them apart: an
        elective attempt is an attempt in CONTEXT.md's sense, counted ten per case
        into one denominator, and a second implementation of this counting for the
        tier is how *held to the same bar* would stop being a property (ADR-0035 §3,
        ADR-0088).
        """
        split: dict[AnyFamily, dict[Transform, list[Attempt]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for family, grouped in _by_family(attempts).items():
            for attempt in grouped:
                split[family][attempt.transform].append(attempt)
        return {
            family: VariantBreakdown(
                tuple(
                    VariantCounts(
                        transform=transform,
                        successes=sum(
                            1 for a in made if a.verdict is Verdict.SUCCEEDED
                        ),
                        attempts=len(made),
                    )
                    for transform in IN_TRANSFORM_ORDER
                    if (made := by_transform.get(transform))
                )
            )
            for family, by_transform in split.items()
        }

    def _rates(self, attempts: Iterable[Attempt]) -> dict[Family, Rate]:
        """Pool each family's variant counts. The one place one of the six's rate is
        computed.

        **Derived from the breakdown rather than counted beside it**, which is what
        makes *the rate is these counts pooled* true by construction and not by
        assertion: two independent walks over the same attempts would be two figures
        that could drift, and `FamilyEntry` would then be refusing an artefact this
        module had already built
        ([ADR-0055](../../docs/adr/0055-a-family-pools-its-variants-and-publishes-the-counts.md)).
        `accounts_for` still guards the two types that carry both, because they can be
        constructed by callers this method never sees.
        """
        return {
            family: breakdown.pooled(self.rule)
            for family, breakdown in self._variants(attempts).items()
        }


def _explained(narrations: Narrations) -> TypeGuard[tuple[Narration, ...]]:
    """Whether this reading is findings, as opposed to one of the three reasons
    there are none.

    `()` is on this side of the line: instruments that ran over a target with
    nothing to explain produced findings, all zero of them, and that is a
    measurement a caller may file and print (ADR-0030). `None` and a
    `NarrativeFailure` are on the other side, and they are two different reasons
    for the same emptiness.

    A `TypeGuard` here rather than an `isinstance` at each of the two properties
    below, so that a fifth reading is one edit in this function and mypy names
    every reader that has to be told about it, instead of a fifth arm somebody has
    to remember to write twice.
    """
    return isinstance(narrations, tuple)


def _by_family(attempts: Iterable[Attempt]) -> dict[AnyFamily, list[Attempt]]:
    """These attempts grouped by the family each was made in, over both tiers.

    One walk feeding two mappings, so the six's rates and the tier's are counted the
    same way and cannot drift — which is what makes *held to the same bar* a property
    rather than a coincidence (ADR-0035). What differs is only which container each
    answer is allowed into, and that is the type.
    """
    counted: dict[AnyFamily, list[Attempt]] = defaultdict(list)
    for attempt in attempts:
        counted[attempt.family].append(attempt)
    return counted


@dataclass(frozen=True)
class CalibrationResult:
    run_state: RunState
    target_runs: tuple[TargetRun, ...]
    budget: RunBudget
    approval: ApprovalOutcome
    """What the operator was shown and what they answered. Carried on the result
    because a run's cost and its consent are part of its record, not preamble to
    it — and because an empty `target_runs` means two different things depending
    on which way this went."""

    usage: UsageLedger = field(default_factory=UsageLedger)
    """What the provider said about every model call this run's instruments made.

    On the result, so the figures a trace carries are figures the *run* holds: a
    token count whose only reader was the sink would be the one thing ADR-0026
    forbids, arrived at from the other side. Empty for a run whose instruments were
    built with no sink — which is a run that reported no tokens and never a run that
    consumed none (`usage.NO_TOKEN_COUNTS_REPORTED`).

    Per layer and never summed, because `UsageLedger` offers no way to sum it
    (ADR-0010).
    """

    namespace: str = ""
    """The one namespace this run planted into, whether or not anything was planted.

    Derived from the run id and computed once, at the top of `run_calibration`, so
    the value a hook was given and the value `teardown()` was given are the same
    value
    ([ADR-0063](../../docs/adr/0063-one-run-scoped-namespace-dropped-wholesale.md)).
    Empty only on a result some other code constructed; every run this module
    produces holds one.
    """

    teardowns: tuple[Teardown, ...] = ()
    """What became of that namespace, per object this run was handed.

    Empty for a run with no planter, which is every endpoint run: nothing was planted,
    so nothing had to be dropped, and `NOTHING_WAS_PLANTED` is the sentence a report
    prints for it. A `Teardown` that failed is on the result rather than raised,
    because the run's numbers are unaffected and the failure is still the operator's
    to act on (ADR-0063 §3).
    """

    filing: Filing = field(default_factory=Filing)
    """What this run contributed to the long-term memory, and what it withheld.

    On the result because a judged family filing nothing is a statement rather
    than an absence: the run says what it refused rather than swallowing the
    refusal (`filing.py`, ADR-0031). Empty for a run that produced no finding to
    file, which every gate run is — and *why* it produced none is answered on
    `TargetRun.narrations` rather than restated here.
    """


@dataclass(frozen=True)
class _UsageFields:
    """Which fields one layer's tokens and cost are emitted under.

    A record per layer rather than a name composed from `Layer` at the call site:
    a field name assembled at runtime is a field the allowlist cannot be read off,
    and the whole of `Field` being greppable is what makes a diff of it reviewable
    (ADR-0026).
    """

    input_tokens: Field
    output_tokens: Field
    reasoning_tokens: Field
    provider_cost: Field
    calls_without_tokens: Field
    calls_without_cost: Field


_USAGE_FIELDS: Final[Mapping[Layer, _UsageFields]] = {
    Layer.SCORED: _UsageFields(
        input_tokens=Field.INPUT_TOKENS_SCORED,
        output_tokens=Field.OUTPUT_TOKENS_SCORED,
        reasoning_tokens=Field.REASONING_TOKENS_SCORED,
        provider_cost=Field.PROVIDER_COST_SCORED,
        calls_without_tokens=Field.CALLS_WITHOUT_TOKENS_SCORED,
        calls_without_cost=Field.CALLS_WITHOUT_COST_SCORED,
    ),
    Layer.ADAPTIVE: _UsageFields(
        input_tokens=Field.INPUT_TOKENS_ADAPTIVE,
        output_tokens=Field.OUTPUT_TOKENS_ADAPTIVE,
        reasoning_tokens=Field.REASONING_TOKENS_ADAPTIVE,
        provider_cost=Field.PROVIDER_COST_ADAPTIVE,
        calls_without_tokens=Field.CALLS_WITHOUT_TOKENS_ADAPTIVE,
        calls_without_cost=Field.CALLS_WITHOUT_COST_ADAPTIVE,
    ),
}
"""One layer, one set of fields, and no entry that spans both.

There is no `total` key here and no function that would build one. A blended token
figure is the arithmetic ADR-0010 exists to prevent, and the enforcement is the
same as `UsageLedger`'s: the shape that would hold it does not exist, so a caller
who wanted one would have to write the sum in the open.
"""


def _tokens_and_cost(layer: Layer, ledger: UsageLedger) -> dict[Field, Value]:
    """One layer's figures as span attributes, and nothing where it has none.

    **Absent rather than zero**, which is what ADR-0026 said about these fields
    when there was no source for them and is still the right reading now there is:
    a layer whose providers reported no counts did not consume nothing, and a `0`
    on a span is the figure a reader is least able to question.

    The shortfall counts travel with the totals and only with them
    (`usage.LayerTotals`): a sum over the calls that reported something understates
    a layer where some call reported nothing, and a reader who cannot see how many
    calls are missing from it cannot tell an understatement from a fact. A layer
    that reported nothing therefore emits no shortfall either — zero missing out of
    zero is not a statement about a total that is not there.

    The cost goes on as a string. `Decimal` is not a span `Value`, and `float` is
    the one conversion this figure may not take: a cost the bench records has to be
    the cost the provider named, and `float("0.0000123")` is a binary expansion of
    it (`usage._reported_decimal`).
    """
    totals: LayerTotals = ledger.totals_in(layer)
    names = _USAGE_FIELDS[layer]
    emitted: dict[Field, Value] = {}
    if totals.input_tokens is not None:
        emitted[names.input_tokens] = totals.input_tokens
    if totals.output_tokens is not None:
        emitted[names.output_tokens] = totals.output_tokens
    if totals.reasoning_tokens is not None:
        emitted[names.reasoning_tokens] = totals.reasoning_tokens
    if totals.input_tokens is not None or totals.output_tokens is not None:
        emitted[names.calls_without_tokens] = (
            totals.calls - totals.calls_reporting_tokens
        )
    if totals.provider_cost is not None:
        emitted[names.provider_cost] = str(totals.provider_cost)
        emitted[names.calls_without_cost] = totals.calls - totals.calls_reporting_cost
    return emitted


def run_calibration(
    cases: Sequence[Case],
    targets: Sequence[TargetConfig],
    attestation: Attestation,
    plant_nonce: PlantNonce | None = None,
    approve: Approve | None = None,
    adjudicator: Completion | None = None,
    narrator: Narrator | None = None,
    attacker: AttackerCompletion = SCRIPTED_ATTACKER,
    precedent: DurablePrecedents = DURABLE_PRECEDENT,
    rule: GateRule = DECLARED_RULE,
    adaptive: AdaptiveBudget = DECLARED_ADAPTIVE_BUDGET,
    selection: AttackSelection = EVERY_CONSTRUCTION,
    budget: RunBudget | None = None,
    run_state: RunState | None = None,
    usage: UsageLedger | None = None,
    planted_nonces: Mapping[str, str] | None = None,
    planters: Mapping[str, Planter] | None = None,
    drop_namespace: DropNamespace | None = None,
    proof_waived: bool = False,
    trace: TracedRun | None = None,
    thread_id: str | None = None,
) -> CalibrationResult:
    """Run the given cases against the given targets and return what was measured.

    Nothing reaches a target until the estimate has been presented and confirmed.
    With no `approve`, the run halts at the interrupt and returns having spent
    nothing — which is the correct behaviour rather than a limitation.

    `budget` is for a ceiling that was declared earlier: at 6b the estimate is
    presented and confirmed in one request and the suite runs in another, and the
    run has to be held to the ceiling the operator actually saw rather than to one
    recomputed later against whatever the library holds by then. It defaults to
    being declared from these inputs, which is the case where the two cannot
    differ.

    `run_state` is the same argument one level down. A run started over HTTP is
    watched while it happens — position, findings so far, calls spent per layer —
    and the only record that holds any of that is this one, so the caller has to be
    able to hand in the state it will read rather than be given it back when the
    run is over. It must count against the same ceiling the run is held to, and a
    state that counts against another one is refused: a run whose counter and whose
    limit disagree is a run with no limit.

    `usage` is the ledger this run's instruments were built to report into, and it
    is the caller's argument for the same reason `budget` is one: the sink an
    instrument records through is fixed when the client is built
    (`completion_for(..., usage=...)`), and that happens before the run exists. So
    the caller that built the instruments is the only thing that could have bound
    them, and it hands in the ledger they were bound to. It defaults to a fresh
    empty one — a run whose instruments keep no usage holds a ledger that reported
    nothing, which is a fact and not a missing field, and the trace says so by
    emitting no token figure rather than a zero.

    **A ledger that already holds calls is refused.** One ledger per run, and the
    failure it guards is the one that matters: a caller reusing a ledger across two
    runs would put the first run's tokens in the second run's trace, and a figure
    on the wrong run is worse than no figure at all. It is checked here because this
    is the one place that knows a run is starting.

    `planted_nonces` is for a target whose nonce was issued before the run began.
    The bench issues the value and the operator plants it by hand, and over HTTP
    those happen in an earlier request — so a run that issued a fresh one here
    would check for a value nobody has planted and refuse every registration. Empty
    for the terminal path, where the run issues its own and `plant_nonce` puts it
    in place.

    `planters` is the object a served callback target is planted through, keyed by
    the target's name. `serve_callback` yields a plain `TargetConfig` and the caller
    keeps the callback (ADR-0059), so the caller is the only thing that can hand the
    hooks over — and it hands over the object rather than a function, because which
    hooks it has is already recorded on `TargetConfig.plants`. Empty for an endpoint
    run: a URL target does not answer for its own plantings and its operator plants
    by hand, exactly where ADR-0024 left that.

    `drop_namespace` is `plant_nonce`'s other half, for the caller whose planting
    equipment is reachable: the reference agents' app holds what a run planted under
    that run's namespace and drops it wholesale when asked. Called from the same
    `finally` the shim teardowns are, so the test equipment is cleaned up on exactly
    the exit paths a user's store is
    ([ADR-0063](../../docs/adr/0063-one-run-scoped-namespace-dropped-wholesale.md)
    §5). `None` for the operator who plants by hand.

    `proof_waived` is the operator declaring that the run may start without the echo
    (ADR-0007, amended). It reaches `register` and changes one thing there: whether a
    missing echo stops the run. The probe is still sent and what came back is still
    recorded, so a target that echoes anyway is recorded as having proved control.

    `trace` is the run's identity and its declared instruments, for the sink — the
    run id a record holds and the three model identifiers this function is given as
    opaque callables and cannot read (`backend/observability.py`). `None` traces the
    run without an id, which joins to nothing and is deliberately still a trace: every
    entry point in this repository passes one — the API from its run record, the five
    scripts from `console.traced_run` — so the anonymous case is a caller holding no
    record, which in practice is this suite. Dropping the trace instead would make a
    forgotten argument look like a sink that is down. Nothing about
    the run changes either way: the sink is not consulted, no figure comes back from
    it, and a sink that is down or absent is a run that completes normally
    (ADR-0026).

    **The inherited tracers are turned off here**, at the top of the one entry point,
    ahead of the first LangGraph invocation and long ahead of the first call to an
    endpoint. One environment variable would otherwise activate a callback tracer
    that sends payloads and replies verbatim, and a guard that works only because
    nobody set the variable is not a guard. Which variables those are is
    `observability.INHERITED_TRACING_VARIABLES` and is not restated here.
    """
    disable_inherited_tracing()
    unscorable = [
        case.id for case in cases if case.verdict_class is VerdictClass.JUDGED
    ]
    if unscorable and adjudicator is None:
        # Before the estimate and before the attestation, because this is the one
        # failure the operator should never pay to discover.
        raise NoAdjudicator(unscorable)

    # The schedules the operator selected, carried onto the budget the layer spends.
    # Through `under`, which is the one join, and here rather than at the layer call
    # below so that the ceiling `RunBudget.declare` prices and the episodes the layer
    # opens are read off one answer: a layer running under both schedules against a
    # ceiling priced for one is ADR-0007's guarantee enforced against the wrong figure
    # (ADR-0096). A gate run passes no selection and gets the default, which is the
    # line the reference agents were gated under (ADR-0023).
    adaptive = adaptive.under(selection.schedules)
    declared = budget or RunBudget.declare(
        cases=cases, targets=targets, rule=rule, adaptive=adaptive, selection=selection
    )
    ledger = usage if usage is not None else UsageLedger()
    if any(ledger.recorded_in(layer) for layer in Layer) or ledger.untagged():
        raise ValueError(
            "the ledger handed in already holds model calls, so it is some other "
            "run's. One ledger per run: a reused one would report the first run's "
            "tokens under the second run's id, and a figure filed against the "
            "wrong run is worse than an absent one (ADR-0026)"
        )
    state = run_state or RunState(budget=declared, library=LibraryVersion.of(cases))
    if state.budget != declared:
        raise ValueError(
            "the run state handed in counts against a different ceiling than the "
            "one this run is held to. A counter and a limit that disagree are a "
            "run with no limit (ADR-0007)"
        )
    target_runs: list[TargetRun] = []
    filing = Filing()
    # One namespace per run, derived from the run's own id and computed once here, so
    # that the value every plant is given and the value every teardown is given are
    # the same value and neither is stored on a shim in between (ADR-0063 §1).
    namespace = namespace_for(trace.id if trace is not None else anonymous_run_id())
    teardowns: tuple[Teardown, ...] = ()

    def run_suite() -> None:
        nonlocal filing
        for target in targets:
            target_runs.append(
                _run_target(
                    target=target,
                    cases=cases,
                    attestation=attestation,
                    run_state=state,
                    plant_nonce=plant_nonce,
                    adjudicator=adjudicator,
                    narrator=narrator,
                    precedent=precedent,
                    rule=rule,
                    planted=(planted_nonces or {}).get(target.name),
                    planter=(planters or {}).get(target.name),
                    namespace=namespace,
                    proof_waived=proof_waived,
                )
            )
        # And only then the second layer, on every target that registered. After
        # the whole suite rather than after each target's own: the ordering
        # ADR-0010 requires is per target, and running the layer here satisfies it
        # for all of them while leaving target order free to be randomised per
        # family, which ADR-0011 requires and a per-target interleaving would not
        # allow.
        #
        # And not at all when the operator switched the layer off. Guarded here rather
        # than by handing the layer an empty list, because *the layer did not run* and
        # *the layer ran and found no target* are two different facts and the second
        # one is what an empty list says (ADR-0058). The estimate the operator
        # confirmed already said nothing would reach the endpoint from it and the
        # ceiling is nothing, so a call from here would be refused at the counter in
        # any case — this line is the statement, and the counter is the enforcement.
        if selection.adaptive:
            run_adaptive_layer(
                attackable=[
                    AttackableTarget(
                        target=completed.target,
                        canary=completed.registration.nonce,
                        # What the scored layer learned from this target's own replies.
                        # This layer applies the declared preconditions, so
                        # a declaration the endpoint contradicted has to be
                        # carried across rather than re-derived.
                        withdrawn=frozenset(completed.not_measurable),
                    )
                    for completed in target_runs
                    if completed.registration.complete
                ],
                cases=cases,
                run_state=state,
                attacker=attacker,
                budget=adaptive,
                precedent=precedent,
            )
        # And last of all, the one write. Here rather than beside each target's
        # narration, so that **nothing in this run reads what this run filed**:
        # `suggest_remediation` has run for every target and the adaptive layer's
        # `retrieve_precedent` has answered every episode, so the store every
        # instrument saw is the store as it stood when the run began. Filing per
        # target instead would make target *n*'s narrations precedent for target
        # *n+1*'s fix, which is a corpus that depends on the order targets were
        # run in — and would put this run's scored findings in front of this run's
        # own attacker, whose `A_break` is then a reading about the attacker plus
        # its own run's hint (ADR-0031, ADR-0019, `seed_precedent.py`).
        filing = file_precedent(
            [
                narration
                for completed in target_runs
                if _explained(completed.narrations)
                for narration in completed.narrations
            ],
            precedent,
        )

    try:
        with traced(Span.RUN, trace.fields() if trace is not None else None) as span:
            try:
                approval = run_under_approval(
                    declared, run_suite, approve, thread_id=thread_id
                )
            finally:
                # In a `finally` because the figures are most wanted on the run that
                # did not finish: a suite that stopped on a transport failure is one
                # whose calls spent per layer say how far it got. Read off the run
                # state, which is the authority for them, and never back out of the
                # sink (ADR-0026).
                span.record(
                    {
                        Field.CALLS_SCORED: state.spent_in(Layer.SCORED),
                        Field.CALLS_ADAPTIVE: state.spent_in(Layer.ADAPTIVE),
                        # Tokens and cost from the ledger, in two separate readings
                        # and merged nowhere: `totals_in` is the only reading
                        # `UsageLedger` offers and there is no `totals()` to be
                        # tempted by (ADR-0010, #9). A layer whose providers
                        # reported nothing contributes no key here at all.
                        **_tokens_and_cost(Layer.SCORED, ledger),
                        **_tokens_and_cost(Layer.ADAPTIVE, ledger),
                    }
                )
    finally:
        # **The cleanup, on every exit path there is**, and the list is the point: a
        # clean finish, a budget breach that aborted mid-run, a `TargetUnreachable`
        # that outlived the retry policy, a `PlantingFailed` that stopped the run
        # before its first attempt, an unhandled exception, a cancellation, and the
        # approval checkpoint being declined — which reaches here having planted
        # nothing and drops a namespace that was never created, because a wholesale
        # drop of nothing is a shim author's no-op and a special case here would be a
        # branch nobody can test (ADR-0028, ADR-0063 §2).
        #
        # A `finally` on the run and not a line at the end of the happy path: the
        # runs that end badly are exactly the runs that leave somebody's store
        # holding what this bench put in it.
        teardowns = teardown_all(planters or {}, namespace)
        if drop_namespace is not None:
            teardowns += (_drop_namespace(drop_namespace, namespace, target_name=None),)
        # Once the root span is closed and not before, so what is pushed is a whole
        # trace. In a `finally` for the same reason the figures above are: a run that
        # stopped on a transport failure is the run whose trace is worth having, and
        # a flush the exception jumped over would leave it in a buffer that dies with
        # the process. Best effort and short.
        flush()

    return CalibrationResult(
        run_state=state,
        target_runs=tuple(target_runs),
        budget=declared,
        approval=approval,
        filing=filing,
        usage=ledger,
        namespace=namespace,
        teardowns=teardowns,
    )


def _run_target(
    target: TargetConfig,
    cases: Sequence[Case],
    attestation: Attestation,
    run_state: RunState,
    plant_nonce: PlantNonce | None,
    adjudicator: Completion | None,
    narrator: Narrator | None,
    precedent: PrecedentStore,
    rule: GateRule,
    planted: str | None,
    namespace: str,
    planter: Planter | None = None,
    proof_waived: bool = False,
) -> TargetRun:
    """Register one target, then run the cases that apply to it if it registered.

    `planted` is the nonce this target already carries, for the caller that issued
    one before the run started. A fresh nonce is issued when there is none, which
    is every terminal run: one value, planted by whoever can edit the target's
    configuration, and checked by the probe below either way.

    `planter` is the object this target's plantings are performed on, for a served
    callback that declared any (ADR-0061). `None` for every URL target, and for a
    served one that declared none — in both of those `plant` performs nothing.

    `namespace` is the run's, not this target's: one run, one namespace, dropped
    wholesale by `run_calibration`'s `finally`
    ([ADR-0063](../../docs/adr/0063-one-run-scoped-namespace-dropped-wholesale.md)).
    It is passed down rather than derived here so that a second target cannot plant
    into a namespace the first target's teardown will not reach.
    """
    # `issue_nonce` is the only source of this value on a surface where the bench
    # plants it, and neither of the two ways a caller can supply one reaches such a
    # target: a canary the caller supplied is one the caller could also have put in a
    # payload, and one value with two provenances is two values (ADR-0064 §1).
    refuse_a_canary_the_run_did_not_issue(
        target, planted=planted, hand_planter=plant_nonce
    )
    nonce = planted or issue_nonce()
    if plant_nonce is not None:
        plant_nonce(target, nonce, namespace)
    # Applicability first, and here rather than after registration, because the plant
    # below is performed for the cases that will actually be attempted: planting an
    # artefact for a case this target's agent type was never written for would be an
    # act on somebody's content store that nothing in the run is going to read.
    written_for = applicable(cases, target)
    # And then the plant, in the one place ADR-0007's ordering puts it: after the
    # attestation, after the nonce is issued, and **before the registration probe**.
    # Before, because the probe is the first thing that can carry evidence the plant
    # landed (#87), and because the attestation is what authorises an act on the
    # operator's own systems and a plant is already one.
    #
    # `run_state` is deliberately not passed and there is no parameter for it. A plant
    # is neither an attempt nor a send, so nothing here may reach a counter, and the
    # signature is what carries that rather than a reviewer remembering it
    # ([ADR-0062](../../docs/adr/0062-planting-is-a-pre-run-step-off-every-counter.md)).
    # A `PlantingFailed` propagates: it stops the run before the first attempt, with
    # no family measured, which is a different reading from a family withdrawn for a
    # hook that does not exist.
    measurable_here = runnable(written_for, target)
    plantings = plant(
        planter,
        target,
        measurable_here,
        canary=nonce,
        namespace=namespace,
        attestation=attestation,
    )
    # The hash and never the url, through the one function that derives it, and
    # recorded before the probe rather than after it: a registration that failed is
    # the misfire a reader most needs to place, and it has no record to read the
    # hash off (ADR-0007, ADR-0011).
    with traced(
        Span.REGISTER, {Field.ENDPOINT_HASH: endpoint_hash(target.url)}
    ) as span:
        try:
            registration = register(target, nonce, attestation, run_state, proof_waived)
        except TargetUnreachable as unreachable:
            # The class of the failure, off the named outcome. Never the exception's
            # message, which contains the url.
            span.errored(unreachable.failure)
            raise

    # Two filters, in this order, and both ahead of the first attempt. Applicability
    # is read above, before the plant; preconditions gate measurability and never
    # scoring, so a case this target cannot answer is skipped before an attempt is
    # spent on it, and the families left with nothing to run report not measurable
    # rather than a rate (ADR-0004).
    #
    # Three filters now, and the third is the endpoint's own answer. Tool-call
    # visibility is the operator's declaration and there is nothing to check it
    # against at registration — nothing has been sent yet — so it is checked against
    # the first thing that comes back. A declaration the probe contradicts withdraws
    # the families that depend on it *before* an attempt is spent, so the run finishes
    # and signs a report over what could be measured rather than stopping at the first
    # trace-dependent verdict with nothing to read (ADR-0004).
    # The read-back, and the reason the plant is ahead of the probe. The value this
    # run generated went into the target through its own hook, and the probe is where
    # the same value either comes back or does not — one probe, two roles, which is
    # the idiom ADR-0007 already uses for the nonce (ADR-0064 §2). Nothing extra goes
    # on the wire to learn it.
    plantings = checked(plantings, registration)

    contradicted = contradicted_by_the_reply(written_for, target, registration.probe)
    attempts: tuple[Attempt, ...] = ()
    if registration.complete:
        # The nonce that proved control is the canary under the leakage case: one
        # planted value, two roles (ADR-0007). On a run whose proof was waived it is
        # a canary that may be planted nowhere, which is why the caller that waives
        # also drops the leakage family rather than measuring it against a value
        # that is not there (`plan_for`).
        attempts = tuple(
            attempt
            for case in measurable_here
            if case.family not in contradicted
            for attempt in run_case(
                target,
                case,
                canary=nonce,
                run_state=run_state,
                rule=rule,
                adjudicator=adjudicator,
            )
        )

    return TargetRun(
        target=target,
        registration=registration,
        attempts=attempts,
        rule=rule,
        plantings=plantings,
        # Read over the cases written for this target, never over the whole
        # library: a family whose every case was skipped for the agent type has
        # not been found unmeasurable, and reporting it that way would send the
        # operator looking for a capability their target is not missing.
        not_measurable={
            **not_measurable_families(written_for, target),
            **contradicted,
        },
        # The same reading over the tier, into a mapping of its own. Read over the
        # cases written for this target for the reason the line above is.
        elective_not_measurable=not_measurable_elective_families(written_for, target),
        not_applicable=skipped_cases(cases, target),
        # Read over the cases written for this target, for the reason the line
        # above is: a narrative is briefed against the case record the attempt was
        # made from, and a record from outside that set carries a coverage claim
        # this target was never asked about (`narration._record_for`).
        narrations=narrate_successes(attempts, written_for, narrator, precedent),
    )
