"""What the admission gate has already decided, and what it will not re-measure.

The money this saves is real and so is the hazard it introduces: a *past* run's
work changing what a *present* run reports is one step from a past run's *decision*
doing it, and the admission gate is the single edge the adaptive layer reaches the
scored side by (ADR-0010). So most of what is asserted here is what the memory
refuses to answer.

Four seams, in the order the code reads:

1. **The route** — `RouteKey.of`, the key. `family` plus a digest of the probe that
   actually ran, never the probe, and stable across a re-proposal under a fresh
   case id.
2. **The memory** — `DecidedRoutes.remember` and `.recall`. What is written, what
   comes back, and that it survives a restart (ADR-0019 point 4).
3. **Invalidation** — the four ways a record stops being this run's measurement:
   other models, another criterion, another denominator, and a recorded conclusion
   the current arithmetic no longer reaches.
The fourth seam — `consult` inside `scripts/swap.py`'s proposal loop, where the
admission run that does not happen is the whole of the saving — is asserted in
`test_multi_model.py`, beside the cross-model bar it is a change to.

The readings are constructed counts rather than measured ones, on the same terms
as `test_promotion.py`: whether a case *would* separate the reference agents is a
question about that case, and what is under test here is what the memory does with
the answer.
"""

import json
import subprocess
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from backend.bench import decided
from backend.bench.adaptive.precedent import DEFAULT_STORE_PATH, PRECEDENT_NAMESPACE
from backend.bench.adaptive.promotion import Promotion, promote
from backend.bench.adaptive.proposal import ProposedRoute, proposed_from
from backend.bench.admission import RejectionKind, kind_of
from backend.bench.decided import (
    DECIDED_ROUTES,
    DECISION_DIRECTORY,
    DECISION_NAMESPACE,
    DEFAULT_DECISION_PATH,
    DecidedRoutes,
    NotAboutTheRoute,
    Remembered,
    RouteKey,
    Stale,
    consult,
    worth_remembering,
)
from backend.bench.library import (
    AdmissionBar,
    AdmissionReading,
    Case,
    Family,
    Precondition,
    SuccessCondition,
    SuccessConditionKind,
)
from backend.bench.rule import DECLARED_RULE
from backend.tests.conftest import (
    BACKEND,
    CASES_DIR,
    REPOSITORY,
    a_target,
    reachable_from,
)

BENCH = BACKEND / "bench"

DECIDED_ON = date(2026, 8, 19)
"""The date the reference agents were run, so nothing here reads a clock."""

A_READER_HAS_FINISHED = 60.0
"""Seconds the subprocess above gets to open a local database and print four lines.

Generous, because what it is protecting against is a hang rather than slowness: a
reader that took longer than this is a reader that is waiting for a lock nothing
holds, and the test should say so rather than run until CI gives up.
"""

CHEAPER_RULE = replace(DECLARED_RULE, attempts_per_case=2)
"""A rule at a denominator ADR-0003 did not declare.

The one number of `GateRule` a console may set (ADR-0025), so it is the one a
reading can honestly have been taken at without anybody having moved the bar — which
makes it the right way to ask what the memory does with a reading at another `n`.
"""

FIRST_MODEL = "openrouter:openai/gpt-4.1-nano"
SECOND_MODEL = "openrouter:openai/gpt-4o-mini"
MODELS = (FIRST_MODEL, SECOND_MODEL)

SEPARATING = {"attempts": 10, "hardened": 0, "weak": 5, "trivial": 10}
"""Counts that clear the bar: D = 1.00 with intervals nowhere near each other."""

FLAT = {"attempts": 10, "hardened": 9, "weak": 9, "trivial": 10}
"""Counts that do not: the two ends are one attempt apart and the intervals
overlap."""

PROBE = "the probe that actually ran"


def a_route(
    objective: Case,
    payload: str = PROBE,
    description: str = "a route worth promoting",
) -> ProposedRoute:
    """One proposal, drafted the way `propose_case` drafts it inside an episode.

    A fresh `uuid` in the case id on every call, because `proposal.py` mints one —
    which is the fact that stops the case id being the key.
    """
    return proposed_from(
        objective=objective,
        target=a_target("trivial"),
        family=Family(objective.family),
        payload=payload,
        description=description,
        today=date(2026, 8, 18),
    )


def reading(model: str, counts: dict[str, int]) -> AdmissionReading:
    """One case's counts against the three agents, on one underlying model."""
    return AdmissionReading(
        model=model,
        attempts=counts["attempts"],
        hardened=counts["hardened"],
        weak=counts["weak"],
        trivial=counts["trivial"],
    )


# --- Seam one: the route is the key, and the probe is not in it ---------------


def test_the_same_route_proposed_twice_under_two_case_ids_is_one_key(
    leakage_case: Case,
) -> None:
    # `proposal.py` mints `adaptive-{family}-{uuid4}` per proposal, so a case id is
    # not stable across runs and cannot be the key. The route is: the family, and a
    # digest of the probe that actually ran.
    first = a_route(leakage_case)
    second = a_route(leakage_case)

    assert first.case.id != second.case.id
    assert RouteKey.of(first.case) == RouteKey.of(second.case)
    assert RouteKey.of(first.case).filed_under == RouteKey.of(second.case).filed_under


def test_a_route_key_carries_a_digest_of_the_probe_and_never_the_probe(
    leakage_case: Case,
) -> None:
    # ADR-0008: a route that beat a target is a working unpublished exploit. A
    # digest is idempotent, survives a re-proposal, and carries no exploit — the
    # same three properties `Precedent.key` is content-addressed for.
    route = RouteKey.of(a_route(leakage_case).case)

    assert PROBE not in route.filed_under
    assert route.probe not in PROBE
    assert route.family is leakage_case.family
    assert str(leakage_case.family) in route.filed_under


def test_two_different_probes_are_two_routes(leakage_case: Case) -> None:
    # The digest is over the probe, so a second route in the same family is a
    # second entry rather than an overwrite of the first.
    first = RouteKey.of(a_route(leakage_case, payload="one probe").case)
    second = RouteKey.of(a_route(leakage_case, payload="another probe").case)

    assert first != second
    assert first.filed_under != second.filed_under


def test_one_probe_in_two_families_is_two_routes(leakage_case: Case) -> None:
    # The family is in the key and not only in the value: the same words sent
    # under two families are two cases with two criteria, and one entry standing
    # for both would answer a question about one of them with the other's counts.
    leakage = RouteKey.of(a_route(leakage_case).case)
    elsewhere = RouteKey.of(
        replace(a_route(leakage_case).case, family=Family.HALT_DEFEAT)
    )

    assert leakage.probe == elsewhere.probe
    assert leakage.filed_under != elsewhere.filed_under


def test_the_namespace_is_single_tenant_and_has_no_tenant_in_it() -> None:
    # ADR-0019 point 5, restated by ADR-0029 point 4 and again here: cross-tenant
    # isolation is a named P1 blocker, so it has to be a visible absence rather
    # than an assumed presence. A third segment naming a user would look like
    # isolation and enforce none.
    assert DECISION_NAMESPACE == ("agentaudit", "admission")
    assert len(DECISION_NAMESPACE) == 2


# --- Seam two: the measurement is remembered, and the decision is not --------


@pytest.fixture
def memory(tmp_path: Path) -> DecidedRoutes:
    """This test's own memory, under a directory that is not there yet.

    Not there yet on purpose, the reason `test_precedent.store_file` gives: the
    store creates its parent, and a fixture that pre-made it would hide a backend
    that could only open a database beside an existing directory.
    """
    return DecidedRoutes.at(tmp_path / "decisions" / "routes.sqlite")


def decided_by_the_bar(
    proposal: ProposedRoute,
    first: dict[str, int],
    second: dict[str, int] | None = None,
) -> Promotion:
    """One proposal put to the bar on one or two models, and the gate's answer."""
    readings = [reading(FIRST_MODEL, first)]
    if second is not None:
        readings.append(reading(SECOND_MODEL, second))
    return promote(proposal, readings, today=DECIDED_ON)


def test_a_refused_route_is_remembered_with_its_rejection_kind_and_its_counts(
    memory: DecidedRoutes, leakage_case: Case
) -> None:
    # ADR-0012 calls a cross-model discard a finding in its own right, and
    # `RejectionKind` says why the four ways of failing are counted apart: "a count
    # means nothing unless the other ways of failing are counted apart from it". So
    # what is kept is the counts, and what comes back is the count *and* the answer
    # the current threshold reaches on it.
    promotion = decided_by_the_bar(a_route(leakage_case), SEPARATING, FLAT)
    assert kind_of(promotion.outcome) is RejectionKind.CROSS_MODEL

    entry = memory.remember(promotion, models=MODELS, today=DECIDED_ON)

    assert entry.decided_as is RejectionKind.CROSS_MODEL
    assert entry.readings == (
        reading(FIRST_MODEL, SEPARATING),
        reading(SECOND_MODEL, FLAT),
    )
    answer = memory.recall(a_route(leakage_case), models=MODELS)
    assert isinstance(answer, Remembered)
    assert kind_of(answer.promotion.outcome) is RejectionKind.CROSS_MODEL
    assert answer.promotion.case is None
    assert "reported from memory" in answer.stated()


def test_an_admitted_route_is_remembered_with_the_measurement_that_admitted_it(
    memory: DecidedRoutes, leakage_case: Case
) -> None:
    # The `AdmissionRecord` the issue asks for, and it is rebuilt from the counts
    # rather than stored: `promote` is what puts the bar and the readings on the
    # record, so a remembered admission and a measured one are the same record
    # produced by the same function.
    promotion = decided_by_the_bar(a_route(leakage_case), SEPARATING, SEPARATING)
    assert promotion.admitted
    memory.remember(promotion, models=MODELS, today=DECIDED_ON)

    answer = memory.recall(a_route(leakage_case), models=MODELS)

    assert isinstance(answer, Remembered)
    admitted = answer.promotion.case
    assert admitted is not None and admitted.admission is not None
    assert admitted.admission.bar is AdmissionBar.CROSS_MODEL
    assert admitted.admission.readings == (
        reading(FIRST_MODEL, SEPARATING),
        reading(SECOND_MODEL, SEPARATING),
    )
    # The date the three reference agents were run, and never the date the memory
    # was read: `admitted_on` is a fact about a measurement.
    assert admitted.admission.admitted_on == DECIDED_ON


def test_a_readings_adjudicator_survives_the_row(
    memory: DecidedRoutes, leakage_case: Case
) -> None:
    """The one field of a reading that is not a count, round-tripped.

    `AdmissionReading.read` is now what a case record's `[admission]` block, an entry
    of its decay series and this memory's rows all go through, and `adjudicator` is
    the field that would go missing quietly: a reading whose instrument was dropped
    reads as one a success condition decided, which is the inference ADR-0004 forbids
    being made from anything but the record.
    """
    judged = AdmissionReading(
        model=FIRST_MODEL,
        attempts=10,
        hardened=0,
        weak=5,
        trivial=10,
        adjudicator="stub:adjudicator",
    )
    memory.remember(
        promote(
            a_route(leakage_case),
            [judged, reading(SECOND_MODEL, FLAT)],
            today=DECIDED_ON,
        ),
        models=MODELS,
        today=DECIDED_ON,
    )

    answer = memory.recall(a_route(leakage_case), models=MODELS)

    assert isinstance(answer, Remembered)
    assert answer.decided.readings[0].adjudicator == "stub:adjudicator"
    assert answer.decided.readings[1].adjudicator is None
    assert "adjudicated by stub:adjudicator" in answer.promotion.outcome.stated()


def test_remembering_an_admission_does_not_write_to_the_case_library(
    memory: DecidedRoutes, leakage_case: Case
) -> None:
    # "Remembering an admission is not admitting." Entry itself is still a human's
    # action and #40 is the ticket that closes the loop; what this asserts is that
    # nothing here took that decision early.
    before = _library_bytes()

    memory.remember(
        decided_by_the_bar(a_route(leakage_case), SEPARATING, SEPARATING),
        models=MODELS,
        today=DECIDED_ON,
    )

    assert _library_bytes() == before


def test_the_same_route_proposed_twice_under_two_case_ids_is_one_entry(
    memory: DecidedRoutes, leakage_case: Case
) -> None:
    # The definition of done, and the reason the route is the key. Two proposals of
    # one path are one entry, and the second replaces the first rather than
    # accumulating beside it.
    first, second = a_route(leakage_case), a_route(leakage_case)
    memory.remember(
        decided_by_the_bar(first, SEPARATING, FLAT), models=MODELS, today=DECIDED_ON
    )
    memory.remember(
        decided_by_the_bar(second, SEPARATING, FLAT), models=MODELS, today=DECIDED_ON
    )

    assert len(memory.store.search(DECISION_NAMESPACE)) == 1
    third = a_route(leakage_case)
    answer = memory.recall(third, models=MODELS)
    assert isinstance(answer, Remembered)
    # This run's proposal is what the gate answered about; the remembered case id is
    # evidence of which earlier proposal the counts came from.
    assert answer.promotion.proposal.case.id == third.case.id
    assert answer.decided.case_id == second.case.id


def test_a_decision_outlives_the_memory_object_that_wrote_it(
    tmp_path: Path, leakage_case: Case
) -> None:
    # ADR-0019 point 4, applied to the second durable store: write, drop the object,
    # build a new one against the same location, read it back. A round trip through
    # one object would pass against `InMemoryStore`, which is what that ADR forbids.
    location = tmp_path / "decisions" / "routes.sqlite"
    DecidedRoutes.at(location).remember(
        decided_by_the_bar(a_route(leakage_case), SEPARATING, FLAT),
        models=MODELS,
        today=DECIDED_ON,
    )

    answer = DecidedRoutes.at(location).recall(a_route(leakage_case), models=MODELS)

    assert isinstance(answer, Remembered), (
        f"a new memory object against {location.name} could not read the decision "
        "back. A memory that dies with the object that wrote it re-measures every "
        "route on every run, which is the defect this store exists to fix"
    )
    assert answer.decided.decided_as is RejectionKind.CROSS_MODEL


READ_BACK = """
import sys
from pathlib import Path

from backend.bench.decided import DECISION_NAMESPACE, DecidedRoute, DecisionDatabase

found = DecisionDatabase(Path(sys.argv[1])).get(DECISION_NAMESPACE, sys.argv[2])
decided = DecidedRoute.read(dict(found.value))
print(decided.decided_as)
print(decided.case_id)
print(decided.decided_on.isoformat())
counted = (f"{r.model}:{r.hardened}/{r.trivial}/{r.attempts}" for r in decided.readings)
print(",".join(counted))
"""
"""A reader, as a program, because ADR-0019 point 4 says *in a new process*.

The test below writes the decision and this reads it back — so what crosses is the
file and nothing else: no object, no import-time cache, no module state the writer
left behind. `test_precedent.py` makes the same argument for the other durable store,
and the argument is what says the object-level test above is not the whole claim.
"""


def test_a_decision_outlives_the_process_that_wrote_it(
    tmp_path: Path, leakage_case: Case
) -> None:
    """ADR-0019 point 4, at the one boundary that cannot be faked.

    The test above drops the memory *object* and rebuilds it, which is the claim the
    ADR states; this drops the whole interpreter. Both are needed and the second is
    the stronger: a store that had quietly kept its rows in a module-level cache
    would satisfy the first and fail this.

    The counts are what is asserted to have crossed, and not the answer — there is no
    answer in the file to cross. What a second process gets back is a measurement.
    """
    location = tmp_path / "decisions" / "routes.sqlite"
    entry = DecidedRoutes.at(location).remember(
        decided_by_the_bar(a_route(leakage_case), SEPARATING, FLAT),
        models=MODELS,
        today=DECIDED_ON,
    )

    reader = subprocess.run(
        [sys.executable, "-c", READ_BACK, str(location), entry.route.filed_under],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        timeout=A_READER_HAS_FINISHED,
    )

    assert reader.returncode == 0, (
        f"a new process could not read the decision back:\n{reader.stderr}"
    )
    assert reader.stdout.splitlines() == [
        str(RejectionKind.CROSS_MODEL),
        entry.case_id,
        DECIDED_ON.isoformat(),
        f"{FIRST_MODEL}:0/10/10,{SECOND_MODEL}:9/10/10",
    ]


def test_consulting_a_memory_nothing_has_written_creates_no_database(
    tmp_path: Path, leakage_case: Case
) -> None:
    # ADR-0029 point 7: opening a database runs the migrations, so a lookup would
    # otherwise leave a file where there was none. A run that consulted the memory
    # and found nothing has learned something true, and *consulting* it is not an
    # event in its history.
    location = tmp_path / "decisions" / "routes.sqlite"

    assert (
        DecidedRoutes.at(location).recall(a_route(leakage_case), models=MODELS) is None
    )
    assert not location.exists()


def test_no_stored_record_carries_payload_text_or_a_target_identity(
    memory: DecidedRoutes, leakage_case: Case
) -> None:
    # ADR-0008: a route that beat a target is a working unpublished exploit.
    # ADR-0011: the contents accumulate across runs, so with enough of them a
    # failure pattern identifies a target on its own — and what is never written
    # cannot be redacted carelessly.
    target = a_target("an-agent-nobody-should-be-able-to-name")
    proposal = proposed_from(
        objective=leakage_case,
        target=target,
        family=Family(leakage_case.family),
        payload=PROBE,
        description="the attacker's own prose about what it did",
        today=DECIDED_ON,
    )
    memory.remember(
        decided_by_the_bar(proposal, SEPARATING, FLAT), models=MODELS, today=DECIDED_ON
    )

    [item] = memory.store.search(DECISION_NAMESPACE)
    written = json.dumps({"key": item.key, "value": item.value})

    for withheld in (PROBE, leakage_case.script, target.name, target.url):
        assert withheld not in written, (
            f"{withheld!r} reached the memory. The key is a digest and the value is "
            "counts and the attacker's prose (ADR-0008, ADR-0011)"
        )


def test_nothing_stored_is_a_verdict_a_rate_an_interval_or_a_threshold(
    memory: DecidedRoutes, leakage_case: Case
) -> None:
    """The invariant the whole module rests on, asserted against the row itself.

    What is remembered is the measurement; the decision is re-derived on the way
    out. So a `D`, a rate, an interval, a bar or a declared threshold in this row
    would be a past run's *answer* deciding what a present run reports — and
    ADR-0010 puts a declared threshold at this edge precisely so that it does not.

    Written as the row's own field names rather than as a behaviour, because the way
    this invariant is lost is somebody adding one convenient field.
    """
    memory.remember(
        decided_by_the_bar(a_route(leakage_case), SEPARATING, FLAT),
        models=MODELS,
        today=DECIDED_ON,
    )
    [item] = memory.store.search(DECISION_NAMESPACE)

    assert set(item.value) == {
        "family",
        "probe",
        "conditions",
        "readings",
        "decided_as",
        "description",
        "case_id",
        "decided_on",
    }
    assert set(item.value["conditions"]) == {"models", "criterion", "attempts"}
    for entry in item.value["readings"]:
        assert set(entry) == {
            "model",
            "attempts",
            "hardened",
            "weak",
            "trivial",
            "adjudicator",
        }
    written = json.dumps(item.value)
    for derived in ("discrimination", "interval", "bar", "clears", "rate", "floor"):
        assert derived not in written, (
            f"{derived!r} is in the remembered row. The memory holds counts, and "
            "everything a threshold decides is decided again on the way out"
        )


@pytest.mark.parametrize(
    ("second", "kind"),
    [(None, RejectionKind.UNREAD), ("nothing", RejectionKind.NOT_MEASURED)],
)
def test_a_run_that_did_not_measure_the_bar_has_nothing_to_remember(
    memory: DecidedRoutes, leakage_case: Case, second: str | None, kind: RejectionKind
) -> None:
    # `RejectionKind` draws the line and this reads it off: `UNREAD` is "a run that
    # did not happen the way the bar needs it to, and it is not evidence about the
    # route", and `NOT_MEASURED` is no reading at all. Remembering either would be
    # remembering that a measurement did not happen, and then answering a later run
    # with it.
    readings = [] if second == "nothing" else [reading(FIRST_MODEL, SEPARATING)]
    promotion = promote(a_route(leakage_case), readings, today=DECIDED_ON)
    assert kind_of(promotion.outcome) is kind

    assert not worth_remembering(promotion)
    with pytest.raises(NotAboutTheRoute, match=str(kind)):
        memory.remember(promotion, models=MODELS, today=DECIDED_ON)

    assert memory.store.search(DECISION_NAMESPACE) == []


# --- Seam three: a record that is not this run's measurement is not used -----


def test_a_decision_measured_on_other_models_is_not_answered_from_memory(
    memory: DecidedRoutes, leakage_case: Case
) -> None:
    """The invalidation that matters most, and the one a stub run makes concrete.

    A gate run on a stub model measures the field not at all (ADR-0022), so a
    cross-model bar met on `stub:obedient` and `stub:cooperative` is not met on two
    provider models — and `docs/validation.md`'s only recorded reading of this bar
    was taken on exactly those two stubs. A memory that answered a paid run from
    them would report a bar cleared against hardcoded replies as a bar cleared
    against the field.
    """
    memory.remember(
        promote(
            a_route(leakage_case),
            [reading("stub:obedient", SEPARATING), reading("stub:cooperative", FLAT)],
            today=DECIDED_ON,
        ),
        models=("stub:obedient", "stub:cooperative"),
        today=DECIDED_ON,
    )

    answer = memory.recall(a_route(leakage_case), models=MODELS)

    assert isinstance(answer, Stale)
    assert "stub:obedient" in answer.why and "ADR-0022" in answer.why
    assert "re-measuring" in answer.stated()


def test_a_decision_measured_at_another_denominator_is_not_answered_from_memory(
    memory: DecidedRoutes, leakage_case: Case
) -> None:
    # `GateRule.NOT_A_GATE_RESULT` in as many words: the Wilson interval, the band,
    # monotonicity and the retirement rule are defined against the declared n, and
    # nothing may compare a reading taken at another one to a reading taken at it.
    # A memory that did that quietly would be worse than no memory at all.
    cheaply = {"attempts": 2, "hardened": 0, "weak": 1, "trivial": 2}
    memory.remember(
        promote(
            a_route(leakage_case),
            [reading(FIRST_MODEL, cheaply), reading(SECOND_MODEL, cheaply)],
            rule=CHEAPER_RULE,
            today=DECIDED_ON,
        ),
        models=MODELS,
        rule=CHEAPER_RULE,
        today=DECIDED_ON,
    )

    answer = memory.recall(a_route(leakage_case), models=MODELS)

    assert isinstance(answer, Stale)
    assert "2 attempts per case" in answer.why
    assert str(DECLARED_RULE.attempts_per_case) in answer.why


def test_a_route_re_proposed_under_another_criterion_is_not_answered_from_memory(
    memory: DecidedRoutes, leakage_case: Case
) -> None:
    # The same probe under a different success condition is a different measurement:
    # the attacker found a new payload, not a new definition of what counts as a
    # break (`proposed_from`, ADR-0004). The counts on the record were read under a
    # question this proposal is not asking.
    memory.remember(
        decided_by_the_bar(a_route(leakage_case), SEPARATING, FLAT),
        models=MODELS,
        today=DECIDED_ON,
    )
    elsewhere = replace(
        a_route(leakage_case),
        case=replace(
            a_route(leakage_case).case,
            success_condition=SuccessCondition(
                kind=SuccessConditionKind.TOOL_CALL_AFTER_STOP
            ),
        ),
    )

    answer = memory.recall(elsewhere, models=MODELS)

    assert isinstance(answer, Stale)
    assert "criterion" in answer.why


def test_a_route_re_proposed_under_another_precondition_is_not_answered_from_memory(
    memory: DecidedRoutes, leakage_case: Case
) -> None:
    # A precondition gates measurability, so a case that now needs a capability the
    # measured one did not is a case a run may skip rather than measure. The counts
    # on the record cannot answer for it.
    memory.remember(
        decided_by_the_bar(a_route(leakage_case), SEPARATING, FLAT),
        models=MODELS,
        today=DECIDED_ON,
    )
    needier = replace(
        a_route(leakage_case),
        case=replace(
            a_route(leakage_case).case,
            requires=(
                Precondition.TOOL_CALL_VISIBILITY,
                # Kept from the case itself, which reads the planted nonce.
                Precondition.CONFIG_CANARY_PLANT,
            ),
        ),
    )

    answer = memory.recall(needier, models=MODELS)

    assert isinstance(answer, Stale)
    assert "preconditions" in answer.why


def test_a_declared_threshold_that_moved_under_the_record_re_measures_the_route(
    memory: DecidedRoutes, leakage_case: Case
) -> None:
    """The defect the ticket has to prevent, and the tripwire that prevents it.

    A route admitted at `D >= 0.4` and read back under a rule that demands more is
    the case where a memory could silently admit what the declared threshold would
    refuse. It cannot here, twice over: nothing stored is an answer, so the counts
    are decided again — and the answer the measuring run reached is stored beside
    them, so a re-derivation that lands somewhere else says so instead of choosing
    between the two thresholds.
    """
    stricter = replace(DECLARED_RULE, discrimination_floor=1.5)
    memory.remember(
        decided_by_the_bar(a_route(leakage_case), SEPARATING, SEPARATING),
        models=MODELS,
        today=DECIDED_ON,
    )

    answer = memory.recall(a_route(leakage_case), models=MODELS, rule=stricter)

    assert isinstance(answer, Stale)
    assert str(RejectionKind.SEPARATED_NOWHERE) in answer.why
    assert str(RejectionKind.ADMITTED) in answer.why
    assert "measured again" in answer.why


def test_a_recorded_answer_the_arithmetic_no_longer_reaches_re_measures_the_route(
    memory: DecidedRoutes, leakage_case: Case
) -> None:
    """The same tripwire, tripped by the row rather than by the rule.

    A record whose `decided_as` does not follow from its own counts is what an
    admission arithmetic that moved under the file looks like from here — and it is
    also what a hand-edited row looks like. Neither is reconciled: this module has
    no standing to decide which of the two answers is right, so the route is
    measured again.
    """
    entry = memory.remember(
        decided_by_the_bar(a_route(leakage_case), SEPARATING, SEPARATING),
        models=MODELS,
        today=DECIDED_ON,
    )
    memory.store.put(
        DECISION_NAMESPACE,
        entry.route.filed_under,
        {**entry.stored(), "decided_as": str(RejectionKind.CROSS_MODEL)},
    )

    answer = memory.recall(a_route(leakage_case), models=MODELS)

    assert isinstance(answer, Stale)
    assert str(RejectionKind.ADMITTED) in answer.why


def test_a_re_measured_route_is_counted_apart_from_one_never_proposed(
    memory: DecidedRoutes, leakage_case: Case
) -> None:
    # `RejectionKind`'s reasoning about counting the four refusals apart, applied to
    # the memory's own two misses. A route re-measured because a record stopped
    # applying is the event that says the invalidation rules are working, and one
    # number over both would report it as a route nobody had ever proposed.
    memory.remember(
        promote(
            a_route(leakage_case),
            [reading("stub:obedient", SEPARATING), reading("stub:cooperative", FLAT)],
            today=DECIDED_ON,
        ),
        models=("stub:obedient", "stub:cooperative"),
        today=DECIDED_ON,
    )
    never_seen = a_route(leakage_case, payload="a probe nothing has decided")

    consulted = consult(memory, (a_route(leakage_case), never_seen), models=MODELS)

    assert consulted.remembered == ()
    assert len(consulted.stale) == 1
    assert len(consulted.to_measure) == 2
    stated = consulted.stated()
    assert "2 proposal(s) put to the bar, 0 answered from memory" in stated
    assert "2 route(s) to measure" in stated
    assert "1 of those route(s) had a record this run will not use" in stated


def test_a_stale_record_is_not_repaired_and_not_deleted(
    memory: DecidedRoutes, leakage_case: Case
) -> None:
    # A lookup does not write. The record stays as the run that measured it left it,
    # for the reason a retired case is marked and never deleted: it is evidence of
    # what was measured, and the run that supersedes it is the run that will replace
    # it (`remember` is idempotent by the key).
    memory.remember(
        promote(
            a_route(leakage_case),
            [reading("stub:obedient", SEPARATING), reading("stub:cooperative", FLAT)],
            today=DECIDED_ON,
        ),
        models=("stub:obedient", "stub:cooperative"),
        today=DECIDED_ON,
    )
    before = memory.store.get(
        DECISION_NAMESPACE, RouteKey.of(a_route(leakage_case).case).filed_under
    )
    assert before is not None

    memory.recall(a_route(leakage_case), models=MODELS)

    after = memory.store.get(DECISION_NAMESPACE, before.key)
    assert after is not None and after.value == before.value


# --- The walls: what may not reach this memory, and what it may not reach ----


def test_no_scored_instrument_can_reach_the_admission_memory() -> None:
    """ADR-0010, in the one direction that would break it.

    The memory reads the admission arithmetic — that is what re-deriving a decision
    *is* — so the wall cannot be "nothing may import anything". It is that no
    instrument producing a scored number may reach the memory: the file is
    machine-local and git-ignored, so a rate, an interval, a band, a `D` or a κ that
    read it would be a figure that depended on the machine.

    The judge and the adjudicator are in the list for ADR-0004 and ADR-0013's reason
    as well as this one, and their own walls against the precedent store are
    unmodified in `test_precedent.py`.
    """
    for source in (
        BENCH / "gate.py",
        BENCH / "scorer.py",
        BENCH / "crossmodel.py",
        BENCH / "calibration.py",
        BENCH / "judge.py",
        BENCH / "adjudication.py",
        BENCH / "admission.py",
    ):
        reachable = [name for name in reachable_from(source) if "bench.decided" in name]
        assert not reachable, (
            f"{reachable} is reachable from {source.name}. Nothing that produces a "
            "signed number may read a machine-local file (ADR-0010)"
        )


def test_the_memory_is_its_own_database_and_not_a_table_in_the_precedent_store() -> (
    None
):
    # ADR-0029 decision 6 — one database, one concern — and the reason it recorded
    # for this ticket: the gate's decisions are scored-side state and precedent is
    # adaptive-layer memory, which ADR-0004 and ADR-0013 keep apart with an import
    # test. One path over both makes "does the separation still hold?" a question
    # every future reviewer has to re-answer.
    assert DEFAULT_DECISION_PATH != DEFAULT_STORE_PATH
    assert DEFAULT_DECISION_PATH.parent != DEFAULT_STORE_PATH.parent
    assert DECISION_NAMESPACE != PRECEDENT_NAMESPACE


@pytest.mark.parametrize(
    "name", ["routes.sqlite", "routes.sqlite-wal", "routes.sqlite-shm"]
)
def test_the_memory_and_its_sidecars_are_ignored_by_git(name: str) -> None:
    """ADR-0008, and the constraint the ticket states: the store is machine-local.

    Asked of git rather than of `.gitignore`'s text, on `test_precedent.py`'s
    reasoning, and the sidecars are parametrised rather than assumed covered: WAL
    writes two files beside the database, and a journal carrying the prose of a route
    that beat an agent must not be the one thing the ignore rule missed.

    Built from `DECISION_DIRECTORY` rather than from `DEFAULT_DECISION_PATH`, because
    `conftest.py` redirects the store and never the directory.
    """
    if not (REPOSITORY / ".git").exists():
        pytest.skip("not a git checkout, so git's own answer cannot be asked for")

    path = DECISION_DIRECTORY / name
    checked = subprocess.run(
        ["git", "check-ignore", "-q", str(path)], cwd=REPOSITORY, check=False
    )

    assert checked.returncode == 0, (
        f"{path} is not ignored by git, so the prose of a route that beat a real "
        "agent is one `git add` away from being published"
    )


def test_the_memory_a_run_reads_is_redirected_into_the_test_that_is_running(
    tmp_path: Path,
) -> None:
    """`conftest.decisions_elsewhere`, asserted rather than trusted.

    Against *this* test's `tmp_path` rather than merely against the real location,
    because two different things have to hold and only one of them is visible from
    "it is not the real file": no test reaches the engineer's own memory, and no
    test reads another test's. The second is what keeps the suite's result
    independent of its order, since this memory decides whether an admission run
    happens at all.
    """
    for live in _live_memory_paths():
        assert live != DEFAULT_DECISION_PATH, (
            "a test can reach the admission memory a real run uses. Every run such "
            "a test makes decides against the engineer's own remembered routes, "
            "which is a suite whose result depends on the machine"
        )
        assert live.is_relative_to(tmp_path), (
            f"{live} is not under this test's own directory, so one test's "
            "remembered decision is what the next test's proposal is answered from"
        )


@pytest.fixture(scope="module")
def memory_at_module_setup() -> tuple[Path, ...]:
    """The live paths, read while a *module-scoped* fixture is being built.

    The window the equivalent defect lived in for the precedent store, recorded in
    ADR-0029's consequences: pytest builds a higher-scoped fixture before a
    function-scoped one, so an autouse redirection that is only function-scoped is
    not in place when `test_gate.py`'s module-scoped gate run is constructed — and
    that run wrote 540 attempts' worth of findings into the working copy for weeks,
    quietly, because the location is git-ignored. This is that defect pre-empted for
    the second store rather than rediscovered.
    """
    return _live_memory_paths()


def test_no_module_scoped_fixture_escapes_the_redirection(
    memory_at_module_setup: tuple[Path, ...],
) -> None:
    """The session-scoped half of the redirection, asserted from the scope that
    escaped the precedent store's."""
    for live in memory_at_module_setup:
        assert live != DEFAULT_DECISION_PATH, (
            "a module-scoped fixture is built outside the per-test redirection, so "
            "any run one of them makes remembers its decisions in the working copy"
        )


def _live_memory_paths() -> tuple[Path, ...]:
    """Every route to the memory, as it stands at the moment of the call.

    Two of them, because `conftest._decisions_at` redirects two and a redirection
    that missed one would leave a route into the working copy. Read off the module
    rather than off the name this file imported, because the fixture patches the
    module and an imported constant answers with the value it had at import — which
    is the real location, and is what the git question above relies on.
    """
    return (decided.DEFAULT_DECISION_PATH, DECIDED_ROUTES.store.path)


def _library_bytes() -> bytes:
    """Every case record in the library, as one value a change of any of them moves."""
    return b"".join(
        sorted(path.read_bytes() for path in CASES_DIR.rglob("*") if path.is_file())
    )
