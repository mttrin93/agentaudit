"""What this instrument is configured to do, and the four ways stating it goes wrong.

`GET /bench/settings` is the second route whose subject is the bench. It is a
reader, and the three writes on the prefix are the settings `PUT`s below (ADR-0025 as
amended by #57 and #79). Rotation stays in the environment, because the factory reads
its key from one place and refuses to boot without it (ADR-0020), and the library stays
what was mounted. Every assertion here is about a way this response could quietly
become something else.

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
import json
from dataclasses import replace
from typing import cast

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend.api.app import (
    ATTACKER_MODELS,
    BENCH_FAMILIES_ROUTE,
    BENCH_GATE_RECORD_ROUTE,
    BENCH_GATE_ROUTE,
    BENCH_NOTES_ROUTE,
    BENCH_SELECTION_ROUTE,
    BENCH_SETTINGS_ROUTE,
    BENCH_TUNING_ROUTE,
    GATE_RUN_APPROVAL_ROUTE,
    GATE_RUNS_ROUTE,
    NO_EFFORT_HELD_FOR_THIS_INSTRUMENT,
    NOT_HELD_BY_THIS_BENCH,
    RULE_OF_TWO_ROUTE,
    TEMPERATURE_RANGE,
    create_app,
)
from backend.api.report import UNDECLARED_MODEL, UNDECLARED_MODELS, ReportConfig
from backend.api.runs import BenchConfig, BenchRuns, DeclaredGap, plan_for
from backend.bench.adaptive.budget import DECLARED_ADAPTIVE_BUDGET, AdaptiveBudget
from backend.bench.adaptive.episode import AttackerTool
from backend.bench.adaptive.tools import ToolInvocation
from backend.bench.adaptive.tree import BranchSchedule
from backend.bench.capability import (
    NO_REASONING_EFFORT_ACCEPTED,
    NO_TEMPERATURE_ACCEPTED,
    ReasoningEffort,
    accepts_temperature,
    capabilities_of,
)
from backend.bench.labels import elective_label_for, label_for
from backend.bench.library import (
    Case,
    ElectiveFamily,
    Family,
    LibraryVersion,
    Transform,
)
from backend.bench.payload import DeclaredModels
from backend.bench.rule import DECLARED_RULE, GateRule
from backend.bench.selection import (
    EVERY_CONSTRUCTION,
    AttackLayer,
    AttackSelection,
    layer_of,
)
from backend.bench.signing import (
    encoded_private,
    fingerprint,
    generate,
    public_key,
)
from backend.bench.verification import SignatureOutcome
from backend.graph.budget import REGISTRATION_PROBES_PER_TARGET, RunBudget
from backend.targets.reference.model import ModelConfig, Provider
from backend.tests.conftest import a_target, retired_case, some_cases

DECLARED = DeclaredModels(
    calibration="openrouter:openai/gpt-4.1-nano",
    adjudicating="openrouter:openai/gpt-4.1-mini",
    attacking="openrouter:anthropic/claude-haiku",
    narrative="openrouter:openai/gpt-4.1-mini",
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

    assert list(body) == [
        "statement",
        "signing",
        "library",
        "models",
        "ceilings",
        # The sixth, and the only one that is a control: the declared inputs of the
        # next run, with the bounds the route enforces (ADR-0025).
        "tuning",
    ]
    assert "a read" in str(body["statement"]).lower()

    # Not one field here is a measurement of anybody's target. A family is named in
    # exactly one place — the switch that says whether the next run covers it — and
    # that row carries no number, so there is nothing on this response that could be
    # read as a rate or a band about an agent somebody registered (ADR-0018).
    body = a_client(configured(models=DECLARED)).get(BENCH_SETTINGS_ROUTE).json()
    switches = body["tuning"].pop("families")
    assert [row["family"] for row in switches] == [str(family) for family in Family]
    for row in switches:
        # The label joined the switch in ADR-0091 and is not a third thing here: it is
        # what the family is *read onto* — published entries and articles — and carries
        # no rate, no interval and no `D`. What it is checked against is
        # `test_every_family_switch_carries_the_labels_its_row_prints`.
        assert set(row) == {"family", "covered", "labels"}
        assert isinstance(row["covered"], bool)
    for family in Family:
        assert family.value not in json.dumps(body)


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


def test_each_model_row_states_the_effort_it_is_set_to_or_the_absence_of_one() -> None:
    """The row was the model and not what the model was set to.

    A reader of this block could see which model the adjudicator runs on and not the
    conditions it ran under — and two runs of one model at one temperature and
    different reasoning effort are two different instruments (#5). So the effort is on
    the row, and where this bench holds none it says so rather than showing a blank:
    the rule the fourth row already followed for its identifier.

    The attacker's is the record's own sentence and never a second wording of it. It
    is the one field on this screen with four statements behind it — a declared level,
    none declared, a model with no such setting, and a model this table holds no line
    for — and the last two are different facts about different things, so a screen
    composing its own version would eventually state one while the signed document
    stated the other (ADR-0017).
    """
    declared = replace(
        DECLARED,
        attacking="openrouter:openai/gpt-5-mini",
        attacking_temperature=None,
        attacking_reasoning_effort=ReasoningEffort.HIGH,
    )
    models = settings_of(configured(models=declared))["models"]
    assert isinstance(models, list)

    [attacker] = [row for row in models if "attacker" in row["instrument"]]
    assert attacker["effort"] == declared.reasoning_effort_stated()
    assert "reasoning effort high" in attacker["effort"]

    # The three this bench sets no thinking budget on say the absence, once each, and
    # never with the attacker's sentence: a row reading *effort high* against the
    # adjudicator would be this route asserting a setting nobody made.
    elsewhere = [row["effort"] for row in models if "attacker" not in row["instrument"]]
    assert elsewhere == [NO_EFFORT_HELD_FOR_THIS_INSTRUMENT] * 3
    assert NO_EFFORT_HELD_FOR_THIS_INSTRUMENT != attacker["effort"]

    # Never a blank on any row, whatever the bench is configured with.
    undeclared = settings_of(configured())["models"]
    assert isinstance(undeclared, list)
    for row in [*models, *undeclared]:
        assert str(row["effort"]).strip()

    # And a model this table holds no line for reads as a presumption rather than as
    # a claim about the provider: the fourth statement, kept apart from *this model
    # has no such setting* because one is about the provider and one is about this
    # bench's own table.
    presumed = settings_of(
        configured(models=replace(DECLARED, attacking="openrouter:a/model-with-no-row"))
    )["models"]
    assert isinstance(presumed, list)
    [row] = [one for one in presumed if "attacker" in one["instrument"]]
    assert "no line in the capability table" in str(row["effort"])


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

    # And no figure anywhere on the response is a sum across the two layers. Read
    # over the two ceiling blocks rather than over the whole body, because `tuning`
    # restates both layers' settings side by side — it is the form's own state, and
    # the numbers on it are the settings themselves rather than figures read off a
    # run. The field-name check below still covers it, so a *named* blend anywhere
    # on the response still fails.
    present = set(numbers_in({key: body[key] for key in body if key != "tuning"}))
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


def test_three_routes_under_the_bench_prefix_write_and_all_are_declared_inputs() -> (
    None
):
    """`/bench` holds exactly three writes: tuning, families, and the selection.

    Over the route table rather than over this module, because the claim is about the
    whole surface. The line is not *no writes* any more and it is not *any write*: a
    setting that changes what the **next run covers or measures** may be set from the
    console, and what it changed is legible in the record of every run made under it.
    Everything else stays where it was — the signing key is read from the environment
    by `signing.signing_key` and by no route (ADR-0020), the library is what was
    mounted, and the citation moves only when a gate run earns it (ADR-0023).

    **Two, and it was two before the name above admitted it.** `PUT
    /bench/settings/families` predates ADR-0025, the ADR was written claiming one
    write anyway, and this set was later widened to admit the second while the name
    and the prose went on saying *one* — so the test kept failing correctly and
    describing itself wrongly (#57). ADR-0025's amendment argues the families route on
    the same four conditions as the tuning route, which is what makes the two below a
    decision rather than an accretion.

    **Three since #79**, and the third is `PUT /bench/settings/selection`: which
    layers the next run runs and which constructions inside them. It is the second
    setting on this prefix that moves the scored denominator, admitted on ADR-0025's
    four conditions and argued in ADR-0058 — condition 1 is met by a printed field
    rather than by an absence, because the artefact carries the selection in
    provenance.

    A **fourth** write appearing under this prefix fails here whatever it is called,
    which is the protection this test is. Every route is named rather than counted for
    exactly that reason: an assertion on how *many* writes there are would pass on a
    route that swapped one of these for something else.
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
        (BENCH_TUNING_ROUTE, "PUT"),
        (BENCH_FAMILIES_ROUTE, "PUT"),
        (BENCH_SELECTION_ROUTE, "PUT"),
    }

    # And nothing anywhere on this bench takes a key: the three setting routes take
    # the declared inputs of a run and nothing else, and the rest take an attestation,
    # an approval, a nonce request, or four declarations that are read and not stored.
    writes = {
        route.path
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods or set()
        if method not in {"GET", "HEAD"}
    }
    assert writes == {
        "/nonces",
        # A `POST` that stores nothing, and named here because it is one: the reading
        # of four declarations against the Agents Rule of Two records no run, spends
        # no nonce, sets nothing and takes no bench in its closure. It is a `POST`
        # for its body — four tri-state answers about somebody's agent do not belong
        # in a query string, a URL or a log (ADR-0092) — so it lands in this set and
        # is admitted by name rather than by widening the filter above.
        RULE_OF_TWO_ROUTE,
        "/runs",
        "/runs/{run_id}/approval",
        # The first of the two settings a console may write, since ADR-0025: the
        # attacker's model, its temperature and its reasoning effort, T, k and
        # attempts per case. Every one of them is printed in the report of every run
        # made under it, and none of them is a key.
        BENCH_TUNING_ROUTE,
        # And the second: which families the next run covers. Its own statement from
        # its own screen, and it takes no instrument.
        BENCH_FAMILIES_ROUTE,
        # And the third, since #79: how the next run attacks what it covers. Two
        # closed enumerations resolved server-side, and no key, model or threshold.
        BENCH_SELECTION_ROUTE,
        # The gate-run family, since ADR-0021: one route that records the attestation
        # and declares the estimate, one that answers the halt. Neither is under
        # `/bench`, and neither takes a key, a model or a threshold — a gate run
        # rewrites the case library and changes no setting.
        GATE_RUNS_ROUTE,
        GATE_RUN_APPROVAL_ROUTE,
    }


def test_the_declared_inputs_of_the_next_run_can_be_set_and_are_read_back() -> None:
    """The tuning write under `/bench`, and it answers with what the bench now holds.

    The response is the whole settings reading rather than an acknowledgement, so a
    console renders what was stored instead of what it hoped it sent — the same
    reason every other route here returns a record instead of a status.
    """
    app = create_app(BenchConfig(cases=[]))
    with TestClient(app) as client:
        answered = client.put(
            BENCH_TUNING_ROUTE,
            json={
                "attacker_model": UNDECLARED_MODEL,
                "temperature": 0.7,
                "turns_per_episode": 12,
                "episodes_per_family": 1,
                "attempts_per_case": 4,
            },
        )
        after = client.get(BENCH_SETTINGS_ROUTE).json()

    assert answered.status_code == 200
    tuned = answered.json()["tuning"]
    assert tuned["turns_per_episode"] == 12
    assert tuned["episodes_per_family"] == 1
    assert tuned["attempts_per_case"] == 4
    assert tuned["temperature"] == 0.7
    # And the reading a later GET serves is the same one: the write moved the record
    # every run is estimated and attempted against, not a copy of it.
    assert after["tuning"] == tuned
    assert after["ceilings"]["adaptive"]["turns_per_episode"] == 12
    assert after["ceilings"]["scored"]["attempts_per_case"] == 4


def test_every_offered_attacker_model_is_a_slug_a_provider_could_answer() -> None:
    """Each offered identifier parses, names a real provider, and says what it is for.

    The list is closed because a mistyped slug is refused by the provider at the
    *first call* — after the operator has attested and confirmed a spend — so the
    shape of every entry is worth asserting where it costs nothing. What this cannot
    check is that the model exists at the provider; what it does check is that nothing
    on the list is unparseable, unprovided, duplicated or unexplained.
    """
    for identifier, purpose in ATTACKER_MODELS:
        config = ModelConfig.parse(identifier)
        assert config.provider is Provider.OPENROUTER, identifier
        # A slug, not a bare model name: OpenRouter addresses every model as
        # `vendor/model`, and one without the vendor is a 404 at the first call.
        assert "/" in config.name, identifier
        # The sentence is the whole reason the list is a list of pairs: a dropdown of
        # four slugs with no purpose beside them is a choice nobody can make.
        assert purpose.strip(), identifier

    offered = [identifier for identifier, _ in ATTACKER_MODELS]
    assert len(offered) == len(set(offered))
    assert UNDECLARED_MODEL not in offered


def test_the_attacker_model_set_here_is_the_one_the_report_will_name() -> None:
    """One call sets the client and the identifier, so a report cannot name a model
    that never ran.

    The pairing `declared_instrument` makes at boot, made again here: the settings
    block's attacker row and the provenance the artefact carries are read off the
    same field.
    """
    app = create_app(BenchConfig(cases=[]))
    with TestClient(app) as client:
        body = client.put(
            BENCH_TUNING_ROUTE,
            json={
                "attacker_model": UNDECLARED_MODEL,
                "temperature": None,
                "turns_per_episode": 8,
                "episodes_per_family": 2,
                "attempts_per_case": 10,
            },
        ).json()

    [attacker] = [
        model for model in body["models"] if "attacker" in model["instrument"]
    ]
    assert attacker["identifier"] == UNDECLARED_MODEL
    [chosen] = [model for model in body["tuning"]["attacker_models"] if model["chosen"]]
    assert chosen["identifier"] == UNDECLARED_MODEL


def test_a_model_this_console_does_not_offer_is_refused_before_anything_is_built() -> (
    None
):
    """A slug the provider refuses fails at the first call, after the spend is
    confirmed. So the list is closed and the refusal names what is on it.
    """
    app = create_app(BenchConfig(cases=[]))
    with TestClient(app) as client:
        answered = client.put(
            BENCH_TUNING_ROUTE,
            json={
                "attacker_model": "openrouter:openai/gpt-9-imaginary",
                "temperature": None,
                "turns_per_episode": 8,
                "episodes_per_family": 2,
                "attempts_per_case": 10,
            },
        )
        after = client.get(BENCH_SETTINGS_ROUTE).json()

    assert answered.status_code == 422
    assert "gpt-9-imaginary" in answered.json()["detail"]
    # Nothing was set: a refused request leaves the bench where it was.
    declared = DECLARED_ADAPTIVE_BUDGET.turns_per_episode
    assert after["tuning"]["turns_per_episode"] == declared


def test_a_setting_outside_its_range_is_refused_rather_than_clamped() -> None:
    """A bench that quietly moved a number would run a setting nobody chose and
    print it in a report as though they had."""
    app = create_app(BenchConfig(cases=[]))
    with TestClient(app) as client:
        answered = client.put(
            BENCH_TUNING_ROUTE,
            json={
                "attacker_model": UNDECLARED_MODEL,
                "temperature": 9.5,
                "turns_per_episode": 8,
                "episodes_per_family": 2,
                "attempts_per_case": 10,
            },
        )
        after = client.get(BENCH_SETTINGS_ROUTE).json()

    assert answered.status_code == 422
    assert "temperature=9.5" in answered.json()["detail"]
    assert after["tuning"]["temperature"] is None


AN_OFFERED_CHAT_MODEL = "openrouter:openai/gpt-4.1-mini"
"""On the offered list, and the baseline: it takes a temperature and no reasoning
effort, which is the row of the capability table this pair of settings turns on."""

A_MODEL_THAT_TAKES_NO_TEMPERATURE = "openrouter:openai/gpt-5-mini"
"""On the offered list, and the model #4 was filed for.

Named rather than searched for, so this test says which model it is about; that it
is still on the list, and still one that accepts none, is asserted below.
"""


def test_a_temperature_a_model_rejects_is_refused_when_it_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Told in front of the estimate, not sixty calls into a run.

    The capability is declared (`bench/capability.py`), so the refusal costs no call
    — which is the whole of #4: the provider used to answer this question at the
    first episode, after the operator had attested and confirmed a spend.

    Refused rather than dropped, on the reasoning `_within` refuses a number out of
    range: a bench that quietly sent no temperature would print the setting in a
    provenance block as though the request had carried it (ADR-0004, ADR-0025).
    """
    monkeypatch.setattr(
        "backend.api.app.attacker_completion_for",
        lambda spec, temperature=None, reasoning_effort=None: _attacking,
    )
    assert A_MODEL_THAT_TAKES_NO_TEMPERATURE in [
        identifier for identifier, _ in ATTACKER_MODELS
    ]
    assert not accepts_temperature(A_MODEL_THAT_TAKES_NO_TEMPERATURE)

    app = create_app(BenchConfig(cases=[]))
    with TestClient(app) as client:
        refused = client.put(
            BENCH_TUNING_ROUTE,
            json={
                "attacker_model": A_MODEL_THAT_TAKES_NO_TEMPERATURE,
                "temperature": 0.4,
                "turns_per_episode": 8,
                "episodes_per_family": 2,
                "attempts_per_case": 10,
            },
        )
        after = client.get(BENCH_SETTINGS_ROUTE).json()["tuning"]

    assert refused.status_code == 422
    detail = refused.json()["detail"]
    assert "temperature=0.4" in detail
    assert A_MODEL_THAT_TAKES_NO_TEMPERATURE in detail
    # Nothing was set: not the temperature, and not the model beside it. A refused
    # request leaves the bench on the instrument it was on.
    assert after["temperature"] is None
    [chosen] = [model for model in after["attacker_models"] if model["chosen"]]
    assert chosen["identifier"] == UNDECLARED_MODEL


def test_a_model_that_takes_no_temperature_can_be_set_without_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """And the run made under it reads as *this model takes none*, never as 0.0.

    The other half of the refusal above, and the one that makes the family usable at
    all: leaving the field empty is available, it is what the console sends for an
    untouched slider, and the provenance block states which of the two absences it
    is (`DeclaredModels.temperature_stated`).
    """
    monkeypatch.setattr(
        "backend.api.app.attacker_completion_for",
        lambda spec, temperature=None, reasoning_effort=None: _attacking,
    )
    app = create_app(BenchConfig(cases=[]))
    with TestClient(app) as client:
        answered = client.put(
            BENCH_TUNING_ROUTE,
            json={
                "attacker_model": A_MODEL_THAT_TAKES_NO_TEMPERATURE,
                "temperature": None,
                "turns_per_episode": 8,
                "episodes_per_family": 2,
                "attempts_per_case": 10,
            },
        )
        models = cast(BenchRuns, app.state.bench).config.report.models

    assert answered.status_code == 200
    assert answered.json()["tuning"]["temperature"] is None
    assert models.attacking == A_MODEL_THAT_TAKES_NO_TEMPERATURE
    assert models.attacking_temperature is None
    assert "accepts no temperature" in models.temperature_stated()


def test_a_reasoning_effort_is_offered_only_for_a_model_that_has_the_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Three levels for a reasoning attacker, none for a chat one, and a sentence both
    times.

    A screen that drew three levels against a chat model would offer a control whose
    every value the route refuses at the moment it is set. The empty list is not the
    same statement as *no level chosen*, which is why `reasoning_effort_stated`
    travels beside it — the same sentence the provenance block of a run made now
    would print (#5).
    """
    monkeypatch.setattr(
        "backend.api.app.attacker_completion_for",
        lambda spec, temperature=None, reasoning_effort=None: _attacking,
    )
    app = create_app(BenchConfig(cases=[]))
    with TestClient(app) as client:
        answered = client.put(
            BENCH_TUNING_ROUTE,
            json={
                "attacker_model": A_MODEL_THAT_TAKES_NO_TEMPERATURE,
                "temperature": None,
                "reasoning_effort": "high",
                "turns_per_episode": 8,
                "episodes_per_family": 2,
                "attempts_per_case": 10,
            },
        )
        reasoning = answered.json()["tuning"]
        chat = client.put(
            BENCH_TUNING_ROUTE,
            json={
                "attacker_model": AN_OFFERED_CHAT_MODEL,
                "temperature": 0.0,
                "reasoning_effort": None,
                "turns_per_episode": 8,
                "episodes_per_family": 2,
                "attempts_per_case": 10,
            },
        ).json()["tuning"]

    assert answered.status_code == 200
    assert [level["level"] for level in reasoning["reasoning_efforts"]] == [
        str(level) for level in ReasoningEffort
    ]
    [chosen] = [level for level in reasoning["reasoning_efforts"] if level["chosen"]]
    assert chosen["level"] == "high"
    assert reasoning["reasoning_effort"] == "high"
    assert "reasoning effort high" in reasoning["reasoning_effort_stated"]

    # And nothing offered for a model with no such setting, with the reason stated
    # rather than left to an empty list.
    assert chat["reasoning_efforts"] == []
    assert chat["reasoning_effort"] is None
    assert "no reasoning effort" in chat["reasoning_effort_stated"]


def test_a_temperature_is_offered_only_for_a_model_that_takes_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A range for a chat attacker, none for a reasoning one, and a sentence both times.

    The reasoning select's own rule read the other way round, and the half of #4 its
    own report named as left undone: the capability was enforced at the route and the
    console learned it from the 422 *after* the operator had moved the slider. Served
    state and not a frontend guess — the table is declared once
    (`bench/capability.py`) and a console holding a copy of it would be a second table
    to disagree with.

    The two absences stay two. `temperature_bounds` being absent is *this model
    accepts none* — a choice nobody was offered — and `temperature_absent` is *no
    temperature declared*, a choice nobody made. `temperature_stated` is the sentence
    a run made now would print, so the screen cannot say one thing while the signed
    document says another (ADR-0017, ADR-0025).
    """
    monkeypatch.setattr(
        "backend.api.app.attacker_completion_for",
        lambda spec, temperature=None, reasoning_effort=None: _attacking,
    )
    app = create_app(BenchConfig(cases=[]))
    with TestClient(app) as client:
        chat = client.put(
            BENCH_TUNING_ROUTE,
            json={
                "attacker_model": AN_OFFERED_CHAT_MODEL,
                "temperature": 0.4,
                "reasoning_effort": None,
                "turns_per_episode": 8,
                "episodes_per_family": 2,
                "attempts_per_case": 10,
            },
        )
        reasoning = client.put(
            BENCH_TUNING_ROUTE,
            json={
                "attacker_model": A_MODEL_THAT_TAKES_NO_TEMPERATURE,
                "temperature": None,
                "reasoning_effort": None,
                "turns_per_episode": 8,
                "episodes_per_family": 2,
                "attempts_per_case": 10,
            },
        ).json()["tuning"]

    assert chat.status_code == 200
    offered = chat.json()["tuning"]
    assert offered["temperature_bounds"] == {
        "low": TEMPERATURE_RANGE[0],
        "high": TEMPERATURE_RANGE[1],
    }
    assert offered["temperature"] == 0.4
    assert "sampled at temperature 0.4" in offered["temperature_stated"]

    # And nothing offered where there is no setting, with the reason stated rather
    # than left to a null: a form drawing a slider here offers a control whose every
    # value the route refuses at the moment it is set.
    assert reasoning["temperature_bounds"] is None
    assert reasoning["temperature"] is None
    assert reasoning["temperature_stated"] == NO_TEMPERATURE_ACCEPTED
    # Two statements about one blank, and they are not the same string.
    assert reasoning["temperature_absent"] != reasoning["temperature_stated"]
    assert offered["temperature_absent"] == reasoning["temperature_absent"]


def test_every_offered_gpt_5_model_is_a_declared_row_and_not_the_presumption() -> None:
    """The ordered prefix table covers every GPT-5 identifier this console offers.

    The hazard the table's ordering exists for, checked on the list rather than
    assumed: `gpt-5-chat` precedes `openai/gpt-5` because a chat variant would
    otherwise be classified by the family prefix, and the same silence would classify
    a chat model added to the list below. Each of these was confirmed against
    OpenRouter's own model list before it was written down: the whole GPT-5 line this
    console offers takes a reasoning effort and no explicit temperature.

    Asserted as `declared`, not merely as the right answer: the presumption is the
    standard chat set, so a slug the table never matched would read as *takes a
    temperature* here and be refused by the provider at the first call of a run whose
    budget was already confirmed.
    """
    line = [
        identifier
        for identifier, _ in ATTACKER_MODELS
        if "openai/gpt-5" in identifier and "gpt-5-chat" not in identifier
    ]
    assert len(line) >= 11

    for identifier in line:
        reading = capabilities_of(identifier)
        assert reading.declared, identifier
        assert reading.accepts_reasoning_effort is True, identifier
        assert reading.accepts_temperature is False, identifier


def test_no_two_offered_models_are_recommended_by_the_same_sentence() -> None:
    """A model added with a filler line is a model nobody can choose between.

    The `decides` line is the whole reason the list is a list of pairs, so *distinct*
    is the property worth asserting rather than *non-empty*: a dropdown of fifteen
    slugs under two sentences repeated is a dropdown of two choices.
    """
    said = [decides for _, decides in ATTACKER_MODELS]
    assert len(said) == len(set(said))
    # And no line is a prefix of another, which is the near miss a copied entry makes.
    for one in said:
        for other in said:
            if one is other:
                continue
            assert not other.startswith(one[:40])


def test_a_reasoning_effort_a_model_has_no_setting_for_is_refused_when_it_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The temperature refusal in the other direction, and nothing is set.

    Told in front of the estimate rather than at the first episode: the capability is
    declared, so this costs no call. Refused rather than dropped, because a bench that
    quietly sent no effort would print the setting in a provenance block as though the
    request had carried it (ADR-0004, ADR-0025).
    """
    monkeypatch.setattr(
        "backend.api.app.attacker_completion_for",
        lambda spec, temperature=None, reasoning_effort=None: _attacking,
    )
    app = create_app(BenchConfig(cases=[]))
    with TestClient(app) as client:
        refused = client.put(
            BENCH_TUNING_ROUTE,
            json={
                "attacker_model": AN_OFFERED_CHAT_MODEL,
                "temperature": 0.0,
                "reasoning_effort": "high",
                "turns_per_episode": 8,
                "episodes_per_family": 2,
                "attempts_per_case": 10,
            },
        )
        unknown = client.put(
            BENCH_TUNING_ROUTE,
            json={
                "attacker_model": A_MODEL_THAT_TAKES_NO_TEMPERATURE,
                "temperature": None,
                "reasoning_effort": "minimal",
                "turns_per_episode": 8,
                "episodes_per_family": 2,
                "attempts_per_case": 10,
            },
        )
        after = client.get(BENCH_SETTINGS_ROUTE).json()["tuning"]

    assert refused.status_code == 422
    assert NO_REASONING_EFFORT_ACCEPTED in refused.json()["detail"]
    assert AN_OFFERED_CHAT_MODEL in refused.json()["detail"]

    # A level this bench does not offer is refused by name, and the refusal says
    # which three it holds: `minimal` is a real OpenAI level the o-series rejects.
    assert unknown.status_code == 422
    assert "not a reasoning effort this bench offers" in unknown.json()["detail"]

    # Neither request set anything: the bench is on the instrument it was on.
    assert after["reasoning_effort"] is None
    [chosen] = [model for model in after["attacker_models"] if model["chosen"]]
    assert chosen["identifier"] == UNDECLARED_MODEL


def test_the_block_says_a_run_below_the_declared_rule_is_not_a_gate_result() -> None:
    """`attempts_per_case` is the scored denominator and the block says so.

    The other five settings bound a layer that is scored on nothing; this one moves
    the number the Wilson interval, the band, monotonicity and the retirement rule
    are all defined against (ADR-0003). A screen offering it without that sentence
    would be offering a way to produce a rate that reads like a gate reading.
    """
    app = create_app(BenchConfig(cases=[]))
    with TestClient(app) as client:
        tuned = client.get(BENCH_SETTINGS_ROUTE).json()["tuning"]

    assert tuned["declared_attempts_per_case"] == DECLARED_RULE.attempts_per_case
    assert "not a gate result" in tuned["attempts_warning"]
    assert "n = 30" in tuned["attempts_warning"]


def test_the_stand_in_is_not_offered_but_the_current_setting_always_is(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Four options, and a fifth row only when the bench is on something else.

    The stand-in is reachable — the route admits it, so a bench can be put back on
    test equipment — and it is not a choice beside four models, because an operator
    who wanted no spend would not be on this screen. What may never happen is a form
    showing four options while the bench runs a fifth: it would draw the first as
    selected and be wrong about the instrument.
    """
    # The client is built when the model is set, which is the point — a slug the
    # provider refuses fails before the spend rather than mid-run. That needs a
    # credential, and a test that needed one would pass on a machine that has it and
    # fail in CI, which is a test about the environment.
    monkeypatch.setattr(
        "backend.api.app.attacker_completion_for",
        lambda spec, temperature=None, reasoning_effort=None: _attacking,
    )
    app = create_app(BenchConfig(cases=[]))
    with TestClient(app) as client:
        # This bench declared no attacker, so it is on the stand-in: the row is there
        # because it is what is *set*, and it is marked as the chosen one.
        offered = client.get(BENCH_SETTINGS_ROUTE).json()["tuning"]["attacker_models"]
        [chosen] = [model for model in offered if model["chosen"]]
        assert chosen["identifier"] == UNDECLARED_MODEL

        # Set one of the offered models, and the stand-in stops being offered.
        after = client.put(
            BENCH_TUNING_ROUTE,
            json={
                "attacker_model": ATTACKER_MODELS[0][0],
                "temperature": None,
                "turns_per_episode": 8,
                "episodes_per_family": 2,
                "attempts_per_case": 10,
            },
        ).json()["tuning"]["attacker_models"]

    assert [model["identifier"] for model in after] == [
        identifier for identifier, _ in ATTACKER_MODELS
    ]
    assert UNDECLARED_MODEL not in [model["identifier"] for model in after]


def _attacking(system_prompt: str, brief: str) -> ToolInvocation:
    """A stand-in attacker client. Never called: nothing here starts a run."""
    return ToolInvocation(tool=AttackerTool.CHECK_CANARY)


def test_a_family_switched_off_is_dropped_and_stated_as_not_run(
    leakage_case: Case, scope_creep_case: Case
) -> None:
    """Not run, and never a rate of zero.

    The gap is the point. A family whose cases are simply absent from a run is a
    reader guessing which of three answers it was — not applicable, not measurable, or
    not asked — and only the report can tell them, so the plan carries the reason.
    """
    app = create_app(BenchConfig(cases=[leakage_case, scope_creep_case]))
    with TestClient(app) as client:
        answered = client.put(
            BENCH_FAMILIES_ROUTE,
            json={"families": [str(leakage_case.family)], "elective": []},
        )
        bench = cast(BenchRuns, app.state.bench)

    assert answered.status_code == 200
    covered = answered.json()["tuning"]["families"]
    assert {row["family"]: row["covered"] for row in covered}[
        str(scope_creep_case.family)
    ] is False

    plan = plan_for(bench.config, note_planted=True)
    assert [case.id for case in plan.cases] == [leakage_case.id]
    assert plan.gaps[Family(scope_creep_case.family)] is DeclaredGap.FAMILY_SWITCHED_OFF
    assert "not run" in DeclaredGap.FAMILY_SWITCHED_OFF.stated()
    assert "not a family that held" in DeclaredGap.FAMILY_SWITCHED_OFF.stated()


def test_a_run_covering_no_family_is_refused() -> None:
    """A run covering nothing attacks nothing and still spends a registration probe.

    Refused rather than accepted as an expensive no-op: the estimate would charge for
    a probe per target and the report would carry six gaps and no reading.
    """
    app = create_app(BenchConfig(cases=[]))
    with TestClient(app) as client:
        answered = client.put(
            BENCH_FAMILIES_ROUTE, json={"families": [], "elective": []}
        )
        after = client.get(BENCH_SETTINGS_ROUTE).json()["tuning"]["families"]

    assert answered.status_code == 422
    assert "attacks nothing" in answered.json()["detail"]
    assert all(row["covered"] for row in after)


def test_a_family_this_bench_does_not_have_is_refused_by_name() -> None:
    """The six are a closed enum, and a typo is not a family switched off."""
    app = create_app(BenchConfig(cases=[]))
    with TestClient(app) as client:
        answered = client.put(
            BENCH_FAMILIES_ROUTE,
            json={"families": ["sql_injection"], "elective": []},
        )

    assert answered.status_code == 422
    assert "sql_injection" in answered.json()["detail"]
    assert "data_leakage" in answered.json()["detail"]


def a_base64_variant(base: Case) -> Case:
    """That case's base64 variant, built here because the library holds none.

    Eighteen records and every one of them `PLAIN`: admission is per variant and needs
    a person at a tty (ADR-0052 §5), so no variant has been admitted yet. The
    selection has to be correct over a library that holds one construction, and the
    only way to assert what it does over a library that holds two is to build the
    second here — which is a statement about this test and not about the bench: **the
    two-construction reading below is held by a test and is not measured today.**
    """
    return replace(
        base,
        id=f"{base.id}-base64",
        transform=Transform.BASE64,
        derived_from=base.id,
        payload=tuple(
            base64.b64encode(turn.encode("utf-8")).decode("ascii")
            for turn in base.payload
        ),
    )


def test_a_construction_switched_off_is_dropped_and_its_family_stated_as_not_run(
    leakage_case: Case,
) -> None:
    """Not run, and never a rate of zero — one level below the family switch.

    The family switch answers *was this family asked*; this answers *was this
    construction sent*. A family whose only remaining variants were switched off has
    no attempt behind it, so it is reported with a gap of its own rather than measured
    on a thinner library — and never as a rate over zero attempts, which is the
    reading `DeclaredGap` exists to make unavailable (ADR-0004, ADR-0058).

    The distinction from #72's *no new absence type*: that was a variant the **bench**
    never wrote, and a family measured by the variants that exist needs no reason
    beside it. This is one the **caller** turned off, and `DeclaredGap` is the surface
    for the caller's gaps.
    """
    variant = a_base64_variant(leakage_case)
    family = Family(leakage_case.family)

    # Both constructions selected: both cases are attempted and there is no gap.
    everything = BenchConfig(cases=[leakage_case, variant])
    whole = plan_for(everything, note_planted=True)
    assert [case.id for case in whole.cases] == [leakage_case.id, variant.id]
    assert whole.gaps == {}

    # The plain construction switched off: the variant is still attempted, so the
    # family is measured on what remains and acquires no gap. A ragged selection is
    # a narrower reading and not an absent one.
    encodings_only = replace(
        everything,
        selection=AttackSelection(
            layers=frozenset(AttackLayer),
            transforms=frozenset(Transform) - {Transform.PLAIN},
        ),
    )
    narrowed = plan_for(encodings_only, note_planted=True)
    assert [case.id for case in narrowed.cases] == [variant.id]
    assert narrowed.gaps == {}

    # And the family's last remaining construction switched off: no attempt, and the
    # gap says *not run* in its own words.
    nothing_left = replace(
        everything,
        selection=AttackSelection(
            layers=frozenset(AttackLayer),
            transforms=frozenset(Transform) - {Transform.PLAIN, Transform.BASE64},
        ),
    )
    emptied = plan_for(nothing_left, note_planted=True)
    assert emptied.cases == ()
    assert emptied.gaps[family] is DeclaredGap.TRANSFORMS_SWITCHED_OFF
    stated = DeclaredGap.TRANSFORMS_SWITCHED_OFF.stated()
    assert "not run" in stated
    assert "not measured rather than measured at zero" in stated
    # Two gaps and never one: a family nobody asked for and a family whose
    # constructions were all switched off are two different things the caller did.
    assert stated != DeclaredGap.FAMILY_SWITCHED_OFF.stated()


def test_fewer_constructions_is_a_cheaper_run_and_the_operator_sees_the_price(
    leakage_case: Case,
) -> None:
    """The estimate moves when the selection moves — the scored half of it.

    `test_budget.py` holds the adaptive half: a layer switched off is nothing on the
    wire. This is the other half and it is the one that moves a **denominator** —
    fewer constructions is a cheaper run and a narrower reading, which is the same
    sentence `families` already earns (ADR-0058). Priced through the composition the
    run actually uses, `plan_for` then `RunBudget.declare`, because that is where an
    operator's figure comes from: the plan drops the cases and the estimate charges
    for what is left, and a selection that narrowed the plan and not the estimate
    would put an operator's confirmation on a run nobody asked for (ADR-0007).
    """
    variant = a_base64_variant(leakage_case)
    whole = BenchConfig(cases=[leakage_case, variant])
    encodings_only = replace(
        whole,
        selection=AttackSelection(
            layers=frozenset(AttackLayer),
            transforms=frozenset(Transform) - {Transform.PLAIN},
        ),
    )

    def priced(config: BenchConfig) -> RunBudget:
        plan = plan_for(config, note_planted=True)
        return RunBudget.declare(
            cases=plan.cases,
            targets=[a_target("customer-agent")],
            rule=config.rule,
            adaptive=config.adaptive,
            selection=config.selection,
        )

    full = priced(whole)
    narrowed = priced(encodings_only)

    assert narrowed.estimate.scored.calls < full.estimate.scored.calls
    assert narrowed.scored_ceiling < full.scored_ceiling
    # One construction of two, and the registration probe is charged either way: the
    # figure is the arithmetic of what was sent and not a fraction of the library.
    assert full.estimate.scored.calls - narrowed.estimate.scored.calls == (
        leakage_case.turns * whole.rule.attempts_per_case
    )
    # And the adaptive figure is untouched, because no construction is scheduled by
    # that layer: the two switches move two different figures (ADR-0010).
    assert narrowed.estimate.adaptive == full.estimate.adaptive


def test_a_family_switched_off_keeps_its_own_gap_when_constructions_are_off_too(
    leakage_case: Case, scope_creep_case: Case
) -> None:
    """The coarser statement wins: a family nobody asked for was not asked.

    Both gaps could apply to one family at once, and the reason it reports the family
    switch is that the two are not equally true of it: a family switched off had no
    construction *offered* to it, so saying its constructions were switched off would
    be reporting the narrower reason for the wider fact.
    """
    config = BenchConfig(
        cases=[leakage_case, scope_creep_case],
        families=frozenset({Family(leakage_case.family)}),
        selection=AttackSelection(
            layers=frozenset(AttackLayer),
            transforms=frozenset(Transform) - {Transform.PLAIN},
        ),
    )
    plan = plan_for(config, note_planted=True)

    assert plan.cases == ()
    assert plan.gaps[Family(scope_creep_case.family)] is DeclaredGap.FAMILY_SWITCHED_OFF
    assert plan.gaps[Family(leakage_case.family)] is DeclaredGap.TRANSFORMS_SWITCHED_OFF


def test_the_console_reads_the_layers_and_the_constructions_it_may_select() -> None:
    """The reading the form is drawn from: three layers, seven constructions.

    Read off the closed enumerations rather than listed here, on `families`' terms one
    level up: a construction the bench performs and a screen does not offer is a
    reading no operator can ask for, and a screen offering one the route refuses is a
    control whose every value fails.

    Each row carries what it *is* in the bench's own words, so the screen states the
    consequence of switching one off rather than paraphrasing it.
    """
    app = create_app(BenchConfig(cases=[]))
    with TestClient(app) as client:
        tuning = client.get(BENCH_SETTINGS_ROUTE).json()["tuning"]

    assert [row["layer"] for row in tuning["layers"]] == [
        str(layer) for layer in AttackLayer
    ]
    assert all(row["selected"] for row in tuning["layers"])
    assert all(
        row["sends"] == AttackLayer(row["layer"]).stated() for row in tuning["layers"]
    )

    assert [row["transform"] for row in tuning["transforms"]] == [
        str(transform) for transform in Transform
    ]
    assert all(row["selected"] for row in tuning["transforms"])
    assert all(
        row["does"] == Transform(row["transform"]).stated()
        for row in tuning["transforms"]
    )
    # Which layer each construction is scheduled by, so a screen can group them under
    # the switch that turns them off — and never a second mapping of its own.
    assert {row["transform"]: row["layer"] for row in tuning["transforms"]} == {
        str(transform): str(layer_of(transform)) for transform in Transform
    }

    assert "not measured" in tuning["selection_off_statement"]
    assert tuning["selection_stated"] == EVERY_CONSTRUCTION.stated()

    # The adaptive layer's own two switches, which are what the box for it holds: the
    # layer names no construction, so before ADR-0096 the switch above them was the
    # whole of it. Only the line is selected on a bench nobody has narrowed — the
    # default is the schedule the reference agents were gated under (ADR-0023).
    assert [row["schedule"] for row in tuning["schedules"]] == [
        str(schedule) for schedule in BranchSchedule
    ]
    assert {row["schedule"]: row["selected"] for row in tuning["schedules"]} == {
        str(BranchSchedule.LINEAR): True,
        str(BranchSchedule.TREE): False,
    }
    assert all(
        row["does"] == BranchSchedule(row["schedule"]).stated()
        for row in tuning["schedules"]
    )
    # And the layer each is switched under, so the console groups them under the box
    # that turns them off without a mapping of its own — `transforms` above carries
    # the same field for the same reason.
    assert {row["layer"] for row in tuning["schedules"]} == {str(AttackLayer.ADAPTIVE)}
    assert "two episode sets" in tuning["schedules_statement"]
    assert "doubles" in tuning["schedules_statement"]


def test_the_layers_and_constructions_the_next_run_sends_can_be_set() -> None:
    """The third write under `/bench`, on ADR-0025's four conditions (ADR-0058).

    What it changed is legible in what the run produced: the cases are dropped from
    the plan, a family it empties is stated as *not run*, and the artefact carries the
    selection in provenance — which is condition 1 met by a printed field rather than
    by an absence, and is the reason this write is admissible at all.
    """
    app = create_app(BenchConfig(cases=[]))
    with TestClient(app) as client:
        answered = client.put(
            BENCH_SELECTION_ROUTE,
            json={
                "layers": [str(AttackLayer.SINGLE_TURN)],
                "transforms": [str(Transform.PLAIN), str(Transform.BASE64)],
            },
        )
        bench = cast(BenchRuns, app.state.bench)
        after = client.get(BENCH_SETTINGS_ROUTE).json()["tuning"]

    assert answered.status_code == 200
    assert bench.config.selection == AttackSelection(
        layers=frozenset({AttackLayer.SINGLE_TURN}),
        transforms=frozenset({Transform.PLAIN, Transform.BASE64}),
    )
    # The whole reading back, so the screen renders what the bench holds rather than
    # what it hoped it sent.
    selected = {row["layer"]: row["selected"] for row in after["layers"]}
    assert selected == {
        str(AttackLayer.SINGLE_TURN): True,
        str(AttackLayer.FIXED_MULTI_TURN): False,
        str(AttackLayer.ADAPTIVE): False,
    }
    assert after["selection_stated"] == bench.config.selection.stated()
    assert "not measured" in after["selection_stated"]


def test_the_schedules_the_adaptive_layer_attacks_under_can_be_set() -> None:
    """Both schedules selected, and the bench holds both (ADR-0096).

    The switch the adaptive box never had. What it changes is not a narrower run but a
    second episode set per family, so the assertion pairs the stored selection with the
    ceiling the next run would be priced against — a selection a screen can set and an
    estimate cannot see would be the doubling arriving after the approval.
    """
    app = create_app(BenchConfig(cases=[]))
    with TestClient(app) as client:
        answered = client.put(
            BENCH_SELECTION_ROUTE,
            json={
                "layers": [str(layer) for layer in AttackLayer],
                "transforms": [str(transform) for transform in Transform],
                "schedules": [str(schedule) for schedule in BranchSchedule],
            },
        )
        bench = cast(BenchRuns, app.state.bench)
        after = client.get(BENCH_SETTINGS_ROUTE).json()["tuning"]

    assert answered.status_code == 200
    assert bench.config.selection.schedules == frozenset(BranchSchedule)
    assert all(row["selected"] for row in after["schedules"])
    # And the provenance sentence says which, and that both is two episode sets rather
    # than one wider search: the selection is half the comparability claim. Its own
    # sentence and not a clause of `selection_stated`, which the verifier re-derives
    # from the layers and constructions beside it (ADR-0096 §8).
    assert "both schedules" in bench.config.selection.schedules_stated()
    assert "schedule" not in after["selection_stated"]
    assert (
        bench.config.adaptive.under(bench.config.selection.schedules).turn_ceiling
        == 2 * bench.config.adaptive.turn_ceiling
    )


def test_a_run_under_no_schedule_is_refused_and_the_field_may_be_omitted() -> None:
    """An empty list is a `422`; an absent one is the line.

    The one defaulted field on this request, and the asymmetry is deliberate: a caller
    written before the field existed asks for the run this bench has always made, and
    a caller who sends `[]` is asking for an adaptive layer that opens no episode —
    which is what switching the layer off already says, so it is refused with the
    type's own sentence rather than quietly stored (ADR-0096).
    """
    app = create_app(BenchConfig(cases=[]))
    with TestClient(app) as client:
        empty = client.put(
            BENCH_SELECTION_ROUTE,
            json={
                "layers": [str(layer) for layer in AttackLayer],
                "transforms": [str(Transform.PLAIN)],
                "schedules": [],
            },
        )
        unknown = client.put(
            BENCH_SELECTION_ROUTE,
            json={
                "layers": [str(layer) for layer in AttackLayer],
                "transforms": [str(Transform.PLAIN)],
                "schedules": ["crescendo"],
            },
        )
        omitted = client.put(
            BENCH_SELECTION_ROUTE,
            json={
                "layers": [str(layer) for layer in AttackLayer],
                "transforms": [str(Transform.PLAIN)],
            },
        )
        bench = cast(BenchRuns, app.state.bench)

    assert empty.status_code == 422
    assert "has to attack under a schedule" in empty.json()["detail"]
    assert unknown.status_code == 422
    assert "is not a schedule this bench attacks under" in unknown.json()["detail"]
    assert omitted.status_code == 200
    assert bench.config.selection.schedules == frozenset({BranchSchedule.LINEAR})


def test_a_selection_the_bench_has_no_member_for_is_refused_by_name() -> None:
    """Closed lists, resolved server-side before anything is stored.

    Condition 3 one level down: a name turned into a member first, so a bench cannot
    be put on a construction it has no function for and an unknown name is a refusal
    rather than a silently empty run.
    """
    app = create_app(BenchConfig(cases=[]))
    with TestClient(app) as client:
        unknown_transform = client.put(
            BENCH_SELECTION_ROUTE,
            json={"layers": [str(AttackLayer.SINGLE_TURN)], "transforms": ["dan"]},
        )
        unknown_layer = client.put(
            BENCH_SELECTION_ROUTE,
            json={"layers": ["tree_jailbreak"], "transforms": [str(Transform.PLAIN)]},
        )
        after = client.get(BENCH_SETTINGS_ROUTE).json()["tuning"]

    assert unknown_transform.status_code == 422
    assert "dan" in unknown_transform.json()["detail"]
    assert unknown_layer.status_code == 422
    assert "tree_jailbreak" in unknown_layer.json()["detail"]
    # And nothing was stored on the way to either refusal.
    assert all(row["selected"] for row in after["transforms"])


def test_a_run_that_would_score_nothing_is_refused_rather_than_widened() -> None:
    """Condition 4 where this route could have clamped.

    A bench that read *nothing* as *everything* would run a selection nobody chose,
    and one that accepted it would start a run whose every family reports *not run*
    while still spending a registration probe per target.
    """
    app = create_app(BenchConfig(cases=[]))
    with TestClient(app) as client:
        nothing = client.put(
            BENCH_SELECTION_ROUTE, json={"layers": [], "transforms": []}
        )
        adaptive_only = client.put(
            BENCH_SELECTION_ROUTE,
            json={
                "layers": [str(AttackLayer.ADAPTIVE)],
                "transforms": [str(Transform.PLAIN)],
            },
        )
        after = client.get(BENCH_SETTINGS_ROUTE).json()["tuning"]

    assert nothing.status_code == 422
    assert "scores nothing" in nothing.json()["detail"]
    assert adaptive_only.status_code == 422
    assert all(row["selected"] for row in after["layers"])


def test_every_family_switch_carries_the_labels_its_row_prints() -> None:
    """The nine rows the console draws as one list, each with what it is read onto.

    The screen prints a family's published claims and the articles it bears beside the
    tick that requests it, and it reads them from here rather than from a table of its
    own: a second copy of a declared label in TypeScript is the drift `labels.py`
    exists to prevent, and ADR-0036's edition tag is exactly the thing a hand copy
    loses (ADR-0091).

    **Two lists on the wire and one list on the screen.** The tier is presented
    undifferentiated (ADR-0091) and is still carried in `elective_families`, because
    `PUT /bench/settings/families` takes the two as one statement and the six are the
    denominator the gate is decided over (ADR-0015, ADR-0035).
    """
    body = a_client(configured(models=DECLARED)).get(BENCH_SETTINGS_ROUTE).json()

    # The two are walked separately and never zipped into one loop, which mypy insists
    # on: `LABELS` and `ELECTIVE_LABELS` are keyed on two enumerations and there is no
    # index type accepting both. The boundary this test relies on refuses the
    # convenience of reading it in one pass, which is the boundary working.
    six = body["tuning"]["families"]
    assert [row["family"] for row in six] == [str(f) for f in Family]
    for row, family in zip(six, Family, strict=True):
        label = label_for(family)
        assert row["labels"]["agentic"] == list(label.agentic)
        assert row["labels"]["llm"] == list(label.llm)
        assert row["labels"]["articles"] == [a.value for a in label.articles]

    tier = body["tuning"]["elective_families"]
    assert [row["family"] for row in tier] == [str(f) for f in ElectiveFamily]
    for row, elective in zip(tier, ElectiveFamily, strict=True):
        held = elective_label_for(elective)
        assert row["labels"]["agentic"] == list(held.agentic)
        assert row["labels"]["llm"] == list(held.llm)
        assert row["labels"]["articles"] == [a.value for a in held.articles]

    # Every one of the nine bears an article, so no row prints an empty legal column
    # (`FamilyLabel.__post_init__`, ADR-0040) — and a family claiming nothing on one of
    # the two published lists says so with an empty list rather than being absent.
    every = six + tier
    assert len(every) == 9
    assert all(row["labels"]["articles"] for row in every)
    assert any(not row["labels"]["agentic"] for row in every)
    assert any(not row["labels"]["llm"] for row in every)

    # And no figure arrives with them. A label is what a family is read onto; how well
    # this bench discriminates on one is a claim about the bench and is in the gate
    # run's own document (ADR-0018).
    for row in every:
        assert set(row["labels"]) == {"agentic", "llm", "articles"}
