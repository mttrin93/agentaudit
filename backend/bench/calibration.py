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
route for it, so the nonce protocol is exercised on every gate run.

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
from typing import Final

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
    Narrator,
    disagreements_in,
    findings_in,
    narrate_successes,
)
from backend.bench.nonce import issue_nonce
from backend.bench.registration import (
    Attestation,
    Registration,
    endpoint_hash,
    register,
)
from backend.bench.rule import DECLARED_RULE, GateRule
from backend.bench.scorer import Rate, failure_rate
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

PlantNonce = Callable[[TargetConfig, str], None]


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

    narrations: tuple[Narration, ...] | None = None
    """This target's succeeded attempts explained, or `None` for a run that
    explained none.

    A fourth field beside the three above and, like them, not a fifth value inside
    `rates`: a finding is a verdict *plus* its narrative and a rate is a count of
    verdicts, so a consumer reading one may not reach the other (CONTEXT.md,
    ADR-0030).

    **`None` and `()` are two facts.** `None` is a run made with no narrative
    instrument — it explained nothing, and reading that as *nothing to explain*
    would report a bench that did not look as a target that held. `()` is the two
    instruments having run against a target that succeeded at nothing, which is a
    measurement. Same distinction `budget.NOT_PRICED` draws about money and
    `not_measurable` draws about a family.
    """

    def __post_init__(self) -> None:
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

        if self.narrations is not None:
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
        """The findings this target run produced, or `None` for a run with no
        narrative instrument.

        The record CONTEXT.md names, for the consumers that want it without the
        fix beside it — the precedent writer, and a report. `None` carries through
        from `narrations` rather than flattening to `()`, because the two are the
        two facts that field exists to keep apart.
        """
        return None if self.narrations is None else findings_in(self.narrations)

    @property
    def disagreements(self) -> tuple[Disagreement, ...] | None:
        """The review queue for this target: the transcripts the two instruments
        read differently, or `None` for a run that ran only one of them.

        Read off the findings rather than accumulated during the run, so it cannot
        disagree with them, and it decides nothing: the verdict stands, the reading
        stands, and a human is handed the list (ADR-0004, PLAN §3).
        """
        return None if self.narrations is None else disagreements_in(self.narrations)

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
        """
        counted = _by_family(self.attempts)
        return {
            family: self._divide(grouped)
            for family, grouped in counted.items()
            if isinstance(family, ElectiveFamily)
        }

    def _rates(self, attempts: Iterable[Attempt]) -> dict[Family, Rate]:
        """Group attempts by family and divide. The one place a rate is computed."""
        return {
            family: self._divide(grouped)
            for family, grouped in _by_family(attempts).items()
            if one_of_the_six(family)
        }

    def _divide(self, grouped: Sequence[Attempt]) -> Rate:
        """Successes over attempts, at the rule these attempts were run under."""
        return failure_rate(
            sum(1 for a in grouped if a.verdict is Verdict.SUCCEEDED),
            len(grouped),
            self.rule,
        )


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
    budget: RunBudget | None = None,
    run_state: RunState | None = None,
    usage: UsageLedger | None = None,
    planted_nonces: Mapping[str, str] | None = None,
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

    declared = budget or RunBudget.declare(
        cases=cases, targets=targets, rule=rule, adaptive=adaptive
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
                    proof_waived=proof_waived,
                )
            )
        # And only then the second layer, on every target that registered. After
        # the whole suite rather than after each target's own: the ordering
        # ADR-0010 requires is per target, and running the layer here satisfies it
        # for all of them while leaving target order free to be randomised per
        # family, which ADR-0011 requires and a per-target interleaving would not
        # allow.
        run_adaptive_layer(
            attackable=[
                AttackableTarget(
                    target=completed.target,
                    canary=completed.registration.nonce,
                    # What the scored layer learned from this target's own replies.
                    # This layer applies the declared preconditions, so a declaration
                    # the endpoint contradicted has to be carried across rather than
                    # re-derived.
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
        # target instead would make target *n*'s findings precedent for target
        # *n+1*'s fix, which is a corpus that depends on the order targets were
        # run in — and would put this run's scored findings in front of this run's
        # own attacker, whose `A_break` is then a reading about the attacker plus
        # its own run's hint (ADR-0031, ADR-0019, `seed_precedent.py`).
        filing = file_precedent(
            [
                finding
                for completed in target_runs
                for finding in completed.findings or ()
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
    proof_waived: bool = False,
) -> TargetRun:
    """Register one target, then run the cases that apply to it if it registered.

    `planted` is the nonce this target already carries, for the caller that issued
    one before the run started. A fresh nonce is issued when there is none, which
    is every terminal run: one value, planted by whoever can edit the target's
    configuration, and checked by the probe below either way.
    """
    nonce = planted or issue_nonce()
    if plant_nonce is not None:
        plant_nonce(target, nonce)
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

    # Two filters, in this order, and both ahead of the first attempt.
    #
    # Applicability first: a case not written for this target's agent type is not
    # this target's business at all, so asking what its preconditions are would be
    # answering a question about a case that is never going to run (spec story 16).
    # Then preconditions, which gate measurability and never scoring: a case this
    # target cannot answer is skipped before an attempt is spent on it, and the
    # families left with nothing to run report not measurable rather than a rate
    # (ADR-0004).
    written_for = applicable(cases, target)
    # Three filters now, and the third is the endpoint's own answer. Tool-call
    # visibility is the operator's declaration and there is nothing to check it
    # against at registration — nothing has been sent yet — so it is checked against
    # the first thing that comes back. A declaration the probe contradicts withdraws
    # the families that depend on it *before* an attempt is spent, so the run finishes
    # and signs a report over what could be measured rather than stopping at the first
    # trace-dependent verdict with nothing to read (ADR-0004).
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
            for case in runnable(written_for, target)
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
