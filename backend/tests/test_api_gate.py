"""The one route whose subject is the bench, and the one document it never opens.

`GET /bench/gate` is the console's front door reading the instrument's own
certification: the outcome of the gate run this bench cites, the date it was
decided, the library version it was earned at, and the path of the document that
recorded it. Five assertions here and each of them is about a way this could go
wrong rather than about the shape of a dict.

**That the citation is the artefact's citation and not a second one.** The strongest
test in this file drives one run to a signed artefact and compares the route's body
with the gate block inside the bytes that were signed. Two serialisers would only
have to disagree once for a screen to state a gate result no artefact carries, and
the disagreement would be in the flattering direction (ADR-0018).

**That an uncited bench states the absence.** Asserted as the absence of the fields
a citation has rather than as the presence of empty ones: `cited: false` is a
different fact from *did not pass*, and a response with `outcome: ""` in it is the
second fact wearing the first one's clothes.

**That the document is named and never read.** The citation names a path; nothing in
this route opens it. Asserted twice — a bench citing a document that is not on this
filesystem still answers, and a bench citing one that is serves not one figure the
document alone holds — because the useful failure is a future contributor deciding
the screen would be nicer with the per-family rates and the per-family `D` in it,
which the spec dropped rather than parse.

**That there is no route that starts a gate run.** Asserted over the application's
own route table rather than by reading this file, because the claim is about the
whole surface: a gate run is 830-odd calls against three reference agents under a
terminal consent flow, and the console's contribution is to have no button
(PLAN.md §8).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend.api.app import BENCH_GATE_ROUTE, create_app
from backend.api.report import ReportConfig
from backend.api.runs import BenchConfig
from backend.bench.library import Case, Family, LibraryVersion
from backend.bench.payload import UNCITED_GATE, GateCitation
from backend.bench.scorer import GateOutcome
from backend.bench.signing import generate
from backend.tests.test_api_report import completed

CITED = GateCitation(
    outcome=GateOutcome.PASSED,
    decided_on=date(2026, 8, 19),
    library=LibraryVersion(cases=18, digest="90a8ebcc3d0c"),
    document="docs/gate-runs/gate-2026-08-19T09-38-37Z.md",
)
"""The gate run of 2026-08-19 — the one this repository's own bench last passed."""


def a_client(gate: GateCitation | None) -> TestClient:
    """A bench that cites that gate run, or one that cites none. No run needed.

    The citation is configuration and not a result, so the route can be read off a
    bench that has never attacked anything — which is also the state a fresh
    deployment is in when an operator opens the console for the first time.
    """
    return TestClient(create_app(BenchConfig(cases=[], report=ReportConfig(gate=gate))))


def test_the_route_cites_the_gate_run_the_bench_last_passed() -> None:
    """Outcome, date and library version, each read off the citation."""
    body = a_client(CITED).get(BENCH_GATE_ROUTE).json()

    assert body == {
        "cited": True,
        "outcome": "passed",
        "decided_on": "2026-08-19",
        "library": {"cases": 18, "digest": "90a8ebcc3d0c"},
        "document": "docs/gate-runs/gate-2026-08-19T09-38-37Z.md",
        "stated": CITED.stated(),
    }

    # The subject is the bench, in the citation's own words. There is no sentence
    # here in which a target passes or fails anything (ADR-0018).
    assert body["stated"].startswith("the bench passed its own gate")
    assert "not a verdict on this target" in body["stated"]


def test_a_bench_citing_no_gate_run_states_the_absence_not_a_blank() -> None:
    """An uncited instrument is a fact, and the route says it in a sentence."""
    body = a_client(None).get(BENCH_GATE_ROUTE).json()

    assert body == {"cited": False, "stated": UNCITED_GATE}
    assert "no gate run is cited" in body["stated"]

    # Not an empty citation: there is no outcome, no date, no library version and no
    # document, so nothing here can be rendered as a gate that did not pass.
    for absent in ("outcome", "decided_on", "library", "document"):
        assert absent not in body


def test_the_route_serves_the_same_citation_the_signed_provenance_carries(
    leakage_case: Case,
) -> None:
    """One citation, two carriers: the artefact's provenance and this route.

    Compared over a real run rather than over a record built by hand, because what
    has to agree is what a recipient verifies and what the console shows.
    """
    with completed([leakage_case], key=generate(), gate=CITED) as served:
        signed = json.loads(served.artefact().canonical)
        body = served.client.get(BENCH_GATE_ROUTE).json()

    assert body == signed["provenance"]["gate"]


def test_the_gate_document_is_named_and_never_opened() -> None:
    """The path is a link for the reader, not an input to this route.

    Two halves. A bench citing a document that is not on this filesystem answers
    with the path it was given — nothing here reads it, so nothing here can fail on
    it. And a bench citing one that *is* on this filesystem serves nothing the
    document alone holds: the three reference agents' rates and the per-family `D`
    are in it and are not in the citation, and the spec dropped them rather than
    parse them, so this is the assertion that fails when somebody lifts them out.
    """
    absent = "docs/gate-runs/gate-2099-01-01T00-00-00Z.md"
    assert not Path(absent).exists()
    named = a_client(
        GateCitation(
            outcome=GateOutcome.NOT_DECIDED,
            decided_on=date(2099, 1, 1),
            library=LibraryVersion(cases=1, digest="0000deadbeef"),
            document=absent,
        )
    ).get(BENCH_GATE_ROUTE)
    assert named.status_code == 200
    assert named.json()["document"] == absent

    on_disk = Path(CITED.document)
    assert on_disk.exists(), "the citation under test names a document in this repo"
    document = on_disk.read_text(encoding="utf-8")
    served = a_client(CITED).get(BENCH_GATE_ROUTE).text

    # Per-family figures are in the document and nowhere in the response: not a
    # family name, not a `D`, not a κ, not a rate over the reference agents.
    for figure in ("D = ", "κ", "hardened", "weak", "trivial"):
        assert figure in document, f"the document under test holds {figure!r}"
        assert figure not in served
    for family in Family:
        assert family.value in document
        assert family.value not in served


def test_no_route_on_this_bench_starts_a_gate_run() -> None:
    """The console cites the gate and offers no way to run one (PLAN.md §8).

    Over the route table, so it is a claim about the whole HTTP surface: a gate run
    attacks three reference agents, spends about 830 calls and writes back to the
    case library, and it stays behind the terminal consent flow that asks the three
    attestation statements one at a time.
    """
    app = create_app(BenchConfig(cases=[], report=ReportConfig(gate=CITED)))
    gate_routes = {
        (route.path, method)
        for route in app.routes
        if isinstance(route, APIRoute) and "gate" in route.path
        for method in route.methods or set()
    }

    assert gate_routes == {(BENCH_GATE_ROUTE, "GET")}
