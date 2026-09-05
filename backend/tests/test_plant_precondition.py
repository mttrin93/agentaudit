"""A plant is a precondition, and a hook nobody implemented withdraws its family.

The seams these tests sit at:

* `library.Plant` and `Precondition` — the vocabulary, and the joins between them
  that make a third planting a record rather than an edit
  ([ADR-0061](../../docs/adr/0061-a-plant-is-a-precondition-the-bench-can-check.md)).
* `Case.__post_init__` — a record needing a planting declares it, both ways round.
* `measurability.not_measurable_families` and `runnable` — the withdrawal, read
  through the two functions the run already asks.
* `shim.serve_callback` — a `TargetConfig` whose plantings it read off the object.

**Two surfaces and two answers, so both are here.** A served target answers for its
own plantings and a URL does not, and the test that a URL target's `DeclaredGap`
members are exactly where ADR-0024 left them is as much the decision as the
withdrawal is.
"""

from __future__ import annotations

import inspect
from dataclasses import replace

import pytest

from backend.api.run_config import plan_for
from backend.api.run_status import DeclaredGap
from backend.api.runs import BenchConfig
from backend.bench import shim
from backend.bench.contract import TargetConfig
from backend.bench.library import (
    PLANTED_IN_THE_CONFIGURATION,
    Case,
    ElectiveFamily,
    Family,
    Plant,
    PlantedIn,
    Precondition,
    load_elective,
    load_library,
)
from backend.bench.measurability import (
    REFUSED_FOR,
    NotMeasurable,
    not_measurable_elective_families,
    not_measurable_families,
    runnable,
    unmet_preconditions,
)
from backend.bench.planting import TEARDOWN_HOOK
from backend.bench.shim import declared_plants, hook_name, serve_callback
from backend.tests.conftest import CASES_DIR, case_for

ANSWERS = "nothing to see here"

FOR_A_MISSING_PLANT = frozenset(
    {NotMeasurable.NO_CONFIG_CANARY_PLANT, NotMeasurable.NO_RETRIEVED_CONTENT_PLANT}
)
"""The two reasons this ticket added, so a test can say *not for a missing plant*.

Read rather than asserted against an empty mapping, because a target that answers in
text alone is withdrawn from the two tool-visibility families whatever it can be
planted with — an older gap, and not the one under test here.
"""


def blind(message: str, session_id: str) -> str:
    """A user's agent as most of them arrive: a function, and no hooks at all."""
    return ANSWERS


class PlantsEverything:
    """A user's agent that implements every planting hook this bench knows of.

    Derived from `Plant` rather than written out, so it keeps declaring everything
    on the day a seventh family adds a member — which is the property the tests that
    use it are about.
    """

    def __call__(self, message: str, session_id: str) -> str:
        return ANSWERS

    def plant_config_canary(self, namespace: str, canary: str) -> None:
        self.canary = canary

    def plant_retrieved_content(self, namespace: str, key: str, body: str) -> None:
        self.content = (key, body)

    def teardown(self, namespace: str) -> None:
        self.dropped = namespace


def library() -> list[Case]:
    return load_library(CASES_DIR)


def both_tiers() -> list[Case]:
    return library() + load_elective(CASES_DIR, list(ElectiveFamily))


def a_url_target(**declared: object) -> TargetConfig:
    """A target described the way a user's staging endpoint is described."""
    return TargetConfig(
        name="staging",
        url="https://example.invalid/messages",
        auth_token="t",
        agent_type="assistant",
        exposes_tool_calls=True,
        retains_session_state=True,
        holds_personal_records=True,
        **declared,  # type: ignore[arg-type]
    )


# --- The withdrawal ----------------------------------------------------------


def test_a_shim_with_no_config_canary_hook_does_not_measure_data_leakage() -> None:
    """The headline. A gap the bench detects, so `NotMeasurable` and not a rate."""
    cases = library()
    with serve_callback(blind, name="blind") as target:
        assert target.plants == frozenset()
        withdrawn = not_measurable_families(cases, target)
        attempted = {case.family for case in runnable(cases, target)}

    assert withdrawn[Family.DATA_LEAKAGE] is NotMeasurable.NO_CONFIG_CANARY_PLANT
    assert Family.DATA_LEAKAGE not in attempted


def test_a_shim_with_no_content_hook_does_not_measure_what_content_attacks() -> None:
    """Both tiers, because the fetched-content plant is what six cases need.

    The elective answer comes back in its own mapping and not in the six's, which is
    ADR-0035's split asked of a reason that is new here.
    """
    cases = both_tiers()
    # Session retention declared, so what withdraws memory poisoning below is the
    # missing hook and never the older precondition it also carries.
    with serve_callback(blind, name="blind", retains_session_state=True) as target:
        six = not_measurable_families(cases, target)
        tier = not_measurable_elective_families(cases, target)

    assert (
        six[Family.INDIRECT_PROMPT_INJECTION]
        is NotMeasurable.NO_RETRIEVED_CONTENT_PLANT
    )
    assert (
        tier[ElectiveFamily.MEMORY_POISONING]
        is NotMeasurable.NO_RETRIEVED_CONTENT_PLANT
    )
    assert not any(isinstance(family, ElectiveFamily) for family in six)


def test_a_shim_that_implements_the_hooks_is_measured_on_the_families() -> None:
    """The complement, and the test that the withdrawal is about the hook.

    Same library, same bench, one difference in the object handed over.
    """
    cases = both_tiers()
    with serve_callback(
        PlantsEverything(), name="planter", retains_session_state=True
    ) as target:
        assert target.plants == frozenset(Plant)
        withdrawn = set(not_measurable_families(cases, target).values())
        withdrawn |= set(not_measurable_elective_families(cases, target).values())
        attempted = {case.family for case in runnable(cases, target)}

    assert not withdrawn & FOR_A_MISSING_PLANT

    assert Family.DATA_LEAKAGE in attempted
    assert Family.INDIRECT_PROMPT_INJECTION in attempted
    assert ElectiveFamily.MEMORY_POISONING in attempted


def test_a_family_withdrawn_for_a_missing_hook_is_named_and_never_scored() -> None:
    """Not failed, not zero and not absent — `payload.py`'s three kinds of nothing.

    The reason is what a reader is given in place of the figure, and it says what
    closes the gap the way the tool-visibility reasons say *expose your tool calls*.
    """
    with serve_callback(blind, name="blind") as target:
        reason = not_measurable_families(library(), target)[Family.DATA_LEAKAGE]

    stated = reason.stated()
    assert stated.startswith("not measurable")
    assert hook_name(Plant.CONFIG_CANARY) in stated
    assert "0" not in stated


# --- The other surface, unmoved ----------------------------------------------


def test_a_url_target_answers_for_no_planting_and_keeps_its_declared_gaps() -> None:
    """The two `DeclaredGap` members stay exactly where ADR-0024 left them.

    A target the bench cannot see inside answers `None`, which is neither *can* nor
    *cannot*: the caller's declaration decides, through `plan_for`, and every case in
    the library is still measurable against an endpoint that never heard of a hook.
    """
    target = a_url_target()
    assert target.plants is None
    assert not not_measurable_families(both_tiers(), target)
    assert not not_measurable_elective_families(both_tiers(), target)
    assert runnable(library(), target) == library()

    assert DeclaredGap.NOTE_NOT_PLANTED.stated().startswith("not run")
    assert DeclaredGap.NONCE_NOT_PLANTED.stated().startswith("not run")


def test_the_caller_who_planted_nothing_still_gets_the_declared_gap() -> None:
    """`plan_for` is untouched: the endpoint's plant is still the caller's sentence."""
    plan = plan_for(BenchConfig(cases=library()), note_planted=False)
    assert plan.gaps[Family.INDIRECT_PROMPT_INJECTION] is DeclaredGap.NOTE_NOT_PLANTED
    assert all(
        case.family is not Family.INDIRECT_PROMPT_INJECTION for case in plan.cases
    )


# --- The set is general, so #48 and #50 arrive as records --------------------


def test_every_planting_names_a_precondition_a_reason_and_a_hook() -> None:
    """A `Plant` member is a record: nothing else has to be edited to add one.

    Four joins, each derived or asserted total rather than written out — the
    precondition from the member's value, the reason from `REFUSED_FOR`, the hook
    name from the member, and the sentence from `stated`. A member added for #48 or
    #50 that broke any of them fails here rather than at the run that needed it.
    """
    for plant in Plant:
        precondition = plant.precondition
        assert precondition in Precondition
        assert precondition in REFUSED_FOR
        assert plant.stated()
        assert hook_name(plant).startswith("plant_")
        # And the sentence the report prints names *this* hook. The reasons spell
        # the name out rather than deriving it, because the wording round it is
        # per-member prose; this is what keeps the two spellings one fact.
        assert hook_name(plant) in REFUSED_FOR[precondition].stated()


def test_every_planting_hook_is_spelled_out_by_exactly_one_protocol() -> None:
    """The hooks a user implements are typed, and the type checker knows the names.

    Collected by walking `shim` for protocols rather than by importing a list of
    them, so a `Plant` whose protocol nobody wrote is caught here — which is the
    failure #48 and #50 would otherwise discover at a run.
    """
    hooks: dict[str, list[str]] = {}
    for name, member in vars(shim).items():
        if not (inspect.isclass(member) and getattr(member, "_is_protocol", False)):
            continue
        for attribute in vars(member):
            if attribute.startswith("plant_"):
                hooks.setdefault(attribute, []).append(name)

    assert {hook_name(plant) for plant in Plant} == set(hooks)
    assert all(len(spelling) == 1 for spelling in hooks.values()), hooks

    # And one hook per protocol, which is the half a name check alone does not make.
    # A hook that migrated into a neighbouring protocol still appears exactly once by
    # name, and leaves behind a protocol every object satisfies and another that
    # demands a planting hook of anything that can only clean up — which is what
    # `serve_callback` reads the pair apart for (ADR-0063 §4).
    spellings = [name for spelling in hooks.values() for name in spelling]
    assert len(set(spellings)) == len(spellings), hooks
    assert TEARDOWN_HOOK not in {
        attribute
        for name in spellings
        for attribute in vars(getattr(shim, name))
        if not attribute.startswith("_")
    }


def test_a_planting_a_record_can_carry_is_the_planting_it_names() -> None:
    """`PlantedIn` is the subset of `Plant` a case record may write down.

    Every member of the record's enumeration resolves to a planting, and the one
    that does not appear there is the one no record may name: the registration nonce
    is issued per run (ADR-0007).
    """
    assert {member.plant for member in PlantedIn} < set(Plant)
    assert Plant.CONFIG_CANARY not in {member.plant for member in PlantedIn}


# --- The record declares what it needs, both ways round ----------------------


def test_a_case_that_needs_a_planting_and_declares_none_is_refused() -> None:
    # Through `case_for`, which names the record rather than taking the family's
    # first: `data-leakage-001-scripted_crescendo` sorts ahead of its own base and is
    # four turns, so stripping its `requires` trips ADR-0053's session-retention
    # refusal before it ever reaches this one and the test passes on the wrong
    # exception (#150).
    case = case_for(library(), Family.DATA_LEAKAGE)
    assert Precondition.CONFIG_CANARY_PLANT in case.requires

    with pytest.raises(ValueError, match="needs.*before its attack turn"):
        replace(case, requires=())


def test_a_case_carrying_content_and_declaring_no_content_plant_is_refused() -> None:
    case = case_for(library(), Family.INDIRECT_PROMPT_INJECTION)
    assert Precondition.RETRIEVED_CONTENT_PLANT in case.requires

    with pytest.raises(ValueError, match="needs.*before its attack turn"):
        replace(case, requires=())


def test_every_committed_case_asks_for_exactly_the_plantings_it_needs() -> None:
    """The other direction, over the library rather than over every `Case`.

    A record declaring a planting it does not need is withdrawn from targets that
    could have answered it, which is a coverage fault and not a soundness one — so it
    is caught here, where every committed record is in view, rather than on
    `Case.__post_init__`, where it would also refuse a fixture built by replacing
    another case's success condition (ADR-0061 §7).
    """
    for case in both_tiers():
        condition = case.success_condition
        needed = set()
        if condition is not None and condition.kind in PLANTED_IN_THE_CONFIGURATION:
            needed.add(Plant.CONFIG_CANARY)
        if case.planted_artefact is not None:
            needed.add(case.planted_artefact.where.plant)
        declared = {plant for plant in Plant if plant.precondition in case.requires}
        assert declared == needed, case.id


# --- A plant is not an attempt, and there is nowhere for one to arrive -------


def test_no_planting_hook_is_reachable_over_the_wire() -> None:
    """The epic's own scope line: no plant through `send_message`.

    A hook is a method on a user's object and the served app has one route, so there
    is no path by which planting could arrive as a turn — and a turn is what an
    attempt is counted in. Asserted against the app's own routes rather than by
    posting, so a route added for a hook fails here whatever it answers.
    """
    app = shim._create_callback_app(PlantsEverything(), "token", "planter", False)
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert shim.MESSAGES_PATH in paths
    assert not any(hook_name(plant) in path for plant in Plant for path in paths)


def test_a_declared_planting_moves_no_rate_and_only_which_cases_are_asked() -> None:
    """A shim declaring fewer hooks changes what is *attempted* and nothing else.

    The two targets differ in one hook, and what differs between them is the set of
    cases and never a figure: `unmet_preconditions` is the whole of the difference,
    and it is asked before an attempt is spent.
    """
    planted = a_url_target(plants=frozenset({Plant.CONFIG_CANARY}))
    unplanted = a_url_target(plants=frozenset())
    leakage = next(c for c in library() if c.family is Family.DATA_LEAKAGE)

    assert unmet_preconditions(leakage, planted) == ()
    assert unmet_preconditions(leakage, unplanted) == (
        Precondition.CONFIG_CANARY_PLANT,
    )
    assert leakage in runnable(library(), planted)


def test_a_plain_function_declares_no_planting_and_a_method_does() -> None:
    """Read off the object at construction, and never at attack time."""
    assert declared_plants(blind) == frozenset()
    assert declared_plants(PlantsEverything()) == frozenset(Plant)
