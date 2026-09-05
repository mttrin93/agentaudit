"""A gate run started from a browser: its own record, and the three things it needs
before it may exist.

PLAN.md §8 put a gate run on the command line and said *not through the API*, and
[ADR-0021](../../docs/adr/0021-the-console-may-start-a-gate-run.md) reverses that.
What the reversal cannot do is weaken either of the two controls the command line
carried, so neither is reimplemented here: the three attestation statements are the
`Attestation` record `registration.py` refuses to construct incomplete, and the halt
in front of the spend is the same `PendingApproval` seam `POST /runs` answers
(`runs.py`). **There is no flag on this module, no setting on its bench and no
environment variable anywhere that lets a gate run proceed without both** — that is
the thing ADR-0007 forbids, and the reason a gate run could not simply be spawned
as a subprocess is that the terminal helper reads absent or piped input as a
refusal, so a spawned one would answer no to all three statements and spend nothing.

**It rewrites the case library, so it reads the library it writes to.** A gate run
appends a `[[history]]` reading to every case record it reads and marks retired
whatever the rule retires (`retirement.store`), and the series a retirement is
re-derived from has to be the record's own. So the library is a **directory** this
bench was configured with rather than the cases it booted with, and the run reads
that directory at the moment it starts and writes back to it at the end. A bench
configured with no writable library directory does not run a gate: the write-back
would land inside a container image and be gone at the next redeploy, and a
measurement whose evidence does not survive the deployment that made it is worse
than a refusal, because it looks exactly like the real thing.

**One writer at a time, and the lease is on the library.** Two overlapping gate
runs on one library are a read-modify-write race over the same files
(`bench/lease.py`), so a gate run takes an exclusive lease on the directory before
it reads anything and releases it after the write-back. The lease is a file in the
library, not a lock in this process, because the command line writes to the same
records: the two entry points exclude each other rather than only themselves. A
second gate run is refused by name rather than queued — 830 calls behind an hour of
waiting is not a request anybody meant to make.

**Nothing here reads a document.** The per-family figures a gate run produces —
the three reference agents' rates and each family's `D` — are on the `GateResult`
this module holds in memory, put there by `read_gate` over the attempts that were
just made. A route that parsed the dated Markdown a command-line run leaves would
break on a rewording, and a gate run started here has the figures already.

**The gate-run side is four modules and this is the service.**
`gate_run_equipment.py` holds what a gate run is run with — the library directory,
the gold sets, the three reference agents and the seam that may be missing;
`gate_run_state.py` holds one gate run's record and the refusals in front of it,
including why `GateRunRecord` and `RunRecord` never appear in one signature;
`gate_run_writeback.py` holds the three writes a gate run leaves behind under its
lease, the gate citation among them. This module starts one, halts it, answers it
and drives it. The names the routes and the suite import from
`backend.api.gate_runs` did not move (#14).
"""

from __future__ import annotations

import threading
import uuid
from contextlib import ExitStack
from pathlib import Path

# Re-exported, not merely imported: the definitions moved into the two modules
# beside this one and the import surface stayed here. The redundant `X as X` is
# what marks a re-export to mypy under `no_implicit_reexport`.
from backend.api.gate_run_equipment import (
    DEPLOYED_LIBRARY as DEPLOYED_LIBRARY,
)
from backend.api.gate_run_equipment import (
    GOLDSET_DIR as GOLDSET_DIR,
)
from backend.api.gate_run_equipment import (
    Equipment as Equipment,
)
from backend.api.gate_run_equipment import (
    GateRunBench as GateRunBench,
)
from backend.api.gate_run_equipment import (
    ServedAgents as ServedAgents,
)
from backend.api.gate_run_equipment import (
    seeded_library as seeded_library,
)
from backend.api.gate_run_equipment import (
    shipped_agents as shipped_agents,
)
from backend.api.gate_run_state import (
    CannotRunAGate as CannotRunAGate,
)
from backend.api.gate_run_state import (
    Cites as Cites,
)
from backend.api.gate_run_state import (
    GateRunRecord as GateRunRecord,
)
from backend.api.gate_run_state import (
    GateRunStatus as GateRunStatus,
)
from backend.api.gate_run_state import (
    NoLongerWaiting as NoLongerWaiting,
)
from backend.api.gate_run_state import (
    NotStartable as NotStartable,
)
from backend.api.gate_run_state import (
    WrittenBack as WrittenBack,
)
from backend.api.gate_run_state import (
    a_holder as a_holder,
)
from backend.api.gate_run_writeback import write_back
from backend.api.run_config import BenchConfig
from backend.api.run_state import PendingApproval
from backend.api.run_status import PRESENT_WAIT_SECONDS
from backend.bench.admission import admitted_library
from backend.bench.calibration import run_calibration
from backend.bench.contract import TargetUnreachable
from backend.bench.gate import NotAGateRun, read_gate
from backend.bench.goldset import load_gold_sets, measure_reliability
from backend.bench.lease import LibraryBusy, held_by, holding_the_library
from backend.bench.library import LibraryVersion
from backend.bench.registration import Attestation
from backend.bench.retirement import (
    live_library,
)
from backend.bench.usage import UsageLedger
from backend.graph.approval import Approval, Approve
from backend.graph.budget import (
    BudgetExceeded,
    CallPrice,
    RunBudget,
)
from backend.graph.runstate import RunState
from backend.observability import TracedRun


class BenchGateRuns:
    """Every gate run this process has started, and the one library they write to.

    In memory and single process, which is the same v1 `BenchRuns` is: what is *not*
    deferred is the lease, because that is correctness rather than durability and it
    lives in the library's own directory where another process can see it.

    A separate registry from `BenchRuns` and not a second dictionary inside it. The
    two hold different records with different statuses reached by different routes,
    and a registry that held either would be the widening this module's docstring
    asks a reader to stop at.
    """

    def __init__(
        self,
        config: BenchConfig,
        bench: GateRunBench,
        cites: Cites | None = None,
    ) -> None:
        self._config = config
        self._bench = bench
        self._cites = cites
        self._runs: dict[str, GateRunRecord] = {}
        self._pending: dict[str, PendingApproval] = {}
        self._lock = threading.Lock()

    @property
    def bench(self) -> GateRunBench:
        """What this bench can run a gate with, readable and frozen.

        Handed to the factory beside the `BenchConfig` rather than kept inside it,
        because what a *run* is measured with and what a *gate run* needs are two
        declarations: a deployment that has said what it signs with has not thereby
        said that it holds a writable case library and ships three reference agents.
        """
        return self._bench

    def records(self) -> list[GateRunRecord]:
        """Every gate run this bench has started, most recently recorded first.

        The records themselves and never a summary: nothing here counts gate runs,
        adds a spend across them or averages one.
        """
        with self._lock:
            return list(self._runs.values())[::-1]

    def record(self, gate_run_id: str) -> GateRunRecord | None:
        """One gate run's record, or `None` for an id this bench never issued."""
        with self._lock:
            return self._runs.get(gate_run_id)

    def why_not(self) -> NotStartable | None:
        """Why a gate run may not start on this bench right now, or `None`.

        Read in the order a reader needs it: the two facts about how the bench was
        built come before the one about this moment, because *this deployment ships
        no reference agents* is not answered by waiting.
        """
        bench = self.bench
        if bench.equipment is None:
            return NotStartable.NO_REFERENCE_AGENTS
        if bench.library is None or not _a_library(bench.library):
            return NotStartable.NO_WRITABLE_LIBRARY
        if self._config.adjudicator is None:
            return NotStartable.NO_ADJUDICATOR
        if held_by(bench.library) or any(
            record.status.in_flight for record in self.records()
        ):
            return NotStartable.ALREADY_IN_FLIGHT
        return None

    def holder(self) -> str:
        """What the lease on this bench's library says, or the empty string."""
        library = self.bench.library
        return held_by(library) if library is not None else ""

    def start(self, attestation: Attestation, price: CallPrice | None) -> GateRunRecord:
        """Take the library, declare the estimate, and halt in front of it.

        The attestation is a constructed `Attestation` rather than three booleans, so
        a gate run that reaches this line was authorised by a record that cannot
        exist with a statement withheld. There is no argument here that could stand
        in for one, and no configuration that makes it optional.

        Returns once the graph is holding its interrupt, which is before anything
        has been sent to a reference agent and before one case record has been
        written to.
        """
        refusal = self.why_not()
        if refusal is not None:
            # The holder travels with the refusal where there is one, because *not
            # now* is only actionable if the operator can tell whose run to wait for
            # — theirs, somebody else's, or a terminal's.
            raise CannotRunAGate(refusal, self.holder())

        bench = self.bench
        # Narrowed for the typechecker by `why_not`, which is the one place these
        # two absences are decided: a second check here would be a second policy.
        assert bench.library is not None and bench.equipment is not None

        gate_run_id = str(uuid.uuid4())
        stack = ExitStack()
        try:
            # The lease first, before the library is read: the critical section is
            # read-then-write across the whole run, not the write on its own.
            stack.enter_context(
                holding_the_library(bench.library, a_holder(attestation, gate_run_id))
            )
            served = stack.enter_context(bench.equipment())
            cases = tuple(live_library(admitted_library(bench.library)))
            if not cases:
                raise CannotRunAGate(
                    NotStartable.NO_WRITABLE_LIBRARY,
                    f"{bench.library} holds no live case, so there is nothing to "
                    "decide a gate over",
                )
            budget = RunBudget.declare(
                cases=cases,
                targets=served.targets,
                rule=self._config.rule,
                adaptive=self._config.adaptive,
                price=price,
            )
            record = GateRunRecord(
                gate_run_id=gate_run_id,
                attestation=attestation,
                library=bench.library,
                cases=cases,
                agents=tuple(target.name for target in served.targets),
                roles=(served.hardened, served.weak, served.trivial),
                budget=budget,
                run_state=RunState(budget=budget, library=LibraryVersion.of(cases)),
                presented=budget.as_payload(),
            )
            pending = PendingApproval(self._config.approval_wait_seconds)
            with self._lock:
                self._runs[gate_run_id] = record
                self._pending[gate_run_id] = pending
            threading.Thread(
                target=_execute,
                args=(record, self._config, served, pending, stack, self._cites),
                name=f"agentaudit-gate-run-{gate_run_id}",
                daemon=True,
            ).start()
        except LibraryBusy as busy:
            stack.close()
            raise CannotRunAGate(NotStartable.ALREADY_IN_FLIGHT, str(busy)) from busy
        except BaseException:
            # The lease and the served agents go back on any failure before the
            # thread exists: a lease held by nothing is a library nobody may write
            # to and no run writing to it.
            stack.close()
            raise

        # The figures the graph is holding, not the ones declared above: the two are
        # built from the same budget, and returning the presented copy is what makes
        # that checkable rather than assumed.
        record.presented = pending.halted(PRESENT_WAIT_SECONDS)
        return record

    def answer(self, gate_run_id: str, approval: Approval) -> GateRunRecord:
        """Answer one gate run's interrupt. A yes is the only thing that spends."""
        with self._lock:
            record = self._runs.get(gate_run_id)
            pending = self._pending.get(gate_run_id)
            if record is None or pending is None:
                raise KeyError(gate_run_id)
            if record.status is not GateRunStatus.AWAITING_APPROVAL:
                raise NoLongerWaiting(record)
            # The record is moved *before* the graph is released, and both happen
            # under the lock. Two threads write this record — this one and the gate
            # run's own — and the order has to be decided rather than raced: a run
            # released first could reach a transport failure and settle before this
            # line ran, and the answer would then put a stopped gate run back into
            # flight. Whatever the run thread writes from here on, it writes last.
            if approval.confirmed:
                record.confirmed_by = approval.identity
                record.settle(
                    GateRunStatus.RUNNING,
                    (
                        f"Confirmed by {approval.identity}: the gate run is going "
                        "in the background, under the ceiling that was confirmed "
                        "and aborting rather than exceeding it. It holds this "
                        "bench's case library until it is finished"
                    ),
                )
            else:
                record.settle(GateRunStatus.DECLINED, _declined(approval.reason))
            answered = pending.answer(approval)
        if not answered:
            # The hour ran out in the instant this answer arrived, so the graph has
            # already been told nobody answered. The gate run's own thread settles it
            # as unanswered, which is the honest record: nobody said no.
            raise NoLongerWaiting(record)
        return record


def _declined(reason: str) -> str:
    stated = reason or "declined at the approval interrupt"
    return (
        f"{stated}. Nothing was sent to a reference agent, nothing was spent, and "
        "not one case record was written to: the library is exactly as it was"
    )


def _a_library(directory: Path) -> bool:
    """Whether that directory holds case records this bench could run a gate over.

    A read and never a write: a bench that created the directory in order to answer
    the question would be deciding a deployment's storage layout on a `GET`.
    """
    try:
        return any(directory.glob("*.toml"))
    except OSError:
        return False


def _execute(
    record: GateRunRecord,
    config: BenchConfig,
    served: ServedAgents,
    pending: PendingApproval,
    stack: ExitStack,
    cites: Cites | None,
) -> None:
    """One gate run, on its own thread: the same entry point the command line takes.

    There is one code path to a reference agent and this does not add a second — the
    attestation, the estimate, the halt, registration, the attempt loop and the
    adaptive layer are all reached through `run_calibration`, which is what
    `scripts/gate.py` reaches them through.

    The `finally` is the whole of the lease's release and the equipment's shutdown:
    whatever this run does, the library goes back and the agents come down.
    """
    try:
        _decide(record, config, served, pending, cites)
    except Exception as failure:
        record.settle(
            GateRunStatus.FAILED,
            f"the gate run stopped rather than produced a decision: {failure}",
        )
    finally:
        stack.close()


def _decide(
    record: GateRunRecord,
    config: BenchConfig,
    served: ServedAgents,
    pending: PendingApproval,
    cites: Cites | None,
) -> None:
    """Run the library against the three agents, decide, and write the series back."""
    # Named against the seam's own type rather than passed straight through, so that
    # a signature drifting away from `Approve` is a typecheck failure here and not a
    # gate run that halts and never resumes.
    approve: Approve = pending.approve
    # One ledger for this gate run, and the instruments built against it, on the
    # thread this run happens on. A gate run started from the console is the case
    # the figures matter most for — it is the expensive one, around 830 calls — and
    # until #28 it was the one that carried none, because the clients were built at
    # boot with nothing to report into.
    ledger = UsageLedger()
    try:
        instruments = config.instruments_for(ledger)
    except (KeyError, ValueError) as unusable:
        record.settle(
            GateRunStatus.FAILED,
            (
                f"this gate run's instruments could not be built: {unusable}. "
                "Nothing was sent to the reference agents and nothing was spent"
            ),
        )
        return
    try:
        result = run_calibration(
            cases=record.cases,
            targets=served.targets,
            attestation=record.attestation,
            plant_nonce=served.plant,
            drop_namespace=served.drop,
            approve=approve,
            adjudicator=instruments.adjudicator,
            attacker=instruments.attacker,
            # And no narrator, which is a decision rather than an omission
            # (ADR-0030): a gate run measures the bench and a finding is about a
            # target (ADR-0018), so a narrative here would be prose about the
            # bench's own test equipment that nothing the gate decides can read.
            # `TargetRun.narrations` is `None` on every gate run and says so.
            # The ledger those two report into. One per gate run, for the reason
            # `run_calibration` refuses a reused one: a figure filed against the
            # wrong run is worse than an absent one (ADR-0026).
            usage=ledger,
            rule=config.rule,
            adaptive=config.adaptive,
            # The ceiling on the record, never one re-declared here: the operator
            # confirmed these figures in an earlier request.
            budget=record.budget,
            run_state=record.run_state,
            # The gate run's own id field, never the run id: the two are different
            # artefacts with different readers, and a shared field would let a
            # search for one return the other (ADR-0018).
            trace=TracedRun(
                id=record.gate_run_id,
                gate=True,
                adjudicator_model=config.report.models.adjudicating,
                attacker_model=config.report.models.attacking,
                reference_model=config.report.models.calibration,
            ),
        )
    except BudgetExceeded as abort:
        record.settle(
            GateRunStatus.ABORTED,
            (
                f"{abort}. An episode the ceiling cut short is recorded as "
                "censored, never as resisted, and no reading was stored: a gate run "
                "writes its series back only from a decision it reached"
            ),
        )
        return
    except TargetUnreachable as unreachable:
        record.settle(
            GateRunStatus.FAILED,
            (
                f"{unreachable} This is the bench's own test equipment rather than "
                "anybody's target, so it is a fault in the instrument and not a "
                "result about an agent"
            ),
        )
        return

    if not result.approval.proceeded:
        refused = (
            GateRunStatus.DECLINED if pending.answered else GateRunStatus.UNANSWERED
        )
        record.settle(refused, _declined(result.approval.reason))
        return

    if any(run.registration.refused for run in result.target_runs):
        record.settle(
            GateRunStatus.FAILED,
            (
                "a reference agent did not echo its nonce, so it was never "
                "attacked. The gate is not decided on two agents: D is trivial "
                "minus hardened and monotonicity is read across all three, so this "
                "is equipment to repair rather than a gate that failed"
            ),
        )
        return

    # After the suite and only if it proceeded, so that a declined gate run spends
    # nothing at all — including on the bench's own instrument.
    gold_sets = load_gold_sets(GOLDSET_DIR, record.cases)
    # The boot-built client and deliberately not this run's bound one (#28). These
    # calls happen after `run_calibration` has returned, which is after it closed
    # the run span and pushed the trace: a κ measurement recorded into the ledger
    # here would be a figure the run holds and its trace cannot carry, and a total
    # that disagrees with the trace beside it is worse than one absent from both
    # (ADR-0026).
    adjudicator = config.adjudicator
    assert adjudicator is not None  # `why_not` refused the bench without one
    reliability = measure_reliability(gold_sets, adjudicator)

    try:
        gate = read_gate(
            result.target_runs,
            trivial=served.trivial,
            weak=served.weak,
            hardened=served.hardened,
            reliability=reliability,
            library=result.run_state.library,
            # The rule this bench declares, and never the module default: a gate run
            # decided under one rule and reported under another would be a pass a
            # reader could not re-derive (ADR-0003).
            rule=config.rule,
        )
    except NotAGateRun as ungated:
        record.settle(
            GateRunStatus.NOT_A_GATE_RUN,
            (
                f"this run cannot be gated: {ungated}. Its attempts are recorded "
                "and no reading was stored, because a series written from a run "
                "the rule was never applied to is a series nobody can re-derive"
            ),
        )
        return

    record.gate = gate
    record.written = write_back(record, result, gate, served, config, cites)
    record.settle(
        GateRunStatus.DECIDED,
        (
            f"decided: {gate.decision.outcome}, confirmed by {record.confirmed_by}, "
            f"inside the ceiling that was confirmed. {record.written.stated()}"
        ),
    )
