"""The two answers a run nobody is sitting in front of gives: who authorised it,
and what bounds it.

A terminal run asks a person two questions before it sends anything — the three
attestation statements, and the estimate — and `scripts/console.py` is the one place
either is asked, so that a `--yes` has nowhere to appear (ADR-0007). A run inside
somebody else's CI has nobody to ask, and the answer this module implements is not a
flag that skips either question: it is the same two questions, answered in a file the
caller's own repository holds under review, by an identity the runner authenticates
([ADR-0065](../../docs/adr/0065-a-ci-attestation-is-committed-prose-by-a-named-actor.md)).

**Nothing here is a second consent mechanism.** `committed_attestation` constructs the
same `Attestation` a terminal builds and reaches the same `__post_init__`, which is
already impossible to satisfy incompletely; `ceiling_approval` returns the same
`Approve` the graph's interrupt takes, which is the second implementation of a type
written for two (`approval.Approve`). Neither adds an argument to `console.attest`,
and `console.confirmed` still treats a run with no terminal as a no.

**Both fail closed, and the failures are the tests worth having.** An attestation that
does not name this run's target is refused before the library is even loaded; a
declared spend ceiling on a run whose calls were never priced is a ceiling that cannot
be compared, so it declines rather than proceeding on a comparison it did not make.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from backend.bench.registration import Attestation
from backend.graph.approval import Approval, Approve
from backend.graph.budget import NOT_PRICED, BudgetPayload, CallPrice

TARGET_KEY = "target"
"""The word that introduces the endpoint a committed attestation is made against.

A key rather than prose, because this one line is compared and not read: the run
refuses unless the target it is about to attack is the target written here, and a
sentence a reader has to interpret is not a thing a comparison can be made against.
"""

ITEM = "- "
"""What begins one statement. A list, so that each statement is a whole item.

The whole item is compared, never a substring of the document, and that is the
difference between prose and a checkbox: *I am not authorised to test this endpoint*
contains the first statement and is not it.
"""


class AttestationNotCommitted(ValueError):
    """The committed document does not authorise this run against this target.

    A `ValueError` like the refusal `Attestation` itself raises, because a caller
    that catches one to refuse a run wants both: an attestation missing a statement
    and an attestation made about somebody else's endpoint are the same answer —
    nothing may be sent — and only the printed sentence differs.
    """


def committed_attestation(document: str, identity: str, target: str) -> Attestation:
    """The attestation a caller's repository commits, made by a named actor.

    `document` is the committed prose, `identity` is who the runner says is running —
    `github.actor`, an authenticated identity rather than a name typed at a prompt —
    and `target` is the endpoint or callback this run is about to attack.

    **The target is checked before anything else and is the whole of the binding.**
    A document that names another endpoint refuses: without that check, a committed
    attestation would authorise a workflow rather than a run against a target, and an
    input swapped in a later commit would point the same three statements at an
    endpoint nobody attested to (ADR-0065 §2).

    A statement that is not written out is passed to `Attestation` as not made, so
    the refusal and its wording come from the type every other path reaches. There is
    no argument here that makes a missing statement pass.
    """
    named = declared_target(document)
    if named is None:
        raise AttestationNotCommitted(
            f"the committed attestation names no {TARGET_KEY}, so it authorises "
            "nothing in particular. An attestation binds a person to an endpoint, "
            f"and a document with no `{TARGET_KEY}:` line binds them to whatever a "
            "workflow input happened to hold on the day it ran (ADR-0065)"
        )
    if named != target:
        raise AttestationNotCommitted(
            f"the committed attestation is made against {named!r} and this run "
            f"attacks {target!r}. Nothing was sent: what is attested is a target, "
            "not a workflow, so the two have to be the same string and a difference "
            "is a refusal rather than something to reconcile"
        )
    written = statements(document)
    return Attestation(
        identity=identity,
        **{
            field: normalised(wording) in written
            for field, wording in Attestation.STATEMENTS
        },
    )


def declared_target(document: str) -> str | None:
    """The endpoint or callback the committed attestation is about, or nothing."""
    for line in document.splitlines():
        stripped = line.strip()
        if stripped.casefold().startswith(f"{TARGET_KEY}:"):
            return stripped.split(":", 1)[1].strip()
    return None


def statements(document: str) -> frozenset[str]:
    """Every statement the document writes out, one whole item each.

    Items are unwrapped across lines before they are compared, because the third
    statement is long and a committed file that could not wrap it is a file nobody
    wants to review. Everything outside an item — a heading, the target line, a
    comment explaining why the file exists — is not a statement and is ignored.
    """
    return frozenset(normalised(item) for item in _items(document))


def _items(document: str) -> Sequence[str]:
    """The list items in that document, each joined back into one line."""
    items: list[str] = []
    current: str | None = None
    for line in document.splitlines():
        stripped = line.strip()
        if stripped.startswith(ITEM):
            if current is not None:
                items.append(current)
            current = stripped[len(ITEM) :]
        elif not stripped:
            if current is not None:
                items.append(current)
            current = None
        elif current is not None:
            current = f"{current} {stripped}"
    if current is not None:
        items.append(current)
    return items


def normalised(text: str) -> str:
    """One statement in the form two of them are compared in.

    Whitespace collapsed so a wrapped line matches, case folded so a sentence that
    begins a line matches, and a trailing full stop dropped so prose somebody wrote
    as prose matches. Nothing else is touched: a word changed is a different
    statement, which is the point of writing them out.
    """
    return " ".join(text.split()).casefold().rstrip(".")


@dataclass(frozen=True)
class DeclaredCeiling:
    """What a run may cost, declared before it is estimated.

    The CI answer to the halt: the graph presents the estimate exactly as it presents
    it to a terminal, and this is what compares. A ceiling declared *after* the
    estimate would be a rubber stamp — this one is written in the caller's workflow
    file, under review, and the run is refused when the estimate exceeds it
    ([ADR-0065](../../docs/adr/0065-a-ci-attestation-is-committed-prose-by-a-named-actor.md)).

    Two units, because two are declarable and neither can be derived from the other:
    a run's calls are arithmetic the bench does, and their price is the operator's own
    (`budget.CallPrice`). Either may be declared, both may be, and at least one must
    be — a ceiling that declares nothing is not a ceiling.
    """

    calls: int | None = None
    """The most calls this run may be permitted to make, or nothing declared."""

    spend: Decimal | None = None
    """The most this run may be permitted to cost, or nothing declared."""

    price: CallPrice | None = None
    """The operator's price per call, which is what makes a spend comparable.

    Held beside the ceiling rather than read off the estimate, because it is the same
    declaration the estimate was priced with and this record is what a caller passes
    around. A spend ceiling with no price declines: see `over`.
    """

    def __post_init__(self) -> None:
        if self.calls is None and self.spend is None:
            raise ValueError(
                "a declared ceiling has to declare something. An unattended run is "
                "answered by a comparison, and a ceiling with no figure in it is a "
                "yes with extra steps (ADR-0065)"
            )
        if self.calls is not None and self.calls < 0:
            raise ValueError("a run cannot be permitted fewer than no calls")
        if self.spend is not None and self.spend < 0:
            raise ValueError("a run cannot be permitted to cost less than nothing")

    def over(self, presented: BudgetPayload) -> str | None:
        """Why this estimate is outside what was declared, or nothing.

        **Compared against `hard_ceiling` and never against the estimate**, because
        that is the figure the run is actually held to: the estimate with every
        message retried to its target\'s transport limit, and the one thing ADR-0007
        says a run may not exceed. A comparison against the smaller figure would
        approve a run that is permitted to spend past what was declared.
        """
        enforced = presented["hard_ceiling"]
        if self.calls is not None and enforced["calls"] > self.calls:
            return (
                f"this run may make up to {enforced['calls']} calls and the workflow "
                f"declared a ceiling of {self.calls}. Declined: the run is not "
                "trimmed to fit, because a suite cut down to a budget would sign a "
                "report over a library subset nobody chose"
            )
        if self.spend is None:
            return None
        if self.price is None:
            return (
                f"the workflow declared a ceiling of {self.spend} and this run is "
                f"{NOT_PRICED}, so there is nothing to compare it with. Declined "
                "rather than proceeded: an unknown cost and a cost inside a ceiling "
                "are different facts, and only one of them was declared"
            )
        cost = self.price.cost_of(enforced["calls"])
        if cost > self.spend:
            return (
                f"this run may cost up to {cost} {self.price.currency} and the "
                f"workflow declared a ceiling of {self.spend} {self.price.currency}. "
                "Declined, and nothing was sent"
            )
        return None


def ceiling_approval(identity: str, ceiling: DeclaredCeiling) -> Approve:
    """Answer the graph\'s interrupt against a ceiling declared before the run.

    The second implementation of the type `console.terminal_approval` is the first of
    — `Approve` was written for exactly this (`approval.py`), so the graph is
    unchanged and the halt is the same halt. What differs is who answers: a person at
    a terminal there, and here a comparison whose two sides are both declarations
    somebody committed.

    A run that is over declines with the figures named, which is what makes the step
    red and legible in a job log. A run inside its ceiling is confirmed as `identity`
    — `github.actor`, the same authenticated identity the attestation records — so
    the artefact names a person for the spend as it does from a terminal.
    """

    def approve(presented: BudgetPayload) -> Approval:
        refusal = ceiling.over(presented)
        if refusal is None:
            return Approval(confirmed=True, identity=identity)
        return Approval(confirmed=False, identity=identity, reason=refusal)

    return approve
