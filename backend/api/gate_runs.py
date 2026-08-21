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

**A gate run is not a run, and nothing here is a `RunRecord`.** A run is one pass
over one target and produces rates, intervals and bands about somebody's agent; a
gate run is the whole library against three agents of this project's own
construction and produces a decision about this bench (ADR-0018). They have
different records, different statuses, different routes and no function in common
that takes either: `GateRunRecord` and `RunRecord` never appear in one signature,
which is ADR-0010's discipline applied to a new axis — if you find yourself
widening one to accept both, stop.

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

**The reference agents may be absent, and then this bench states it.** They are
test equipment served by a different application (`backend/targets/reference`) and
never reach a user, so a deployment that does not ship them cannot run a gate. The
equipment is therefore a seam that can be *missing* — `shipped_agents` returns
`None` when the module is not importable — and the console reads the refusal and
offers no control rather than failing when one is pressed.

**Nothing here reads a document.** The per-family figures a gate run produces —
the three reference agents' rates and each family's `D` — are on the `GateResult`
this module holds in memory, put there by `read_gate` over the attempts that were
just made. A route that parsed the dated Markdown a command-line run leaves would
break on a rewording, and a gate run started here has the figures already.
"""

from __future__ import annotations

import secrets
import threading
import uuid
from collections.abc import Callable, Iterator, Sequence
from contextlib import AbstractContextManager, ExitStack, contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from backend.api.runs import PRESENT_WAIT_SECONDS, BenchConfig, PendingApproval
from backend.bench.admission import admitted_library
from backend.bench.calibration import CalibrationResult, PlantNonce, run_calibration
from backend.bench.contract import TargetConfig, TargetUnreachable
from backend.bench.gate import GateResult, NotAGateRun, read_gate
from backend.bench.goldset import load_gold_sets, measure_reliability
from backend.bench.lease import LibraryBusy, held_by, holding_the_library
from backend.bench.library import Case, LibraryVersion
from backend.bench.registration import Attestation
from backend.bench.retirement import (
    RetirementDecision,
    live_library,
    readings_of,
    store,
)
from backend.graph.approval import Approval, Approve
from backend.graph.budget import (
    BudgetExceeded,
    BudgetPayload,
    CallPrice,
    Layer,
    RunBudget,
)
from backend.graph.runstate import RunState

GOLDSET_DIR = Path(__file__).resolve().parents[1] / "goldset"
"""The hand-labelled transcripts a judged family's κ is measured against.

Read from the image rather than from the library's own directory, because a gold set
is not a case: it is the reference a judged family's reliability is measured on and
it is labelled before any user sees the bench (CONTEXT.md). A gate run writes to the
case records and never to these.
"""

DEPLOYED_LIBRARY = Path("/var/lib/agentaudit/cases")
"""Where a deployed bench keeps the case library a gate run may write to.

**One declared path, outside the image, and it is a decision rather than a
convenience.** A gate run's write-back is evidence: the decay series a retirement is
re-derived from, and the retirement itself. Written inside the container it would be
gone at the next redeploy, and a bench that had retired a case would come back with
it live again and no record that it ever went — which is the state a reader of the
library cannot detect. So the deployment mounts a volume here, `deployed_bench`
seeds it once from the image's own admitted library if it is empty, and a bench with
nothing mounted declares **no writable library** and runs no gate at all.

Not read from the environment, deliberately: no module of this package is an
environment reader (ADR-0020), and a path that could be pointed anywhere by a
variable is a path a redeploy can silently change. It is a mount point, which is the
one place a deployment already has to say something about storage.
"""


def seeded_library(mount: Path, seed: Path) -> Path | None:
    """The mounted case library, seeded once from the image, or `None` if none is
    mounted.

    Three states and they are three different facts. **No mount** is a deployment
    that declared no storage: it gets `None`, runs no gate, and says so — never a
    silent write into the image. **An empty mount** is a first boot against a fresh
    volume: the image's own admitted library is copied in once, because a bench whose
    library is empty has nothing to run and nothing to serve. **A mount with records
    in it** is the library this deployment has been accumulating, and it is left
    exactly as it is — a seed written over a series would erase the decay history
    every retirement is re-derived from, which is the one thing here that cannot be
    recomputed.

    Copied file by file rather than by any tree copy, so that what lands is case
    records and nothing else: no lease left behind by a previous run, no document,
    nothing that is not a `*.toml` this bench wrote itself.
    """
    if not mount.is_dir():
        return None
    if not any(mount.glob("*.toml")):
        for record in sorted(seed.glob("*.toml")):
            (mount / record.name).write_text(
                record.read_text(encoding="utf-8"), encoding="utf-8"
            )
    return mount


@dataclass(frozen=True)
class ServedAgents:
    """The three reference agents, served, and the roles they were served under.

    The roles are three named fields rather than an order, for the reason
    `read_gate` takes them as required keyword arguments: `D` is trivial minus
    hardened and is not symmetric, so a call site that could pass them positionally
    could invert the bench's central claim and report a broken instrument as a
    working one.
    """

    targets: tuple[TargetConfig, ...]
    plant: PlantNonce
    trivial: str
    weak: str
    hardened: str

    measured_the_field: bool
    """Whether the model these three ran on was the field, or a stub fixture.

    Answered by whatever served them, because that is what holds the `ModelConfig`,
    and carried here so that the write-back can record it on every reading it stores
    (ADR-0022). Not derived from the declared model string in this module: the answer
    is a fact about a closed `Provider` enum which lives in `backend/targets/`, and
    this module reaches that package through the equipment seam and an import that is
    allowed to fail — never at module scope.

    Required rather than defaulted, on the same terms as the three roles above: the
    permissive answer is the one that lets the rule retire a case, so equipment that
    could leave it out could retire a library on a run that spent nothing.
    """


Equipment = Callable[[], AbstractContextManager[ServedAgents]]
"""How a gate run gets hold of the three reference agents while it runs.

A callable that serves them and takes them down again, so that the equipment is a
seam rather than an import: it can be missing, which is the case a deployment that
ships no test equipment is in, and it can be substituted, which is how this is
tested without a model.
"""


def shipped_agents(model: str) -> Equipment | None:
    """The three reference agents this deployment ships, or `None` if it ships none.

    The import is inside the function and its failure is an answer rather than an
    error: `backend/targets/reference` is test equipment that never reaches a user,
    so a build that leaves it out is a legitimate deployment which cannot run a gate
    — and the console has to be able to say so rather than break on it.

    `model` is the reference agents' declared model, off the record that declares it
    (`DeclaredModels.calibration`), and never a literal here. The bearer token is
    issued inside `served`, once per gate run, because these endpoints exist for the
    length of one and a token minted at boot would outlive every run that used it.
    """
    try:
        from backend.targets.reference.hardened import HARDENED
        from backend.targets.reference.model import ModelConfig, measures_the_field
        from backend.targets.reference.operator import nonce_planter
        from backend.targets.reference.server import (
            ReferenceConfig,
            create_reference_app,
        )
        from backend.targets.reference.serving import serve
        from backend.targets.reference.tools import DECLARED_TOOL_NAMES
        from backend.targets.reference.trivial import TRIVIAL
        from backend.targets.reference.weak import WEAK
    except ImportError:
        return None

    @contextmanager
    def served() -> Iterator[ServedAgents]:
        """All three, on an ephemeral port, for the length of one gate run.

        All three and never fewer: `D` is trivial minus hardened and monotonicity is
        read across all three, so a gate on two agents is not a smaller gate but a
        different and undeclared one. There is no argument here that could ask for a
        subset.
        """
        auth_token = secrets.token_urlsafe(16)
        app = create_reference_app(
            ReferenceConfig(model=ModelConfig.parse(model), auth_token=auth_token)
        )
        with serve(app) as base_url:
            yield ServedAgents(
                measured_the_field=measures_the_field(ModelConfig.parse(model)),
                targets=tuple(
                    TargetConfig(
                        name=agent.name,
                        url=f"{base_url}/reference/{agent.name}/messages",
                        auth_token=auth_token,
                        agent_type="assistant",
                        # The reference agents expose their tool calls and declare
                        # the document tools, which is what makes scope creep and
                        # halt defeat measurable against them at all (ADR-0004).
                        exposes_tool_calls=True,
                        declared_tools=DECLARED_TOOL_NAMES,
                    )
                    for agent in (TRIVIAL, WEAK, HARDENED)
                ),
                plant=nonce_planter(base_url),
                trivial=TRIVIAL.name,
                weak=WEAK.name,
                hardened=HARDENED.name,
            )

    return served


@dataclass(frozen=True)
class GateRunBench:
    """What a gate run on this bench needs, and the two ways it may be absent.

    Its own record beside `BenchConfig` rather than four more fields on it, because
    none of this is what a *run* is measured with: a bench that can serve every
    route under `/runs` and cannot run a gate is a normal deployment, and a bench
    that can run a gate has said two extra things about itself.

    Both fields default to absent, which is what every bench in the test suite and
    every bench that declared nothing is: a gate run is the one operation on this
    surface that spends 830 calls and writes to the library, and it is not something
    a deployment gets by omission.
    """

    library: Path | None = None
    """The case library directory a gate run reads and writes back to.

    A directory and not the loaded cases, because the write-back is per record: the
    reading a retirement is re-derived from has to be on the case's own file
    (`retirement.store`). `None` is a bench that runs no gate, and it is the honest
    answer for a deployment with nothing durable to write to.
    """

    equipment: Equipment | None = None
    """How the three reference agents are served, or `None` where they are absent.

    Absent is not an error: they are test equipment that never reaches a user, so a
    deployment can legitimately not ship them, and the console states it and offers
    no start control.
    """


class NotStartable(StrEnum):
    """Why a gate run may not start on this bench right now, as a name.

    Four members and four different facts, and the caller is told which. Two are
    about how the bench was built and two are about this moment — a screen that
    could not tell them apart would offer *try again later* to an operator whose
    deployment ships no reference agents, and *this deployment cannot* to one who is
    merely second in the queue.
    """

    NO_REFERENCE_AGENTS = "no_reference_agents"
    NO_WRITABLE_LIBRARY = "no_writable_library"
    NO_ADJUDICATOR = "no_adjudicator"
    ALREADY_IN_FLIGHT = "already_in_flight"

    def stated(self) -> str:
        """What this refusal means, and what would change it.

        No fallback branch: a fifth member has to fail the typecheck rather than
        print as a name with nothing said about it.
        """
        match self:
            case NotStartable.NO_REFERENCE_AGENTS:
                return (
                    "this deployment does not ship the three reference agents, so "
                    "there is nothing for a gate run to be decided over. They are "
                    "test equipment that never reaches a user — the gate is the "
                    "contrast between a hardened, a weak and a trivial agent of "
                    "known construction — and a build that leaves them out is a "
                    "legitimate deployment that cannot run a gate. The last gate "
                    "run this bench cites was made where they are shipped, and the "
                    "citation is still a fact about this instrument"
                )
            case NotStartable.NO_WRITABLE_LIBRARY:
                return (
                    "this bench has no case library it may write to, and a gate run "
                    "writes: it appends a discrimination reading to every case "
                    "record it reads and marks retired what the rule retires. A "
                    "run whose write-back landed inside a container image would "
                    "lose the series a retirement is re-derived from at the next "
                    "redeploy, so a deployment declares the library at "
                    f"{DEPLOYED_LIBRARY} and a deployment that declares none runs "
                    "no gate"
                )
            case NotStartable.NO_ADJUDICATOR:
                return (
                    "this bench has no adjudicating instrument configured, and the "
                    "gate is decided over six families of which two reach their "
                    "verdicts by adjudication. Without one they are not fit to "
                    "report and are excluded, which leaves four fit families and a "
                    "gate that cannot be decided (ADR-0015) — 830 calls to reach an "
                    "answer that was arithmetic before the first one was sent"
                )
            case NotStartable.ALREADY_IN_FLIGHT:
                return (
                    "a gate run already holds this case library, and one runs at a "
                    "time on one library: it reads every case record and writes "
                    "back to every one of them, so two overlapping runs would "
                    "decide a retirement off a series missing a reading. Nothing "
                    "has been sent and nothing has been spent. The holder is named "
                    "on the lease"
                )


class CannotRunAGate(RuntimeError):
    """A gate run that was asked for and may not happen, with the reason named.

    Carries the `NotStartable` as well as the sentence, because the caller branches
    on one and a person reads the other — and because two of the four are permanent
    facts about the deployment while two are about right now.
    """

    def __init__(self, refusal: NotStartable, detail: str = "") -> None:
        super().__init__(f"{refusal.stated()}{f'. {detail}' if detail else ''}")
        self.refusal = refusal


class GateRunStatus(StrEnum):
    """Where a gate run is, in the words its own record keeps.

    Not `RunStatus`, and the difference is not cosmetic. A run *completes* and has a
    report; a gate run is **decided** and has an outcome — passed, failed or not
    decided — and there is no member here that a run could be in and no member
    there that a gate run could be in. Two enums, so nothing can hold either.
    """

    AWAITING_APPROVAL = "awaiting_approval"
    DECLINED = "declined"
    UNANSWERED = "unanswered"
    RUNNING = "running"
    DECIDED = "decided"
    NOT_A_GATE_RUN = "not_a_gate_run"
    ABORTED = "aborted"
    FAILED = "failed"

    @property
    def in_flight(self) -> bool:
        """Whether this gate run is still going, or has stopped for good."""
        return self in {GateRunStatus.AWAITING_APPROVAL, GateRunStatus.RUNNING}


@dataclass(frozen=True)
class WrittenBack:
    """What one gate run wrote to the case library, and where it wrote it.

    Kept on the record because the write-back is the half of a gate run that
    outlives it: the decision is a fact about this bench right now, and the series
    on the case records is what the *next* gate run reads. A run that stored nothing
    says so with an empty tuple rather than by having no field.
    """

    library: Path
    readings: int
    """Case records this run appended a reading to — one per case that ran."""

    unread: tuple[str, ...]
    """Cases no attempt was spent on, so no reading exists to store. Never a zero:
    a case that did not run has no `D`."""

    retired: tuple[str, ...]
    """Cases the rule retired on this run, marked and kept and never deleted."""

    def stated(self) -> str:
        """The write-back as the record states it."""
        retired = (
            f"{len(self.retired)} case(s) marked retired: {', '.join(self.retired)}"
            if self.retired
            else "no case was retired: the rule needs two consecutive runs on one "
            "model below the floor, and one run below it is not two"
        )
        return (
            f"{self.readings} reading(s) appended to the case records in "
            f"{self.library}, and {retired}. Marked and never deleted, because a "
            "case the field caught up with is evidence that the field moved"
        )


@dataclass
class GateRunRecord:
    """One gate run: what authorised it, what it was estimated at, what it decided.

    Deliberately not a `RunRecord`. There is no target on it and no report — the
    subject is this bench — and `gate` holds a `GateResult`, which is the one thing
    a target's record may never carry (ADR-0018). The budget, the run state and the
    library it holds are all on the record for `RunRecord`'s reason: the ceiling the
    run is held to has to be the one the operator was shown.
    """

    gate_run_id: str
    attestation: Attestation
    library: Path
    cases: tuple[Case, ...]
    agents: tuple[str, ...]
    budget: RunBudget
    run_state: RunState
    presented: BudgetPayload
    recorded_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    """When this gate run went on the record: the attestation taken, the estimate
    declared, the library held. Before anything was served an attempt."""

    status: GateRunStatus = GateRunStatus.AWAITING_APPROVAL
    statement: str = (
        "halted at the approval interrupt: nothing has been sent to a reference "
        "agent, nothing has been spent, and not one case record has been written "
        "to. None of that happens until this estimate is answered, and answering "
        "anything but yes leaves the library exactly as it is"
    )
    confirmed_by: str = ""
    gate: GateResult | None = None
    """What this gate run decided, once it has. Every per-family figure a reader
    needs is on it, in memory, put there by `read_gate` over the attempts that were
    just made — never read back out of a document."""

    written: WrittenBack | None = None

    @property
    def spent(self) -> dict[Layer, int]:
        """Calls spent, per layer and never summed (ADR-0007, ADR-0010)."""
        return dict(self.run_state.spent)

    def settle(self, status: GateRunStatus, statement: str) -> None:
        """Move the gate run to its next state, and say in words what that is."""
        self.status = status
        self.statement = statement


def a_holder(attestation: Attestation, gate_run_id: str) -> str:
    """Who the lease says is holding the library. A person and a gate run, both."""
    return f"{attestation.identity}, gate run {gate_run_id} from the console"


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

    def __init__(self, config: BenchConfig, bench: GateRunBench) -> None:
        self._config = config
        self._bench = bench
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
                args=(record, self._config, served, pending, stack),
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
                        f"confirmed by {approval.identity}: the gate run is going "
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


class NoLongerWaiting(RuntimeError):
    """An answer to a gate run's interrupt that is not waiting for one any more."""

    def __init__(self, record: GateRunRecord) -> None:
        super().__init__(
            f"gate run {record.gate_run_id} is {record.status} and is no longer "
            "waiting on an answer. An interrupt is answered once"
        )


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
        _decide(record, config, served, pending)
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
) -> None:
    """Run the library against the three agents, decide, and write the series back."""
    # Named against the seam's own type rather than passed straight through, so that
    # a signature drifting away from `Approve` is a typecheck failure here and not a
    # gate run that halts and never resumes.
    approve: Approve = pending.approve
    try:
        result = run_calibration(
            cases=record.cases,
            targets=served.targets,
            attestation=record.attestation,
            plant_nonce=served.plant,
            approve=approve,
            adjudicator=config.adjudicator,
            attacker=config.attacker,
            rule=config.rule,
            adaptive=config.adaptive,
            # The ceiling on the record, never one re-declared here: the operator
            # confirmed these figures in an earlier request.
            budget=record.budget,
            run_state=record.run_state,
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
    record.written = _write_back(record, result, gate, served, config)
    record.settle(
        GateRunStatus.DECIDED,
        (
            f"decided: {gate.decision.outcome}, confirmed by {record.confirmed_by}, "
            f"inside the ceiling that was confirmed. {record.written.stated()}"
        ),
    )


def _write_back(
    record: GateRunRecord,
    result: CalibrationResult,
    gate: GateResult,
    served: ServedAgents,
    config: BenchConfig,
) -> WrittenBack:
    """Append this run's `D` to every case record it read, and retire what retires.

    After the decision and never before it: what a case scored is stored whatever
    the gate answered, and the rule that retires one is read over two runs rather
    than over this one. Written to the case records by the run that measured them, so
    the series a retirement is re-derived from is the case's own — and written under
    the lease this gate run has held since before it read them.

    The models are read off the record that declares them (`DeclaredModels`) rather
    than named here: a reading stored under a model identifier this module invented
    would be a decay series about a pair of models nobody declared (ADR-0012).
    """
    runs = {run.target.name: run for run in result.target_runs}
    history = readings_of(
        record.cases,
        hardened=runs[served.hardened],
        weak=runs[served.weak],
        trivial=runs[served.trivial],
        model=config.report.models.calibration,
        # Whether the run measured the field, from the equipment that served the
        # agents rather than from the declared string: a reading taken on a stub
        # fixture is stored, marked, and retires nothing (ADR-0022).
        measured_the_field=served.measured_the_field,
        ran_on=datetime.now(tz=UTC).date(),
        # The families the gate did not decide on. A reading from one is stored and
        # the rule is not applied to it: retirement declines on a family the bench
        # cannot vouch for (ADR-0016).
        excluded=gate.decision.excluded_families,
        adjudicator=config.report.models.adjudicating,
    )
    decisions: Sequence[RetirementDecision] = store(
        record.library, history, config.rule
    )
    return WrittenBack(
        library=record.library,
        readings=len(history.readings),
        unread=history.unread,
        retired=tuple(decision.case_id for decision in decisions if decision.retires),
    )
