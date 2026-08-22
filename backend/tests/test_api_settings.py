"""What this instrument is configured to do, and the four ways stating it goes wrong.

`GET /bench/settings` is the second route whose subject is the bench. It is a
reader: nothing under `/bench` writes, rotation stays in the environment and
configuration stays on the command line, because the factory reads its key from one
place and refuses to boot without it (ADR-0020). Every assertion here is about a way
this response could quietly become something else.

**Two key identifiers, because they are two facts.** The key an artefact will be
signed by and the key a verification is run against are the two halves of
`SignatureResult`, and a bench holding a private key nobody has published verifies
against the published one and reports `signed_by_another_key` on every report it ever
produces. That state is reachable, it is named, and it is invisible on a screen that
printed one identifier and called it *the key* — so the strongest test here builds
exactly that bench and asserts the two fingerprints differ. Beside it, the assertion
that neither is anything derived from the private half: the encoded private key, its
raw bytes and its base64 appear nowhere in the response.

**Four model settings, and four is a length.** The reference agents' model is what is
measured, the adjudicator's is the instrument measuring it, the adaptive attacker's
decides nothing, and the second reference model is what a swap is measured against.
Collapsing any two would report an instrument's agreement with itself, so the test
asserts four rows, four distinct instruments, and the three declared ones read off
`DeclaredModels` rather than out of a literal here.

**Two layer ceilings with no unit in common.** The strongest form of *nothing adds
them* is that there is nothing to add: the two records share no numeric field name,
so no sum has a name to be written under. Asserted that way, and then asserted over
the numbers on a bench whose declared figures are chosen so that no cross-layer sum
could appear by coincidence.

**Retired cases counted and kept.** The version is over the live half, so it is
comparable with the gate citation's by eye; the retired count sits beside it; and
neither the count of live cases plus retired nor any other pairing appears anywhere,
because *live* and *retired* answer different questions and their sum is a case count
nothing runs.
"""

from __future__ import annotations

import base64
from dataclasses import replace

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend.api.app import (
    BENCH_GATE_RECORD_ROUTE,
    BENCH_GATE_ROUTE,
    BENCH_NOTES_ROUTE,
    BENCH_SETTINGS_ROUTE,
    GATE_RUN_APPROVAL_ROUTE,
    GATE_RUNS_ROUTE,
    NOT_HELD_BY_THIS_BENCH,
    create_app,
)
from backend.api.report import UNDECLARED_MODEL, UNDECLARED_MODELS, ReportConfig
from backend.api.runs import BenchConfig
from backend.bench.adaptive.budget import AdaptiveBudget
from backend.bench.library import Case, Family, LibraryVersion
from backend.bench.payload import DeclaredModels
from backend.bench.rule import DECLARED_RULE, GateRule
from backend.bench.signing import (
    encoded_private,
    fingerprint,
    generate,
    public_key,
)
from backend.bench.verification import SignatureOutcome
from backend.graph.budget import REGISTRATION_PROBES_PER_TARGET
from backend.tests.conftest import retired_case, some_cases

DECLARED = DeclaredModels(
    calibration="openrouter:openai/gpt-4.1-nano",
    adjudicating="openrouter:openai/gpt-4.1-mini",
    attacking="openrouter:anthropic/claude-haiku",
)
"""Three identifiers a deployment declared, each one different from the others.

Different on purpose: two settings holding the same string is a legitimate
misconfiguration and not the collapse under test, and a fixture that repeated one
value could not tell a screen showing three rows from a screen showing one three
times.
"""

A_RULE = GateRule(attempts_per_case=7)
"""A declared rule whose sample size is not the shipped one.

Seven rather than ten so that the figure on the wire is provably read off the record
rather than defaulted, and so that the cross-layer sums below cannot collide with a
number that happens to be on the response for another reason.
"""

A_BUDGET = AdaptiveBudget(turns_per_episode=5, episodes_per_family=3, family_count=11)
"""A declared adaptive budget whose figures make every cross-layer sum absent.

The layer's ceiling is 11 x 3 x 5 = 165 turns. With the scored layer's 7 attempts
per case and 1 registration probe, every sum of one figure from each layer — 12, 10,
18, 172, 6, 4, 166 — is a number that appears nowhere on this response, so the scan
below fails when somebody adds one rather than passing by coincidence.
"""


def a_client(config: BenchConfig) -> TestClient:
    """A bench built through the factory, read through the client. No run needed.

    The configuration is what this route is about, so it can be read off a bench that
    has never attacked anything — which is also the state a fresh deployment is in
    when an operator opens the console for the first time.
    """
    return TestClient(create_app(config))


def configured(
    signing_key: Ed25519PrivateKey | None = None,
    pinned: Ed25519PublicKey | None = None,
    models: DeclaredModels = UNDECLARED_MODELS,
) -> BenchConfig:
    """A bench with those report settings, the declared rule and the declared budget."""
    return BenchConfig(
        cases=[],
        rule=A_RULE,
        adaptive=A_BUDGET,
        report=ReportConfig(signing_key=signing_key, pinned=pinned, models=models),
    )


def settings_of(config: BenchConfig) -> dict[str, object]:
    body = a_client(config).get(BENCH_SETTINGS_ROUTE)
    assert body.status_code == 200
    decoded: dict[str, object] = body.json()
    return decoded


def numbers_in(node: object) -> list[float]:
    """Every numeric leaf of the response, which is every figure it can be read for.

    Over the decoded structure rather than over the text, because the sentences on
    this response name ADRs by number and a scan of the bytes would be a scan of
    those. A boolean is not a figure and is not counted: `bool` is a subclass of
    `int` in Python and `declared: false` is not a zero.
    """
    if isinstance(node, bool):
        return []
    if isinstance(node, (int, float)):
        return [float(node)]
    if isinstance(node, list):
        return [figure for item in node for figure in numbers_in(item)]
    if isinstance(node, dict):
        return [figure for item in node.values() for figure in numbers_in(item)]
    return []


def fields_in(node: object) -> list[str]:
    """Every field name anywhere in the response, which is where a total would live."""
    if isinstance(node, list):
        return [field for item in node for field in fields_in(item)]
    if isinstance(node, dict):
        return [
            name for field, value in node.items() for name in (field, *fields_in(value))
        ]
    return []


def test_the_route_states_the_configuration_a_run_will_actually_use() -> None:
    """The bench's own configuration, read off the record the factory was handed.

    Through the factory and through the client, in the shape the console reads it:
    the two key identifiers, the library, the four model settings and the two
    ceilings, in that order, because the order on the wire is the order on the
    screen and the key an artefact is signed by is the first thing an operator opens
    this screen to learn.
    """
    body = settings_of(configured(models=DECLARED))

    assert list(body) == ["statement", "signing", "library", "models", "ceilings"]
    assert "a read" in str(body["statement"]).lower()

    # Not one field here is a measurement of anybody's target: no family is named,
    # so there is nothing on this response that could be read as a rate or a band
    # about an agent somebody registered (ADR-0018).
    served = a_client(configured(models=DECLARED)).get(BENCH_SETTINGS_ROUTE).text
    for family in Family:
        assert family.value not in served


def test_the_two_key_identifiers_are_two_facts_and_never_one() -> None:
    """The key an artefact is signed by, and the key a verification is run against.

    The bench under test is the one that matters: it signs with a key of its own and
    declares no pin, so its verifications run against the committed public half and
    every report it produces reads `signed_by_another_key`. A settings screen naming
    only the first would show that bench as correctly configured.
    """
    key = generate()
    body = settings_of(configured(signing_key=key))
    signing = body["signing"]
    assert isinstance(signing, dict)

    signs = signing["will_be_signed_by"]
    verifies = signing["verified_against"]
    assert isinstance(signs, dict)
    assert isinstance(verifies, dict)

    assert signs == {
        "holds_a_key": True,
        "fingerprint": fingerprint(key.public_key()),
        "stated": signs["stated"],
    }
    assert verifies["fingerprint"] == fingerprint(public_key())
    assert verifies["declared"] is False

    # Two facts, and on this bench they are different values. A response holding one
    # fingerprint could not say this, and neither could one that derived the second
    # from the first.
    assert signs["fingerprint"] != verifies["fingerprint"]
    assert SignatureOutcome.ANOTHER_KEY in str(signing["statement"])

    # And a bench whose pin is its own published half says so, on the same two
    # fields: *rotated* and *said nothing* are distinguishable rather than inferred
    # from a fingerprint a reader would have to recognise.
    pinned = settings_of(configured(signing_key=key, pinned=key.public_key()))
    keys = pinned["signing"]
    assert isinstance(keys, dict)
    declared = keys["verified_against"]
    signed_by = keys["will_be_signed_by"]
    assert isinstance(declared, dict)
    assert isinstance(signed_by, dict)
    assert declared["declared"] is True
    assert declared["fingerprint"] == signed_by["fingerprint"]


def test_nothing_derived_from_the_private_half_is_ever_served() -> None:
    """A fingerprint over a public key, and nothing else.

    Asserted over the bytes rather than over a field, because the failure this guards
    is a field somebody adds — and the useful form of *the private key is not served*
    is that no representation of it appears anywhere in the response.
    """
    key = generate()
    served = a_client(configured(signing_key=key)).get(BENCH_SETTINGS_ROUTE).text

    private = key.private_bytes_raw()
    for secret in (
        encoded_private(key),
        base64.b64encode(private).decode("ascii"),
        private.hex(),
    ):
        assert secret not in served

    # The public half is what identifies a key, and it is served as the one
    # representation of it a recipient is ever shown — never as PEM, never as bytes.
    assert fingerprint(key.public_key()) in served
    assert "BEGIN PUBLIC KEY" not in served
    assert "BEGIN PRIVATE KEY" not in served


def test_a_bench_that_does_not_sign_states_the_absence_where_a_key_would_be() -> None:
    """A stated absence and not a blank fingerprint.

    `holds_a_key: false` is a different fact from a key whose name failed to load, so
    there is no `fingerprint` field to be empty — the shape a caller branches on
    carries no place for one.
    """
    body = settings_of(configured())
    signing = body["signing"]
    assert isinstance(signing, dict)
    signs = signing["will_be_signed_by"]
    assert isinstance(signs, dict)

    assert signs["holds_a_key"] is False
    assert "fingerprint" not in signs
    assert "never_signed" in str(signs["stated"])

    # The other identifier is still answered: a bench that signs nothing still
    # verifies against something, and the question *which key* has an answer here
    # whether or not this bench can sign.
    verifies = signing["verified_against"]
    assert isinstance(verifies, dict)
    assert verifies["fingerprint"] == fingerprint(public_key())


def test_the_library_version_is_the_live_half_and_the_retired_are_counted_and_kept(
    leakage_case: Case,
) -> None:
    """Two figures, both read off the records, and no third that is their sum.

    A library with cases on both sides of retirement, because the failure this
    guards is a retired case dropped from the count — a screen showing a library
    with no past.
    """
    live = some_cases(4)
    retired = [
        retired_case(replace(leakage_case, id=f"retired-{index}")) for index in range(3)
    ]
    body = settings_of(
        BenchConfig(cases=[*live, *retired], rule=A_RULE, adaptive=A_BUDGET)
    )
    library = body["library"]
    assert isinstance(library, dict)
    version = LibraryVersion.of(live)

    # The version is over the cases a run scores, so it is comparable by eye with the
    # version the gate citation carries — the digest included, because a library
    # described only as four cases cannot say whether the four are the same four.
    assert library["live"] == {"cases": 4, "digest": version.digest}
    assert library["stated"] == version.stated()

    # Counted and kept. Marked, never deleted: a case the field caught up with is
    # evidence that the field moved.
    assert library["retired"] == 3
    assert "never deleted" in str(library["kept"])

    # The agent types the live half has cases for, in one sorted list and off the
    # records rather than from a constant: a console offering a kind no case names
    # would be offering a registration that silently skips every case.
    assert library["agent_types"] == sorted(
        {kind for case in live for kind in case.applies_to}
    )

    # And nothing here is their sum. Seven is a case count nothing runs: the live
    # half is what a run attempts and the retired half is what it no longer does.
    assert 7.0 not in numbers_in(library)
    assert LibraryVersion.of([*live, *retired]).digest != library["live"]["digest"]


def test_the_four_model_settings_are_four_rows_and_never_one() -> None:
    """Four instruments, four rows, and the three declared ones off the record.

    The fourth is the second reference model, which this bench does not hold: it is
    declared to the swap script on the command line, and stating that is what stops a
    screen showing three of four and reading as complete.
    """
    body = settings_of(configured(models=DECLARED))
    models = body["models"]
    assert isinstance(models, list)

    assert len(models) == 4
    assert [row["instrument"] for row in models] == [
        "the reference agents",
        "the adjudicator",
        "the adaptive attacker",
        "the second reference model",
    ]
    assert [row["identifier"] for row in models] == [
        DECLARED.calibration,
        DECLARED.adjudicating,
        DECLARED.attacking,
        NOT_HELD_BY_THIS_BENCH,
    ]
    assert [row["declared"] for row in models] == [True, True, True, False]

    # Four distinct rows, and no row that is two settings at once: every value on
    # every row belongs to that row's own instrument, so there is nowhere here for a
    # κ measured on the model that produced the transcripts to hide.
    assert len({row["identifier"] for row in models}) == 4
    for row in models:
        others = [
            other["identifier"]
            for other in models
            if other["instrument"] != row["instrument"]
        ]
        for elsewhere in others:
            assert elsewhere not in str(row["decides"])

    # And a bench that declared none of them says so on each row rather than naming a
    # default: a model named by omission would be this route asserting which
    # instrument produced a figure.
    undeclared = settings_of(configured())["models"]
    assert isinstance(undeclared, list)
    assert [row["declared"] for row in undeclared] == [False, False, False, False]
    assert [row["identifier"] for row in undeclared[:3]] == [UNDECLARED_MODEL] * 3


def test_the_two_layer_ceilings_share_no_field_and_nothing_adds_them() -> None:
    """Two records, two units, and no name under which a sum could be written.

    The type carries the invariant: attempts over cases on one side, turns over
    episodes on the other, and not one numeric field in common. Then the numbers,
    against a bench whose declared figures make every cross-layer sum a number that
    is absent — so a total added later fails here rather than coinciding with
    something already on the response.
    """
    body = settings_of(configured())
    ceilings = body["ceilings"]
    assert isinstance(ceilings, dict)

    assert list(ceilings) == ["scored", "adaptive", "statement"]
    scored = ceilings["scored"]
    adaptive = ceilings["adaptive"]
    assert isinstance(scored, dict)
    assert isinstance(adaptive, dict)

    assert scored == {
        "layer": "scored",
        "attempts_per_case": 7,
        "registration_probes_per_target": REGISTRATION_PROBES_PER_TARGET,
        "declared_in": scored["declared_in"],
        "statement": scored["statement"],
    }
    assert adaptive == {
        "layer": "adaptive",
        "turns_per_episode": 5,
        "episodes_per_family": 3,
        "families": 11,
        "turns_per_target": 165,
        "declared_in": adaptive["declared_in"],
        "statement": adaptive["statement"],
    }

    # No numeric field name in common, which is the whole of *neither layer borrows
    # the other's budget* expressed as a shape: an attempt is the unit of a
    # denominator and a turn is a spending limit, and there is no field here that
    # holds both.
    def figures(block: dict[str, object]) -> set[str]:
        return {
            field
            for field, value in block.items()
            if isinstance(value, int) and not isinstance(value, bool)
        }

    assert figures(scored) & figures(adaptive) == set()

    # And no figure anywhere on the response is a sum across the two layers.
    present = set(numbers_in(body))
    for one in figures(scored):
        for other in figures(adaptive):
            here, there = scored[one], adaptive[other]
            assert isinstance(here, int) and isinstance(there, int)
            crossed = float(here + there)
            assert crossed not in present, f"{one} + {other} is on the response"

    # Nor is there a field named for one. A combined budget would need somewhere to
    # live, and this is the assertion that fails when somebody gives it a home.
    for field in fields_in(body):
        assert not any(
            word in field
            for word in ("total", "combined", "sum", "overall", "both", "budget")
        )


def test_the_declared_figures_are_read_off_the_records_that_declare_them() -> None:
    """A threshold moved in `rule.py` moves here; a number written here is impossible.

    The shipped bench, with no rule or budget handed in, so what is asserted is that
    the route reads the declared records rather than a literal kept for a screen.
    """
    body = settings_of(BenchConfig(cases=[]))
    ceilings = body["ceilings"]
    assert isinstance(ceilings, dict)
    scored = ceilings["scored"]
    adaptive = ceilings["adaptive"]
    assert isinstance(scored, dict)
    assert isinstance(adaptive, dict)

    assert scored["attempts_per_case"] == DECLARED_RULE.attempts_per_case
    assert adaptive["turns_per_episode"] == AdaptiveBudget().turns_per_episode
    assert adaptive["episodes_per_family"] == AdaptiveBudget().episodes_per_family
    assert adaptive["families"] == AdaptiveBudget().family_count
    assert adaptive["turns_per_target"] == AdaptiveBudget().turn_ceiling

    # The records are named, so an operator reading a figure they disagree with knows
    # which file to open. The gate rule and the adaptive budget are deliberately two
    # records: nothing in the adaptive one decides anything (ADR-0010).
    assert "rule.py" in str(scored["declared_in"])
    assert "adaptive/budget.py" in str(adaptive["declared_in"])


def test_no_route_under_the_bench_prefix_changes_a_setting() -> None:
    """`/bench` is the instrument's own prefix and every method on it is a `GET`.

    Over the route table rather than over this module, because the claim is about the
    whole surface: rotation and configuration stay in the environment and the command
    line, so a settings screen has nothing to post to and a write appearing here
    fails whatever it is called.
    """
    app = create_app(BenchConfig(cases=[]))
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
    }

    # And nothing anywhere on this bench takes a key, a model or a threshold: the
    # settings screen is a reader, and the routes that write take an attestation, an
    # approval, or a nonce request.
    writes = {
        route.path
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods or set()
        if method not in {"GET", "HEAD"}
    }
    assert writes == {
        "/nonces",
        "/runs",
        "/runs/{run_id}/approval",
        # The gate-run family, since ADR-0021: one route that records the attestation
        # and declares the estimate, one that answers the halt. Neither is under
        # `/bench`, and neither takes a key, a model or a threshold — a gate run
        # rewrites the case library and changes no setting.
        GATE_RUNS_ROUTE,
        GATE_RUN_APPROVAL_ROUTE,
    }
