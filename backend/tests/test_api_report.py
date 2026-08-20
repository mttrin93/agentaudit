"""What the endpoint serves is what a recipient verifies, byte for byte.

Every assertion in this file that matters is over **bytes**. A test that decoded the
response and compared dictionaries would pass on exactly the failure this route
exists to prevent: FastAPI's ordinary path takes a returned object and serialises it
on the way out, with its own key order and its own separators, and the document that
arrives is then equal to the one that was signed in every way except the one a
signature is over. So the payload test compares byte strings, and one test writes the
three responses to a directory under the names they arrive with and runs the real
`scripts/verify.py` over them with nothing in between (#56).

The three refusals are asserted **by name** rather than by status code. Two of them
share a code, and a caller that could not tell *not completed yet* from *never
signed* would poll forever for a report that is never coming.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast, get_type_hints

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from fastapi import Response
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend.api.app import REPORT_ROUTE, create_app
from backend.api.report import ReportConfig, Unsigned
from backend.api.runs import BenchConfig, BenchRuns, RunRecord, RunStatus
from backend.bench.library import Case
from backend.bench.payload import canonical, document
from backend.bench.rendering import REPORT_MARKDOWN, REPORT_PAYLOAD
from backend.bench.signing import (
    SIGNATURE_FILE,
    SignedArtefact,
    encoded,
    fingerprint,
    generate,
    public_key,
    public_pem,
)
from backend.bench.verification import (
    CHECKS,
    BindingOutcome,
    ReDerivationOutcome,
    SignatureOutcome,
)
from backend.tests.test_api_runs import (
    a_request,
    registered,
    settled,
    watched_reference,
)
from backend.tests.test_payload import FORBIDDEN_IN_A_KEY
from scripts.verify import main


@contextmanager
def completed(
    cases: list[Case],
    key: Ed25519PrivateKey | None,
    pinned: Ed25519PublicKey | None = None,
) -> Iterator[Served]:
    """One run taken through the API to completion, against a served reference agent.

    The whole flow rather than a record built by hand: what is under test is the
    artefact a *run* produced, and a payload assembled inside a test would be a
    payload nothing signed.

    `pinned` is the key a verification of that artefact is run against. Left out, it
    is the key committed to this repository — which is what a recipient pins, and so
    what a bench signing with a test key is honestly reported against.
    """
    app = create_app(
        BenchConfig(
            cases=cases,
            approval_wait_seconds=60.0,
            report=ReportConfig(signing_key=key, pinned=pinned),
        )
    )
    bench = cast(BenchRuns, app.state.bench)
    with watched_reference() as watched, TestClient(app) as client:
        nonce = registered(client, watched)
        started = client.post("/runs", json=a_request(watched.target, nonce)).json()
        run_id = str(started["run_id"])
        record = bench.record(run_id)
        assert record is not None
        client.post(
            f"/runs/{run_id}/approval",
            json={"confirmed": True, "identity": "operator"},
        )
        settled(record)
        assert record.status is RunStatus.COMPLETED, record.statement
        yield Served(client=client, record=record, run_id=run_id)


class Served:
    """A live client, the run's own record, and the id the routes are asked for."""

    def __init__(self, client: TestClient, record: RunRecord, run_id: str) -> None:
        self.client = client
        self.record = record
        self.run_id = run_id

    def fetch(self, suffix: str = "") -> Any:
        return self.client.get(f"/report/{self.run_id}{suffix}")

    def artefact(self) -> SignedArtefact:
        """What this run signed, for the tests that compare the wire against it."""
        assert isinstance(self.record.report, SignedArtefact), self.record.statement
        return self.record.report


# --- the bytes -------------------------------------------------------------------


def test_the_payload_served_is_the_bytes_that_were_signed(leakage_case: Case) -> None:
    """Byte for byte, and asserted on the bytes.

    The signature covers one byte string. A route that returned the parsed payload
    would have the framework re-encode it — same document, different bytes — and
    every signature it served would be over something the recipient never received.
    """
    with completed([leakage_case], generate()) as served:
        response = served.fetch()

    artefact = served.artefact()
    assert response.status_code == 200
    assert response.content == artefact.canonical
    # And a second time without reference to the record, because the first assertion
    # is only as good as what the record holds: a canonical form is a fixed point of
    # its own serialiser, so a body that had been through a framework's encoder —
    # its key order, its separators — would not survive this round trip.
    assert response.content == canonical(json.loads(response.content)).encode("utf-8")


def test_the_report_routes_hand_back_bytes_rather_than_a_value_to_serialise() -> None:
    """The byte copy is structural, and this is the assertion that says so.

    A byte comparison alone cannot see this. Starlette's `JSONResponse` happens to
    encode with the same separators this repository calls canonical and to leave a
    parsed document's key order alone, so a route that parsed the payload and handed
    the dict back to the framework serves identical bytes **today** — and the day a
    framework upgrade changes an encoder default is the day every signature this
    route ever served stops verifying, with no test to say why.

    So what is asserted is the shape of the route: no response model, and a return
    annotation that is `Response`. A route that returns bytes has nothing in it for
    an encoder to decide.
    """
    app = create_app(BenchConfig(cases=[]))
    routes = {route.path: route for route in app.routes if isinstance(route, APIRoute)}

    for path in (
        REPORT_ROUTE,
        f"{REPORT_ROUTE}/rendering",
        f"{REPORT_ROUTE}/signature",
    ):
        route = routes[path]
        assert route.response_model is None, f"{path} serialises through a model"
        assert get_type_hints(route.endpoint)["return"] is Response, (
            f"{path} returns a value for the framework to encode, not bytes"
        )


def test_a_payload_fetched_from_the_endpoint_verifies_under_the_real_verifier(
    leakage_case: Case, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The recipient's own script, over exactly what the endpoint returned.

    Downloaded and written straight to disk with no decode, no re-encode and no
    parse in between — which is the whole claim of the ticket, and the one a test
    that compared dictionaries could not make.
    """
    key = generate()
    with completed([leakage_case], key) as served:
        payload = served.fetch()
        rendering = served.fetch("/rendering")
        signature = served.fetch("/signature")

    (tmp_path / REPORT_PAYLOAD).write_bytes(payload.content)
    (tmp_path / REPORT_MARKDOWN).write_bytes(rendering.content)
    (tmp_path / SIGNATURE_FILE).write_bytes(signature.content)
    pinned = tmp_path / "pinned.pub"
    pinned.write_bytes(public_pem(key.public_key()))

    code = main([str(tmp_path), "--pubkey", str(pinned)])

    printed = capsys.readouterr().out
    assert code == 0, printed
    assert SignatureOutcome.VALID.value in printed
    assert BindingOutcome.MATCHES.value in printed
    assert ReDerivationOutcome.AGREES.value in printed


def test_the_rendering_served_still_hashes_to_the_digest_inside_the_payload(
    leakage_case: Case,
) -> None:
    """The binding survives the wire.

    `rendered_sha256` is taken over the rendering's own UTF-8 bytes, so a route that
    added a banner, re-wrapped the document or handed it back through a JSON string
    would serve a rendering that no longer matches the payload beside it — which is
    the doctored-document substitution the field exists to prevent (ADR-0017).
    """
    with completed([leakage_case], generate()) as served:
        payload = served.fetch()
        rendering = served.fetch("/rendering")

    bound = json.loads(payload.content)["rendered_sha256"]
    assert rendering.status_code == 200
    assert hashlib.sha256(rendering.content).hexdigest() == bound
    assert rendering.headers["content-type"].startswith("text/markdown")


def test_no_response_adds_a_figure_or_a_wrapper_the_payload_does_not_carry(
    leakage_case: Case,
) -> None:
    """Three bodies, three fields of the artefact, and nothing of the route's own.

    An envelope is the shape a summary arrives in — a wrapper with the payload under
    one key and *findings* or *total* under another — so what is asserted is that
    each body is the artefact's own field and that no key anywhere in the served
    document totals across families (ADR-0005, D12).
    """
    with completed([leakage_case], generate()) as served:
        payload = served.fetch()
        rendering = served.fetch("/rendering")
        signature = served.fetch("/signature")

    artefact = served.artefact()
    body = json.loads(payload.content)
    for key in _keys(body):
        assert not [word for word in FORBIDDEN_IN_A_KEY if word in key], (
            f"{key} reads as a figure over more than one family"
        )
    assert body == document(artefact.payload)
    assert rendering.content == artefact.rendering.encode("utf-8")
    assert signature.content == encoded(artefact.signature).encode("utf-8")


# --- the three results over those bytes ------------------------------------------


def test_the_verification_route_reports_all_three_results_and_both_claims(
    leakage_case: Case,
) -> None:
    """Three results, always all three, and the two claims that scope them.

    A response carrying the signature alone would let its reader infer
    re-derivability from integrity, which is the inference ADR-0017 exists to
    prevent. The third result is the one about the bench rather than about the
    transport, and it is the reason this is not a padlock icon.
    """
    key = generate()
    with completed([leakage_case], key, pinned=key.public_key()) as served:
        body = served.fetch("/verification").json()

    assert body["signature"]["outcome"] == SignatureOutcome.VALID.value
    assert body["binding"]["outcome"] == BindingOutcome.MATCHES.value
    assert body["arithmetic"]["outcome"] == ReDerivationOutcome.AGREES.value
    assert body["verified"] is True
    assert body["contradicted"] is False
    assert body["target"] == served.artefact().payload.result.target_name

    # Both claims, in the verifier's own words, and the second scoped to the layer
    # it is true of: the adaptive layer is recorded and not reproducible (ADR-0010).
    assert "Integrity, for the whole document" in body["integrity"]
    assert "Re-derivability, for the scored layer only" in body["re_derivability"]
    assert "recorded and not reproducible" in body["re_derivability"]

    # And whose check this is. A sender's word for their own document is the thing a
    # signature exists to replace, so the response says who computed it and what the
    # recipient runs instead.
    assert "by the bench that produced the artefact" in body["checked_by"]
    assert "scripts.verify" in body["checked_by"]


def test_a_signature_under_a_key_nobody_pinned_is_not_reported_as_a_valid_one(
    leakage_case: Case,
) -> None:
    """The outcome that makes this route worth serving at all.

    A bench signing with a key whose public half nobody has published produces
    reports that no recipient can check, and the engineer about to send one to a
    customer is the person who needs to know. Reported under its own name rather
    than as tampering: the document was not altered, it was signed by somebody
    else's key, and the two send a reader to different places.
    """
    key = generate()
    with completed([leakage_case], key) as served:
        body = served.fetch("/verification").json()

    assert body["signature"]["outcome"] == SignatureOutcome.ANOTHER_KEY.value
    assert body["verified"] is False
    assert body["contradicted"] is True
    # Both fingerprints, so the reader can see which key they are missing rather
    # than being told that something about the key is wrong.
    assert fingerprint(key.public_key()) in body["signature"]["statement"]
    assert fingerprint(public_key()) in body["signature"]["statement"]
    # The other two are separate questions and are answered separately: the document
    # beside these bytes is still the one they are bound to, and the arithmetic still
    # re-derives.
    assert body["binding"]["outcome"] == BindingOutcome.MATCHES.value
    assert body["arithmetic"]["outcome"] == ReDerivationOutcome.AGREES.value


def test_the_verification_states_no_verdict_on_the_target_and_no_figure_over_families(
    leakage_case: Case,
) -> None:
    """A reading of an artefact, and never a grade for an agent.

    Two prohibitions in one response, because this is the part of the interface
    most likely to be mistaken for one: a green tick beside somebody's agent name
    reads as a pass, and ADR-0018 says a target has rates and bands and passes
    nothing. So the check is that the words *this target passed* have nowhere to
    appear, and that no key here totals across families (ADR-0005, D12).
    """
    key = generate()
    with completed([leakage_case], key, pinned=key.public_key()) as served:
        response = served.fetch("/verification")

    body = response.json()
    for key_name in _keys(body):
        assert not [word for word in FORBIDDEN_IN_A_KEY if word in key_name], (
            f"{key_name} reads as a figure over more than one family"
        )
    target = body["target"]
    for sentence in _sentences(body):
        for verdict in (f"{target} passed", f"{target} failed", "the target passed"):
            assert verdict not in sentence, (
                f"{verdict!r} appears in a verification. A target has rates, "
                "intervals and bands and passes nothing (ADR-0018)"
            )
    # Nor is there a field that reduces the three results to one word. `verified`
    # and `contradicted` are the verifier's own two properties and they answer two
    # different questions — nothing contradicted with one result never established
    # is a third answer, and a single flag could not carry it.
    assert set(body) == {
        "artefact",
        "artefact_version",
        "target",
        "signature",
        "binding",
        "arithmetic",
        "verified",
        "contradicted",
        "integrity",
        "re_derivability",
        "checked_by",
    }


def test_the_verification_is_the_same_reading_the_recipient_s_own_script_prints(
    leakage_case: Case, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One definition of verifying, reached two ways.

    The route and the script are the same three checks over the same three byte
    strings, so a report the script calls valid is one this route calls valid — and
    a second implementation behind the route would be a second definition that only
    has to disagree once for a screen to show a property nobody checked.
    """
    key = generate()
    with completed([leakage_case], key, pinned=key.public_key()) as served:
        body = served.fetch("/verification").json()
        payload = served.fetch()
        rendering = served.fetch("/rendering")
        signature = served.fetch("/signature")

    (tmp_path / REPORT_PAYLOAD).write_bytes(payload.content)
    (tmp_path / REPORT_MARKDOWN).write_bytes(rendering.content)
    (tmp_path / SIGNATURE_FILE).write_bytes(signature.content)
    pinned = tmp_path / "pinned.pub"
    pinned.write_bytes(public_pem(key.public_key()))

    code = main([str(tmp_path), "--pubkey", str(pinned)])

    printed = capsys.readouterr().out
    assert code == 0, printed
    for result in ("signature", "binding", "arithmetic"):
        assert body[result]["outcome"] in printed
        assert body[result]["statement"] in printed
    for name in CHECKS:
        assert name in printed


def test_a_run_with_no_artefact_refuses_the_verification_by_the_same_name(
    leakage_case: Case,
) -> None:
    """No artefact, no reading of one — and the refusal is the route's own four.

    A verification of a report that does not exist would have to be built out of
    nothing, and the caller polling for one needs the same named answer the three
    file routes give: *not yet* and *not ever* are different facts.
    """
    with completed([leakage_case], None) as served:
        response = served.fetch("/verification")

    assert response.status_code == 409
    assert response.json()["detail"]["outcome"] == "never_signed"
    assert "signature" not in response.json()["detail"]


# --- what is not served ----------------------------------------------------------


def test_a_run_that_has_not_completed_is_a_named_outcome_rather_than_a_partial_report(
    leakage_case: Case,
) -> None:
    """A run still at its interrupt has no report, and says which fact that is.

    Named rather than coded: *not completed* is a run to poll again and *never
    signed* is a run that will never have one, and a caller that could not tell them
    apart would wait forever for the second.
    """
    app = create_app(
        BenchConfig(cases=[leakage_case], report=ReportConfig(signing_key=generate()))
    )
    with watched_reference() as watched, TestClient(app) as client:
        nonce = registered(client, watched)
        started = client.post("/runs", json=a_request(watched.target, nonce)).json()
        response = client.get(f"/report/{started['run_id']}")

    detail = response.json()["detail"]
    assert response.status_code == 409
    assert detail["outcome"] == "in_flight"
    assert "awaiting_approval" in detail["statement"]
    # Nothing partial came back with the refusal: no payload, no rendering, no
    # figure of any kind.
    assert set(detail) == {"outcome", "statement"}
    assert "rendered_sha256" not in response.text


def test_a_run_whose_report_was_never_signed_cannot_be_served_as_a_report(
    leakage_case: Case,
) -> None:
    """A bench with no key runs, measures, and produces no report at all.

    Not an unsigned payload under the same path, and not a payload signed by a key
    generated on the spot: a signature over a key nobody has published is a valid
    signature over unknown provenance, which is the reading the published
    fingerprint exists to prevent (ADR-0017).
    """
    with completed([leakage_case], None) as served:
        payload = served.fetch()
        rendering = served.fetch("/rendering")
        signature = served.fetch("/signature")

    assert isinstance(served.record.report, Unsigned)
    for response in (payload, rendering, signature):
        assert response.status_code == 409
        assert response.json()["detail"]["outcome"] == "never_signed"
        assert "no signing key" in response.json()["detail"]["statement"]
        assert "rendered_sha256" not in response.text


def test_a_run_that_stopped_without_completing_will_never_have_a_report(
    leakage_case: Case,
) -> None:
    """Declined at the interrupt, and told so rather than told to poll.

    *Not yet* and *not ever* are two facts and only one of them is worth waiting on.
    A run that stopped — declined, unanswered, refused at registration, aborted by
    its own ceiling, or stopped on the wire — has no report coming, and a caller
    handed the poll-again outcome would wait for the lifetime of the process.
    """
    app = create_app(
        BenchConfig(cases=[leakage_case], report=ReportConfig(signing_key=generate()))
    )
    with watched_reference() as watched, TestClient(app) as client:
        nonce = registered(client, watched)
        started = client.post("/runs", json=a_request(watched.target, nonce)).json()
        run_id = str(started["run_id"])
        client.post(
            f"/runs/{run_id}/approval",
            json={"confirmed": False, "identity": "operator", "reason": "too costly"},
        )
        response = client.get(f"/report/{run_id}")

    detail = response.json()["detail"]
    assert response.status_code == 409
    assert detail["outcome"] == "did_not_complete"
    assert "declined" in detail["statement"]
    assert "will not produce one" in detail["statement"]


def test_an_artefact_that_could_not_be_assembled_is_a_completed_run_with_no_report(
    leakage_case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A publication that fails does not fail the run, and does not hide either.

    The suite ran and the target was measured, so a run marked *failed* for this
    would be reporting a publication fault as a fact about somebody's agent. What it
    must not do is go quiet: the reason is on the run's own statement, where a poller
    reads it, and the route names it.
    """

    def unbuildable(*_: object, **__: object) -> None:
        raise ValueError("no episode belongs to this target")

    monkeypatch.setattr("backend.api.runs.artefact_for", unbuildable)

    with completed([leakage_case], generate()) as served:
        response = served.fetch()
        progress = served.client.get(f"/runs/{served.run_id}").json()

    detail = response.json()["detail"]
    assert response.status_code == 409
    assert detail["outcome"] == "never_signed"
    assert "no episode belongs to this target" in detail["statement"]
    # The run completed, said so, and said what it does not have. And it advertises
    # no report location, because there is no report at the end of it.
    assert progress["status"] == "completed"
    assert progress["report"] is None
    assert "no signed report" in progress["statement"]


def test_a_completed_run_with_no_key_advertises_no_report_to_fetch(
    leakage_case: Case,
) -> None:
    """The location is read off the artefact, not off the status.

    A completed run on a bench that cannot sign has finished and has nothing to
    serve. A location advertised for it would send a caller to three paths that all
    refuse, which is a report presented as existing — the reading story 8 forbids.
    """
    with completed([leakage_case], None) as served:
        progress = served.client.get(f"/runs/{served.run_id}").json()

    assert progress["status"] == "completed"
    assert progress["report"] is None
    assert "no signed report" in progress["statement"]
    assert "no signing key" in progress["statement"]


def test_an_unknown_run_id_is_refused_by_its_own_name(leakage_case: Case) -> None:
    """A run this bench never started is neither incomplete nor unsigned."""
    app = create_app(BenchConfig(cases=[leakage_case]))
    with TestClient(app) as client:
        response = client.get("/report/not-a-run-this-bench-started")

    assert response.status_code == 404
    assert response.json()["detail"]["outcome"] == "no_such_run"


# --- helpers ---------------------------------------------------------------------


def _sentences(node: Any) -> Iterator[str]:
    """Every string anywhere in the response, however deeply nested."""
    if isinstance(node, dict):
        for value in node.values():
            yield from _sentences(value)
    elif isinstance(node, list):
        for value in node:
            yield from _sentences(value)
    elif isinstance(node, str):
        yield node


def _keys(node: Any) -> Iterator[str]:
    """Every key anywhere in the served document, however deeply nested."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield str(key)
            yield from _keys(value)
    elif isinstance(node, list):
        for value in node:
            yield from _keys(value)
