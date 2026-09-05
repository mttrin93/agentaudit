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

import re
import secrets
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from backend.bench.contract import TargetConfig
from backend.bench.library import Case, Plant
from backend.bench.registration import Attestation, AttestationRecord

NAMESPACE_PREFIX = "run-"
"""What every namespace this bench asks a shim to create begins with.

A shim author who has to answer *is this mine to drop* answers it by looking at the
prefix, and an operator reading a poisoned-store line in a report knows which of the
things in their store the sentence is about.
"""

_NAMESPACE_BODY = re.compile(r"[A-Za-z0-9._-]+")
"""What a run id may contribute to a namespace.

A namespace is pasted into somebody else's store — a vector-store collection name, a
folder, a key prefix — so what reaches it is restricted here rather than at each of
the places that could be surprised by it. Refused rather than sanitised: a namespace
quietly rewritten is a namespace a `teardown()` might not recognise, and the run id
this is derived from is minted by this bench.
"""

DropNamespace = Callable[[str], None]
"""A teardown that is reached as a call rather than as a method on an object.

The reference agents' `DELETE /reference/namespaces/{namespace}` is the one of these
that exists: test equipment served over HTTP, so the caller holds a function and not
the object the namespace lives in. Held to the same contract as `teardown()` — one
call, wholesale, and it never takes the run's own exception's place (ADR-0063 §5).
"""

TEARDOWN_HOOK = "teardown"
"""The method a callback implements to drop its namespace.

One name, spelled here, for the reason `Plant.hook` is spelled on the member: the
shim's construction check, the harness's call and the protocol are three readers of
one fact. Not a member of `Plant`, because a teardown is not a planting — there is
one of these however many plantings a target declares, and that is the whole of the
decision (ADR-0063).
"""


def anonymous_run_id() -> str:
    """A run id for a run that holds no record of its own.

    Every entry point in this repository hands `run_calibration` a `TracedRun` and so
    a run id — the API from its run record, the five scripts from
    `console.traced_run` — so this is a caller holding no record, which in practice is
    the test suite. It is drawn fresh rather than fixed, because *this run's writes*
    is the property a namespace has to carry and a constant would give two runs one
    namespace: the second's teardown would drop the first's plants.

    Deliberately not `issue_nonce`: a namespace named after the value the leakage
    family reads would put the canary's own prefix into somebody's content store
    (`nonce.inside_a_nonce`, ADR-0043).
    """
    return secrets.token_hex(8)


def namespace_for(run_id: str) -> str:
    """The one namespace this run plants into, derived from the run's own id.

    `run-<id>`, and derived rather than stored: the value handed to a hook and the
    value handed to `teardown()` are computed from the same run id, so there is no
    field on a shim between the two calls that a later run could have overwritten
    ([ADR-0063](../../docs/adr/0063-one-run-scoped-namespace-dropped-wholesale.md)).

    One per run and not one per target: what it scopes is *this run's writes into
    somebody's store*, and a run that dropped a namespace per target would be back to
    a list of things to delete.
    """
    if not _NAMESPACE_BODY.fullmatch(run_id):
        raise ValueError(
            f"a run namespace cannot be derived from {run_id!r}: a run id reaches "
            "somebody else's content store as the name of a namespace they have to "
            "create and drop, so it is letters, digits, dot, dash and underscore or "
            "it is refused. Sanitising it instead would hand a `teardown()` a name "
            "the plant never used"
        )
    return f"{NAMESPACE_PREFIX}{run_id}"


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
    namespace: str
    """The run-scoped namespace this was planted into, and the one `teardown()` drops.

    On the record because *where it went* is the only thing that makes a plant
    reversible, and because a teardown that failed has to be able to say which
    namespace an operator is now holding
    ([ADR-0063](../../docs/adr/0063-one-run-scoped-namespace-dropped-wholesale.md)).
    """

    authorised_by: AttestationRecord


def required_plantings(
    cases: Sequence[Case], target: TargetConfig, *, canary: str, namespace: str
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
            request = _request_for(needed, case, canary, namespace)
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
    namespace: str,
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
    requests = required_plantings(cases, target, canary=canary, namespace=namespace)
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
                namespace=namespace,
                authorised_by=authorised_by,
            )
        )
    return tuple(performed)


class TeardownFailure(StrEnum):
    """Why a namespace was not dropped — one named outcome per mode.

    Two members and not three: there is no `NO_PLANTER` here, because a run holding
    no object to tear down planted nothing with one either, and *nothing to drop* is
    not a failure to drop it (ADR-0063 §3).
    """

    HOOK_MISSING = "hook_missing"
    """The object handed in has no `teardown()`.

    Unreachable through `serve_callback`, which refuses a callback with plant hooks
    and no teardown at construction (ADR-0063 §4) — and named anyway, because the
    caller hands the object to `run_calibration` separately and could hand over a
    different one, which is the mistake `PlantingFailure.HOOK_MISSING` is also for.
    """

    HOOK_RAISED = "hook_raised"
    """The teardown exists, was called, and threw. The store may now be poisoned."""

    def stated(self) -> str:
        """The outcome in the words a report prints.

        No fallback branch, on `PlantingFailure.stated`'s terms.
        """
        match self:
            case TeardownFailure.HOOK_MISSING:
                return (
                    "no teardown — the object this run was given has no "
                    "`teardown()`, so nothing dropped the namespace it planted into"
                )
            case TeardownFailure.HOOK_RAISED:
                return "the teardown raised, so the namespace was not dropped"


@dataclass(frozen=True)
class Teardown:
    """What became of one run-scoped namespace, and it is always answered.

    **A record and never a `None`**, because the outcome this exists to carry is the
    one nobody would go looking for: the run's figures are unaffected — every attempt
    was made and every verdict stands — and the only person who can act on a poisoned
    store is an operator who is told (ADR-0063 §3). So a teardown that worked is a
    record saying so, and a teardown that failed is the same record carrying the
    namespace and the error.

    `error` is the operator's own exception, in their own words, and this is the one
    place in the bench where that text travels. It is not payload and not a reply
    from a target: it is the operator's cleanup code failing against the operator's
    own store, in a document written for them (ADR-0008 governs the other case, and
    ADR-0063 says why this is not it).
    """

    namespace: str
    target_name: str | None
    """Whose planter this was, or `None` for the run's own equipment.

    `None` is the reference-agent stand-in a gate run drops through `drop_namespace`
    — test equipment, and deliberately not something a target's artefact reports on
    (`calibration.run_calibration`).
    """

    failure: TeardownFailure | None = None
    error: str | None = None

    @property
    def failed(self) -> bool:
        return self.failure is not None

    def stated(self) -> str:
        """The sentence a report prints, whichever way this went."""
        if self.failure is None:
            # The name is deliberately not in this half. On a run that cleaned up
            # there is nothing for a reader to do with it, and it is derived from the
            # run id — which a signed artefact does not otherwise carry (ADR-0018,
            # ADR-0063 §3).
            return (
                "the namespace this run planted into was dropped wholesale, so "
                "nothing this run wrote is still in the store"
            )
        return (
            f"the namespace {self.namespace} this run planted into was NOT dropped: "
            f"{self.failure.stated()}. The figures in this report are unaffected — "
            "every attempt was made and every verdict stands — and what is left is a "
            f"store holding this run's planted content. The error was: {self.error}"
        )


NOTHING_WAS_PLANTED = (
    "the bench planted nothing on this run, so no namespace was created and none "
    "had to be dropped. Every target here was reached over the contract and any "
    "artefact a family needed was put in place by its operator, where ADR-0024 left "
    "it"
)
"""What a run with no planter says about its cleanup.

A sentence rather than an absent line, on `PLANTING_CALLS = 0`'s reasoning: a
document that said nothing about the cleanup would leave a reader deciding for
themselves whether this bench had put something in their store and not taken it out.
"""


def teardown(
    planter: Planter | None, namespace: str, *, target_name: str | None
) -> Teardown | None:
    """Drop this run's namespace on one planter, and never raise doing it.

    `None` for a run holding no planter: there is nothing that could have planted, so
    there is nothing to report having dropped.

    **This never raises**, and that is the decision rather than an omission
    ([ADR-0063](../../docs/adr/0063-one-run-scoped-namespace-dropped-wholesale.md)
    §3). It is called from a `finally`, which is very often a `finally` unwinding an
    exception that is the run's actual answer — a `TargetUnreachable`, a
    `BudgetExceeded`, a `PlantingFailed`. A teardown that raised there would replace
    the reason the run ended with the reason its cleanup failed, and the operator
    would lose the first to learn the second. So both are kept: the original
    propagates and this comes back as a record.

    It drops the **namespace** and not the records. One call whose failure is total
    and visible, rather than an item-by-item delete that leaves a poisoned document
    behind the first failure and needs a manifest — a second copy of what was
    planted, in this harness, going stale — to be correct at all.
    """
    if planter is None:
        return None
    hook = getattr(planter, TEARDOWN_HOOK, None)
    if not callable(hook):
        # No `error`: there was no call, so there are no words of the operator's to
        # report, and `TeardownFailure.HOOK_MISSING.stated()` already says the whole
        # of it (ADR-0063 §3).
        return Teardown(
            namespace=namespace,
            target_name=target_name,
            failure=TeardownFailure.HOOK_MISSING,
        )
    return drop_namespace(hook, namespace, target_name=target_name)


def drop_namespace(
    drop: DropNamespace, namespace: str, *, target_name: str | None
) -> Teardown:
    """Make one drop call, and never raise doing it.

    The half of `teardown` that is about the call rather than about finding it, and
    public because the test equipment's drop is reached as a function and needs the
    same guarantee (`calibration.run_calibration`'s `drop_namespace`). One
    never-raises wrapper and one spelling of the error, rather than a second copy
    beside the caller that holds a callable.
    """
    try:
        drop(namespace)
    except Exception as raised:
        # The operator's own words, unlike `PlantingFailed`'s: a plant that raised
        # stops the run and its traceback is right there in the console, and this one
        # happens while another exception is on its way out and has nowhere else to
        # be read (ADR-0063 §3).
        return Teardown(
            namespace=namespace,
            target_name=target_name,
            failure=TeardownFailure.HOOK_RAISED,
            error=f"{type(raised).__name__}: {raised}",
        )
    return Teardown(namespace=namespace, target_name=target_name)


def teardown_all(
    planters: Mapping[str, Planter], namespace: str
) -> tuple[Teardown, ...]:
    """Drop this run's namespace on every object the run was handed.

    **Every planter, and not only the ones something was planted through.** A plant
    that raised halfway through a target's requests left the earlier ones in place,
    and a teardown that only visited the targets whose plant *finished* would leave
    exactly those behind. The namespace is one call to drop and dropping one that was
    never created is a shim author's no-op, so the safe direction is to ask everybody
    (ADR-0063 §2).
    """
    return tuple(
        dropped
        for name, planter in planters.items()
        if (dropped := teardown(planter, namespace, target_name=name)) is not None
    )


def _request_for(
    needed: Plant, case: Case, canary: str, namespace: str
) -> PlantingRequest:
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
                plant=needed,
                case_id=None,
                arguments={"namespace": namespace, "canary": canary},
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
                arguments={
                    "namespace": namespace,
                    "key": artefact.key,
                    "body": artefact.body,
                },
            )
