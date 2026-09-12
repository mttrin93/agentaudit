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

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend.api.app import NO_DOOR, UNAUTHENTICATED, NoIssuer, create_app
from backend.api.run_config import BenchConfig
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
