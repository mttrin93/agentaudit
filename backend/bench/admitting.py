"""The one code path from a proposed route to an admission decision.

`admission.py` is the arithmetic — what counts clear the bar, and what a rejection is
counted as. This module is the **path**: consult the admission memory, measure what it
could not answer against the three reference agents on each model, decide one
promotion per proposal, and remember what is worth remembering.

**It is in the backend because it has two callers, and a copy would be a second code
path to a reference agent.**
[ADR-0105](../../docs/adr/0105-deciding-a-pending-route-is-its-own-surface-and-not-a-gate-runs-second-job.md)
§5 is the decision. `scripts/swap.py` puts the routes its own attacker proposed to the
bar; the `/pending-routes` surface puts the routes a customer run filed
(`docs/specs/pending-routes.md`). Two surfaces, one function, and a route admitted on
either was decided on the same arithmetic — which is what "there is one code path to a
reference agent" means, and what two copies drifting apart would silently end.

**Nothing here reaches out to a terminal.** The admission run is a `Measure` seam and
the prose is a `Say` seam, so the module names neither `print` nor anything under
`scripts/`. An entry point that has a terminal passes `print`; an API route passes a
sink of its own. The direction of the dependency is asserted as reachability in
`backend/tests/test_admitting.py`, because the second caller is a route on an HTTP API
and a backend that could reach a command line would not be callable from one.

**Which bar applies is decided nowhere here.** `promote` reads it off the proposal's
own `discovered_by` (`adaptive/promotion.py`, ADR-0012), and this module names neither
`AdmissionBar` nor `bar_for` and has no parameter one could be passed through.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol

from backend.bench.adaptive.promotion import Promotion, promote
from backend.bench.adaptive.proposal import ProposedRoute
from backend.bench.adjudication import Completion
from backend.bench.admission import CrossModelRejections, rejections
from backend.bench.decided import (
    DECIDED_ROUTES,
    Consultation,
    DecidedRoutes,
    RouteKey,
    consult,
    worth_remembering,
)
from backend.bench.library import AdmissionReading, Case
from backend.bench.registration import Attestation
from backend.graph.approval import Approve
from backend.graph.budget import CallPrice

Say = Callable[[str], None]
"""Where this path's prose goes, one line at a time.

A seam and not `print`, for the reason `Measure` is one: the consultation's and the
rejections' prose is what an operator reads to check the bar, and the two callers read
it in different places — a terminal's standard output, and a surface that has none.
No default, so a caller that has nowhere to put the prose has to say so rather than
lose it silently.
"""


class Measure(Protocol):
    """How a caller measures one set of proposed cases on one model.

    A seam rather than a direct call, and it exists for one reason: what this
    function has to be able to demonstrate is *that a remembered route is not
    measured*, and an assertion about a call that did not happen needs the call to be
    observable. `scripts/admit.py`'s `measure_on` is the only implementation a run
    ever uses — one admission run in one place, so nothing enters the library on an
    arithmetic this path invented.
    """

    def __call__(
        self,
        *,
        cases: Sequence[Case],
        model: str,
        adjudicator: Completion,
        adjudicator_model: str,
        attestation: Attestation,
        approve: Approve,
        price_per_call: CallPrice | None,
    ) -> dict[str, AdmissionReading] | int: ...


def cross_model_bar(
    *,
    proposals: Sequence[ProposedRoute],
    models: Sequence[str],
    attestation: Attestation,
    approve: Approve,
    adjudicator: Completion,
    adjudicator_model: str,
    price_per_call: CallPrice | None,
    measure: Measure,
    say: Say,
    memory: DecidedRoutes = DECIDED_ROUTES,
) -> tuple[CrossModelRejections, tuple[Promotion, ...], Consultation] | int:
    """Put every undecided route to the bar, on every model, and count what it refused.

    One proposed case against three agents on each model is what ADR-0012's bar
    costs, and an exit code is returned rather than raised where an admission run did
    not happen — the operator declined the cost, the run hit its ceiling, or an agent
    never registered. A caller's own reason for putting routes to the bar belongs at
    its call site; this is the path they share.

    **The memory is consulted before anything is sent** (ADR-0032). A route the gate
    already measured under this run's own conditions is reported from it, and the
    three reference agents are never called for it — which is the whole of what #39
    saves, since a refused route the attacker rediscovers every run was costing an
    admission run on two models for an answer already known. What is remembered is
    the *measurement*: `promote` decides it again below, so the declared threshold
    still decides every proposal in this run.

    A route is measured **once per run** even where several proposals took it.
    `docs/validation.md` records one run proposing four cases all describing the same
    route, and the counts do not improve for being bought twice; the proposal stays
    the unit the rejections are counted on.

    Which bar applies is never decided here. `promote` reads it off the proposal's own
    `discovered_by`, and nothing in this function can name one.
    """
    proposals = tuple(proposals)
    models = tuple(models)
    consulted = consult(memory, proposals, models=models)
    if not proposals:
        say(
            "\nNo route was proposed in either run, so the cross-model bar decided "
            "nothing. That is a fact about the attacker and not about the bar."
        )
        return rejections(()), (), consulted

    say("")
    say(consulted.stated())
    unmeasured = consulted.to_measure
    readings: dict[str, list[AdmissionReading]] = {
        proposal.case.id: [] for proposal in unmeasured
    }
    for model in models:
        if not unmeasured:
            break
        say(f"\nputting {len(unmeasured)} proposed case(s) to the bar on {model}")
        # `scripts/admit.py`'s own admission run, and deliberately: a proposal is
        # decided on counts read the way every other admission's counts are read, so
        # nothing enters the library on an arithmetic this path invented. The caller's
        # own adaptive layer is ignored — a proposal made while measuring a proposal
        # has had no admission run of its own, and following it would be a loop with
        # no end.
        measured = measure(
            cases=[proposal.case for proposal in unmeasured],
            model=model,
            adjudicator=adjudicator,
            adjudicator_model=adjudicator_model,
            attestation=attestation,
            approve=approve,
            price_per_call=price_per_call,
        )
        if isinstance(measured, int):
            return measured
        for case_id, reading in measured.items():
            readings[case_id].append(reading)

    # The counts, keyed by the route, so that a second proposal of a route this run
    # measured once is decided from them rather than from a second admission run.
    counted: dict[str, tuple[AdmissionReading, ...]] = {
        RouteKey.of(proposal.case).filed_under: tuple(readings[proposal.case.id])
        for proposal in unmeasured
    }
    # One decision per proposal, made once and used twice — the promotions this run
    # reports are the objects it remembers. Per *proposal* and not per route, because
    # the proposal is the unit the rejections are counted on (ADR-0012, and the
    # reading `docs/validation.md` records for #15): four proposals of one route are
    # four decisions over one measurement, each carrying its own case id.
    decided_now = {
        one.proposal.case.id: promote(one.proposal, counted[one.route.filed_under])
        for one in consulted.consulted
        if one.remembered is None
    }
    # Remembered once per route. A second write of one route replaces the first with
    # identical counts, so the loop is over what was measured rather than over what
    # was decided.
    for proposal in unmeasured:
        promotion = decided_now[proposal.case.id]
        # Selection rather than a caught exception, on ADR-0031 point 3's reasoning:
        # a run that did not measure the bar the way it needs measuring has nothing
        # to hand a later run, and the memory refuses it either way.
        if worth_remembering(promotion):
            memory.remember(promotion, models=models)

    promotions = tuple(
        one.remembered.promotion
        if one.remembered is not None
        else decided_now[one.proposal.case.id]
        for one in consulted.consulted
    )
    return (
        rejections(promotion.outcome for promotion in promotions),
        promotions,
        consulted,
    )
