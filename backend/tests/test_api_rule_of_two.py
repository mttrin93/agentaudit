"""The four Rule-of-Two declarations over HTTP: registered, and read back.

Two claims, and they are two because the surface has two halves.

**A target registered over HTTP can declare all four.** Until #177 it could not:
`TargetRequest` had no fields for them, so `config()` built a `TargetConfig` with
four unstated declarations whatever the caller sent, and every report this bench
produced read `not_declared` because there was no way to say anything else
([ADR-0092](../../docs/adr/0092-the-rule-of-two-is-declared-on-the-register-walk-and-the-reading-is-the-backends.md)).
So the first tests here are about the request model, and they assert the values
arrive on the `TargetConfig` the scan reads — the far end of that is
`test_scan.py`, which owns the reading itself.

**The reading is the backend's, and `POST /rule-of-two` is where a screen gets it.**
The route computes nothing: it hands the four answers to `scanner` and returns the
standing's name and the sentence that goes with it. The standings are asserted as
literal names rather than against a second call to the reading — a test that
recomputed the expected value the way the route does could not disagree with it —
and one of them is the ordering ADR-0038 decision 5 records getting wrong on its
first draft, which is the arm worth pinning from the outside.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.app import RULE_OF_TWO_ROUTE, TargetRequest, create_app
from backend.api.runs import BenchConfig
from backend.bench.library import Case
from backend.bench.scanner import NOT_A_MEASUREMENT, RuleOfTwoStanding


def a_request(
    processes_untrusted_input: bool | None = None,
    reaches_private_data: bool | None = None,
    changes_state_or_communicates: bool | None = None,
    under_human_supervision: bool | None = None,
) -> TargetRequest:
    """A registration for an endpoint, with whatever it declares about its shape.

    The four written out rather than taken as keywords, so that a field renamed on
    the model is a type error here rather than a keyword this helper forwards into
    a `TargetRequest` that ignores it — which is the failure the first test below
    exists to catch and would then never see.
    """
    return TargetRequest(
        name="staging support agent",
        url="https://staging.example/agent",
        auth_token="token",
        agent_type="customer support",
        exposes_tool_calls=False,
        processes_untrusted_input=processes_untrusted_input,
        reaches_private_data=reaches_private_data,
        changes_state_or_communicates=changes_state_or_communicates,
        under_human_supervision=under_human_supervision,
    )


def test_a_registration_carries_all_four_declarations_to_the_config() -> None:
    """The blocking dependency for the whole of #177: the answers have to arrive.

    All four, each with a value the reading distinguishes: one held, one declared
    absent, one left out entirely, and the supervision answer. A `TargetRequest`
    that dropped any of them would post a walk's declarations into nothing and the
    report would print `not_declared` with nobody able to see why.
    """
    config = a_request(
        processes_untrusted_input=True,
        reaches_private_data=False,
        under_human_supervision=True,
    ).config()

    assert config.processes_untrusted_input is True
    assert config.reaches_private_data is False
    # Never sent, and so never stated. `False` here would be a claim the caller did
    # not make, in the direction ADR-0038 calls the profitable one.
    assert config.changes_state_or_communicates is None
    assert config.under_human_supervision is True


def test_a_registration_that_declares_nothing_states_none_of_the_four() -> None:
    """Every registration made before #177, and every one made by a caller that
    says nothing: four unstated declarations rather than four denials."""
    config = a_request().config()

    assert config.processes_untrusted_input is None
    assert config.reaches_private_data is None
    assert config.changes_state_or_communicates is None
    assert config.under_human_supervision is None


def test_the_reading_route_names_the_standing_and_prints_the_sentence(
    library: list[Case],
) -> None:
    """What a screen asks for: the name, and the prose the report prints.

    All three capabilities declared held and unsupervised, which is the one arm the
    published rule warns about — and the one that most needs to say it was not
    measured, since on a register screen it prints before a single attempt exists.
    """
    with TestClient(create_app(BenchConfig(cases=library))) as client:
        answer = client.post(
            RULE_OF_TWO_ROUTE,
            json={
                "processes_untrusted_input": True,
                "reaches_private_data": True,
                "changes_state_or_communicates": True,
                "under_human_supervision": False,
            },
        )

    assert answer.status_code == 200
    read = answer.json()
    assert read["standing"] == "three_unsupervised"
    assert NOT_A_MEASUREMENT in read["stated"]


def test_a_declared_absence_settles_the_reading_whatever_went_unsaid(
    library: list[Case],
) -> None:
    """ADR-0038 decision 5's ordering, asserted from outside the module.

    One property declared absent and one left unsaid. `partly_declared` is what
    reading `unstated` first would print, and it would print *the rule cannot be
    read over this* about a declaration the rule can be read over: a property the
    operator says their agent does not have is one it cannot hold, so the shape is
    at most two whatever else went unanswered.

    This is the one arm the record says it got wrong on its first draft, and the
    reason no standing may be derived a second time in another language.
    """
    with TestClient(create_app(BenchConfig(cases=library))) as client:
        answer = client.post(
            RULE_OF_TWO_ROUTE,
            json={"reaches_private_data": False, "processes_untrusted_input": True},
        )

    assert answer.json()["standing"] == "at_most_two"


def test_the_reading_route_states_the_absence_of_a_declaration(
    library: list[Case],
) -> None:
    """A body that declares nothing is answered, and answered with a reading.

    The register walk fetches this before the operator has touched the fieldset, so
    an empty declaration is the first thing the route is ever asked. It is not a
    refusal and not an empty response: `not_declared` is a reading, and the block
    prints whether or not anything was declared (ADR-0038, decision 8).
    """
    with TestClient(create_app(BenchConfig(cases=library))) as client:
        answer = client.post(RULE_OF_TWO_ROUTE, json={})

    assert answer.status_code == 200
    assert answer.json()["standing"] == RuleOfTwoStanding.NOT_DECLARED


def test_the_reading_route_records_nothing_and_starts_nothing(
    library: list[Case],
) -> None:
    """Stateless, asserted where a state change would show.

    A reading is a question about a declaration and not a registration: nothing is
    sent to any endpoint, no run goes on the record, and no nonce is spent. Read off
    the run list, which is the surface a recorded run would appear on.
    """
    with TestClient(create_app(BenchConfig(cases=library))) as client:
        for _ in range(3):
            assert (
                client.post(
                    RULE_OF_TWO_ROUTE, json={"processes_untrusted_input": True}
                ).status_code
                == 200
            )
        assert client.get("/runs").json()["runs"] == []
