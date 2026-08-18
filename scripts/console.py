"""The terminal side of a run: what is asked, how it is asked, and how a rate prints.

Held in one place because there is more than one script that reaches a target —
`calibrate.py` runs the reference agents, `probe_target.py` runs somebody's own —
and the consent mechanism must not exist twice. Two copies of the attestation is
two places for a `--yes` to appear in, and ADR-0007 is explicit that a consent
mechanism with a flag to skip it is a convenience feature after all.

Nothing here decides anything. It asks, it formats, and it hands back what the
human said, so that the difference between the two scripts is which target they
point at rather than what they ask before pointing.
"""

import sys
from decimal import Decimal

from backend.bench.registration import Attestation
from backend.bench.rule import DECLARED_RULE
from backend.bench.scorer import Rate
from backend.graph.approval import Approval, Approve
from backend.graph.budget import BudgetPayload, CallPrice

EXIT_WITHHELD = 2
"""Exit code when the attestation was not made. Not an error — a refusal."""

EXIT_DECLINED = 3
"""Exit code when the estimated cost was not confirmed at the interrupt."""

EXIT_ABORTED = 4
"""Exit code when the run hit its declared ceiling and stopped."""

REPLY_EXCERPT = 400


def price(per_call: str | None, currency: str) -> CallPrice | None:
    """The operator's price per call, or `None` for a run they did not price."""
    if per_call is None:
        return None
    return CallPrice(per_call=Decimal(per_call), currency=currency)


def attest(identity: str) -> Attestation | None:
    """Collect the three statements, one question each.

    One question each rather than one question for all three, because the record
    has a field per statement and a single `[y/N]` cannot fill them honestly.
    Asking separately is also the only way the type's refusal is ever reached on
    the path a human takes — a partial attestation can be *given* here, and is
    then declined with the statement that was withheld named back.
    """
    if not identity.strip():
        print("An attestation records who made it, so --identity cannot be blank.")
        return None

    print(
        f"Attestation, as {identity}. All three are required before anything is sent."
    )
    answers = {
        field: confirmed(f"  · {wording}? [y/N] ")
        for field, wording in Attestation.STATEMENTS
    }

    try:
        return Attestation(identity=identity, **answers)
    except ValueError as refusal:
        print(f"\n{refusal}")
        return None


def terminal_approval(identity: str) -> Approve:
    """Answer the graph's interrupt from the terminal.

    The same halt is answered by an HTTP request at 6b. Only this function
    changes; the graph does not.
    """

    def approve(presented: BudgetPayload) -> Approval:
        print("\nEstimated cost of this run, before the first call:")
        for line in presented["presented"]:
            print(line)
        if confirmed("\nProceed and spend this? [y/N] "):
            return Approval(confirmed=True, identity=identity)
        return Approval(
            confirmed=False,
            identity=identity,
            reason="declined at the approval interrupt",
        )

    return approve


def confirmed(prompt: str) -> bool:
    """A yes, and only from a human at a terminal.

    A run that is not being watched has nobody to consent on its behalf, so a
    piped or absent stdin is a no rather than a default.
    """
    if not sys.stdin.isatty():
        print(f"{prompt}\n  no terminal to ask — treating as no")
        return False
    return input(prompt).strip().lower() in {"y", "yes"}


def pause(prompt: str) -> None:
    """Wait for a human to do something off-machine, then carry on.

    Not a consent question and deliberately not `confirmed`: what it waits for is
    an edit the bench cannot make and cannot check, so there is no answer to
    record. Without a terminal it does not block, because the run has already
    been refused by then and hanging would be the wrong failure.
    """
    if not sys.stdin.isatty():
        print(f"{prompt}\n  no terminal to wait at — carrying on")
        return
    input(prompt)


def rate_line(rate: Rate) -> str:
    """One failure rate, with the counts it came from and its interval."""
    interval = rate.interval
    return (
        f"{rate.value:.2f} ({rate.successes}/{rate.attempts}), "
        f"Wilson {DECLARED_RULE.interval_confidence:.0%} "
        f"[{interval.lower:.3f}, {interval.upper:.3f}]"
    )


def excerpt(text: str) -> str:
    """As much of a reply as a reader needs, with the full length stated."""
    collapsed = " ".join(text.split())
    if len(collapsed) <= REPLY_EXCERPT:
        return collapsed
    return (
        f"{collapsed[:REPLY_EXCERPT]}… "
        f"[{len(collapsed)} chars, full transcript recorded]"
    )
