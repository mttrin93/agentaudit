"""The plant: what a run puts in place before it registers, and counts nowhere.

Two families need an artefact inside the target's boundary before their attack turn
— the registration nonce in the target's *configuration* (ADR-0007) and third-party
text in what the target *retrieves* (ADR-0060) — and `POST {message, session_id}`
cannot put either there. On the one surface where the bench holds the operator's own
object, it can: `serve_callback` reads the hooks off the callback and
`TargetConfig.plants` says which plantings this target can be given (ADR-0061). This
module is what calls them.

**The decision, the counters a plant stays off, and how a planting call is
authorised without being an attempt are
[ADR-0062](../../docs/adr/0062-planting-is-a-pre-run-step-off-every-counter.md).**
The consequence here is the shape of the module, and it is an absence: `plant` takes
an `Attestation` and takes no `RunState`, so there is no counter in scope for it to
move, and it names neither `send_message` nor a `Layer` nor an `Attempt`. Each of
those is checked by a test rather than left as a promise
(`backend/tests/test_planting_off_the_counters.py`).

The ordering this step sits in is attestation → nonce issued → **plant** →
registration probe → run, and `calibration._run_target` is where it is spelled out.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from backend.bench.contract import TargetConfig
from backend.bench.library import Case, Plant
from backend.bench.registration import Attestation, AttestationRecord

Planter = object
"""What a run is given to plant with: the operator's own object, whatever it is.

`object` and not a `Protocol`, because the hooks are optional by construction and a
protocol spelling out both of them would describe a shape almost no callback has —
`shim.ConfigCanaryPlanting` and `shim.RetrievedContentPlanting` are the two that
spell one hook each out for a type checker, and which of them a given object
satisfies is already recorded on `TargetConfig.plants`. What is called here is read
off that record and never off this annotation.
"""


class PlantingFailure(StrEnum):
    """Why a plant did not happen — one named outcome per mode.

    **None of these is a withdrawal** — that distinction is ADR-0062 §5, and it is
    why this enumeration exists at all. Every member here is a target that said it
    could be planted and was not; a withdrawal is a target with no hook to call, and
    the run carries on through one (ADR-0061).

    Named per mode rather than collapsed into one *planting failed*, on
    `TargetFailure`'s reasoning: the three are three different mistakes, and two of
    them are made by the caller before a hook is ever reached.
    """

    NO_PLANTER = "no_planter"
    """The target declared a planting and the run was handed nothing to plant with.

    A caller that served a callback with hooks and did not pass the object on to
    `run_calibration`. Refused rather than skipped: the cases that needed the
    planting are `runnable` against this target — `can_be_planted` said yes — so
    skipping would spend every one of their attempts against an artefact that is
    nowhere and report the clean zero that reads as a defence.
    """

    HOOK_MISSING = "hook_missing"
    """The object handed in does not have the hook the target declared.

    Which means the object handed in is not the object that was served, since
    `declared_plants` read the record off the served one. A different mistake from
    `NO_PLANTER` and worth its own name, because the fix is *pass the callback you
    served* rather than *pass a callback at all*.
    """

    HOOK_RAISED = "hook_raised"
    """The hook exists, was called, and threw.

    The one mode that is about the operator's own planting code rather than about
    how the run was wired up.
    """

    def stated(self) -> str:
        """The outcome in the words a run prints, with what it is not.

        No fallback branch, on `TargetFailure.stated`'s terms: a fourth mode has to
        fail the type check rather than reach a reader as a bare member name.
        """
        match self:
            case PlantingFailure.NO_PLANTER:
                return (
                    "no planter — the target declared it can be given this planting "
                    "and the run holds no object to perform it. Not a withdrawn "
                    "family: a withdrawal is a target with no hook, and this one has "
                    "one nobody handed over"
                )
            case PlantingFailure.HOOK_MISSING:
                return (
                    "hook missing — the object this run was given to plant with does "
                    "not have the hook the target declared, so it is not the object "
                    "that was served"
                )
            case PlantingFailure.HOOK_RAISED:
                return (
                    "the planting hook raised — the hook exists and did not work, "
                    "which is not the same reading as a target that has none"
                )


class PlantingFailed(RuntimeError):
    """A plant this run needed did not happen, so no family is measured.

    Raised out of `plant`, which is called before the registration probe, so it
    stops the run **before the first attempt**: nothing has been sent, no attempt is
    recorded, and no rate is reported over a target whose artefact is not in place.
    Loud rather than degraded, on `BudgetExceeded`'s reasoning — a suite that ran
    against half a precondition is void rather than smaller.

    The exception carries the named outcome and the planting it was about. It never
    carries the artefact's body: the content is on the case record and a traceback
    travels into logs (ADR-0008).
    """

    def __init__(
        self,
        failure: PlantingFailure,
        plant: Plant,
        target_name: str,
        case_id: str | None = None,
    ) -> None:
        self.failure = failure
        self.plant = plant
        self.target_name = target_name
        self.case_id = case_id
        about = f" for case {case_id}" if case_id is not None else ""
        super().__init__(
            f"the {plant} planting of target {target_name!r}{about} did not happen: "
            f"{failure.stated()}. What the target needed in place is {plant.stated()}"
        )


@dataclass(frozen=True)
class PlantingRequest:
    """One planting this run has to perform, and the arguments its hook takes.

    Derived from the case records and the run's own nonce, never from the family: a
    case that moved families would otherwise change which planting it asks for, which
    is the reading `Case._refuse_a_plant_the_record_does_not_require` already refuses
    on the record (ADR-0061 §7).
    """

    plant: Plant
    case_id: str | None
    """Which record asked for this, or `None` for a planting the run issues.

    `None` on the configuration canary and only there: the value is the registration
    nonce, issued per run, so no case record names it and none can be cited for it
    (ADR-0007). Every retrieved-content planting is one record's own artefact and
    carries that record's id.
    """

    arguments: Mapping[str, str]
    """What the hook is called with, keyed by the parameter names the protocols spell
    out — `canary` for one, `key` and `body` for the other."""


@dataclass(frozen=True)
class Planting:
    """One planting that was performed, and what authorised it.

    **The record ADR-0007 requires, and deliberately not an `Attempt`.** It carries
    an `AttestationRecord` and no `Layer`, no `sends` and no `Transcript`, which is
    the whole of what *authorised and uncounted* means here: the operator's
    attestation is what permits the bench to touch their systems, and nothing about
    this record can be summed into a denominator.

    It carries the planting and the record that asked for it, and never the body.
    The content is on the case record, which is where a reader re-derives it from,
    and a signed artefact is not a place for payload text (ADR-0008, ADR-0060).
    """

    plant: Plant
    case_id: str | None
    authorised_by: AttestationRecord


def required_plantings(
    cases: Sequence[Case], target: TargetConfig, *, canary: str
) -> tuple[PlantingRequest, ...]:
    """What this target has to be given before these cases may be attempted.

    Read off two facts the run already holds — the preconditions each record
    declares, and `TargetConfig.plants` — so there is no third statement of which
    family needs what. A planting the target cannot be given is **not** requested
    here: `unmet_preconditions` already withdrew the cases that asked for it, before
    an attempt is spent, and requesting it would turn a named withdrawal into a
    failed run (ADR-0061 §6).

    **A target whose `plants` is `None` requests nothing at all.** That is every
    target that is a URL: it does not answer for its own plantings, its operator
    plants by hand, and `plan_for`'s `NOTE_NOT_PLANTED` / `NONCE_NOT_PLANTED` decide
    for it exactly where ADR-0024 left them. A harness that planted into one anyway
    would be inventing an act it cannot perform.

    The configuration canary is requested **once** however many cases need it —
    there is one nonce per run — and retrieved content once per record, because each
    record carries its own artefact.
    """
    if target.plants is None:
        return ()
    requested: list[PlantingRequest] = []
    seen: set[tuple[Plant, str | None]] = set()
    for case in cases:
        for needed in Plant:
            if needed.precondition not in case.requires:
                continue
            if needed not in target.plants:
                continue
            request = _request_for(needed, case, canary)
            key = (request.plant, request.case_id)
            if key in seen:
                continue
            seen.add(key)
            requested.append(request)
    return tuple(requested)


def plant(
    planter: Planter | None,
    target: TargetConfig,
    cases: Sequence[Case],
    *,
    canary: str,
    attestation: Attestation,
) -> tuple[Planting, ...]:
    """Put every artefact these cases need in place, before the run counts anything.

    **The signature is the invariant.** There is no `RunState` parameter and no
    `Layer`, so no counter is in scope to be moved: not the per-layer spend, not the
    attempt list the denominator is read off, not the adaptive episodes. Taking one
    and declining to charge it is the widening the standing rule asks anyone who
    reaches for it to stop at — the invariant is carried by the type, or it is
    carried by a reviewer remembering (ADR-0010's shape, applied to ADR-0062's
    subject).

    **The `Attestation` is how a planting call is authorised** (ADR-0062 §3), and it
    is a required argument for the reason `register`'s is: the echo probe and the
    plant are both acts on the operator's systems, and there is no point in this flow
    at which the bench may perform one without an attestation in hand. Authorised and
    counted are different questions, and this signature answers the first *yes* and
    the second *no*.

    The hook is called on the object, never over the wire. `send_message` is not
    imported here, the served app has one route, and the argument each hook is given
    comes from the case record or from the run's own nonce.

    Every failure is a `PlantingFailed`, raised before the registration probe, so a
    run whose plant did not work has spent nothing and measures nothing.
    """
    requests = required_plantings(cases, target, canary=canary)
    if not requests:
        return ()
    authorised_by = AttestationRecord.of(attestation, target)
    performed: list[Planting] = []
    for request in requests:
        if planter is None:
            raise PlantingFailed(
                PlantingFailure.NO_PLANTER, request.plant, target.name, request.case_id
            )
        hook = getattr(planter, request.plant.hook, None)
        if not callable(hook):
            raise PlantingFailed(
                PlantingFailure.HOOK_MISSING,
                request.plant,
                target.name,
                request.case_id,
            )
        try:
            hook(**request.arguments)
        except Exception as raised:
            # The named outcome and never the exception's own words on the way out:
            # a planting hook is the operator's code and its message is theirs to
            # read, in the traceback this chains to (ADR-0059 §2's reasoning, over a
            # hook rather than over a reply).
            raise PlantingFailed(
                PlantingFailure.HOOK_RAISED,
                request.plant,
                target.name,
                request.case_id,
            ) from raised
        performed.append(
            Planting(
                plant=request.plant,
                case_id=request.case_id,
                authorised_by=authorised_by,
            )
        )
    return tuple(performed)


def _request_for(needed: Plant, case: Case, canary: str) -> PlantingRequest:
    """One planting's arguments, off the member and the record that asked for it.

    A `match` with no fallback arm, on `Plant.stated`'s terms: the two hooks take
    different arguments, so a third member has to fail the type check here rather
    than default onto one of the two existing shapes and plant the wrong thing.
    What the arms read is a record — the run's nonce for one, `PlantedArtefact`'s own
    `key` and `body` for the other — so neither of them holds content of its own.
    """
    match needed:
        case Plant.CONFIG_CANARY:
            return PlantingRequest(
                plant=needed, case_id=None, arguments={"canary": canary}
            )
        case Plant.RETRIEVED_CONTENT:
            artefact = case.planted_artefact
            if artefact is None:
                raise ValueError(
                    f"case {case.id} requires {needed} and carries no planted "
                    "artefact, so there is nothing to plant. A record declaring a "
                    "planting it does not carry is refused on the record itself "
                    "(`Case._refuse_a_planting_its_record_disagrees_with`), and "
                    "reaching this line means one got past it"
                )
            return PlantingRequest(
                plant=needed,
                case_id=case.id,
                arguments={"key": artefact.key, "body": artefact.body},
            )
