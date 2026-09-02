"""One run's state: the record, the halt it waits at, and the four refusals a
caller can be handed.

The upper of the three modules `runs.py` was split into, and the only one that
mutates. `RunRecord` is where a run's authorisation, its estimate and where it got
to are held together — the ceiling the suite is enforced against has to be the one
the caller was shown, and an estimate separated from the run it was presented for
is an estimate nobody can check. `PendingApproval` is the rendezvous that makes the
halt reachable from an HTTP request: the graph reaches its interrupt on the run's
own thread, the request that started the run waits for it, and the answer travels
back the other way.

**The errors live beside the state they are about.** `RunsInFlight`,
`NonceNotIssued`, `NeverPresented` and `NoLongerWaiting` are each a statement about
a record or a nonce rather than about the service that raises them, so they are
here rather than in `runs.py` — a reader working out what a route can refuse reads
one module.

**This module imports `run_config.py` and `run_status.py` and neither imports it.**
That is the split's load-bearing direction: state may know what it was configured
with, configuration may not know what state a run reached. `BenchRuns`, the service
that drives a run through this record, stays in `runs.py`.
"""

from __future__ import annotations

import threading
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from backend.api.report import Unsigned
from backend.api.run_config import RunPlan
from backend.api.run_status import RunStatus
from backend.bench.calibration import CalibrationResult
from backend.bench.contract import TargetConfig, TargetFailure
from backend.bench.registration import Attestation
from backend.bench.signing import SignedArtefact
from backend.graph.approval import Approval
from backend.graph.budget import BudgetPayload, Layer, RunBudget
from backend.graph.runstate import RunState


@dataclass(frozen=True)
class RunsInFlight(RuntimeError):
    """An instrument was changed while a run was still going, and was refused.

    Named rather than swallowed, and it names the runs: an operator told *not now*
    with no way to see what is holding the lock has to guess whether to wait or to
    decline something.
    """

    def __init__(self, run_ids: Sequence[str]) -> None:
        super().__init__(
            f"{len(run_ids)} run(s) still going — {', '.join(run_ids)}. A run "
            "awaiting approval was shown an estimate built from the settings it was "
            "declared with, and changing them now would make that confirmation a "
            "statement about a different run (ADR-0007). Let them finish, or decline "
            "them, and set this again"
        )


class NonceNotIssued(ValueError):
    """A run asked to start against a nonce this bench never issued.

    The half of the authorisation guard that can be enforced before anything is
    sent. It does not prove the target echoes the value — only the probe inside
    the run can, and it runs after the halt — but it does prove the caller went
    through registration rather than pointing the bench at an endpoint and
    inventing a token.

    Not raised for a run that declared the nonce unplanted: that run has waived the
    proof this value carries and dropped the family it is the canary for, so there
    is nothing left for it to be checked against (ADR-0007, as amended).
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
    proof_waived: bool = False
    """The operator started this run without planting the nonce (ADR-0007, amended).

    Held on the record because it decides two things and outlives both: the run still
    sends its echo probe but is not stopped by a missing echo, and the leakage family
    is dropped from the plan rather than measured against a value nobody planted. The
    artefact says which of the two ways the run was authorised, and it says it from
    what the registration recorded rather than from this field — this is the
    declaration, and that is what the endpoint did.
    """

    recorded_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    """When this run went on the record: the moment the attestation was taken and
    the estimate declared.

    Deliberately not *when the target was registered*. Registration is the nonce
    echo (CONTEXT.md), and the echo probe is the run's first call on the operator's
    endpoint — on the far side of the interrupt — so a run awaiting approval, a run
    declined and a run nobody answered have no registration time at all, and a
    field that claimed to be one would be empty for exactly the runs a list is most
    useful for. This is the time the bench took responsibility for the run, which
    every run has.

    A wall clock in UTC, because it is read by somebody asking *which of these did I
    start yesterday*. `RunState.started_at` is `time.monotonic()` and stays that
    way: it exists so that the layer-ordering invariant is checkable (ADR-0010), and
    a monotonic reading has no date in it.
    """

    status: RunStatus = RunStatus.AWAITING_APPROVAL
    statement: str = (
        "halted at the approval interrupt: nothing has been sent to the target "
        "and nothing has been spent, and nothing will be until this estimate is "
        "answered. The nonce is checked by the run's own registration probe, "
        "which is the first call it makes — a target that does not echo it is "
        "not attempted, unless the operator declared the proof waived when they "
        "started this run"
    )
    confirmed_by: str = ""

    finished: threading.Event = field(default_factory=threading.Event, repr=False)
    """Set by the thread that ran this run, when it has finished writing to it.

    A run has two threads that can reach its record — the worker, and whatever
    request is asking about it — and exactly one of them may say what the run
    *did*. This is how the other one knows to wait. It says the record is complete
    and not that the run succeeded: an aborted run, a failed one and a declined one
    all set it, because all three are the worker having nothing left to write.
    """

    result: CalibrationResult | None = None
    report: SignedArtefact | Unsigned = field(default_factory=Unsigned)
    """The signed report this run produced, or the reason it has none.

    Built once, by the thread that ran the run, and read by every request for it:
    what a recipient downloads has to be the bytes that were signed, and bytes
    re-assembled per request are bytes nobody signed (#56).

    One of two records rather than a nullable one, so *why there is no report* is
    carried by the thing that stands in for it: `Unsigned` is served as that under
    its own name, and it is never made good by serving an unsigned payload in its
    place. It is not a failed run either — the suite ran and the target was
    measured.
    """

    failure: TargetFailure | None = None
    """The named transport outcome that stopped this run, if one did.

    Kept as the enum the transport raised rather than folded into `statement`,
    because the four the spec names are four different jobs for the person reading
    the run and a reporting surface has to be able to name the one it got. `None`
    for every run that was not stopped by the wire — and a failure here is never a
    verdict, never an attempt and never a finding: `TargetUnreachable` is raised
    precisely so that no counter has anywhere to put it.
    """

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
        self._closed = False
        self._lock = threading.Lock()

    @property
    def answered(self) -> bool:
        """Whether a human ever answered. False for a run that timed out waiting."""
        return self._answer is not None

    def approve(self, presented: BudgetPayload) -> Approval:
        """What the graph calls when it has halted. Blocks until somebody answers.

        The payload is published before the wait, so the request that started the
        run returns the figures the interrupt is holding rather than a recomputed
        copy of them.

        When the wait runs out this closes: an answer arriving afterwards has
        nothing to answer, because the graph has already been told nobody did. The
        close and the answer take the same lock, so a confirmation landing in that
        instant is either taken or refused and never both.
        """
        self._payload = presented
        self._halted.set()
        answered = self._answered.wait(self._wait)
        with self._lock:
            if not answered or self._answer is None:
                self._closed = True
                return Approval(
                    confirmed=False,
                    identity="",
                    reason=(
                        "the approval interrupt was never answered, so the run "
                        "never started"
                    ),
                )
            return self._answer

    def answer(self, approval: Approval) -> bool:
        """Record the human's answer, if this interrupt is still waiting on one.

        False when it is not — answered already, or closed because the wait ran
        out. A caller that took that for a yes would be telling somebody their run
        had started when the graph had already been told it would not.
        """
        with self._lock:
            if self._closed or self._answer is not None:
                return False
            self._answer = approval
            self._answered.set()
            return True

    def halted(self, timeout: float) -> BudgetPayload:
        """The estimate the graph is holding, once it is holding one."""
        if not self._halted.wait(timeout) or self._payload is None:
            raise NeverPresented(
                "the run reached no approval interrupt, so it has no estimate to "
                "confirm. Nothing was sent"
            )
        return self._payload


class NoLongerWaiting(RuntimeError):
    """An answer to an interrupt that is not waiting for one any more.

    Refused rather than applied, whichever of the two it is. A second answer would
    be consent recorded for a spend that is already happening; an answer arriving
    after the wait ran out would be consent for a run the graph has already been
    told nobody authorised.
    """

    def __init__(self, record: RunRecord) -> None:
        super().__init__(
            f"run {record.run_id} is {record.status} and is no longer waiting on "
            "an answer. An interrupt is answered once"
        )
