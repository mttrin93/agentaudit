"""What the client makes of the bench's answers: six calls and five named outcomes.

Run against the real app, through the `api()` context manager `test_api_runs.py`
already defines. There are no recorded responses in this module and that is the point
of it: the client's whole job is to assemble one request body and read one status
code, and a fixture would be this file agreeing with itself about both. A route that
moves, a payload field that is renamed and a status code that changes have to break
these tests in CI, which they cannot do against a recording.

The `TestClient` is handed to `BenchClient` as itself rather than wrapped, because it
*is* a client of the same shape — a second transport built around it would be a second
thing to keep in step with the app the tests are for. It is not the same *package*,
which is what `_bench_client` below is about.
"""

from __future__ import annotations

import dataclasses
from typing import Any, cast

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.api.app import NOBODY_VERIFIED
from backend.api.run_state import NeverPresented
from backend.bench.contract import RetryPolicy, TargetConfig
from backend.bench.library import Case
from backend.declaration import Declaration
from backend.mcp.client import (
    BenchClient,
    BenchRefused,
    BenchUnreachable,
    NoEstimate,
    ReportNotSigned,
    _body,
)
from backend.tests.test_api_runs import (
    Watched,
    api,
    registered,
    settled,
    watched_reference,
)


def _bench_client(client: TestClient) -> BenchClient:
    """The bench client, speaking to the app this test built.

    One cast, in one place, and it is a fact about the two packages rather than about
    the interface. Starlette's `TestClient` extends `httpx2.Client`; this project
    declares `httpx` and `backend/mcp/client.py` is typed against it. Same class,
    same methods, same `base_url` — two distributions, and no supertype either of
    them shares. The one call that does not go through here is the unreachable test,
    which uses a real `httpx.Client` because a transport failure is the one thing an
    in-process client cannot produce.
    """
    return BenchClient(cast(httpx.Client, client))


NOWHERE = "http://127.0.0.1:9"
"""Discard, on a port nothing listens on. The client that points here has no app
behind it and never gets as far as a status code."""


def a_declaration(target: TargetConfig, nonce: str, **fields: Any) -> Declaration:
    """One target as an operator would have committed it, at this nonce."""
    declared = Declaration(
        name=target.name,
        url=target.url,
        auth_token=target.auth_token,
        agent_type=target.agent_type,
        exposes_tool_calls=True,
        declared_tools=tuple(target.declared_tools),
        retains_session_state=False,
        holds_personal_records=False,
        processes_untrusted_input=None,
        reaches_private_data=None,
        changes_state_or_communicates=None,
        under_human_supervision=None,
        sends=None,
        nonce=nonce,
        note_planted=False,
        nonce_planted=True,
        echo_waived=False,
        identity="matteo",
        authorised_to_test=True,
        not_production=True,
        accepts_provider_policy_and_cost=True,
        price_per_call="0.002",
        currency="USD",
    )
    return dataclasses.replace(declared, **fields)


def _started(client: TestClient, watched: Watched, **fields: Any) -> dict[str, Any]:
    """A run held at its estimate, started the way an operator would start one."""
    nonce = registered(client, watched)
    return _bench_client(client).start(a_declaration(watched.target, nonce, **fields))


def test_the_nonce_this_client_issues_is_the_one_the_bench_starts_a_run_on(
    leakage_case: Case,
) -> None:
    """`issue_nonce` returns the value and not the sentence beside it.

    `POST /nonces` answers with three fields — the value, the probe that will check
    it and what both are for — and the operator plants exactly one of them. A client
    that handed back the whole body would make every caller pick, and one that
    handed back the wrong field would be refused at the start below, which is the
    negative this test is the positive of.
    """
    with watched_reference() as watched, api([leakage_case]) as (client, bench):
        bench_client = _bench_client(client)
        nonce = bench_client.issue_nonce()
        watched.plant(watched.target, nonce, "by-hand")
        started = bench_client.start(a_declaration(watched.target, nonce))
        record = bench.record(str(started["run_id"]))

    assert record is not None
    assert record.nonce == nonce


def test_a_start_carries_the_whole_declaration_and_stops_at_the_estimate(
    leakage_case: Case,
) -> None:
    """The body `POST /runs` takes, assembled from a committed file and nothing else.

    Read off the record the bench kept rather than off the response, because what
    this test is about is whether the declaration arrived: a response that echoed
    the fields back would be the client agreeing with itself.
    """
    with watched_reference() as watched, api([leakage_case]) as (client, bench):
        started = _started(
            client,
            watched,
            retains_session_state=True,
            holds_personal_records=True,
            declared_tools=("search", "email"),
        )
        record = bench.record(str(started["run_id"]))

    assert record is not None
    assert started["status"] == "awaiting_approval"
    assert started["estimate"]["total"]["calls"] > 0
    # The one field of the committed file that does not travel: the attestation is
    # recorded against the operator the API verified this client as, and this bench
    # has no door, so it names nobody and says so (ADR-0116 §1). What this client
    # presents is #251's.
    assert record.attestation.identity == NOBODY_VERIFIED.subject
    assert record.target.url == watched.target.url
    assert record.target.declared_tools == ("search", "email")
    assert record.target.retains_session_state is True
    assert record.target.holds_personal_records is True


def test_the_four_rule_of_two_declarations_reach_the_target_the_bench_registered(
    leakage_case: Case,
) -> None:
    """A committed declaration is read against the published rule, on this surface too.

    Without them a run started here read `not_declared` for all four whatever its
    operator would have said — the defect ADR-0092 closed for the console, and
    [ADR-0102](../../docs/adr/0102-the-declaration-file-carries-the-four-rule-of-two-declarations.md)
    closes for the file. Asserted on the `TargetConfig` the bench holds, which is
    the record `scanner.read_rule_of_two` derives the standing from.
    """
    with watched_reference() as watched, api([leakage_case]) as (client, bench):
        started = _started(
            client,
            watched,
            processes_untrusted_input=True,
            reaches_private_data=False,
            changes_state_or_communicates=True,
            under_human_supervision=None,
        )
        record = bench.record(str(started["run_id"]))

    assert record is not None
    assert record.target.processes_untrusted_input is True
    assert record.target.reaches_private_data is False
    assert record.target.changes_state_or_communicates is True
    assert record.target.under_human_supervision is None


def test_a_nonce_this_bench_never_issued_is_a_name_and_the_route_s_own_sentence(
    leakage_case: Case,
) -> None:
    """A refusal the caller branches on, carrying the words the route chose.

    Both halves matter. The type is what a tool acts on, and the detail is the only
    place the bench says *which* thing was wrong — a client that kept the status and
    dropped the sentence would leave the caller with a number and no reason.
    """
    with watched_reference() as watched, api([leakage_case]) as (client, _):
        with pytest.raises(BenchRefused) as refused:
            _bench_client(client).start(a_declaration(watched.target, "never-issued"))

    assert refused.value.status == 422
    assert "this bench never issued that nonce" in refused.value.detail


def test_a_declined_approval_is_a_status_a_confirmed_one_is_not(
    leakage_case: Case,
) -> None:
    """A no is answered in full and the run is over, having sent nothing.

    Two runs rather than one assertion about a string: *declined* only means
    anything against the status a yes reaches, and the pair is what says the
    `confirmed` flag is on the wire rather than defaulted.
    """
    with watched_reference() as watched, api([leakage_case]) as (client, bench):
        bench_client = _bench_client(client)
        declined = bench_client.approve(
            str(_started(client, watched)["run_id"]),
            confirmed=False,
            reason="too dear",
        )
        confirmed = bench_client.approve(
            str(_started(client, watched)["run_id"]),
            confirmed=True,
        )
        for record in bench.records():
            settled(record)

    assert declined["status"] == "declined"
    assert "too dear" in declined["statement"]
    assert confirmed["status"] != declined["status"]


def test_a_report_that_was_never_signed_is_named_and_carries_the_refusal(
    leakage_case: Case,
) -> None:
    """A completed run on a bench with no key has no artefact, and says which fact.

    Its own name rather than the `BenchRefused` every other non-2xx becomes: a run
    that finished and cannot be sent to anybody is the one refusal on this surface a
    caller acts on differently, and it shares its status code with two facts about a
    run that is not finished at all.
    """
    with watched_reference() as watched, api([leakage_case]) as (client, bench):
        bench_client = _bench_client(client)
        run_id = str(_started(client, watched)["run_id"])
        bench_client.approve(run_id, confirmed=True)
        record = bench.record(run_id)
        assert record is not None
        settled(record)
        reached = bench_client.status(run_id)

        with pytest.raises(ReportNotSigned) as unsigned:
            bench_client.report(run_id)

    assert reached["status"] == "completed"
    assert unsigned.value.outcome == "never_signed"
    assert "no signing key" in unsigned.value.reason


def test_a_report_for_a_run_this_bench_never_started_is_not_called_unsigned(
    leakage_case: Case,
) -> None:
    """An id nobody has a record of is a `404`, and *never signed* is not what it is.

    The report route refuses by name on both codes, and the two mean different
    things: a `409` is a run this bench has and cannot serve a document for, and a
    `404` is a run it does not have. Told the second was *not signed*, a caller
    would go looking for the run that produced it.
    """
    with api([leakage_case]) as (client, _):
        with pytest.raises(BenchRefused) as refused:
            _bench_client(client).report("not-a-run-this-bench-started")

    assert refused.value.status == 404
    assert "was started by this bench" in refused.value.detail


def test_a_run_that_reached_no_interrupt_has_no_estimate_to_confirm(
    leakage_case: Case,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The one 500 `POST /runs` declares, and it is not a failure of the bench.

    Provoked at the seam the route translates rather than by contriving a graph that
    stalls: what is under test is that the status becomes a name, and the condition
    behind it is `run_state.py`'s to raise.
    """
    with watched_reference() as watched, api([leakage_case]) as (client, bench):
        nonce = registered(client, watched)

        def _no_interrupt(*_: object, **__: object) -> None:
            raise NeverPresented(
                "the run reached no approval interrupt, so it has no estimate to "
                "confirm. Nothing was sent"
            )

        monkeypatch.setattr(bench, "start", _no_interrupt)
        with pytest.raises(NoEstimate) as none:
            _bench_client(client).start(a_declaration(watched.target, nonce))

    assert "no estimate to confirm" in str(none.value)


def test_a_bench_that_is_not_listening_is_named_and_names_where_it_looked() -> None:
    """No app, no status code, and a sentence an operator can act on.

    The likeliest failure this surface has: a coding agent calls a tool against a
    bench nobody started. What it must not produce is a transport traceback — the
    caller cannot start the API from inside a tool (ADR-0100) and the answer is a
    sentence saying where the client looked.
    """
    with httpx.Client(base_url=NOWHERE) as http:
        with pytest.raises(BenchUnreachable) as unreachable:
            BenchClient(http).issue_nonce()

    assert NOWHERE in str(unreachable.value)


def test_artefact_urls_names_the_four_paths_and_fetches_none() -> None:
    """Where the artefact is, computed and not requested.

    Proved by pointing the client at a closed port: a call that fetched anything
    would raise `BenchUnreachable` here, so the four coming back is the assertion
    that nothing went on the wire. Four rather than three because the verification
    is a reading of the artefact and not a file of it, and a caller that saved the
    three would still verify.
    """
    with httpx.Client(base_url=NOWHERE) as http:
        urls = BenchClient(http).artefact_urls("run-7")

    assert urls == {
        "payload": f"{NOWHERE}/report/run-7",
        "rendering": f"{NOWHERE}/report/run-7/rendering",
        "signature": f"{NOWHERE}/report/run-7/signature",
        "verification": f"{NOWHERE}/report/run-7/verification",
    }


def test_the_four_artefact_routes_are_the_ones_the_app_serves() -> None:
    """The paths written twice, asserted to be the same paths.

    `client.py` spells the routes rather than importing them, because `app.py`'s
    module graph reaches the bench — and it justifies the duplication by saying a
    route that moves breaks this client in CI. For `/report/{run_id}` that is held
    by every test above, which fetches it. For the three beside it nothing fetches
    anything, so without this the claim covered three routes it did not: renaming
    `RENDERING_ROUTE` in `app.py` would have left `artefact_urls` handing out a path
    nobody serves. A test may import `app.py`; the client may not.
    """
    from backend.api.app import report_paths

    served = report_paths("run-7")
    urls = BenchClient(httpx.Client(base_url=NOWHERE)).artefact_urls("run-7")

    assert tuple(f"{NOWHERE}{path}" for path in served) == (
        urls["payload"],
        urls["rendering"],
        urls["signature"],
        urls["verification"],
    )


def test_a_status_for_a_run_on_no_row_of_the_list_is_refused_and_says_so(
    leakage_case: Case,
) -> None:
    """The one refusal this client raises that the bench did not send.

    `GET /runs` answers `200` and a list, so an id that is on none of its rows is an
    absence only the reader can notice. It is still a no, and a caller that got an
    empty dict back instead would poll an id this bench has never held until it gave
    up. Untested until now, which is why the synthesised status is asserted here
    rather than left to the docstring.
    """
    with api([leakage_case]) as (client, _):
        with pytest.raises(BenchRefused) as refused:
            _bench_client(client).status("not-a-run-this-bench-started")

    assert refused.value.status == 404
    assert "no run not-a-run-this-bench-started" in refused.value.detail


def test_a_declared_send_ceiling_reaches_the_target_the_bench_registered(
    leakage_case: Case,
) -> None:
    """`sends` is the caller's declaration, and this surface can now make it.

    `TargetRequest.sends` is *what the enforced ceiling is built from, so it is the
    caller's declaration and not a constant hidden inside the bench* — and the
    console declares it while the file could not, which made this the narrower
    surface. Read off the retry policy the bench holds, which is what the ceiling is
    enforced from.
    """
    with watched_reference() as watched, api([leakage_case]) as (client, bench):
        started = _started(client, watched, sends=5)
        record = bench.record(str(started["run_id"]))

    assert record is not None
    assert record.target.retry.sends == 5


def test_a_file_that_declares_no_send_ceiling_leaves_the_route_its_own(
    leakage_case: Case,
) -> None:
    """An absent `sends` puts no key on the wire, so `TargetRequest` applies its own.

    The negative of the test above and the reason `sends` is `int | None` rather
    than an `int` this reader defaults: the default is built from `RetryPolicy`,
    which lives behind the wall this package may not import, so the only way to let
    the bench choose it is to say nothing.
    """
    with watched_reference() as watched, api([leakage_case]) as (client, bench):
        started = _started(client, watched, sends=None)
        record = bench.record(str(started["run_id"]))

    assert record is not None
    assert "sends" not in _body(a_declaration(watched.target, "n"))["target"]
    assert record.target.retry.sends == RetryPolicy().sends
