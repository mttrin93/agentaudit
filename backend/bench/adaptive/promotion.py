"""The promotion loop: a proposed route submitted to the admission gate.

The one edge from the adaptive layer into anything scored (ADR-0010), and the
place it is decided. `propose_case` drafts — `proposal.py` — and this module
submits the draft to `admission.decide`, which answers against a declared
threshold. The agent explores, the gate admits, the library grows, and the signed
number stays reproducible because nothing crossed the boundary except a case that
beat a stated bar. **The arbiter is a declared number, not the model's own
confidence**, which is what makes "an agent that learns" auditable here.

**The cross-model bar is enforced here and cannot be argued around** (ADR-0012).
A proposal carries `discovered_by = adaptive`, which selects the two-model bar by
itself: `bar_for` reads it off the record, `MODELS_REQUIRED` says two, and
`AdmissionOutcome.admitted` refuses a case read on one. The bar exists because the
attacker discovers its route *by exploiting the same three agents admission then
tests it against* — a route found against the trivial agent that the hardened agent
happens to resist scores `D ≈ 1` for free, and trivial breaks on nearly everything,
so that is close to free. Nothing in this module accepts a bar as an argument, and
there is no branch here that could reach a weaker one.

**A rejected proposal is discarded, not parked.** A refused promotion returns no
case at all: there is no field on the result holding a case waiting for a second
opinion, and nothing here writes anywhere. The counts behind the refusal are kept,
because ADR-0012 calls a cross-model discard a finding in its own right — direct
evidence that a route the attacker found was a property of one model rather than of
the agents' defences.

**`A_break` is not in this file and reaches nothing in it.** The adaptive layer's
own discrimination statistic decides nothing about admission, about the gate, or
about a single case: a promotion turns on the readings the proposed case measured
against the reference agents and on nothing the attacker or its statistics say.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date

from backend.bench.adaptive.proposal import ProposedRoute
from backend.bench.admission import AdmissionOutcome, decide
from backend.bench.library import AdmissionReading, AdmissionRecord, Case, bar_for
from backend.bench.rule import DECLARED_RULE, GateRule


@dataclass(frozen=True)
class Promotion:
    """What the gate answered about one proposed route, and the case if it cleared.

    Holds the outcome whichever way it went, because a reader deciding whether to
    believe a discard needs the counts behind it as much as a reader deciding
    whether to believe an entry. What it does not hold is a rejected case in a state
    anything downstream could mistake for admitted: `case` is `None` there, and
    there is no second field it could be hiding in.
    """

    proposal: ProposedRoute
    outcome: AdmissionOutcome
    case: Case | None
    """The case as it enters the library, with the admission block that let it in.

    `None` for a refusal. A refusal is a discard, and a discard has no record.
    """

    @property
    def admitted(self) -> bool:
        return self.case is not None

    def stated(self) -> str:
        """The lines a report prints for one promotion, discard included."""
        heading = (
            f"promoted {self.proposal.case.id}"
            if self.admitted
            else f"discarded {self.proposal.case.id} — it does not enter the library"
        )
        return "\n".join(
            (
                f"{heading}: {self.proposal.description}",
                *(f"  {line}" for line in self.outcome.stated().splitlines()),
            )
        )


def promote(
    proposal: ProposedRoute,
    readings: Sequence[AdmissionReading],
    rule: GateRule = DECLARED_RULE,
    today: date | None = None,
) -> Promotion:
    """Submit one proposed route to the admission gate, and take its answer.

    The bar is read off the proposal's own `discovered_by` and is not an argument:
    a caller able to name the bar could admit an adaptive-discovered case on one
    model by supplying the word that says so. `readings` are what the case measured
    against the three reference agents, one per underlying model — the cross-model
    bar is met by there being two of them and by both clearing, and neither half is
    redundant (`AdmissionOutcome.admitted` says why).

    Nothing is written. The admitted case is *returned*, so the decision to put it
    on disk stays with the caller that also owns the library directory — and a
    refusal returns no case for anybody to put anywhere.
    """
    measured = tuple(readings)
    outcome = decide(proposal.case.id, proposal.case.discovered_by, measured, rule)
    if not outcome.admitted:
        return Promotion(proposal=proposal, outcome=outcome, case=None)
    return Promotion(
        proposal=proposal,
        outcome=outcome,
        case=replace(
            proposal.case,
            admission=AdmissionRecord(
                bar=bar_for(proposal.case.discovered_by),
                admitted_on=today or date.today(),
                readings=measured,
            ),
        ),
    )
