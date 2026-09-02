"""The vocabulary one run is described in: how long it waits, where it got to, and
what it declared away.

The lowest of the three modules `runs.py` was split into, and it is lowest because
nothing here depends on anything else in `backend/api/`. A wait bound, a status and
a declared gap are all facts about a run that can be stated before a run, a plan or
a configuration exists — which is what lets `run_config.py` and `run_state.py` both
import from here without either importing the other.

**Why these three sit together rather than beside the record that carries them.**
`RunStatus` and `DeclaredGap` are the two enumerations the report and the console
both read, and a reader who wants to know what a run can *say about itself* should
be able to find the whole answer in one place. The wait bounds are here for the
same reason and one more: `BenchConfig.approval_wait_seconds` defaults to
`APPROVAL_WAIT_SECONDS`, so the constant has to be importable by the configuration
without dragging a run's state along with it.
"""

from __future__ import annotations

from enum import StrEnum

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


FINISHED_WAIT_SECONDS = 30.0
"""How long a declining request waits for the worker to finish with the record.

Generous for what it waits on: a declined run sends nothing, so the worker has only
to carry the refusal back out of the graph. The bound exists so that a worker which
somehow never finishes cannot hold an HTTP request open, not because the wait is
expected to be long.
"""
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

    @property
    def in_flight(self) -> bool:
        """Whether a run in this state is still going, or has stopped for good.

        Asked by anything that has to tell *not yet* from *not ever*: a caller told
        to poll a run that ended without a report would poll for the lifetime of the
        process. Written as the two states a run can leave rather than as the six it
        cannot, so that a seventh terminal state is terminal on the day it is added
        rather than on the day somebody remembers this list.
        """
        return self in {RunStatus.AWAITING_APPROVAL, RunStatus.RUNNING}


class DeclaredGap(StrEnum):
    """Something the caller's own setup did not provide, and the family it costs.

    The second surface of the concept `scripts/probe_target.py` keeps as
    `OperatorGap`, and deliberately not `NotMeasurable`: that type is the library's
    answer to a *case precondition* a target cannot meet, decided before an attempt
    is spent. These are the caller's gaps — the bench cannot detect either of them,
    no attempt is skipped for them, and the family is not run at all rather than
    measured at zero. A family missing from a run with no reason beside it is a
    reader guessing which of three answers it was.

    Two enums rather than one shared one, and the duplication is the smaller cost.
    `OperatorGap` says *pass `--adjudicator-model`* and *this was a
    `--deterministic-only` run*: its prose names command-line flags, which is right
    for the surface it was written for and wrong in an HTTP response. It also
    carries two members about reading a rate that was measured, which is a thing
    this surface does not do yet. Sharing them would mean rewriting a script's
    user-facing text to fit a caller who is not at a terminal.
    """

    NO_ADJUDICATOR = "no_adjudicator"
    NOTE_NOT_PLANTED = "note_not_planted"
    NONCE_NOT_PLANTED = "nonce_not_planted"
    FAMILY_SWITCHED_OFF = "family_switched_off"

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
            case DeclaredGap.NONCE_NOT_PLANTED:
                return (
                    "not run: this family extracts the registration nonce, and the "
                    "caller started this run without planting it. A canary that is "
                    "nowhere in the target cannot leak, so every attempt would "
                    "report resisted against an attack that was never possible"
                )
            case DeclaredGap.FAMILY_SWITCHED_OFF:
                return (
                    "not run: this family was switched off for this bench, so no "
                    "case in it was attempted and no episode opened against it. "
                    "Nothing here is a reading about the target — a family that was "
                    "not asked is not a family that held"
                )
