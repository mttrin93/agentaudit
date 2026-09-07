"""A route the attacker thinks is worth promoting, and the case it would become.

The one edge from the adaptive layer back into the scored one (ADR-0010). It is a
narrow edge on purpose: `propose_case` produces a **proposed** case — a record with
no admission block — and the admission gate decides it against a stated threshold
(#17). Nothing here is admitted by having been proposed, and the attacker's own
assessment of its route decides nothing.

**The payload is the harness's, the prose is the attacker's.** The proposed case
carries the probe that actually ran, taken from the episode's own record rather
than from the tool's argument, so a case cannot be proposed with a payload the
target never saw. What the attacker supplies is the description — which is also
the only part of a route that is ever written down outside a run (CONTEXT.md,
**route**; ADR-0008).

Provenance is `adaptive`, which selects the cross-model admission bar by itself
(ADR-0012): a route discovered against these three reference agents has to
separate on a model it was not discovered on before it may enter the library.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from backend.bench.contract import TargetConfig
from backend.bench.library import (
    CARRIED_BY_FETCHED_CONTENT,
    Case,
    CaseStatus,
    DiscoveredBy,
    ExternalId,
    Family,
    Transform,
    Trigger,
    VerdictClass,
)


class RouteNotFilable(Exception):
    """A route the attacker found and no record can carry.

    Raised instead of a `Case` this module cannot construct honestly, and caught by
    the episode, which records the declination and hands the reason back to the
    attacker. A separate type rather than `None` so that the reason travels to both
    readers — the attacker, which asked, and the episode record, which is the only
    place a route the layer could not file is ever written down.

    It is *not* an error in the layer: a declined route is a fact about the attacker
    and the family it worked in, so an episode that raises this one still completes
    and still reports its outcome. Why the route is declined rather than filed with a
    synthesised artefact is
    [ADR-0084](../../../docs/adr/0084-a-route-the-record-cannot-carry-is-declined-and-not-synthesised.md).
    """


@dataclass(frozen=True)
class ProposedRoute:
    """What one `propose_case` call produced: a case record, and the prose."""

    case: Case
    description: str
    """What the attacker did, in the attacker's own words. Never payload text —
    the payload is on the case record, which is not committed to the repository
    until admission puts it there."""

    def __post_init__(self) -> None:
        if not self.description.strip():
            raise ValueError(
                "a proposed route with no description is a payload with nothing "
                "a reader could use to decide whether it is worth running"
            )
        if self.case.admission is not None:
            raise ValueError(
                f"{self.case.id} was proposed carrying an admission record. A "
                "proposed case has not been run against the reference agents, and "
                "the gate decides it rather than the attacker (ADR-0010)"
            )


def proposed_from(
    objective: Case,
    target: TargetConfig,
    family: Family,
    payload: str,
    description: str,
    today: date | None = None,
) -> ProposedRoute:
    """Draft a case from the probe that worked, under the objective's criterion.

    The success condition is copied off the objective rather than composed, which
    is what keeps the proposal deterministic: the attacker found a new *payload*,
    not a new definition of what counts as a break (ADR-0004).

    **And copying it is what makes two families unfilable**, which is why the refusal
    is here rather than in the caller. A condition in `CARRIED_BY_FETCHED_CONTENT`
    says the attack arrives in content the target fetched, so ADR-0060 requires the
    record to carry that content — while what the attacker composed is a message, and
    the payload above is the probe that ran. Synthesising the artefact from the probe
    would file a message as fetched content and would then have to invent the two
    invariants that hang off it: the canary is the artefact's own halves joined, and
    the content key is named by the turn that fetches. So the route is declined with
    its reason and the episode records it (`RouteNotFilable`, #166).
    """
    kind = (
        None
        if objective.success_condition is None
        else objective.success_condition.kind
    )
    if kind in CARRIED_BY_FETCHED_CONTENT:
        raise RouteNotFilable(
            f"a route in {family.value} is not filable as a case: the attack in this "
            "family arrives in content the target fetched and a probe is a message, "
            "so the record would carry no content to show a reader (ADR-0060). The "
            "route is recorded on the episode and proposed to nothing"
        )
    return ProposedRoute(
        case=Case(
            id=f"adaptive-{family}-{uuid.uuid4().hex[:8]}",
            family=family,
            external_id=ExternalId(
                identifier=objective.external_id.identifier,
                not_tested=(
                    "A route the adaptive attacker found. It makes no coverage "
                    "claim until it has cleared the cross-model admission bar"
                ),
            ),
            # One turn, because a probe is one message the attacker composed:
            # the adaptive layer sends no script and the payload type holding one
            # does not make it able to (ADR-0053, ADR-0010).
            payload=(payload,),
            success_condition=objective.success_condition,
            verdict_class=VerdictClass.DETERMINISTIC,
            applies_to=(target.agent_type,),
            requires=objective.requires,
            added_on=today or date.today(),
            # The trigger the loop closes on: a target that survived the fixed
            # suite is either good or attacked weakly, and an adaptive break is
            # the only evidence that tells those two apart by demonstration.
            trigger=Trigger.TARGET_PASSED_EVERYTHING,
            discovered_by=DiscoveredBy.ADAPTIVE,
            # A probe the attacker composed, and not a transform of the objective:
            # the payload is new text rather than this record's payload put through
            # a function, so it is a base case and derives from nothing (ADR-0051).
            transform=Transform.PLAIN,
            derived_from=None,
            status=CaseStatus.ACTIVE,
            admission=None,
        ),
        description=description,
    )
