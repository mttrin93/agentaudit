"""One gate run's record, the four refusals in front of it, and the single edge the
citation leaves by.

Split out of `gate_runs.py`. This is what a gate run *is* while it happens —
`GateRunRecord` — together with the vocabulary that describes it: why one may not
start (`NotStartable`, `CannotRunAGate`), where one got to (`GateRunStatus`), what
it wrote back (`WrittenBack`), and who the lease says is holding the library
(`a_holder`). `BenchGateRuns`, the service that drives a record through all of it,
stays in `gate_runs.py`.

**A gate run is not a run, and nothing here is a `RunRecord`.** A run is one pass
over one target and produces rates, intervals and bands about somebody's agent; a
gate run is the whole library against three agents of this project's own
construction and produces a decision about this bench (ADR-0018). They have
different records, different statuses, different routes and no function in common
that takes either: `GateRunRecord` and `RunRecord` never appear in one signature,
which is ADR-0010's discipline applied to a new axis — if you find yourself widening
one to accept both, stop. The split makes that harder to do by accident rather than
easier: the two records are now defined in two modules that do not import each
other.

**`Cites` is the whole of the citation's outbound edge.** A `GateCitation` in,
nothing out, and no decision or record crossing in either direction
([ADR-0023](../../docs/adr/0023-a-gate-run-updates-the-citation-it-earned.md)). It
is declared here, beside the record the citation is derived from, and the function
that calls it is in `gate_runs.py`.

**This module never constructs an `Attestation`** — it receives one, so there is no
line in it that could fill in three booleans on somebody's behalf, and no name in it
is a bypass. That is asserted over the source of every module on this side in
`test_api_gate_runs.py`, which is why the assertion's file list grew with this split
rather than staying pointed at one file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from backend.api.gate_run_equipment import DEPLOYED_LIBRARY
from backend.bench.gate import GateResult
from backend.bench.library import Case
from backend.bench.payload import GateCitation
from backend.bench.registration import Attestation
from backend.graph.budget import BudgetPayload, Layer, RunBudget
from backend.graph.runstate import RunState


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


class Cites(Protocol):
    """The one edge from a gate run back onto the bench a run is measured with.

    A gate run decides whether this instrument discriminates, and after ADR-0023 the
    bench starts citing the one it just made. That is a write from the gate-run side
    onto `ReportConfig.gate`, and it is narrowed to this: **a `GateCitation` in,
    nothing out.** No `GateResult` crosses it, no decision, no per-family figure and
    no record of either — so the widening ADR-0021 forbids is not available here, and
    `BenchRuns` and `GateRunRecord` still never meet in one signature.

    A callable rather than the bench itself for the same reason `Approve` is a
    callable: what this module needs is the one operation, and holding the object
    would give it every other one as well. `None` is a registry nobody wired a bench
    to — the durable citation is still written into the library either way, and the
    next process reads it (`bench/cited.py`, `app.deployed_bench`).
    """

    def __call__(self, citation: GateCitation) -> None: ...


@dataclass(frozen=True)
class WrittenBack:
    """What one gate run wrote to the case library, and where it wrote it.

    Kept on the record because the write-back is the half of a gate run that
    outlives it: the decision is a fact about this bench right now, and the series
    on the case records is what the *next* gate run reads. A run that stored nothing
    says so with an empty tuple rather than by having no field.

    **Three writes since ADR-0023, and all three are reported here.** The readings,
    this gate run's own record as fields, and the citation the bench carries from now
    on. The last of those is the one an operator has to be told about rather than be
    able to look up, because it replaced something: `cited` is that sentence.
    """

    library: Path
    readings: int
    """Case records this run appended a reading to — one per case that ran."""

    unread: tuple[str, ...]
    """Cases no attempt was spent on, so no reading exists to store. Never a zero:
    a case that did not run has no `D`."""

    retired: tuple[str, ...]
    """Cases the rule retired on this run, marked and kept and never deleted."""

    record: str
    """The file name this gate run's own record was written under, in that library.

    The console's counterpart to the dated `.json` a command-line gate run leaves
    beside its document: the figures as fields, in the library, so the citation
    written next to it has somewhere to point (ADR-0023). Never overwritten by a
    later gate run — the name carries this run's stamp — because the citation moving
    is a choice of which record a report names and not a loss of the ones before it.
    """

    cited: str
    """What citing this gate run did to the one this library cited before it.

    On the record rather than only in a log, because the whole of what makes *the
    last gate run wins* safe is that a replacement is announced: a failing gate run
    displacing a passing citation is the case this field exists for
    (`cited.Replaced.stated`).
    """

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
            f"case the field caught up with is evidence that the field moved. This "
            f"run's own figures are in {self.record} beside them, and {self.cited}"
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
    roles: tuple[str, str, str]
    """The three agents' names in construction order: hardened, then weak, then trivial.

    `agents` is whatever order the equipment served them in, which is the equipment's
    business and is not an order anything may report in. This is the order the whole
    bench reads the three in — cool to warm, floor to ceiling of the contrast, the
    order `GateResult.rates` is built in — carried as three names because the record
    holds names and the roles are the served equipment's own answer, never inferred
    from a name.
    """
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


class NoLongerWaiting(RuntimeError):
    """An answer to a gate run's interrupt that is not waiting for one any more."""

    def __init__(self, record: GateRunRecord) -> None:
        super().__init__(
            f"gate run {record.gate_run_id} is {record.status} and is no longer "
            "waiting on an answer. An interrupt is answered once"
        )
