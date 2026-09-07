"""An elective family, requested for a normal run, measured, and on the report.

[ADR-0088](../../docs/adr/0088-an-elective-familys-rate-against-a-target-is-a-fact-about-that-target.md)
separates two figures that shared one prohibition: the bench's own `D` on the tier,
which stays in the gate run's document (ADR-0018), and the failure rate an elective
family measured **against the operator's own agent**, which is a fact about that
agent and belongs in its report.

Most of what this file asserts is therefore a pair: the rate arrived, and the `D`
did not. The two halves are asserted together on purpose — a test that only checked
the arrival would pass on the shape ADR-0035 rejected by name, and one that only
checked the absence would pass on the shape that existed before this ticket.

`test_elective.py` keeps the prohibitions that did **not** move, and in particular
the structural assertion that `FamilyEntry.family` still names `Family` alone. The
parallel section this file exercises is what makes that assertion survivable.
"""

import json
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.api.app import BENCH_FAMILIES_ROUTE, create_app
from backend.api.run_config import BenchConfig, plan_for
from backend.bench.admission import admitted_elective, admitted_library
from backend.bench.assembler import (
    AdaptiveSection,
    DeclaredSection,
    ElectiveEntry,
    MeasuredSection,
    TargetResult,
    assemble,
)
from backend.bench.calibration import TargetRun
from backend.bench.contract import Transcript
from backend.bench.elective import ElectiveSelection
from backend.bench.evaluator import Verdict
from backend.bench.library import (
    ElectiveFamily,
    Family,
    LibraryVersion,
    Transform,
    VerdictClass,
)
from backend.bench.measurability import NotMeasurable
from backend.bench.payload import (
    ARTEFACT_VERSION,
    Provenance,
    TargetPayload,
    canonical,
    document,
)
from backend.bench.registration import AttestationRecord, Registration
from backend.bench.rendering import render
from backend.bench.rule import DECLARED_RULE
from backend.bench.scorer import (
    DECLARED_BAND_CUTS,
    VariantBreakdown,
    VariantCounts,
    band_for,
)
from backend.bench.selection import EVERY_CONSTRUCTION
from backend.bench.signing import generate, public_key, public_pem, publish_signed
from backend.bench.verification import (
    NotThisArtefact,
    Published,
    ReDerivation,
    ReDerivationOutcome,
    checked,
)
from backend.graph.budget import Layer
from backend.graph.runstate import Attempt
from backend.tests.conftest import BENCH_ATTESTATION, CASES_DIR, a_target
from backend.tests.test_payload import ATTESTED, MODELS
from scripts.verify import main

# --- The selection is a declared input of a normal run -----------------------


def test_a_bench_that_requested_nothing_plans_no_elective_case(
    both_tiers: BenchConfig,
) -> None:
    # The default, and it is every run made before this ticket: the tier's cases are
    # loaded and none of them is planned, because the selection is what asks for
    # them (ADR-0035 §5).
    plan = plan_for(both_tiers, note_planted=True)

    assert plan.cases
    assert not [case for case in plan.cases if isinstance(case.family, ElectiveFamily)]


def test_a_requested_elective_family_reaches_the_plan_and_the_others_do_not(
    both_tiers: BenchConfig,
) -> None:
    # The lever spec story 12 asked for, arriving at the one place a run's cost and
    # a run's coverage are both decided.
    asked = ElectiveFamily.PII_LEAKAGE
    config = _requesting(both_tiers, asked)

    plan = plan_for(config, note_planted=True)

    elective = {
        case.family for case in plan.cases if isinstance(case.family, ElectiveFamily)
    }
    assert elective == {asked}
    # And the six are untouched by the request: a lever on the tier is not a lever on
    # the denominator ADR-0015 fixed.
    assert {case.family for case in plan.cases if isinstance(case.family, Family)} == {
        case.family for case in plan_for(both_tiers, note_planted=True).cases
    }


def test_an_unrequested_elective_family_is_no_declared_gap(
    both_tiers: BenchConfig,
) -> None:
    # `RunPlan.gaps` is keyed on the six and says which of the *mandatory* families
    # this run's caller declared away (ADR-0075). An elective family nobody asked for
    # is the fifth kind of nothing and not the fourth, so it must not appear here —
    # a family in both would be two answers to why nothing was attempted.
    plan = plan_for(both_tiers, note_planted=True)

    assert all(isinstance(family, Family) for family in plan.gaps)


# --- The artefact's shape moved, and says so ---------------------------------


def test_the_artefact_version_moved_because_the_shape_did() -> None:
    # ADR-0088 §7. A verifier reading version 1 would re-derive nothing at all for
    # the tier's block and report the document verified, which is the one failure the
    # verifier exists to make impossible.
    assert ARTEFACT_VERSION == 2


def test_the_measured_section_carries_the_tier_beside_the_six_and_not_among_them(
    entry: ElectiveEntry,
) -> None:
    section = MeasuredSection(elective=(entry,))

    assert section.elective == (entry,)
    # Beside, and in neither: a consumer iterating the six's figures never meets one.
    assert section.deterministic == ()
    assert section.judged == ()


def test_an_elective_entry_carries_no_discrimination_no_label_no_reliability(
    entry: ElectiveEntry,
) -> None:
    # ADR-0088 §2, and it is the half of this ticket that ADR-0018 still governs.
    # Asserted over the attributes rather than over a rendered document, because the
    # prohibition is carried by the type: a contributor who wanted the tier's `D` in
    # a report would have to add a field here.
    for absent in ("discrimination", "reliability", "label", "coverage"):
        assert not hasattr(entry, absent), (
            f"ElectiveEntry.{absent} exists, so this bench can print a claim about "
            "itself beside a claim about somebody's agent (ADR-0018, ADR-0088 §2)"
        )


def test_an_elective_entry_refuses_a_judged_verdict_class(
    entry: ElectiveEntry,
) -> None:
    # Every family in the tier reaches its verdict by canary check, deliberately, so
    # that `minimum_fit_families` is untouched and no elective reading can be unfit
    # (ADR-0035, "Why three runs" / no fitness stop). A judged elective family is a
    # decision needing its own ADR, and this is where it would be noticed.
    with pytest.raises(ValueError, match="judged"):
        ElectiveEntry(
            family=entry.family,
            rate=entry.rate,
            verdict_class=VerdictClass.JUDGED,
            band=entry.band,
            variants=entry.variants,
        )


def test_a_requested_family_that_could_not_be_measured_prints_its_reason(
    entry: ElectiveEntry,
) -> None:
    # ADR-0088 §4. Memory poisoning against a target that carries no session state is
    # the case this exists for: the request names it, and without this block the
    # figures would simply not hold it and a reader would be guessing which of the
    # absences it was.
    section = MeasuredSection(
        elective_not_measurable={
            ElectiveFamily.MEMORY_POISONING: NotMeasurable.NO_SESSION_RETENTION
        }
    )

    assert section.elective_not_measurable[ElectiveFamily.MEMORY_POISONING]


def test_a_family_cannot_be_measured_and_unmeasurable_at_once(
    entry: ElectiveEntry,
) -> None:
    with pytest.raises(ValueError, match="not measurable"):
        MeasuredSection(
            elective=(entry,),
            elective_not_measurable={entry.family: NotMeasurable.NO_SESSION_RETENTION},
        )


# --- Fixtures ----------------------------------------------------------------


@pytest.fixture
def both_tiers() -> BenchConfig:
    """A bench holding the six's library and the whole of the tier's, requesting none.

    Both are loaded at boot and the *selection* is what asks for them, which is what
    keeps a run that requested nothing byte-identical to the run it was before this
    ticket: `plan_for` plans the six and none of the tier, so `LibraryVersion.of` over
    the plan is the version it always was.
    """
    return BenchConfig(
        cases=admitted_library(CASES_DIR),
        elective_cases=admitted_elective(CASES_DIR, list(ElectiveFamily)),
    )


@pytest.fixture
def entry() -> ElectiveEntry:
    counts = VariantBreakdown(
        (VariantCounts(transform=Transform.PLAIN, successes=3, attempts=10),)
    )
    rate = counts.pooled()
    return ElectiveEntry(
        family=ElectiveFamily.PII_LEAKAGE,
        rate=rate,
        verdict_class=VerdictClass.DETERMINISTIC,
        # Read against the declared cut points rather than named, so the fixture is a
        # document a recipient's own re-derivation agrees with: a band chosen by hand
        # would make every check below a check on this file's arithmetic.
        band=band_for(rate, DECLARED_BAND_CUTS),
        variants=counts,
    )


def _requesting(config: BenchConfig, *families: ElectiveFamily) -> BenchConfig:
    return replace(config, elective=ElectiveSelection(requested=families))


# --- The figures reach the signed document ------------------------------------


def test_a_measured_elective_family_carries_its_rate_interval_and_band(
    entry: ElectiveEntry,
) -> None:
    # The whole of what #171 asked for, at the seam where the bytes are decided.
    body = document(_payload_carrying(entry))

    [published] = body["measured"]["elective"]
    assert published["family"] == entry.family.value
    assert (published["successes"], published["attempts"]) == (3, 10)
    assert published["rate"] == pytest.approx(0.3)
    assert published["interval"]["lower"] < published["rate"]
    assert published["interval"]["upper"] > published["rate"]
    assert published["band"] == entry.band.value
    assert published["band_stated"]
    # And the counts it was pooled from, so a recipient takes the figure apart the
    # way they take one of the six's apart (ADR-0055).
    assert [one["transform"] for one in published["variants"]] == [
        Transform.PLAIN.value
    ]


def test_the_tiers_discrimination_reaches_no_key_of_the_document(
    entry: ElectiveEntry,
) -> None:
    # The half of the old prohibition that stands (ADR-0018, ADR-0088 §2). Asserted
    # over the serialised block rather than over the type alone, because this is what
    # travels: `memory_poisoning`'s D = 0.33 is a claim about this bench and it is
    # printed in the gate run's own document.
    [published] = document(_payload_carrying(entry))["measured"]["elective"]

    for forbidden in ("discrimination", "reliability", "label", "coverage"):
        assert forbidden not in published, (
            f"the elective block carries {forbidden!r}, which is a claim about the "
            "bench travelling in a document about somebody's agent (ADR-0018)"
        )


def test_the_elective_figures_are_in_neither_of_the_six_s_lists(
    entry: ElectiveEntry,
) -> None:
    # ADR-0088 §6. The declared bar reads `deterministic` and `judged`, so a run that
    # requested the tier may not turn a pipeline red or green on a family nobody's
    # bar names (ADR-0067).
    measured = document(_payload_carrying(entry))["measured"]

    named = {
        one["family"]
        for key in ("deterministic", "judged", "withheld", "not_measurable", "not_run")
        for one in measured[key]
    }
    assert entry.family.value not in named


def test_the_rendered_document_prints_the_tiers_figures_and_not_its_discrimination(
    entry: ElectiveEntry,
) -> None:
    markdown = render(_payload_carrying(entry))

    assert "pii_leakage" in markdown
    assert "3 of 10 attempts succeeded" in markdown
    # And the sentence the old shape printed — that the tier carries no figure here —
    # is not printed over a family that has one.
    assert "discrimination" not in markdown.lower().split("pii_leakage", 1)[1]


def test_a_verifier_re_derives_the_tiers_figures_from_the_counts_beside_them(
    entry: ElectiveEntry,
) -> None:
    # A block a verifier did not read would be figures in a signed document nobody
    # can check, which is the state ADR-0088 §7 moved the version to prevent. The
    # honest reading and the doctored one are asserted together: a check that only
    # ran over the honest document would pass on a verifier that read nothing.
    body = document(_payload_carrying(entry))
    honest = _arithmetic(body)
    assert honest.held

    doctored = json.loads(json.dumps(body))
    doctored["measured"]["elective"][0]["rate"] = 0.01

    reading = _arithmetic(doctored)
    assert not reading.held
    assert "elective" in reading.stated()


def test_a_verifier_that_reads_an_earlier_version_refuses_this_shape(
    entry: ElectiveEntry,
) -> None:
    # ADR-0088 §7 in the one place it is a behaviour rather than a number: the
    # recipient is told to get a verifier that reads this shape, and is never handed
    # a clean reading over half a document.
    stale = {**document(_payload_carrying(entry)), "artefact_version": 1}

    with pytest.raises(NotThisArtefact, match="version"):
        _arithmetic(stale)


# --- Helpers over the artefact -----------------------------------------------


def _payload_carrying(entry: ElectiveEntry) -> TargetPayload:
    """One payload whose measured section holds that elective entry and nothing else.

    Deliberately no family of the six: what is under test is the tier's own block, and
    a document holding both would let a check pass on a figure the six put there.
    """
    return TargetPayload(
        result=TargetResult(
            target_name="a target",
            measured=MeasuredSection(elective=(entry,)),
            declared=DeclaredSection(),
            adaptive=AdaptiveSection(),
            elective=ElectiveSelection(requested=(entry.family,)),
        ),
        provenance=Provenance(
            attestation=ATTESTED,
            models=MODELS,
            library=LibraryVersion(cases=3, digest="90a8ebcc3d0c"),
            calls_spent={Layer.SCORED: 30, Layer.ADAPTIVE: 0},
            selection=EVERY_CONSTRUCTION,
        ),
    )


def _arithmetic(body: Mapping[str, Any]) -> ReDerivation:
    """The re-derivation a recipient gets over those bytes, through their own code.

    `verification.checked` and never a second implementation, which is the whole
    point of the check: a verifier written for this test would agree with itself.
    """
    return checked(
        Published(
            payload=canonical(body).encode("utf-8"),
            rendering=None,
            signature=None,
        ),
        public_key(),
        source="this payload",
    ).arithmetic


# --- End to end, from the run's own attempts ---------------------------------


def test_a_run_that_measured_an_elective_family_reports_it(
    an_elective_run: TargetRun,
) -> None:
    # The chain, whole: attempts in an elective family, counted by the one walk that
    # counts the six's, pooled from the breakdown, into an entry, into the section.
    result = assemble(an_elective_run, cases=())

    [published] = result.measured.elective
    assert published.family is ElectiveFamily.PII_LEAKAGE
    assert (published.rate.successes, published.rate.attempts) == (1, 2)
    assert published.variants.accounts_for(published.rate)
    # And none of it reached the six's lists, which is the split ADR-0035 §2 built
    # and this ticket relies on.
    assert result.measured.deterministic == ()
    assert result.measured.judged == ()


def test_the_tiers_rate_is_the_pooled_breakdown_and_not_a_second_count(
    an_elective_run: TargetRun,
) -> None:
    # Two independent walks over the same attempts would be two figures that could
    # drift, and `ElectiveEntry` would then refuse a breakdown the run had already
    # built (ADR-0055). Asserted here rather than assumed, because the refusal is
    # what a caller would meet and this is the property behind it.
    for family, rate in an_elective_run.elective_rates.items():
        assert an_elective_run.elective_variant_counts[family].accounts_for(rate)


@pytest.fixture
def an_elective_run() -> TargetRun:
    """One target run holding two attempts in one elective family and nothing else.

    Constructed rather than measured, on `test_elective.py`'s terms: what a target
    does with a payload is a question about that target, and what is under test here
    is which container the counts are allowed into.
    """
    target = a_target("a target")
    probe = Transcript(
        url=target.url, sent={}, status_code=200, received={"reply": "nonce"}
    )
    return TargetRun(
        target=target,
        registration=Registration(
            target=target,
            nonce="nonce",
            echoed=True,
            probe=probe,
            attestation=AttestationRecord.of(BENCH_ATTESTATION, target),
        ),
        attempts=tuple(
            Attempt(
                case_id="pii-leakage-001",
                family=ElectiveFamily.PII_LEAKAGE,
                target_name=target.name,
                index=index,
                transcripts=(probe,),
                verdict=(Verdict.SUCCEEDED if index == 0 else Verdict.RESISTED),
                verdict_class=VerdictClass.DETERMINISTIC,
                transform=Transform.PLAIN,
            )
            for index in range(2)
        ),
        rule=DECLARED_RULE,
    )


# --- The console lever --------------------------------------------------------


def test_the_families_route_takes_an_elective_name_beside_the_six(
    both_tiers: BenchConfig,
) -> None:
    # Step 5 of #171, and the first door the tier has ever had at a target run.
    client = TestClient(create_app(both_tiers))

    response = client.put(
        BENCH_FAMILIES_ROUTE,
        json={
            "families": [str(family) for family in Family],
            "elective": [str(ElectiveFamily.PII_LEAKAGE)],
        },
    )

    assert response.status_code == 200
    rows = response.json()["tuning"]["elective_families"]
    assert {one["family"]: one["covered"] for one in rows} == {
        str(ElectiveFamily.MEMORY_POISONING): False,
        str(ElectiveFamily.DIRECT_PROMPT_INJECTION): False,
        str(ElectiveFamily.PII_LEAKAGE): True,
    }
    # And the tick means something: the next run's plan holds that family's cases.
    planned = plan_for(client.app.state.bench.config, note_planted=True)  # type: ignore[attr-defined]
    assert ElectiveFamily.PII_LEAKAGE in {case.family for case in planned.cases}


def test_a_name_from_the_wrong_tier_is_refused_by_the_list_it_was_sent_in(
    both_tiers: BenchConfig,
) -> None:
    # Two closed sets and two lists, so a name in the wrong one is a refusal rather
    # than a family quietly landing in the other tier's counts (ADR-0035 §1).
    client = TestClient(create_app(both_tiers))

    wrong_tier = client.put(
        BENCH_FAMILIES_ROUTE,
        json={"families": [str(Family.DATA_LEAKAGE)], "elective": ["scope_creep"]},
    )
    assert wrong_tier.status_code == 422
    assert "elective family" in wrong_tier.json()["detail"]

    other_way = client.put(
        BENCH_FAMILIES_ROUTE,
        json={"families": ["pii_leakage"], "elective": []},
    )
    assert other_way.status_code == 422
    assert "The six are" in other_way.json()["detail"]


def test_an_empty_tier_is_a_statement_and_an_omitted_one_is_a_refusal(
    both_tiers: BenchConfig,
) -> None:
    # Two different things, and the route keeps them apart. An **empty** list is the
    # one empty list this bench accepts — *the six and only the six*, which is every
    # run made before #171. An **omitted** field is a caller silently clearing what the
    # bench is holding, which is a state drop nobody wrote down, so it is a 422 naming
    # the field. Asserted after a request that turned one on, because what is under
    # test is that the `PUT` is the whole statement.
    client = TestClient(create_app(both_tiers))
    six = [str(family) for family in Family]
    client.put(
        BENCH_FAMILIES_ROUTE,
        json={"families": six, "elective": [str(ElectiveFamily.PII_LEAKAGE)]},
    )

    cleared = client.put(BENCH_FAMILIES_ROUTE, json={"families": six, "elective": []})

    assert cleared.status_code == 200
    assert not [
        one for one in cleared.json()["tuning"]["elective_families"] if one["covered"]
    ]

    client.put(
        BENCH_FAMILIES_ROUTE,
        json={"families": six, "elective": [str(ElectiveFamily.PII_LEAKAGE)]},
    )

    omitted = client.put(BENCH_FAMILIES_ROUTE, json={"families": six})

    assert omitted.status_code == 422
    # And the selection the bench was holding is untouched: a refused request changed
    # nothing, which is what makes the refusal better than the default it replaced.
    held = client.get("/bench/settings").json()["tuning"]["elective_families"]
    assert [one["family"] for one in held if one["covered"]] == [
        str(ElectiveFamily.PII_LEAKAGE)
    ]


def test_the_offline_verifier_passes_over_a_document_carrying_an_elective_family(
    entry: ElectiveEntry, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The recipient's own script, over a directory holding a tier's figures.

    The `_arithmetic` tests above go through `verification.checked`; this one goes
    through `scripts/verify` and the three files, because what #171 promised is that
    the *verifier a recipient runs* passes over such a document — and a check that
    only ever ran in-process would not have established that the published entry
    point reads it.
    """
    key = generate()
    publish_signed(_payload_carrying(entry), tmp_path, key)
    pinned = tmp_path / "pinned.pub"
    pinned.write_bytes(public_pem(key.public_key()))

    code = main([str(tmp_path), "--pubkey", str(pinned)])

    printed = capsys.readouterr().out
    assert code == 0, printed
    assert ReDerivationOutcome.AGREES.value in printed


def test_no_discovery_count_prints_against_an_elective_family(
    entry: ElectiveEntry,
) -> None:
    """A row that could only ever say *none* says nothing, so it is not drawn.

    `adaptive/layer.objectives_for` picks its objectives over the six, so no episode is
    ever opened in the tier — a discovery line here could print only its own empty
    answer, and a reader would take that for the search having looked and found
    nothing (ADR-0056, ADR-0010).
    """
    markdown = render(_payload_carrying(entry))
    tier = markdown.split("### The elective families this run asked for", 1)[1]

    assert "3 of 10 attempts succeeded" in tier
    assert "adaptive attacker found here" not in tier
