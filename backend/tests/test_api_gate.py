"""The one route whose subject is the bench, and the one document it never opens.

`GET /bench/gate` is the console's front door reading the instrument's own
certification: the declared rule the gate is decided under, and then the outcome of
the gate run this bench cites, the date it was decided, the library version it was
earned at, and the path of the document that recorded it. Every assertion here is
about a way this could go wrong rather than about the shape of a dict.

**That the rule is served, whole, above the outcome.** A pass with no bar beside it
is a verdict to be trusted; the rule beside it is an answer to be re-derived, which
is the whole of ADR-0003 and the reason the numbers were declared before the code
that evaluates them existed. Asserted three ways: that `rule` precedes `citation` on
the wire, that every threshold on it is the one `rule.py` declares rather than a
literal copied for a screen, and that a bench citing no gate run still serves it —
the rule is a fact about the bench, and an uncited instrument is held to the same bar
as a certified one.

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

The scan behind that second half is aimed at **measurements** and not at words. The
gate run's document prints the declared rule inside itself, so the rule's own clauses
appear in both places and their presence in a response proves nothing either way —
which is why the rule is asserted equal to `rule.py`'s own text, and why every marker
scanned for is one only a measured figure produces: a `D` with an `=` after it rather
than a `≥`, a count over a denominator, an interval, a family named, an outcome
shouted. A scan that had banned the word *hardened* would have banned the
monotonicity clause of the rule the screen is required to print.

**That there is no route that starts a gate run.** Asserted over the application's
own route table rather than by reading this file, because the claim is about the
whole surface: a gate run is 830-odd calls against three reference agents under a
terminal consent flow, and the console's contribution is to have no button
(PLAN.md §8). Twice, from two directions — no route whose path says *gate* but the
one that reads the citation, and nothing under `/bench` that is not a read — because
the first assertion is escapable by naming a route something else and a gate run
started under a friendlier word would spend the same 830 calls.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend.api.app import BENCH_GATE_ROUTE, BENCH_SETTINGS_ROUTE, create_app
from backend.api.report import ReportConfig
from backend.api.runs import BenchConfig
from backend.bench.library import Case, Family, LibraryVersion
from backend.bench.payload import UNCITED_GATE, GateCitation
from backend.bench.rule import DECLARED_RULE
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

    assert body["citation"] == {
        "cited": True,
        "outcome": "passed",
        "decided_on": "2026-08-19",
        "library": {"cases": 18, "digest": "90a8ebcc3d0c"},
        "document": "docs/gate-runs/gate-2026-08-19T09-38-37Z.md",
        "stated": CITED.stated(),
    }

    # The subject is the bench, in the citation's own words. There is no sentence
    # here in which a target passes or fails anything (ADR-0018).
    assert body["citation"]["stated"].startswith("the bench passed its own gate")
    assert "not a verdict on this target" in body["citation"]["stated"]


def test_the_declared_rule_is_served_above_the_outcome() -> None:
    """The bar first, then what it answered — on the wire, in that order.

    A pass read with no rule beside it is a verdict somebody trusted. So the rule is
    not merely present: it is the first field of the response, it is whole, and every
    threshold on it is `rule.py`'s own rather than a number copied out for a screen.
    A threshold moved in one place and not the other is the failure ADR-0003 exists
    to make impossible, and this is where it lands.
    """
    body = a_client(CITED).get(BENCH_GATE_ROUTE).json()

    assert list(body) == ["rule", "citation"]

    rule = body["rule"]
    assert rule["stated"] == DECLARED_RULE.stated()
    assert rule == {
        "stated": DECLARED_RULE.stated(),
        "interval_confidence": DECLARED_RULE.interval_confidence,
        "attempts_per_case": DECLARED_RULE.attempts_per_case,
        "discrimination_floor": DECLARED_RULE.discrimination_floor,
        "retirement_floor": DECLARED_RULE.retirement_floor,
        "kappa_floor": DECLARED_RULE.kappa_floor,
        "gold_transcripts_per_family": DECLARED_RULE.gold_transcripts_per_family,
        "tolerated_inversions": DECLARED_RULE.tolerated_inversions,
        "family_count": DECLARED_RULE.family_count,
        "families_required": DECLARED_RULE.families_required,
        "monotonic_families_required": DECLARED_RULE.monotonic_families_required,
        "minimum_fit_families": DECLARED_RULE.minimum_fit_families,
    }

    # Whole, in the sense that matters: every clause the gate prints beside its
    # answer is here, so a reader can re-derive the outcome rather than trust it.
    for clause in ("per-family pass", "monotonicity", "not fit to report"):
        assert clause in rule["stated"]

    # And nothing adaptive, because the adaptive layer decides nothing and the rule
    # the gate prints holds only what decides (ADR-0010).
    assert not any(threshold in rule for threshold in ("turns", "episodes", "T", "k"))


def test_a_bench_citing_no_gate_run_states_the_absence_not_a_blank() -> None:
    """An uncited instrument is a fact, and the route says it in a sentence."""
    body = a_client(None).get(BENCH_GATE_ROUTE).json()

    assert body["citation"] == {"cited": False, "stated": UNCITED_GATE}
    assert "no gate run is cited" in body["citation"]["stated"]

    # Not an empty citation: there is no outcome, no date, no library version and no
    # document, so nothing here can be rendered as a gate that did not pass.
    for absent in ("outcome", "decided_on", "library", "document"):
        assert absent not in body["citation"]

    # And the rule is still served, whole and first. An uncited bench is held to the
    # same declared bar as a certified one — the rule is a fact about the bench, not
    # a field of a citation — so the screen an operator opens on a fresh deployment
    # states the rule and the command with nothing decided under them yet.
    assert list(body) == ["rule", "citation"]
    assert body["rule"]["stated"] == DECLARED_RULE.stated()


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

    # Field for field, and not merely field for field of the fields a screen wanted:
    # the citation is nested under its own key precisely so that this comparison
    # stays an equality. The rule sits beside it rather than inside it, because the
    # artefact's citation does not carry one and this block has to stay the same
    # block (ADR-0018).
    assert body["citation"] == signed["provenance"]["gate"]
    assert "rule" not in body["citation"]


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
    assert named.json()["citation"]["document"] == absent

    on_disk = Path(CITED.document)
    assert on_disk.exists(), "the citation under test names a document in this repo"
    document = on_disk.read_text(encoding="utf-8")
    body = a_client(CITED).get(BENCH_GATE_ROUTE).json()
    served = a_client(CITED).get(BENCH_GATE_ROUTE).text

    # The rule in the response is `rule.py`'s own text, so every clause of it that
    # also appears in the document got here from the declared record and not out of
    # the prose. This assertion is what lets the scan below be about measurements.
    assert body["rule"]["stated"] == DECLARED_RULE.stated()
    assert DECLARED_RULE.stated() in document

    # Per-family figures are in the document and nowhere in the response: not a
    # measured `D`, not a measured κ, not a count over its denominator, not an
    # interval, not the shouted outcome, and not one family named.
    for figure in (
        "D = ",
        "(0/30)",
        "(30/30)",
        "[0.000, 0.083]",
        "inversions (ordered)",
        "against the gold set (",
        "the gate PASSED",
    ):
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


def test_nothing_under_the_bench_prefix_does_anything_but_read() -> None:
    """`/bench` is the instrument's own prefix, and it is read-only.

    The assertion above is about the word *gate* in a path, and a route called
    `/bench/validate` would walk straight past it. This one is about the prefix: the
    subject of `/bench` is the instrument, everything the console asks of the
    instrument is a question, and a gate run is the one thing under it that would
    spend money and write to the case library. So every method on every route here is
    `GET`, and a write appearing under this prefix fails here whatever it is called.

    The prefix has a second route now — `GET /bench/settings`, the reader that states
    what this bench is configured to do — and it is named here rather than allowed
    for, because the claim this test makes is about the whole set and not about how
    many are in it. `test_api_settings.py` asserts the same equality from its own end.
    """
    app = create_app(BenchConfig(cases=[], report=ReportConfig(gate=CITED)))
    under_bench = {
        (route.path, method)
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/bench")
        for method in route.methods or set()
        if method != "HEAD"
    }

    assert under_bench == {
        (BENCH_GATE_ROUTE, "GET"),
        (BENCH_SETTINGS_ROUTE, "GET"),
    }
