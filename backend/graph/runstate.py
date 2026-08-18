"""The bench's short-term memory: where a run is, what it has found, what it has spent.

A run state is carried as a plain object here, in the module PLAN.md §7 assigns it.
Ticket #5 gives it the LangGraph state that the approval interrupt halts on, and
#13 adds the library version and the budget ceiling; nothing here assumes either
has happened yet.
"""

from dataclasses import dataclass, field

from backend.bench.contract import Transcript
from backend.bench.evaluator import Verdict
from backend.bench.library import Family


@dataclass(frozen=True)
class Attempt:
    """One execution of one case against one target, with the evidence behind
    its verdict."""

    case_id: str
    family: Family
    """Which family this attempt counts towards.

    Carried on the attempt rather than looked up from the case later, because a
    rate is per family per agent and every count that forgets its family is a
    count that can be pooled across six of them by accident.
    """

    target_name: str
    index: int
    transcript: Transcript
    verdict: Verdict


@dataclass(frozen=True)
class Position:
    """Where the run is in the library."""

    target_name: str
    case_id: str
    attempt_index: int


@dataclass
class RunState:
    position: Position | None = None
    attempts: list[Attempt] = field(default_factory=list)
    calls_spent: int = 0

    def enter(self, target_name: str, case_id: str, attempt_index: int) -> None:
        self.position = Position(target_name, case_id, attempt_index)

    def record_call(self, sends: int = 1) -> None:
        """Count what an exchange put on the wire, retries included.

        Every send reaches the operator's endpoint on the operator's inference
        budget, so a retried message costs what it cost. Attempts are counted
        separately, and deliberately are not this number: the budget #5 enforces
        and the denominator of a rate measure different things.
        """
        self.calls_spent += sends

    def record(self, attempt: Attempt) -> None:
        self.attempts.append(attempt)

    @property
    def succeeded_attempts(self) -> list[Attempt]:
        """The attempts whose verdict was `succeeded`.

        Deliberately not called findings: a finding is a verdict *plus* its
        narrative — reason, article, external identifier, remediation, exposure —
        and the judge that produces the narrative arrives in #8.
        """
        return [a for a in self.attempts if a.verdict is Verdict.SUCCEEDED]
