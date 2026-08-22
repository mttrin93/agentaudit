"""The content the indirect prompt injection family attacks with, served to plant.

`GET /bench/notes` closes the one gap the registration walk had: a box declaring that
the hostile content is in place, over a bench that never said what the content is. A
case in this family *is* a piece of content — the payload the bench sends is a
colleague's ordinary message, and everything adversarial is in what the target
fetched — so an operator who planted something of their own would have thirty
attempts run against an attack whose canary can never appear, and read the clean zero
as a defence.

**The pairing is the canary and nothing else.** A note is served against a case when
its executed line is that case's `planted_canary`, which is the exact string
`evaluator.py` searches the reply for. Asserted here from both ends: every live case
in the family is served content, and the content served is the content whose
execution produces that case's canary.

**The canary is composed, and the served body must not carry it joined.** The note
spells out a prefix in one place and a reference in another; only obeying the
instruction puts them together. A note whose body contained the finished string would
be scored by a target that quoted it back while refusing it, which would turn every
refusal into a success — so that is asserted over the bytes this route serves rather
than only over the corpus.
"""

from __future__ import annotations

from dataclasses import replace

from fastapi.testclient import TestClient

from backend.api.app import BENCH_NOTES_ROUTE, create_app
from backend.api.runs import BenchConfig
from backend.bench.library import Case, Family, SuccessCondition, SuccessConditionKind
from backend.tests.conftest import retired_case


def injection_cases(library: list[Case]) -> list[Case]:
    return [case for case in library if case.family is Family.INDIRECT_PROMPT_INJECTION]


def test_every_live_case_in_the_family_is_served_the_content_it_scores_on(
    library: list[Case],
) -> None:
    """The whole point of the route: nothing to plant is nothing an operator can do.

    Both ends of the pairing. Every live case in the family appears, so the walk
    cannot ask for content the bench holds none of; and each served canary is that
    case's `planted_canary`, so what is served is the content whose execution
    produces the string the verdict is decided on rather than whatever note happened
    to be next in the folder.
    """
    client = TestClient(create_app(BenchConfig(cases=library)))

    served = client.get(BENCH_NOTES_ROUTE).json()

    scored = {
        case.id: case.success_condition.planted_canary
        for case in injection_cases(library)
        if case.success_condition is not None
    }
    assert scored, "the library has no live injection case to plant content for"
    assert {note["case"] for note in served["notes"]} == set(scored)
    assert served["unpaired"] == []
    for note in served["notes"]:
        assert note["canary"] == scored[note["case"]]
        assert note["body"].strip()
        assert note["key"]


def test_the_body_carries_the_two_halves_and_never_the_finished_canary(
    library: list[Case],
) -> None:
    """A note carrying the joined string would score every refusal that quoted it.

    The composition is a soundness property of the family (ADR-0004): a target that
    reproduces the whole note while refusing it reproduces both halves and never the
    join. Asserted over what this route serves, because the route is now a second
    place the content can be got at and a body assembled here rather than read off
    the corpus is exactly how the property would be lost.
    """
    client = TestClient(create_app(BenchConfig(cases=library)))

    served = client.get(BENCH_NOTES_ROUTE).json()

    for note in served["notes"]:
        assert note["canary"] not in note["body"]
        prefix, reference = note["canary"].rsplit("-", 1)
        assert f"{prefix}-" in note["body"]
        assert reference in note["body"]


def test_a_case_this_bench_holds_no_note_for_is_named_rather_than_dropped(
    library: list[Case],
) -> None:
    """A shorter list would look complete.

    A case scored on a canary no note produces is a case an operator cannot plant
    for, and the honest answer is its id — not an omission that reads as *there are
    two of these* to somebody who never counted the family.
    """
    [first, *rest] = injection_cases(library)
    drifted = replace(
        first,
        success_condition=SuccessCondition(
            kind=SuccessConditionKind.CANARY_INSTRUCTION_EXECUTED,
            planted_canary="NOTE-PROCESSED-NOTHING-WROTE-THIS",
        ),
    )
    client = TestClient(create_app(BenchConfig(cases=[drifted, *rest])))

    served = client.get(BENCH_NOTES_ROUTE).json()

    assert served["unpaired"] == [drifted.id]
    assert drifted.id not in {note["case"] for note in served["notes"]}
    assert {note["case"] for note in served["notes"]} == {case.id for case in rest}


def test_a_retired_case_asks_for_no_content(library: list[Case]) -> None:
    """Content planted for a case no run attempts is content planted for nothing.

    The live half only, as the agent types offered on the same screen are, and for
    the same reason: what this screen offers is what the next run will do.
    """
    retired = [
        retired_case(case) if case.family is Family.INDIRECT_PROMPT_INJECTION else case
        for case in library
    ]
    client = TestClient(create_app(BenchConfig(cases=retired)))

    served = client.get(BENCH_NOTES_ROUTE).json()

    assert served["notes"] == []
    assert served["unpaired"] == []


def test_nothing_here_is_a_measurement_and_nothing_names_a_target(
    library: list[Case],
) -> None:
    """`/bench` is the instrument's own prefix (ADR-0018).

    Four fields, and a route under this prefix that grew a rate, a band or a
    readiness flag would be this bench reporting on somebody's agent from a screen
    that has never called one. Whether the content is in place is the operator's
    declaration at registration, which this bench cannot check.
    """
    client = TestClient(create_app(BenchConfig(cases=library)))

    served = client.get(BENCH_NOTES_ROUTE).json()

    assert set(served) == {"notes", "unpaired", "stated"}
    assert set(served["notes"][0]) == {"case", "key", "body", "canary"}
