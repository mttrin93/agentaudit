"""Starting a run from something other than a terminal, and the two controls that
survive the move.

A run is 181 calls in the scored layer and up to 96 more in the adaptive one, every
one of them on the operator's endpoint and their inference budget. The two controls
that make one authorised — a completed three-part attestation, and a halt in front
of the spend — are the whole of what this module is for (ADR-0007), and neither of
them becomes a request field. The attestation is the same record `registration.py`
refuses to construct incomplete. The halt is the same LangGraph `interrupt()`
against a checkpointer that a terminal run stops at: what changes between a
terminal and a browser is the `Approve` seam and nothing else, which is what
`scripts/console.py` said when it wrote the other one.

**The guard is in two places, and it has to be.** The three statements are checked
before a run exists, because nothing about them needs the target. The nonce echo
cannot be checked there: the echo probe is itself a call on the operator's
endpoint, and ADR-0007 puts the halt *ahead* of registration precisely so that a
run has spent nothing by the time it asks. So the bench issues the nonce, the
operator plants it, `start` refuses a nonce this bench never issued, and the echo
itself is checked by `register` inside the run — after the interrupt was answered.
A target that does not echo is a run that makes no attempt and says so. A guard
that checked the echo at the request would be a guard that spent the operator's
money before asking them.

**Two figures, and they are the two figures a terminal shows.** What comes back is
`RunBudget.as_payload()`: the scored layer exact, the adaptive layer a ceiling,
each carrying its own arithmetic, beside the bounded total and the hard ceiling
that ADR-0007's own table prints and that is the figure actually enforced. Nothing
here adds a figure, and nothing averages one — `CallFigure.__add__` makes a fact
plus a bound a bound, so a total cannot be presented as exact by anything
downstream.

**The run is on a thread and the request that started it does not wait for it.**
`start` returns once the graph has halted, carrying the figures the interrupt
presented rather than a second computation of them, so what a caller confirms is
what the graph is holding. The suite is on the far side of the edge the answer
decides, and it is held to the ceiling on the record — never one re-declared later
against whatever the library holds by then.

**Nothing here reads the environment.** The price per call arrives in the request
or the run is *not priced*: the caller's confirmation is the liability record, and
a figure the bench filled in from its own configuration is a figure nobody agreed
to. An unpriced run is a stated fact and never a zero.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from backend.bench.adaptive.attacker import AttackerCompletion
from backend.bench.adaptive.budget import DECLARED_ADAPTIVE_BUDGET, AdaptiveBudget
from backend.bench.adaptive.scripted import SCRIPTED_ATTACKER
from backend.bench.adjudication import Completion
from backend.bench.calibration import CalibrationResult, run_calibration
from backend.bench.contract import TargetConfig, TargetUnreachable
from backend.bench.library import Case, Family, LibraryVersion, VerdictClass
from backend.bench.registration import Attestation, issue_nonce
from backend.bench.rule import DECLARED_RULE, GateRule
from backend.graph.approval import Approval, Approve
from backend.graph.budget import (
    BudgetExceeded,
    BudgetPayload,
    CallPrice,
    Layer,
    RunBudget,
)
from backend.graph.runstate import RunState

APPROVAL_WAIT_SECONDS = 3600.0
"""How long a run waits at the interrupt for an answer that may never come.

A halted run holds a thread and a checkpoint, so the wait is finite; it is an hour
because the human it is waiting for has to read two figures and decide whether to
spend them, and a limit short enough to catch somebody thinking would be a consent
mechanism that answered on their behalf. What happens at the end of it is a *no*
recorded as **unanswered** rather than as declined — nobody said no, nobody said
anything — and either way nothing was sent and nothing was spent.
"""

PRESENT_WAIT_SECONDS = 30.0
"""How long `start` waits for the graph to reach its interrupt.

Nothing has been sent to the target by then — the halt is ahead of registration —
so this bounds a graph that never halted rather than a run that is working. A run
that reaches it has failed to present an estimate, and a request that returned a
`run_id` for one would be handing back a run nobody could ever confirm.
"""


class RunStatus(StrEnum):
    """Where a run is, in the words the record keeps.

    `DECLINED` and `UNANSWERED` are two states rather than one, on `approval.py`'s
    own reasoning: a caller that treats them as the same loses the difference
    between "refused by a human" and "awaiting one". `ABORTED` is separate from
    `FAILED` for the same kind of reason — a run stopped by its own ceiling is the
    budget working, and one stopped by a transport failure is not a result at all.
    """

    AWAITING_APPROVAL = "awaiting_approval"
    DECLINED = "declined"
    UNANSWERED = "unanswered"
    RUNNING = "running"
    COMPLETED = "completed"
    REGISTRATION_REFUSED = "registration_refused"
    ABORTED = "aborted"
    FAILED = "failed"


class DeclaredGap(StrEnum):
    """Something the caller's own setup did not provide, and the family it costs.

    The second surface of the concept `scripts/probe_target.py` keeps as
    `OperatorGap`, and deliberately not `NotMeasurable`: that type is the library's
    answer to a *case precondition* a target cannot meet, decided before an attempt
    is spent. These are the caller's gaps — the bench cannot detect either of them,
    no attempt is skipped for them, and the family is not run at all rather than
    measured at zero. A family missing from a run with no reason beside it is a
    reader guessing which of three answers it was.
    """

    NO_ADJUDICATOR = "no_adjudicator"
    NOTE_NOT_PLANTED = "note_not_planted"

    def stated(self) -> str:
        match self:
            case DeclaredGap.NO_ADJUDICATOR:
                return (
                    "not run: this family reaches its verdict by adjudication and "
                    "this bench has no adjudicating instrument configured. A "
                    "family nothing can score is not attempted, so the estimate "
                    "does not charge for it"
                )
            case DeclaredGap.NOTE_NOT_PLANTED:
                return (
                    "not run: this family needs a third-party note planted in "
                    "content the target retrieves, and the caller declared it is "
                    "not in place. Run without it, the family would report a clean "
                    "zero that reads as a defence and is not one"
                )


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
    operator's endpoint the way a real one would. Naming a configured model here
    is the deployment's business.
    """

    adjudicator: Completion | None = None
    """The instrument that decides the two judged families, or `None`.

    `None` by default, and the consequence is stated rather than absorbed: the
    judged cases are not run, and their families are reported with the gap that
    explains why. A run that reached its first judged attempt before discovering
    it had no instrument would have spent the operator's budget on attempts
    nothing can score.
    """

    approval_wait_seconds: float = APPROVAL_WAIT_SECONDS


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


def plan_for(config: BenchConfig, note_planted: bool) -> RunPlan:
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

    return RunPlan(cases=tuple(cases), gaps=gaps)


class NonceNotIssued(ValueError):
    """A run asked to start against a nonce this bench never issued.

    The half of the authorisation guard that can be enforced before anything is
    sent. It does not prove the target echoes the value — only the probe inside
    the run can, and it runs after the halt — but it does prove the caller went
    through registration rather than pointing the bench at an endpoint and
    inventing a token.
    """

    def __init__(self, nonce: str) -> None:
        super().__init__(
            "this bench never issued that nonce, so no run may start against it. "
            "Register the target first: the bench issues the value, you plant it "
            "in the target's configuration, and the run's own registration probe "
            "checks that it comes back (ADR-0007)."
            if nonce
            else "a run has to name the nonce it was registered with, and this "
            "request named none (ADR-0007)."
        )


class NeverPresented(RuntimeError):
    """The graph did not reach its interrupt, so there is no estimate to confirm."""


@dataclass
class RunRecord:
    """One run: what authorised it, what it was estimated at, and where it got to.

    The budget, the plan and the run state are all held here rather than in the
    thread's locals, because the ceiling the suite is held to has to be the one the
    caller was shown — an estimate that has become separated from the run it was
    presented for is an estimate nobody can check.
    """

    run_id: str
    target: TargetConfig
    attestation: Attestation
    nonce: str
    plan: RunPlan
    budget: RunBudget
    run_state: RunState
    presented: BudgetPayload
    status: RunStatus = RunStatus.AWAITING_APPROVAL
    statement: str = (
        "halted at the approval interrupt: nothing has been sent to the target "
        "and nothing has been spent, and nothing will be until this estimate is "
        "answered"
    )
    confirmed_by: str = ""
    result: CalibrationResult | None = None

    @property
    def spent(self) -> dict[Layer, int]:
        """Calls spent, per layer and never summed.

        Two counters, because a single blended figure hides which half of a run is
        consuming the operator's budget — the same reason the estimate is two
        figures (ADR-0007). `RunState.calls_spent` exists for reporting and is
        deliberately not what a ceiling is read against.
        """
        return dict(self.run_state.spent)

    def settle(self, status: RunStatus, statement: str) -> None:
        """Move the run to its next state, and say in words what that state is."""
        self.status = status
        self.statement = statement


class PendingApproval:
    """The interrupt's two ends: the graph waits here, an HTTP request answers here.

    This is the `Approve` seam and nothing more. The graph does not know it is
    being answered over HTTP any more than it knows it is being answered at a
    terminal, which is the property ADR-0007 asks for — the run does not proceed
    because it *cannot* proceed, not because a code path chose not to.
    """

    def __init__(self, wait_seconds: float) -> None:
        self._wait = wait_seconds
        self._halted = threading.Event()
        self._answered = threading.Event()
        self._payload: BudgetPayload | None = None
        self._answer: Approval | None = None

    @property
    def answered(self) -> bool:
        """Whether a human ever answered. False for a run that timed out waiting."""
        return self._answer is not None

    def approve(self, presented: BudgetPayload) -> Approval:
        """What the graph calls when it has halted. Blocks until somebody answers.

        The payload is published before the wait, so the request that started the
        run returns the figures the interrupt is holding rather than a recomputed
        copy of them.
        """
        self._payload = presented
        self._halted.set()
        if not self._answered.wait(self._wait) or self._answer is None:
            return Approval(
                confirmed=False,
                identity="",
                reason=(
                    "the approval interrupt was never answered, so the run never "
                    "started"
                ),
            )
        return self._answer

    def answer(self, approval: Approval) -> None:
        """The human's answer, from the request that carried it."""
        self._answer = approval
        self._answered.set()

    def halted(self, timeout: float) -> BudgetPayload:
        """The estimate the graph is holding, once it is holding one."""
        if not self._halted.wait(timeout) or self._payload is None:
            raise NeverPresented(
                "the run reached no approval interrupt, so it has no estimate to "
                "confirm. Nothing was sent"
            )
        return self._payload


class BenchRuns:
    """Every run this process has started, and every nonce it has issued.

    In memory, single process, and that is the v1 the spec licensed: a queue and a
    store outlive a restart and are P1. What is *not* deferred is that a run holds
    its own ceiling and its own state — those are correctness rather than
    durability, and they are on `RunRecord`.
    """

    def __init__(self, config: BenchConfig) -> None:
        self._config = config
        self._issued: set[str] = set()
        self._runs: dict[str, RunRecord] = {}
        self._pending: dict[str, PendingApproval] = {}
        self._lock = threading.Lock()

    @property
    def config(self) -> BenchConfig:
        return self._config

    def issue(self) -> str:
        """Issue a nonce for a target the caller is about to register."""
        nonce = issue_nonce()
        with self._lock:
            self._issued.add(nonce)
        return nonce

    def record(self, run_id: str) -> RunRecord | None:
        with self._lock:
            return self._runs.get(run_id)

    def start(
        self,
        target: TargetConfig,
        attestation: Attestation,
        nonce: str,
        price: CallPrice | None,
        note_planted: bool,
    ) -> RunRecord:
        """Declare the estimate, start the run, and return once it has halted.

        The attestation is a constructed `Attestation` rather than three booleans:
        a statement that was not made cannot be constructed, so a run that reaches
        this line was authorised by a record that exists.
        """
        with self._lock:
            issued = nonce in self._issued
        if not issued:
            raise NonceNotIssued(nonce)

        plan = plan_for(self._config, note_planted)
        budget = RunBudget.declare(
            cases=plan.cases,
            targets=[target],
            rule=self._config.rule,
            adaptive=self._config.adaptive,
            price=price,
        )
        pending = PendingApproval(self._config.approval_wait_seconds)
        run_id = str(uuid.uuid4())
        record = RunRecord(
            run_id=run_id,
            target=target,
            attestation=attestation,
            nonce=nonce,
            plan=plan,
            budget=budget,
            run_state=RunState(budget=budget, library=LibraryVersion.of(plan.cases)),
            presented=budget.as_payload(),
        )
        with self._lock:
            self._runs[run_id] = record
            self._pending[run_id] = pending

        threading.Thread(
            target=_execute,
            args=(record, self._config, pending),
            name=f"agentaudit-run-{run_id}",
            daemon=True,
        ).start()

        # The figures the graph is holding, not the ones declared above: the two
        # are built from the same budget, and returning the presented copy is what
        # makes that checkable rather than assumed.
        record.presented = pending.halted(PRESENT_WAIT_SECONDS)
        return record

    def answer(self, run_id: str, approval: Approval) -> RunRecord:
        """Answer one run's interrupt. A yes is the only thing that starts a suite."""
        with self._lock:
            record = self._runs.get(run_id)
            pending = self._pending.get(run_id)
        if record is None or pending is None:
            raise KeyError(run_id)
        if record.status is not RunStatus.AWAITING_APPROVAL:
            raise AlreadyAnswered(record)

        if approval.confirmed:
            record.confirmed_by = approval.identity
            record.settle(
                RunStatus.RUNNING,
                (
                    f"confirmed by {approval.identity}: the suite is running in "
                    "the background, under the ceiling that was confirmed and "
                    "aborting rather than exceeding it"
                ),
            )
        else:
            record.settle(RunStatus.DECLINED, _declined(approval.reason))
        pending.answer(approval)
        return record


class AlreadyAnswered(RuntimeError):
    """A second answer to an interrupt that has already been answered once.

    Refused rather than applied. The first answer is the one a human gave in front
    of the figures, and a second request arriving after the suite has started
    would be consent recorded for a spend that is already happening.
    """

    def __init__(self, record: RunRecord) -> None:
        super().__init__(
            f"run {record.run_id} is {record.status} and its approval interrupt "
            "has already been answered. An answer is recorded once"
        )


def _declined(reason: str) -> str:
    stated = reason or "declined at the approval interrupt"
    return f"{stated}. Nothing was sent to the target and nothing was spent"


def _execute(record: RunRecord, config: BenchConfig, pending: PendingApproval) -> None:
    """One run, on its own thread: the same entry point a terminal run takes.

    There is one code path to a target and this does not add a second — the
    attestation, the estimate, the halt, registration, the attempt loop and the
    adaptive layer are all reached through `run_calibration`, which is what the
    gate and `scripts/probe_target.py` reach them through.
    """
    # Named against the seam's own type rather than passed straight through, so
    # that a signature drifting away from `Approve` is a typecheck failure here
    # and not a run that halts and never resumes.
    approve: Approve = pending.approve
    try:
        result = run_calibration(
            cases=record.plan.cases,
            targets=[record.target],
            attestation=record.attestation,
            approve=approve,
            adjudicator=config.adjudicator,
            attacker=config.attacker,
            rule=config.rule,
            adaptive=config.adaptive,
            # The ceiling on the record, never one re-declared here: the operator
            # confirmed these figures in an earlier request, and a run held to a
            # limit recomputed against whatever the library holds by now would be
            # a run held to a number nobody saw.
            budget=record.budget,
            run_state=record.run_state,
            planted_nonces={record.target.name: record.nonce},
        )
    except BudgetExceeded as abort:
        record.settle(
            RunStatus.ABORTED,
            (
                f"{abort}. An episode the ceiling cut short is recorded as "
                "censored, never as resisted"
            ),
        )
        return
    except TargetUnreachable as unreachable:
        record.settle(RunStatus.FAILED, str(unreachable))
        return
    except Exception as failure:
        record.settle(
            RunStatus.FAILED,
            f"the run stopped rather than produced a result: {failure}",
        )
        return

    record.result = result
    if not result.approval.proceeded:
        refused = RunStatus.DECLINED if pending.answered else RunStatus.UNANSWERED
        record.settle(refused, _declined(result.approval.reason))
        return

    [target_run] = result.target_runs
    if target_run.registration.refused:
        record.settle(
            RunStatus.REGISTRATION_REFUSED,
            (
                "the nonce was not echoed, so no attempt was made. Registration "
                "proves you control the endpoint and nothing runs without it: "
                "check that the nonce line is in the target's configuration and "
                "that it reloaded"
            ),
        )
        return

    record.settle(
        RunStatus.COMPLETED,
        (
            f"the run finished inside the ceiling that was confirmed by "
            f"{record.confirmed_by}"
        ),
    )
