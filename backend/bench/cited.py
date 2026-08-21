"""The gate run a case library cites, written into the library it was decided over.

[ADR-0021](../../docs/adr/0021-the-console-may-start-a-gate-run.md) left two
questions shut and
[ADR-0023](../../docs/adr/0023-a-gate-run-updates-the-citation-it-earned.md)
opens them: a gate run now updates the **gate citation** the bench carries, and the
**gate run record** is the machine-readable form of that citation rather than a
sidecar nothing points at. This module is the whole of the first half — where the
citation lives, who may write it, and what a gate run that did not pass does to one
that did.

**The citation is rendered off the record, never composed beside it.**
`citation_of` takes the `RecordedGateRun` a gate run produced and reads every field
off it: the outcome, the date, the library version, the document's name and the
record's own name. There is no second reading of a `GateResult` here and no
arithmetic at all, which is what makes the citation and the record unable to
disagree rather than merely observed to agree — the same guarantee the record and the
dated document already had, extended to a third rendering of one reading
(`gate_record.py`).

**It lives in the library, because the library is what it is a claim about.** A
citation says *this bench passed its own gate at eighteen cases, digest 90a8ebcc* —
a claim about a library version, earned by running that library. So it is written
into the case directory the gate run wrote its readings back to, under the same
lease, and a bench reads it from the library it booted with (`app.deployed_bench`).
A citation kept anywhere else is a citation that can drift from the cases it
describes, which is the same argument that puts the decay series on the case's own
record (ADR-0006) and the library on a mounted volume (ADR-0021, condition 4).

**Nothing here loads a case, and no case loader sees this file.** The library is
`*.toml` and this is one `.json` beside them (`library.load_library`), for the same
reason the lease is a dot-prefixed file and not a case (`lease.py`). Writing it does
not move the library's digest, which matters because the digest is what the citation
claims.

**A gate run that left no prose says so as an absence and not as a sentence.**
`RecordedGateRun.document` is `None` for one started from the console, and the words a
reader is given for that are written where they are read — on the screen, and in
`GateCitation.stated()`. A field that were sometimes a file name and sometimes a
paragraph is a field every consumer has to guess about, and the first one to guess
wrong prints the paragraph as a path.

**A gate run of any outcome replaces the citation, and never silently.** `cite`
returns what it displaced, and the caller states it: a failed gate run overwriting a
passing citation is the correct arithmetic — the citation is what the bench last put
itself through, not the best answer it ever got — and it is only safe because the
outcome is a field every surface reads and the replacement is announced by name. The
two alternatives are both wrong and are recorded as rejected in ADR-0023: a stale
pass left in place is a report claiming a certification the bench has since lost, in
the flattering direction, and a citation cleared to nothing states *no gate run is
cited* about a bench that has just measured its own discriminating power and found it
wanting.

**Nothing is deleted.** Only the pointer moves. Every gate run's record survives
where it was written — beside its dated document for a command-line run, in the
library for one from the console — so the citation naming the latest is a choice of
which one a report carries and never a loss of the ones before it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from backend.bench.gate_record import RecordedGateRun
from backend.bench.library import LibraryVersion
from backend.bench.payload import GateCitation, citation
from backend.bench.scorer import GateOutcome

CITED_GATE_RUN = "gate-run.json"
"""What the cited gate run is called inside the library that cites it.

One name and not a dated one, because there is one citation: a directory of them
would be a reader's choice about which gate run a report cites, and that choice is
the arithmetic ADR-0023 settles rather than a file listing. The dated records the
citation points at are the history, and they are never overwritten.
"""


def citation_of(record: RecordedGateRun) -> GateCitation:
    """The citation this gate run earned, read off the record it produced.

    Every field is the record's. The date is the record's `decided_at` truncated to
    the day the citation is stated in — one value, narrowed, and never a second clock
    — and the outcome and the library version are the decision's own. Nothing here
    computes a figure, and nothing here opens a file.
    """
    decision = record.decision
    return GateCitation(
        outcome=GateOutcome(decision.outcome),
        decided_on=datetime.fromisoformat(record.decided_at).date(),
        library=LibraryVersion(
            cases=decision.library.cases, digest=decision.library.digest
        ),
        document=record.document,
        record=record.record,
    )


@dataclass(frozen=True)
class Replaced:
    """What a citation update displaced, so that no citation changes in silence.

    Returned by `cite` and stated by its caller — the terminal prints it, the console
    gate run's own record carries it — because the one thing that makes *the last
    gate run wins* safe is that the loss is announced. A gate run whose outcome is
    worse than the one it replaced is the case this record exists for, and it is not a
    special case in the code: it is the general one, said out loud.
    """

    now: GateCitation
    previous: GateCitation | None

    @property
    def displaced_a_pass(self) -> bool:
        """Whether this update took a passing citation off the bench.

        The reading a caller raises its voice about. Not a branch in `cite` — a
        failed gate run replaces a pass exactly the way it replaces anything else —
        but a fact about what just happened, and the one an operator has to be told.
        """
        return (
            self.previous is not None
            and self.previous.outcome is GateOutcome.PASSED
            and self.now.outcome is not GateOutcome.PASSED
        )

    def stated(self) -> str:
        """The replacement in words, naming what it displaced."""
        if self.previous is None:
            was = "this library cited no gate run before now, so nothing was displaced"
        else:
            was = (
                f"it displaces the gate run of {self.previous.decided_on.isoformat()}, "
                f"which this library cited as {self.previous.outcome.value} at "
                f"{self.previous.library.stated()}. That record is not deleted — it "
                f"is still where it was written, at {self.previous.record}"
            )
        louder = (
            " This bench cited a passing gate run a moment ago and does not now: "
            "every report it signs from here carries the outcome above, and the "
            "citation is what the bench last put itself through rather than the best "
            "answer it ever got (ADR-0023)."
            if self.displaced_a_pass
            else ""
        )
        return (
            f"this library now cites the gate run of {self.now.decided_on.isoformat()} "
            f"as {self.now.outcome.value}, and {was}.{louder}"
        )


def cite(record: RecordedGateRun, library: Path) -> Replaced:
    """Make this gate run the one its library cites, and say what that displaced.

    **Called under the lease the write-back was made under**, by both entry points,
    which is what stops two gate runs interleaving one citation: the lease is on the
    library directory and this writes into it, so the readings and the citation land
    inside one critical section rather than in two a second gate run could slip
    between (ADR-0021, condition 5).

    **After the write-back and never before it.** The citation is a claim about a
    library at a version, and the version it claims is the one the readings were just
    stored against.

    The previous citation is read before the new one lands so that the caller can
    state what it displaced. A file that cannot be read is *no previous citation*,
    which is the same answer an absent one gives: a bench that cannot parse its own
    citation has none, and guessing at a half-written one is how a stale pass would
    survive.
    """
    now = citation_of(record)
    previous = the_citation(library)
    (library / CITED_GATE_RUN).write_text(
        json.dumps(citation(now), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return Replaced(now=now, previous=previous)


def the_citation(library: Path) -> GateCitation | None:
    """The gate run this library cites, or `None` where it cites none.

    Read back out of the shape `payload.citation` wrote — the one serialiser the
    provenance block and the console's own route already share — and never out of
    prose: this opens a `.json` this module wrote and it has no reader for a `.md`
    at all. A dated document is written for a person, and a figure recovered from one
    would break on a rewording (#75, #84).

    **Anything unreadable is the stated absence, not a partial citation.** A missing
    file, an unparsable one, a shape from a future field set: all of them answer
    `None`, and `UNCITED_GATE` is what a reader is then told. The alternative is a
    citation assembled out of whatever keys happened to be present, which is exactly
    how a bench would come to claim an outcome nothing decided.
    """
    try:
        body: Any = json.loads((library / CITED_GATE_RUN).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(body, dict) or not body.get("cited"):
        return None
    try:
        return GateCitation(
            outcome=GateOutcome(body["outcome"]),
            decided_on=date.fromisoformat(body["decided_on"]),
            library=LibraryVersion(
                cases=int(body["library"]["cases"]),
                digest=str(body["library"]["digest"]),
            ),
            document=(None if body["document"] is None else str(body["document"])),
            record=str(body["record"]),
        )
    except (KeyError, TypeError, ValueError):
        return None
