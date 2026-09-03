"""The halt before the first call: a graph interrupt, not a form field.

A run is 180 target calls in the scored layer and up to 96 more in the adaptive
layer, on the operator's endpoint and the operator's inference spend. That is an
irreversible, costly action, so the graph stops in front of it and will not
continue unattended. Per ADR-0007 this is also the project's human-in-the-loop
pattern, which is why it is a real interrupt against a checkpointer rather than a
boolean the caller is trusted to have collected: the run does not proceed because
it *cannot* proceed, not because a code path chose not to.

**What is presented is two figures.** The scored layer exactly, the adaptive layer
as a ceiling, never blended into one and never averaged — `budget.py` carries that
invariant, and this module only surfaces it.

**The suite is a node of its own, after the approval node.** LangGraph re-runs the
interrupting node from its start on resume, so anything above `interrupt()` runs
again. The approval node therefore does nothing but ask, and everything that
spends is on the far side of the edge that the human's answer decides.

**The checkpoint is on disk, and one `ApprovalRun` owns one connection to it**
([ADR-0028](../../docs/adr/0028-the-approval-checkpoint-outlives-the-process.md)).
`APPROVAL_WAIT_SECONDS` gives the human an hour, so the halt has to outlive a
deploy inside that hour, and the answer arrives on a thread that did not invoke the
graph — so the connection is owned by the object rather than by a thread, and
`approval_checkpoints` below says what that costs at the line that pays it.
"""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, TypedDict, cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from backend.graph.budget import BudgetPayload, RunBudget
from backend.observability import Field, Span, traced

CONFIRM_COST: Final = "confirm_cost"
RUN_SUITE: Final = "run_suite"
STOP: Final = "__end__"
"""LangGraph's own `END`, spelled out, because a router has to return a literal."""

CHECKPOINT_DIRECTORY: Final = Path(__file__).resolve().parents[2] / "checkpoints"
"""Where halted runs are kept. A directory, and git-ignored as one — `.gitignore`
carries the pattern and ADR-0028 point 5 the reason."""

DEFAULT_CHECKPOINT_DATABASE: Final = CHECKPOINT_DIRECTORY / "approvals.sqlite"


def approval_checkpoints(database: Path | None = None) -> SqliteSaver:
    """Open a checkpointer over that database, creating it if it is not there.

    **The connection is owned by the `ApprovalRun` that opened it and not by a
    thread** — the decision ADR-0028 records, with the alternatives it beat. What
    belongs here is why the two flags below are what that decision costs.

    `check_same_thread=False` is demanded twice over, and the second time is the
    reason a convenient test would not have found its absence: LangGraph writes the
    checkpoint from its Pregel executor's pool rather than from the caller, so even
    a single-threaded `invoke` uses the connection off the thread that opened it and
    raises `ProgrammingError` before the halt and the answer are on two threads of
    ours at all. Safe because `SqliteSaver` holds a lock across every cursor.

    WAL so that one run reading its own halt is not blocked by another writing one.
    """
    location = DEFAULT_CHECKPOINT_DATABASE if database is None else database
    location.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(location, check_same_thread=False)
    connection.execute("PRAGMA journal_mode=WAL")
    return SqliteSaver(connection)


@dataclass(frozen=True)
class Approval:
    """A human's answer to the interrupt."""

    confirmed: bool
    identity: str
    reason: str = ""
    """Why, when the answer is no. Kept because a declined run is a result about
    the estimate — a figure a user refused is the one piece of evidence that the
    cost display is doing its job."""


Approve = Callable[[BudgetPayload], Approval]
"""How a human is asked. Given what the interrupt surfaced, returns their answer.

A seam rather than an `input()` call, because the same halt is answered from a
terminal here, and from an HTTP request at 6b. Both resume the same graph.
"""


@dataclass(frozen=True)
class ApprovalOutcome:
    """What the approval interrupt decided, and what was put in front of the human."""

    budget: RunBudget
    presented: BudgetPayload
    confirmed: bool
    halted: bool
    """True while the graph is still paused at the interrupt — no answer was ever
    collected. Distinct from a declined run: nobody said no, nobody said anything.
    Both spend nothing, and a caller that treats them as one loses the difference
    between "awaiting a human" and "refused by one"."""

    identity: str = ""
    reason: str = ""

    @property
    def proceeded(self) -> bool:
        return self.confirmed and not self.halted


class ApprovalState(TypedDict):
    """The graph's state: the human's answer, and nothing else.

    Deliberately primitives only. The run's real state lives in `RunState`, which
    the suite node mutates through a closure. Nothing here carries a case, a
    target, a transcript or a callable: this state is checkpointed, and a
    checkpoint is not the place to discover which of a run's records happen to
    survive a serializer.

    It holds no record of whether the suite ran, either. That fact belongs to
    `RunState`, which counts what was spent — a second copy of it here would be a
    checkpointed field that no reader consults and that can disagree with the
    counters.
    """

    confirmed: bool
    identity: str
    reason: str


class ApprovalRun:
    """One run's approval graph: present the cost, halt, and proceed only on a yes."""

    def __init__(
        self,
        budget: RunBudget,
        run_suite: Callable[[], None],
        *,
        thread_id: str | None = None,
        checkpoints: Path | None = None,
    ) -> None:
        """`thread_id` names an existing halt; omitted, this run is a new one.

        Both parameters exist for the same reason: a checkpoint on disk is only
        reachable by something that knows which thread and which database to look
        in, so a run that could not be named could not be resumed after the object
        that halted it was gone, and the durability would be unobservable (ADR-0028).
        """
        self.budget = budget
        self._suite = run_suite
        self.thread_id = thread_id if thread_id is not None else f"run-{uuid.uuid4()}"
        self._config: RunnableConfig = {"configurable": {"thread_id": self.thread_id}}
        self._saver = approval_checkpoints(checkpoints)

        builder = StateGraph(ApprovalState)
        builder.add_node(CONFIRM_COST, self._confirm_cost)
        builder.add_node(RUN_SUITE, self._run_the_suite)
        builder.add_edge(START, CONFIRM_COST)
        builder.add_conditional_edges(
            CONFIRM_COST, self._decided, {RUN_SUITE: RUN_SUITE, STOP: END}
        )
        builder.add_edge(RUN_SUITE, END)
        self._graph = builder.compile(checkpointer=self._saver)

    def __enter__(self) -> ApprovalRun:
        """A context manager because this object now owns an OS resource.

        Before the checkpoint was a file, constructing an `ApprovalRun` and dropping
        it cost nothing, so every caller was free to. It costs a connection now, and
        a `with` is how that stops being something each caller has to remember.
        """
        return self

    def __exit__(self, *exception: object) -> None:
        self.close()

    def close(self) -> None:
        """Release this run's connection. The halt it wrote stays on disk.

        Called for its file handle and not for the checkpoint: a thread per halted
        run is the v1 `api/runs.py` licensed, and a connection per halted run that
        nothing closes is the same cost paid twice.
        """
        self._saver.conn.close()

    def _confirm_cost(self, state: ApprovalState) -> ApprovalState:
        """Surface the estimate and stop. Nothing above the interrupt spends."""
        with traced(Span.CONFIRM_COST, {Field.NODE: Span.CONFIRM_COST}):
            answer = interrupt(self.budget.as_payload())
            return read_answer(answer)

    def _decided(self, state: ApprovalState) -> Literal["run_suite", "__end__"]:
        """The one edge the human's answer decides. Everything that spends is
        past it."""
        return RUN_SUITE if state["confirmed"] else STOP

    def _run_the_suite(self, state: ApprovalState) -> None:
        """The spending, on the far side of the edge the answer decides.

        Returns no state update: what this node did is visible in the run's own
        counters, and the graph has no second opinion to offer about it.

        The span around it is how long the suite took, which is the figure that
        separates a bench working slowly from a bench stuck on one endpoint. The
        node's name is on the span as well as being the span's name, so a reader
        querying by node does not have to know that the two coincide here.
        """
        with traced(Span.RUN_SUITE, {Field.NODE: Span.RUN_SUITE}):
            self._suite()

    @property
    def paused(self) -> bool:
        """Whether the graph is still waiting on the human."""
        return bool(self._graph.get_state(self._config).next)

    def present(self) -> BudgetPayload:
        """Run up to the interrupt and stop there. No target has been called yet."""
        result = self._graph.invoke(
            ApprovalState(confirmed=False, identity="", reason=""),
            self._config,
        )
        interrupts = result.get("__interrupt__")
        if not interrupts:
            raise AssertionError(
                "the approval graph reached the end without halting. A run that "
                "does not stop in front of the spend has no human in its loop "
                "(ADR-0007)."
            )
        return cast(BudgetPayload, interrupts[0].value)

    def resume(self, approval: Approval) -> ApprovalState:
        """Answer the interrupt. The suite runs on a yes and on nothing else."""
        result = self._graph.invoke(
            Command(
                resume={
                    "confirmed": approval.confirmed,
                    "identity": approval.identity,
                    "reason": approval.reason,
                }
            ),
            self._config,
        )
        return cast(ApprovalState, result)


def read_answer(answer: Any) -> ApprovalState:
    """Take the resume value at arm's length. The boundary, so it is public.

    A malformed answer is not a yes. The resume value crosses a checkpoint and will
    one day arrive from an HTTP request, so the one thing this must not do is let
    anything that is not an explicit confirmation read as one — a truthy-looking
    value spending a user's inference budget is the failure to guard against.
    """
    if not isinstance(answer, dict):
        return ApprovalState(
            confirmed=False, identity="", reason="the answer was not a decision"
        )
    return ApprovalState(
        confirmed=answer.get("confirmed") is True,
        identity=str(answer.get("identity", "")),
        reason=str(answer.get("reason", "")),
    )


def run_under_approval(
    budget: RunBudget,
    run_suite: Callable[[], None],
    approve: Approve | None = None,
) -> ApprovalOutcome:
    """Present the cost, halt, and run the suite only if a human confirms.

    `approve` defaults to `None`, and that default is the point: a caller that has
    not said how a human will be asked gets a run that halts and stays halted.
    Nothing is sent, and the outcome says so.
    """
    # The `with` releases the connection and not the checkpoint: a run that halted
    # here is still on disk, and still answerable by something that knows its
    # thread id — which is the half of restart survival issue #61 carries.
    with ApprovalRun(budget, run_suite) as run:
        presented = run.present()

        if approve is None:
            return ApprovalOutcome(
                budget=budget,
                presented=presented,
                confirmed=False,
                halted=True,
                reason="halted at the approval interrupt: nobody was asked",
            )

        final = run.resume(approve(presented))
        return ApprovalOutcome(
            budget=budget,
            presented=presented,
            confirmed=final["confirmed"],
            halted=run.paused,
            identity=final["identity"],
            reason=final["reason"],
        )
