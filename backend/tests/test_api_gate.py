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

**That a deployment cites the gate run its own library recorded.** ADR-0021 left
`deployed_bench` declaring no citation, so a live deployment read as an instrument
with no certification even where it had passed a gate — true, and misleading, and the
same surface as a gate run not updating what the bench cites. ADR-0023 reverses it,
and the three tests at the end of this file are the reversal: the cases and the
citation come out of one directory, an absent citation is still a stated absence
rather than an invented pass, and the value the route serves is the value every
report's provenance block is built from.

**That both files are named and neither is read.** The citation names two paths — the
dated document, and the gate run record ADR-0023 made it point at — and nothing in
this route opens either. Asserted twice — a bench citing a document that is not on this
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

**That this route is not the one that starts a gate run, and that the one which
does is where it says it is.** This file used to assert that no such route existed
anywhere, on PLAN.md §8's authority. ADR-0021 reversed that decision, so the
assertions were turned around rather than deleted: a gate run is started at
`POST /gate-runs`, that route family is pinned by its own constants, and everything
else about the word *gate* on this surface is still a read. Asserted from two
directions, because the first is escapable by naming a route something else and a
gate run started under a friendlier word would spend the same 830 calls: nothing
whose path says *gate* is a write unless it is one of the two the gate-run family
declares, and the only writes under `/bench` are the two settings routes ADR-0025
admits (as amended by #57) — a gate run is not one of them and never moved there.
What the reversal did not touch is why the pinning matters — the estimate and the
three attestation statements are what make those 830 calls somebody's decision
(ADR-0007), and they are asserted in `test_api_gate_runs.py`.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import cast

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend.api.app import (
    BENCH_FAMILIES_ROUTE,
    BENCH_GATE_RECORD_ROUTE,
    BENCH_GATE_ROUTE,
    BENCH_NOTES_ROUTE,
    BENCH_SELECTION_ROUTE,
    BENCH_SETTINGS_ROUTE,
    BENCH_TUNING_ROUTE,
    GATE_RUN_APPROVAL_ROUTE,
    GATE_RUN_ROUTE,
    GATE_RUNS_ROUTE,
    PENDING_MEASUREMENT_APPROVAL_ROUTE,
    PENDING_MEASUREMENTS_ROUTE,
    RULE_OF_TWO_ROUTE,
    create_app,
)
from backend.api.report import ReportConfig
from backend.api.runs import BenchConfig, BenchRuns
from backend.bench.cited import citation_of, cite
from backend.bench.gate_record import write_the_record
from backend.bench.library import Case, Family, LibraryVersion
from backend.bench.payload import UNCITED_GATE, GateCitation, citation
from backend.bench.rule import DECLARED_RULE
from backend.bench.scorer import GateOutcome
from backend.bench.signing import SIGNING_KEY_VARIABLE, encoded_private, generate
from backend.tests.test_api_report import completed
from backend.tests.test_cited import a_passing_gate, a_record

CITED = GateCitation(
    outcome=GateOutcome.PASSED,
    decided_on=date(2026, 8, 19),
    library=LibraryVersion(cases=18, digest="90a8ebcc3d0c"),
    document="docs/gate-runs/gate-2026-08-19T09-38-37Z.md",
    record="docs/gate-runs/gate-2026-08-19T09-38-37Z.json",
)
"""The gate run of 2026-08-19 — the one this repository's own bench last passed."""

RECORDED = a_record(a_passing_gate())
"""One gate run's record, as a library that has run one holds it (ADR-0023).

Built through `gate_record.recorded_gate_run` rather than written as JSON here,
because the assertions below are that the citation a deployment reads is rendered off
this record — and a hand-written record would be exactly the second reading the
arrangement exists to prevent."""


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
        "record": "docs/gate-runs/gate-2026-08-19T09-38-37Z.json",
        # `null` and never a missing key: this library still holds exactly the
        # cases that gate run put itself through, and a reader who cannot tell that
        # from a serialiser that stopped writing the key will assume the
        # reassuring one (ADR-0033).
        "moved": None,
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
    """Both paths are links for the reader, not inputs to this route.

    Three halves now. A bench citing files that are not on this filesystem answers
    with the paths it was given — nothing here reads either, so nothing here can fail
    on them. A bench citing a document that *is* on this filesystem serves nothing the
    document alone holds: the three reference agents' rates and the per-family `D`
    are in it and are not in the citation, and the spec dropped them rather than
    parse them, so this is the assertion that fails when somebody lifts them out.

    And the third is what ADR-0023 added: `record` names the same gate run as fields,
    so those figures are *reachable* — and reachable is the whole difference. The
    assertion is that the name is served verbatim and that the response still holds
    no figure, because a route that had started inlining the record's contents would
    be serving per-family figures the spec dropped, arriving from a file instead of
    from prose.
    """
    absent = "docs/gate-runs/gate-2099-01-01T00-00-00Z.md"
    beside_it = absent.replace(".md", ".json")
    assert not Path(absent).exists() and not Path(beside_it).exists()
    named = a_client(
        GateCitation(
            outcome=GateOutcome.NOT_DECIDED,
            decided_on=date(2099, 1, 1),
            library=LibraryVersion(cases=1, digest="0000deadbeef"),
            document=absent,
            record=beside_it,
        )
    ).get(BENCH_GATE_ROUTE)
    assert named.status_code == 200
    assert named.json()["citation"]["document"] == absent
    assert named.json()["citation"]["record"] == beside_it

    assert CITED.document is not None
    on_disk = Path(CITED.document)
    assert on_disk.exists(), "the citation under test names a document in this repo"
    document = on_disk.read_text(encoding="utf-8")
    body = a_client(CITED).get(BENCH_GATE_ROUTE).json()
    served = a_client(CITED).get(BENCH_GATE_ROUTE).text

    # The rule in the response is `rule.py`'s own text and not a number scraped out
    # of the prose beside it, which is what lets the scan below be about
    # measurements rather than about wording.
    assert body["rule"]["stated"] == DECLARED_RULE.stated()

    # The document carries a printed rule of its own, and it is deliberately *not*
    # asserted equal to today's: a dated gate document carries the text it was
    # written with, and since ADR-0033 the rule prints no per-family `n` — the
    # library's shape is read off the attempts that ran instead. Every recorded
    # document from that ticket on carries different rule text, and the ones already
    # signed are unaffected, which is the point of recording it on the document
    # rather than looking it up (ADR-0017).
    assert "the decision rule as applied, from ADR-0003 and ADR-0015:" in document
    assert DECLARED_RULE.stated() not in document

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


def test_this_route_reads_and_the_one_that_starts_a_gate_run_is_elsewhere() -> None:
    """Which route starts a gate run, exactly, over the whole HTTP surface.

    The assertion this replaces said that no route did, and it was right until
    ADR-0021: a gate run is 830-odd calls against three reference agents and a
    write-back to every case record, and PLAN.md §8 kept it on the command line. The
    reversal did not weaken the claim, it moved it — so this now says *where*, and
    says it over the route table rather than by reading a file, because the useful
    failure is a second start route appearing under a friendlier word.

    Three things at once. This route is a `GET` and nothing else. The two routes that
    write are the gate-run family's own, named by the constants that declare them, so
    a write appearing anywhere else with *gate* in its path fails here. And the
    citation route is not one of them: reading what a gate run decided and starting
    one are two operations, which is unchanged by ADR-0023 making the citation the
    gate run this bench last made rather than the one a deployment declared.
    """
    app = create_app(BenchConfig(cases=[], report=ReportConfig(gate=CITED)))
    gate_routes = {
        (route.path, method)
        for route in app.routes
        if isinstance(route, APIRoute) and "gate" in route.path
        for method in route.methods or set()
        if method != "HEAD"
    }

    assert gate_routes == {
        (BENCH_GATE_ROUTE, "GET"),
        (BENCH_GATE_RECORD_ROUTE, "GET"),
        (GATE_RUNS_ROUTE, "GET"),
        (GATE_RUNS_ROUTE, "POST"),
        (GATE_RUN_ROUTE, "GET"),
        (GATE_RUN_APPROVAL_ROUTE, "POST"),
    }
    assert {(path, method) for path, method in gate_routes if method != "GET"} == {
        (GATE_RUNS_ROUTE, "POST"),
        (GATE_RUN_APPROVAL_ROUTE, "POST"),
    }
    assert (BENCH_GATE_ROUTE, "POST") not in gate_routes


def test_only_the_two_settings_routes_write_under_the_bench_prefix() -> None:
    """`/bench` reads, apart from the two routes that set a run's declared inputs.

    The assertion above is about the word *gate* in a path, and a route called
    `/bench/validate` would walk straight past it. This one is about the prefix: the
    subject of `/bench` is the instrument, everything the console asks of the
    instrument is a question, and a gate run is the one thing under it that would
    spend money and write to the case library. So every method on every route here is
    a `GET` bar the two that declare the next run's inputs, and a **third** write
    appearing under this prefix fails here whatever it is called.

    Every route on the prefix is named here rather than allowed for, because the claim
    this test makes is about the whole set and not about how many are in it:
    `GET /bench/settings` states what this bench is configured to do, and
    `GET /bench/notes` serves the content the injection family attacks with — content
    an operator plants in their own system and declares at registration, which is why
    even that one is a read. `test_api_settings.py` asserts the same equality from its
    own end.

    **ADR-0021 did not weaken this one.** A gate run can now be started over HTTP,
    and it is started at `POST /gate-runs` — a route whose path says plainly that it
    is not a read. Nothing moved under `/bench` to do it.

    **ADR-0025, as amended, admits three writes here**, and the set below is how
    narrow they are: the instruments the next run is set with, the families it covers,
    and — since #79 — the layers and constructions it sends. The decision paragraph
    said *one* and the families route already existed, which is a claim the tree had
    outgrown before it was written down (#57); the third is argued in ADR-0058 on the
    same four conditions. A gate run is
    still not one of them — it spends money and rewrites the case library, and it
    stays at its own `POST`.
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
        (BENCH_GATE_RECORD_ROUTE, "GET"),
        (BENCH_NOTES_ROUTE, "GET"),
        (BENCH_SETTINGS_ROUTE, "GET"),
        (BENCH_TUNING_ROUTE, "PUT"),
        (BENCH_FAMILIES_ROUTE, "PUT"),
        (BENCH_SELECTION_ROUTE, "PUT"),
    }

    # And the not-`GET` routes on this bench are the eleven that are named — eight
    # `POST`s and the three settings `PUT`s. Three of the eight start something that
    # spends — a run, a gate run and a pending-route measurement — and each is behind
    # an attestation that cannot be constructed incomplete and a halt in front of the
    # figures (ADR-0007). The count is asserted by naming every pair rather than by
    # its length, because a **twelfth** is either a spend nobody declared or a
    # setting no ADR admitted, and the failure has to name which route it is.
    #
    # **The third spend arrived with ADR-0105** and is named here on the same terms
    # as the second: deciding a pending route measures it against three reference
    # agents on two models and writes an admitted one into the case library, so it
    # is its own `POST` under its own prefix — nothing moved under `/bench` to do
    # it, and its halt is answered at a route of its own rather than by a field on
    # the request that started it.
    #
    # **One of the six writes nothing at all, and it is named here for that reason.**
    # `POST /rule-of-two` reads four declarations against a published rule and
    # records none of them: no run, no nonce, no setting, and no bench in its
    # closure. It is a `POST` for its body rather than for a change — four tri-state
    # answers about somebody's agent in a query string would be a declaration in a
    # URL and in a log (ADR-0092) — so it arrives in this set and has to be admitted
    # by name, which is this test working rather than an exception to it.
    writes = {
        (route.path, method)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods or set()
        if method not in {"GET", "HEAD"}
    }
    assert writes == {
        ("/nonces", "POST"),
        (RULE_OF_TWO_ROUTE, "POST"),
        ("/runs", "POST"),
        ("/runs/{run_id}/approval", "POST"),
        (GATE_RUNS_ROUTE, "POST"),
        (GATE_RUN_APPROVAL_ROUTE, "POST"),
        (PENDING_MEASUREMENTS_ROUTE, "POST"),
        (PENDING_MEASUREMENT_APPROVAL_ROUTE, "POST"),
        (BENCH_TUNING_ROUTE, "PUT"),
        (BENCH_FAMILIES_ROUTE, "PUT"),
        (BENCH_SELECTION_ROUTE, "PUT"),
    }


def test_a_deployment_cites_the_gate_run_its_own_library_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The gap four tickets declined to close: a deployment that has passed a gate.

    `deployed_bench` declared no citation, so a live deployment's front door and gate
    screen read *no gate run cited* even where the bench had passed one — true, and
    misleading, and the same surface as a gate run not updating what the bench cites
    (ADR-0023). The cases and the citation now come out of one directory, so the claim
    and the cases it is a claim about cannot come apart.

    Driven through the factory rather than through `deployed_bench` directly, because
    the claim is about what a deployed *app* answers: a factory that read the citation
    and dropped it would satisfy an assertion on the function and still serve
    *uncited* on the route an operator opens.
    """
    mount = tmp_path / "cases"
    mount.mkdir()
    write_the_record(RECORDED, mount)
    cite(RECORDED, mount)
    monkeypatch.setenv(SIGNING_KEY_VARIABLE, encoded_private(generate()))
    monkeypatch.setattr("backend.api.app.DEPLOYED_LIBRARY_MOUNT", mount)

    body = TestClient(create_app()).get(BENCH_GATE_ROUTE).json()

    expected = citation_of(RECORDED)
    assert body["citation"] == citation(expected)
    assert body["citation"]["outcome"] == expected.outcome.value
    # And the figures are reachable from what the citation names, in the library the
    # deployment is running on, without opening a document.
    assert (mount / body["citation"]["record"]).exists()
    assert list(mount.glob("*.md")) == []


def test_a_deployment_whose_library_records_no_gate_run_states_the_absence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No citation in the library is a stated absence, not an invented pass.

    The other half, and it has to be the other half rather than a fallback: a
    deployment citing a gate run its own library has no record of would be a claim
    nobody can check, which is worse than the blank ADR-0023 set out to remove.
    """
    mount = tmp_path / "cases"
    mount.mkdir()
    monkeypatch.setenv(SIGNING_KEY_VARIABLE, encoded_private(generate()))
    monkeypatch.setattr("backend.api.app.DEPLOYED_LIBRARY_MOUNT", mount)

    app = create_app()
    body = TestClient(app).get(BENCH_GATE_ROUTE).json()

    assert body["citation"] == {"cited": False, "stated": UNCITED_GATE}
    # And the cases arrived: the library was seeded from the image, so it is the
    # citation that is absent rather than the bench.
    assert cast(BenchRuns, app.state.bench).config.cases
    # The rule is still served, because an uncited instrument is held to the same bar.
    assert body["rule"]["stated"] == DECLARED_RULE.stated()


def test_the_citation_a_deployment_reads_is_the_one_its_reports_carry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One value, two carriers: the route the console reads and the signed payload.

    The strongest form of *the citation and the record cannot disagree* on this
    surface. `ReportConfig.gate` is what every report's provenance block is built
    from, and the route serves the same object through the same serialiser — so a
    deployment that read its citation off the library and then signed something else
    is a state this asserts out of existence.
    """
    mount = tmp_path / "cases"
    mount.mkdir()
    cite(RECORDED, mount)
    monkeypatch.setenv(SIGNING_KEY_VARIABLE, encoded_private(generate()))
    monkeypatch.setattr("backend.api.app.DEPLOYED_LIBRARY_MOUNT", mount)

    app = create_app()
    carried = cast(BenchRuns, app.state.bench).config.report.gate
    served = TestClient(app).get(BENCH_GATE_ROUTE).json()["citation"]

    assert carried == citation_of(RECORDED)
    assert citation(carried) == served
