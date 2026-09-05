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
be able to find the whole answer in one place. Since
[ADR-0075](../../docs/adr/0075-a-declared-gap-reaches-the-signed-artefact.md)
the second of them is *declared* in `backend/bench/declared_gap.py` and re-exported
here: the signed artefact carries a block of them, and no module of `backend/bench/`
imports `backend/api/`. What a reader finds here is unchanged — the name resolves,
and the module it resolves into says why it moved. The wait bounds are here for the
same reason and one more: `BenchConfig.approval_wait_seconds` defaults to
`APPROVAL_WAIT_SECONDS`, so the constant has to be importable by the configuration
without dragging a run's state along with it.
"""

from __future__ import annotations

from enum import StrEnum

from backend.bench.declared_gap import DeclaredGap as DeclaredGap

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
