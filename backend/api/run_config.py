"""What every run through this API is measured with, and the plan one run is
estimated against.

The middle of the three modules `runs.py` was split into: the declared
configuration a bench is built from, the instruments one run is made with, and the
plan `start` prices. Nothing here holds a run. `BenchConfig` is frozen, `RunPlan`
is frozen, and `plan_for` is a function of a configuration and a registration
rather than of a run — so this module can be read, and its arithmetic checked,
without knowing anything about a run's lifecycle.

**The boundary is drawn where the mutation starts.** `run_state.py` imports
`RunPlan` from here because a record carries the plan it was estimated against;
nothing here imports `run_state.py`. A configuration that could be reached from a
run's state would be a configuration a run could change, and the point of
`BenchConfig` is the opposite — that the library a run is estimated against and
the library it is run against are the same object by construction.

**Nothing here reads the environment.** The invariant is asserted over every module
of `backend/api/`, so a new module under `api/` inherits it by being under `api/`
(`test_no_module_of_the_api_reads_an_environment_of_its_own`). The price per call
arrives in the request or the run is *not priced*; the signing key arrives in
`BenchConfig.report`, read through the one line in `signing.py` that is allowed to
be an environment reader (ADR-0020).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from backend.api.report import ReportConfig
from backend.api.run_status import APPROVAL_WAIT_SECONDS, DeclaredGap
from backend.bench.adaptive.attacker import AttackerCompletion
from backend.bench.adaptive.budget import DECLARED_ADAPTIVE_BUDGET, AdaptiveBudget
from backend.bench.adaptive.scripted import SCRIPTED_ATTACKER
from backend.bench.adjudication import Completion
from backend.bench.capability import ReasoningEffort
from backend.bench.library import Case, Family, VerdictClass
from backend.bench.payload import DeclaredModels
from backend.bench.rule import DECLARED_RULE, GateRule
from backend.bench.usage import UsageLedger


@dataclass(frozen=True)
class Instruments:
    """The two instrument clients one run is made with, bound to that run's ledger.

    A pair rather than two returns, and the pairing is the point: both are built
    from one call, against one `UsageLedger`, into two different layers of it. A
    caller that could take the adjudicator without the attacker could bind half a
    run's usage and leave the other half reporting into nothing, which is the state
    #28 was about — a figure absent for a reason nobody stated.
    """

    adjudicator: Completion | None
    attacker: AttackerCompletion


class PerRunInstruments(Protocol):
    """How a bench builds a fresh pair of instruments for one run's ledger.

    **This exists because a sink is fixed when a client is built.**
    `completion_for(..., usage=...)` binds its sink once, at configuration time, and
    that happens before a run exists — so a bench that built its instruments at boot
    had nothing to bind them to, and every run started over HTTP carried a ledger
    that reported nothing (#28). The two ways out were a client whose sink can be
    reassigned per run, and a client built per run; this is the second.

    A process-global sink was not one of them. The API runs each run on its own
    thread, so a slot the clients share would file one run's tokens under
    another's — and a `ContextVar` silently drops every adjudicator call, because
    the pool that decides a judged family does not propagate context (#10). Both
    failures are invisible in the figure they corrupt, which is the argument for
    the shape that cannot express them: one ledger, one build, one run.

    **It takes the declared models rather than holding them.** The strings this
    builds from are the ones `report.models` prints, read at the moment of the
    build — so an attacker set through the console reaches the next run's client
    and the provenance block from one record, and the pairing `declared_instrument`
    makes at boot cannot come apart later (`BenchRuns.instrument`).
    """

    def __call__(self, models: DeclaredModels, usage: UsageLedger) -> Instruments: ...


@dataclass(frozen=True)
class BenchConfig:
    """What every run through this API is measured with.

    One record rather than arguments threaded through the routes, so that the
    library a run is estimated against and the library it is run against are the
    same object by construction. The declared rule and the declared adaptive
    budget are the defaults for the same reason `RunBudget.declare` takes them: a
    run held to numbers that were chosen for it is a run whose figures can be
    checked against `rule.py` and `adaptive/budget.py` rather than against
    whatever this module happened to pass.
    """

    cases: Sequence[Case]
    rule: GateRule = DECLARED_RULE
    adaptive: AdaptiveBudget = DECLARED_ADAPTIVE_BUDGET
    attacker: AttackerCompletion = SCRIPTED_ATTACKER
    """The adaptive layer's attacker, defaulting to the deterministic stand-in.

    Same default as `run_calibration`, and for the same reason: the layer always
    runs, and a bench with no model credential configured still spends the
    operator's endpoint the way a real one would.

    **A deployment that declared a model is handed one here.** The factory reads
    `AGENTAUDIT_ATTACKER_MODEL` and builds the client beside the identifier that
    goes into `report.models.attacking`, in one call, so the attacker a run is
    made with and the model its provenance names cannot come apart
    (`app.declared_instrument`). A caller that builds its own `BenchConfig` is
    making both of those statements itself, and the stand-in is what it says when
    it makes neither.
    """

    adjudicator: Completion | None = None
    """The instrument that decides the two judged families, or `None`.

    `None` by default, and the consequence is stated rather than absorbed: the
    judged cases are not run, and their families are reported with the gap that
    explains why. A run that reached its first judged attempt before discovering
    it had no instrument would have spent the operator's budget on attempts
    nothing can score.
    """

    report: ReportConfig = field(default_factory=ReportConfig)
    """The key this bench signs a finished run's report with, and what it declares
    beside the figures.

    Its own record rather than three more fields here, because none of it changes
    what a run does to a target: a bench with the default of every one of them
    attempts the same suite and produces no artefact. What that costs is stated at
    the route rather than absorbed — a run with no signed report is refused by name
    (`report.py`).
    """

    families: frozenset[Family] = frozenset(Family)
    """The failure families the next run covers. Every one of them, by default.

    A declared input like the six in `Instrumented`, and the one an operator sets
    per family rather than per number: a run that covers four families is a cheaper
    run and a narrower reading, and both of those are the operator's to choose.

    **A family switched off is *not run*, never measured at zero.** `plan_for` drops
    its cases and records `DeclaredGap.FAMILY_SWITCHED_OFF`, so the report says the
    family was not attempted — which is the same discipline `NotMeasurable` keeps for
    a precondition and `OperatorGap` keeps for an unplanted note. A rate of zero over
    no attempts is the reading this type exists to make unavailable (ADR-0004).

    It reaches the adaptive layer without a second mechanism: an episode needs a
    deterministic case for its family, and a family whose cases are gone has none, so
    the layer opens no episode against it (`adaptive/layer.objectives_for`).
    """

    approval_wait_seconds: float = APPROVAL_WAIT_SECONDS

    per_run_instruments: PerRunInstruments | None = None
    """How this bench builds instruments for one run, or `None` for the pair above.

    `None` says *this bench's instruments keep no usage record*, which is the
    honest reading for a caller that handed in clients of its own: a stub
    adjudicator has no provider to report a token count. The deployed factory
    always supplies one, because a run started from the console is the run whose
    figures an operator has no other way to see (#28).

    Named as an alternative to the two fields above rather than replacing them. The
    boot-built pair is what `plan_for` reads to decide whether the judged cases are
    attempted at all, and it is what makes a model named and unbuildable a refusal
    at boot instead of a discovery after an operator has confirmed a spend
    (`app.declared_instrument`, `app.NAMED_BUT_UNUSABLE`).
    """

    def instruments_for(self, usage: UsageLedger) -> Instruments:
        """This run's instruments, reporting into this run's ledger.

        One ledger per run and one build per run: `run_calibration` refuses a ledger
        that already holds calls, because a reused one would file the first run's
        tokens under the second run's id, and two runs on two threads sharing a sink
        would do it silently.

        **A build that disagrees with the boot-time pair is refused rather than
        run.** `plan_for` decided which cases this run may attempt from
        `self.adjudicator` — before the run, before the estimate — so a builder that
        handed back `None` here would leave a run attempting judged cases with no
        instrument, and one that handed back a client where boot had none would mean
        the operator was shown an estimate for a narrower run than the one that ran.
        """
        if self.per_run_instruments is None:
            return Instruments(adjudicator=self.adjudicator, attacker=self.attacker)
        built = self.per_run_instruments(self.report.models, usage)
        if (built.adjudicator is None) != (self.adjudicator is None):
            raise ValueError(
                "this bench built a run an adjudicator its boot-time pair does not "
                "agree about. The plan and the estimate an operator confirmed were "
                "built from the pair at boot, so the two have to say the same thing "
                "about whether the judged families run at all (ADR-0007)"
            )
        return built


@dataclass(frozen=True)
class RunPlan:
    """The cases one run will actually attempt, and the families it will not.

    Built per request rather than per bench, because one of the two gaps is a
    statement the caller makes about their own content store and the other is a
    property of this bench. They land in the same record because a reader of the
    estimate needs to know what it covers, and the estimate covers what is here.
    """

    cases: tuple[Case, ...]
    gaps: Mapping[Family, DeclaredGap]


def plan_for(
    config: BenchConfig, note_planted: bool, nonce_planted: bool = True
) -> RunPlan:
    """Which of the library's cases this run may attempt, and why the rest are out.

    Selected on `Case.verdict_class` and on the family, never on the family name
    alone for the judged half: the class is a field of the record for exactly this
    reason (ADR-0013), so a case that moves between families cannot change which
    instrument the run needed.
    """
    gaps: dict[Family, DeclaredGap] = {}
    cases = list(config.cases)

    if config.adjudicator is None:
        judged = {
            case.family for case in cases if case.verdict_class is VerdictClass.JUDGED
        }
        gaps.update(dict.fromkeys(judged, DeclaredGap.NO_ADJUDICATOR))
        cases = [
            case for case in cases if case.verdict_class is not VerdictClass.JUDGED
        ]

    if not note_planted:
        injection = Family.INDIRECT_PROMPT_INJECTION
        if any(case.family is injection for case in cases):
            gaps[injection] = DeclaredGap.NOTE_NOT_PLANTED
        cases = [case for case in cases if case.family is not injection]

    # The same argument one family over. The registration nonce is the leakage
    # canary — one planted value, two roles (ADR-0007) — so a run whose operator
    # never planted it is a run whose leakage cases go after a string that is
    # nowhere in the target. Thirty attempts would come back resisted and the
    # report would read as a defence that was never tested.
    # The operator's own choice, and it is a gap like the others rather than a
    # silent narrowing: a family they switched off has to read as *not run* on the
    # report, because a family absent with no reason beside it is a reader guessing
    # which of three answers it was.
    off = [family for family in Family if family not in config.families]
    for family in off:
        if any(case.family is family for case in cases):
            gaps[family] = DeclaredGap.FAMILY_SWITCHED_OFF
    cases = [case for case in cases if case.family in config.families]

    if not nonce_planted:
        leakage = Family.DATA_LEAKAGE
        if any(case.family is leakage for case in cases):
            gaps[leakage] = DeclaredGap.NONCE_NOT_PLANTED
        cases = [case for case in cases if case.family is not leakage]

    return RunPlan(cases=tuple(cases), gaps=gaps)


@dataclass(frozen=True)
class Instrumented:
    """The declared inputs of a run that the console may set, as one statement.

    Six settings and a model identifier, and every one of them changes what a run
    *measured* rather than how it looks. That is why they arrive together: a caller
    that could set the turn budget without restating the attacker model could leave
    a bench whose report names one instrument and whose episodes were run by
    another, and the four settings of a run's provenance exist to make exactly that
    unreadable (ADR-0004, ADR-0013).

    **`attempts_per_case` is in a different class from the other five**, and
    ADR-0025 argues the difference: the other five bound a layer scored on nothing
    (ADR-0010), and this one is the scored denominator that ADR-0003 sets to give
    `n = 30` per family. What the difference buys here is that a run at a lower
    number is honest and is **not a gate result** —
    `GateRule` travels on `TargetRun` and prints beside every figure, and
    `scripts/gate.py` stays on `DECLARED_RULE` and takes no setting from this type.
    """

    attacker_model: str
    """`<provider>:<model>`, or `UNDECLARED_MODEL` for the deterministic stand-in."""

    temperature: float | None
    """The attacker's sampling temperature, or `None` for the provider's own default.

    `None` and a number are different declarations: one says *whatever the provider
    does*, and a bench that wrote its own number into that field would be naming a
    setting nobody chose.
    """

    reasoning_effort: ReasoningEffort | None
    """How hard a reasoning attacker may think, or `None` for two different absences.

    Beside the temperature because it is the second declared input of the same
    instrument, and the two are not interchangeable: a model that takes one takes no
    other, and two runs of one model at one temperature and different effort are two
    different instruments (#5). `None` is *nothing declared* here, and a model with no
    such setting is a fact the record states rather than a value this carries.
    """

    turns_per_episode: int
    episodes_per_family: int
    attempts_per_case: int
