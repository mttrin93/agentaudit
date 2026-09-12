"""The door: what a request with no operator behind it gets, and what one with an
operator behind it reaches.

Authentication is the fourth declaration on `create_app`
([ADR-0116](../../docs/adr/0116-the-identity-in-a-report-is-a-verified-claim-and-not-a-typed-string.md)
§3), and this file is the behavioural half of it. The shape of a verification — a
subject or a refusal, never an exception — is ADR-0120's and is asserted in
`test_identity.py`; what is asserted here is only what the HTTP surface does with
one.

**No test here reaches an issuer.** Every one of them declares a stub, which is the
whole reason the constructor argument is a protocol rather than an import: a suite
that needed an account to assert that an unauthenticated request is refused would be
a suite nobody could run on a fork.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend.api.app import (
    NO_DOOR,
    NOBODY_VERIFIED,
    UNAUTHENTICATED,
    DeclaredDoor,
    NoIssuer,
    create_app,
)
from backend.api.run_config import BenchConfig
from backend.api.run_state import RunRecord
from backend.api.runs import BenchRuns
from backend.bench.attested_name import NOT_ESTABLISHED, NameGiven, VerifiedSubject
from backend.bench.library import Case
from backend.bench.signing import SIGNING_KEY_VARIABLE, encoded_private, generate
from backend.identity import (
    ISSUER_JWT_KEY_VARIABLE,
    ISSUER_SECRET_KEY_VARIABLE,
    Operator,
    Unverifiable,
    Unverified,
    Verification,
    Verifier,
)

SUBJECT = "user_2NxTheOperatorAsking"
"""The subject the stub below puts on a session. An issuer's identifier and not a
name, which is the distinction `identity.Operator` exists to keep."""

TOKEN = "a-token-this-stub-accepts"

AUTHORIZED = {"Authorization": f"Bearer {TOKEN}"}
"""The header an operator the stub below admits arrives with."""

GATE_ROUTE = "/bench/gate"
"""The route the door tests address. Chosen because it reaches no bench state and
spends nothing: what is under test is whether the request arrived, not what the
route answered."""


@dataclass(frozen=True)
class Admits:
    """A verifier that admits one token and refuses everything else as `ABSENT`.

    Satisfies `Verifier` structurally and is asserted to, rather than annotated as
    doing so — a stub that had drifted from the protocol would otherwise pass every
    test in this file while the deployed verifier failed.
    """

    token: str = TOKEN
    subject: str = SUBJECT

    def verify(self, authorization: str | None) -> Verification:
        if authorization == f"Bearer {self.token}":
            return Operator(subject=self.subject)
        return Unverified(
            cause=Unverifiable.ABSENT,
            reason="no token was presented, and this stub admits exactly one",
        )


@dataclass(frozen=True)
class Refuses:
    """A verifier that refuses everything, for a cause the test names."""

    cause: Unverifiable
    reason: str = "the stub refused this one"

    def verify(self, authorization: str | None) -> Verification:
        return Unverified(cause=self.cause, reason=self.reason)


def a_door(verifier: Verifier) -> FastAPI:
    """An app over a bench that declared itself and a door that was handed in.

    The bench is empty on purpose: a door is not about what a run measures, and a
    configuration declared here is what keeps this file's apps out of the deployed
    reading and so out of the environment.
    """
    return create_app(BenchConfig(cases=[]), verifier=verifier)


def _addressable(route: APIRoute) -> tuple[str, str]:
    """One method and one concrete path for a route, path parameters filled in.

    The value put in a parameter is deliberately one no record could have: what is
    being asserted is that the request never reached the route, and a route that
    answered `404` for an id it looked up would have run.
    """
    path = route.path
    for parameter in ("run_id", "report_id", "measurement_id", "route", "gate_run_id"):
        path = path.replace(f"{{{parameter}}}", "no-such-thing")
    methods = sorted(route.methods or {"GET"})
    method = "GET" if "GET" in methods else methods[0]
    return method, path


def _api_routes(app: FastAPI) -> list[APIRoute]:
    routes = [route for route in app.routes if isinstance(route, APIRoute)]
    assert routes, "no routes were found to sweep, so this test asserts nothing"
    return routes


def test_the_stub_this_file_declares_is_a_verifier() -> None:
    """The seam, checked once. `Verifier` is `runtime_checkable` for this."""
    assert isinstance(Admits(), Verifier)
    assert isinstance(Refuses(Unverifiable.EXPIRED), Verifier)


def test_an_unauthenticated_request_is_refused_in_this_surfaces_shape() -> None:
    """No token is a `401` carrying the verifier's own sentence.

    The sentence travels rather than being replaced by a category, for the reason
    every other refusal on this surface carries prose: a console showing *401* and
    nothing else leaves an operator to guess between an expired session and a bench
    that never had a door.
    """
    refused = TestClient(a_door(Admits())).get(GATE_ROUTE)

    assert refused.status_code == 401
    assert refused.json()["detail"] == {
        "refusal": "absent",
        "statement": "no token was presented, and this stub admits exactly one",
    }
    assert refused.headers["WWW-Authenticate"] == "Bearer"


def test_an_authenticated_request_reaches_the_route_it_addressed() -> None:
    """The other half, and it has to be the other half: a door that refused
    everything would satisfy the assertion above and serve nobody."""
    served = TestClient(a_door(Admits())).get(
        GATE_ROUTE, headers={"Authorization": f"Bearer {TOKEN}"}
    )

    assert served.status_code == 200
    assert served.json()["rule"]


def test_every_route_on_this_surface_carries_the_door() -> None:
    """One dependency on the router, swept over every route the app holds.

    This is the assertion that makes *a route added next year is authenticated by
    construction* true rather than intended. It is behavioural and not an inspection
    of `route.dependant`: what matters is that the request is refused, and a
    dependency present and not raising would pass an inspection.

    Every path parameter is filled with a value no record could have, so a route
    that answered at all would answer `404` — which is what this catches.
    """
    app = a_door(Admits())
    client = TestClient(app)

    refused = {}
    for route in _api_routes(app):
        method, path = _addressable(route)
        refused[route.path] = client.request(method, path).status_code

    assert set(refused.values()) == {401}, (
        f"these routes answered without an operator: "
        f"{sorted(path for path, code in refused.items() if code != 401)}"
    )


def test_a_bench_that_declared_its_own_configuration_serves_every_route_openly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The declaration this suite runs on: a configuration and no verifier is an app
    with no door.

    Asserted with both issuer variables deleted, because the claim is that this path
    reads no environment at all — a factory that fell back to the deployed reading
    would refuse to boot here rather than serve.
    """
    monkeypatch.delenv(ISSUER_JWT_KEY_VARIABLE, raising=False)
    monkeypatch.delenv(ISSUER_SECRET_KEY_VARIABLE, raising=False)

    app = create_app(BenchConfig(cases=[]))
    client = TestClient(app)

    assert client.get(GATE_ROUTE).status_code == 200
    assert all(
        client.request(*_addressable(route)).status_code != 401
        for route in _api_routes(app)
    )


def test_an_issuer_that_could_not_be_reached_is_not_the_callers_fault() -> None:
    """`UNAVAILABLE` is a `503` and carries no challenge.

    The one refusal that is not a statement about the credential presented. A `401`
    here would tell an operator their session was rejected while the issuer was
    down, and the challenge header would invite them to present something else when
    nothing they could present would have been checked.
    """
    refused = TestClient(a_door(Refuses(Unverifiable.UNAVAILABLE))).get(
        GATE_ROUTE, headers={"Authorization": f"Bearer {TOKEN}"}
    )

    assert refused.status_code == 503
    assert "WWW-Authenticate" not in refused.headers
    assert refused.json()["detail"] == {
        "refusal": "unavailable",
        "statement": "the stub refused this one",
    }


@pytest.mark.parametrize(
    "cause",
    [
        Unverifiable.ABSENT,
        Unverifiable.MALFORMED,
        Unverifiable.EXPIRED,
        Unverifiable.UNTRUSTED,
    ],
)
def test_the_four_refusals_about_a_credential_are_all_401(
    cause: Unverifiable,
) -> None:
    """Four causes, one status. The console branches on the cause it is told in the
    sentence and on `401` against `503` for whose problem it is; nothing on this
    surface distinguishes *expired* from *untrusted* by status code, because both
    are answered by signing in again."""
    refused = TestClient(a_door(Refuses(cause))).get(GATE_ROUTE)

    assert refused.status_code == 401
    assert refused.json()["detail"]["refusal"] == str(cause)


def test_a_deployment_that_declares_no_door_boots_with_no_issuer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`NO_DOOR` is the declared-off path, and it is the only one.

    A deployed bench — the signing key, the admitted library, the citation — served
    to anybody, because the caller said so. This is what `frontend/e2e/harness.py`
    runs: a walkthrough that drives the console with no issuer and no account.
    """
    monkeypatch.setenv(SIGNING_KEY_VARIABLE, encoded_private(generate()))
    monkeypatch.delenv(ISSUER_JWT_KEY_VARIABLE, raising=False)
    monkeypatch.delenv(ISSUER_SECRET_KEY_VARIABLE, raising=False)

    client = TestClient(create_app(verifier=NO_DOOR))

    assert client.get(GATE_ROUTE).status_code == 200


def test_a_verifier_handed_in_is_the_door_a_deployed_bench_gets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fourth declaration is independent of the first three.

    A caller may take the deployed bench and hand in its own door, which is what the
    tests that read a deployed factory's answers on a route do. Asserted with the
    issuer deleted: a declared verifier is a declaration, so the deployed reading is
    never consulted and the boot does not need one.
    """
    monkeypatch.setenv(SIGNING_KEY_VARIABLE, encoded_private(generate()))
    monkeypatch.delenv(ISSUER_JWT_KEY_VARIABLE, raising=False)
    monkeypatch.delenv(ISSUER_SECRET_KEY_VARIABLE, raising=False)

    client = TestClient(create_app(verifier=Admits()))

    assert client.get(GATE_ROUTE).status_code == 401
    assert (
        client.get(GATE_ROUTE, headers={"Authorization": f"Bearer {TOKEN}"}).status_code
        == 200
    )


def test_a_deployment_that_declares_nothing_at_all_refuses_to_boot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The refusal, asserted here as well as beside the signing key's.

    `test_api_runs.py` asserts it next to `NoSigningKey` because that is the pair a
    reader of the deployed factory needs to see together. It is asserted again here
    because this is the file about the door, and the refusal is the door's most
    consequential behaviour: it is what makes *unconfigured* mean *shut*.
    """
    # The key, because `deployed_bench()` runs before the door and a bench with
    # neither credential refuses on the first one. What is asserted here is that a
    # bench which *can* sign still does not start without an issuer.
    monkeypatch.setenv(SIGNING_KEY_VARIABLE, encoded_private(generate()))
    monkeypatch.delenv(ISSUER_JWT_KEY_VARIABLE, raising=False)
    monkeypatch.delenv(ISSUER_SECRET_KEY_VARIABLE, raising=False)

    with pytest.raises(NoIssuer) as refused:
        create_app()

    assert ISSUER_JWT_KEY_VARIABLE in str(refused.value)


def test_every_refusal_this_bench_distinguishes_has_a_status() -> None:
    """The table is total, and a sixth cause is a failure here rather than a `503`.

    `UNAUTHENTICATED` names four of the five, and `identity._REFUSALS` is written out
    member by member for the same reason: a mapping that defaulted would answer a
    cause added next year with a sentence saying this deployment's issuer is down,
    which is a statement about the bench rather than about what was presented.
    """
    assert UNAUTHENTICATED | {Unverifiable.UNAVAILABLE} == set(Unverifiable)


def test_a_bench_with_a_door_does_not_publish_its_own_schema() -> None:
    """`/openapi.json`, `/docs` and `/redoc` are not `APIRoute`s, so the dependency
    the router carries never reaches them.

    Served, they would be three routes on this surface answering without an operator.
    Turned off with the door rather than gated beside it, and ADR-0121 decision 3
    says why.
    """
    client = TestClient(a_door(Admits()))

    assert client.get("/openapi.json").status_code == 404
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404


def test_a_bench_with_no_door_keeps_its_schema() -> None:
    """The other half: a laptop and the browser walkthrough keep `/docs`.

    There is nothing to disclose about a bench anybody may already call, and a
    contributor reading the surface is the reason the schema is served at all.
    """
    client = TestClient(create_app(BenchConfig(cases=[])))

    assert client.get("/openapi.json").status_code == 200


# --- the name ---------------------------------------------------------------------


ATTESTED = {
    "authorised_to_test": True,
    "not_production": True,
    "accepts_provider_policy_and_cost": True,
}
"""The three statements, and no fourth field naming who made them.

This dictionary is the shape of the deployed surface after
[ADR-0116](../../docs/adr/0116-the-identity-in-a-report-is-a-verified-claim-and-not-a-typed-string.md)
§1: a caller states what they attest to and cannot state who they are.
"""


def a_bench_behind_a_door(case: Case, verifier: Verifier | DeclaredDoor) -> FastAPI:
    """An app over one case, with whatever door the test named.

    One case because a run has to be startable: the halt is what these tests read,
    and a bench with nothing to attempt has nothing to halt over.
    """
    return create_app(
        BenchConfig(cases=[case], approval_wait_seconds=5.0), verifier=verifier
    )


def a_run_that_names_nobody(nonce: str) -> dict[str, object]:
    """A start body in the shape a caller may now send: the statements, no name.

    The target is an address nothing is listening on, and nothing reaches it: the
    run halts at the approval interrupt before the probe, and every test below
    declines.
    """
    return {
        "target": {
            "name": "a target this run never reaches",
            "url": "http://127.0.0.1:1/never",
            "auth_token": "",
            "agent_type": "assistant",
            "exposes_tool_calls": True,
            "declared_tools": ["search"],
        },
        "attestation": dict(ATTESTED),
        "nonce": nonce,
        "cost": {"price_per_call": "0.002", "currency": "USD"},
    }


def _started(client: TestClient, headers: dict[str, str]) -> str:
    """One run, halted at its interrupt, started by whoever those headers are."""
    nonce = str(client.post("/nonces", headers=AUTHORIZED).json()["nonce"])
    started = client.post(
        "/runs", json=a_run_that_names_nobody(nonce), headers=AUTHORIZED
    )
    assert started.status_code == 202, started.json()
    return str(started.json()["run_id"])


def _record(app: FastAPI, run_id: str) -> RunRecord:
    """The record that run became, read where a signed report reads it from."""
    record = cast(BenchRuns, app.state.bench).record(run_id)
    assert record is not None, f"this bench did not start {run_id}"
    return record


def _declining(app: FastAPI, run_id: str) -> str:
    """Who the record says answered that run's interrupt.

    Read off the result the graph unwound with rather than off `confirmed_by`, which
    a declined run does not carry: a no is answered by somebody too, and this is
    where the bench keeps their name.
    """
    result = _record(app, run_id).result
    assert result is not None, f"run {run_id} settled with no result on it"
    return result.approval.identity


def test_a_run_is_attested_by_the_subject_the_token_was_verified_as(
    leakage_case: Case,
) -> None:
    """The assertion ADR-0116 §1 comes to: the record names the verified operator.

    The body carried no name — it cannot — so the only place this string could have
    come from is the header the door read.
    """
    app = a_bench_behind_a_door(leakage_case, Admits())

    with TestClient(app) as client:
        run_id = _started(client, AUTHORIZED)
        client.post(
            f"/runs/{run_id}/approval",
            json={"confirmed": False, "reason": "the test that started this is over"},
            headers=AUTHORIZED,
        )

    assert _record(app, run_id).attestation.identity == SUBJECT


def test_the_answer_to_an_interrupt_is_recorded_against_the_same_subject(
    leakage_case: Case,
) -> None:
    """The second record a request becomes, and the same source for its name.

    An approval is the consent seam itself (ADR-0007), so who answered is the half
    of it that has to be founded on something: `confirmed_by` is read off the
    token and never off the body.
    """
    app = a_bench_behind_a_door(leakage_case, Admits())

    with TestClient(app) as client:
        run_id = _started(client, AUTHORIZED)
        answered = client.post(
            f"/runs/{run_id}/approval",
            json={"confirmed": False, "reason": "too dear"},
            headers=AUTHORIZED,
        )

    assert answered.status_code == 200
    assert _declining(app, run_id) == SUBJECT


def test_a_start_body_that_still_names_an_operator_is_refused(
    leakage_case: Case,
) -> None:
    """Refused and never ignored, which is the half of §1 that can go wrong quietly.

    A client that still sends the field would otherwise be served: the attestation
    would be recorded against the token's subject, the caller would believe they had
    named it, and nothing anywhere would say the two disagreed.
    """
    app = a_bench_behind_a_door(leakage_case, Admits())

    with TestClient(app) as client:
        nonce = str(client.post("/nonces", headers=AUTHORIZED).json()["nonce"])
        body = a_run_that_names_nobody(nonce)
        body["attestation"] = {"identity": "somebody else", **ATTESTED}
        refused = client.post("/runs", json=body, headers=AUTHORIZED)

        assert refused.status_code == 422
        assert "identity" in str(refused.json()["detail"])
        # And no run was started by the request that was refused.
        assert client.get("/runs", headers=AUTHORIZED).json()["runs"] == []


def test_an_approval_body_that_still_names_an_operator_is_refused(
    leakage_case: Case,
) -> None:
    """The same refusal on the body that answers the halt, and the halt stays held.

    The interrupt is still waiting afterwards: a refused answer is not an answer, so
    the run is neither confirmed nor declined by it.
    """
    app = a_bench_behind_a_door(leakage_case, Admits())

    with TestClient(app) as client:
        run_id = _started(client, AUTHORIZED)
        refused = client.post(
            f"/runs/{run_id}/approval",
            json={"confirmed": True, "identity": "somebody else", "reason": ""},
            headers=AUTHORIZED,
        )

        assert refused.status_code == 422
        assert "identity" in str(refused.json()["detail"])
        assert _record(app, run_id).confirmed_by == ""

        client.post(
            f"/runs/{run_id}/approval",
            json={"confirmed": False, "reason": "the test that started this is over"},
            headers=AUTHORIZED,
        )


def test_a_bench_with_no_door_records_that_it_verified_nobody(
    leakage_case: Case,
) -> None:
    """The declared-open reading, which still has to put something in the field.

    `Attestation` refuses a blank identity, so a bench that verified nobody says so
    in the words `NOBODY_VERIFIED` carries rather than borrowing a name from the body
    it no longer reads
    ([ADR-0122](../../docs/adr/0122-a-bench-with-no-door-records-that-it-verified-nobody.md)).
    """
    app = a_bench_behind_a_door(leakage_case, NO_DOOR)

    with TestClient(app) as client:
        run_id = _started(client, {})
        client.post(
            f"/runs/{run_id}/approval",
            json={"confirmed": False, "reason": "the test that started this is over"},
        )

    assert _record(app, run_id).attestation.identity == NOBODY_VERIFIED.subject
    assert _declining(app, run_id) == NOBODY_VERIFIED.subject

    # And the artefact says it in a sentence rather than in a name a reader could
    # take for an unusual username: what a bench with no door recorded is a name
    # nothing verified, stated (ADR-0123).
    stated = _record(app, run_id).attestation.attested_by.stated()
    assert isinstance(_record(app, run_id).attestation.attested_by, NameGiven)
    assert NOBODY_VERIFIED.subject in stated
    assert "a name nothing verified" in stated


def test_a_run_behind_a_door_is_attested_by_a_subject_the_issuer_verified(
    leakage_case: Case,
) -> None:
    """The other half, and the one that may make the stronger claim.

    The same route, the same body, and the difference is the door: a request the
    verifier admitted is recorded as a verified subject, and a signed report says
    which issuer's signature established the name. Beside the `NO_DOOR` assertion
    above, because the pair is the whole of what #247 put in the document — a reader
    holding one report can now tell which of the two they have (ADR-0116, ADR-0123).
    """
    app = a_bench_behind_a_door(leakage_case, Admits())

    with TestClient(app) as client:
        run_id = _started(client, AUTHORIZED)
        client.post(
            f"/runs/{run_id}/approval",
            json={"confirmed": False, "reason": "the test that started this is over"},
            headers=AUTHORIZED,
        )

    attested = _record(app, run_id).attestation.attested_by
    assert attested == VerifiedSubject(name=SUBJECT)
    assert (
        "verified session at the issuer this deployment declares" in attested.stated()
    )
    assert NOT_ESTABLISHED in attested.stated()
