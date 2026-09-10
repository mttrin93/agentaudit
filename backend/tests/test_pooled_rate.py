"""One scored rate over every variant a family holds, and the counts to take it apart.

A family's rate is successes over attempts, and every variant of a family measures
the same failure against the same criterion — so an attempt that succeeded through a
base64 wrapper and one that succeeded through a four-rung script are both attempts
that succeeded, and the family's rate adds them
([ADR-0055](../../docs/adr/0055-a-family-pools-its-variants-and-publishes-the-counts.md)).
What pooling costs is that the rate depends on the variant mix, and this file holds
the bench to *publishing* that cost rather than hiding it: the counts per variant
travel beside the rate, through the run, the entry, the signed payload, the verifier
and the rendered document.

Four hazards, and each test below is one of them.

**The mean of the per-variant rates is the wrong answer that looks right.** One plain
case at 3 of 10 and one variant at 7 of 10 is 10 of 20, and the mean of 0.30 and 0.70
is the same 0.50 by coincidence at equal denominators. The tests use unequal ones so
the two answers differ.

**A count that does not add up must be refused rather than rounded.** A family whose
`attempts` is not the sum of its variants' is a document whose rate is over a
denominator nothing in it accounts for, and `verification.py` says so.

**No adaptive result may reach any of it** (ADR-0010). An `AdaptiveEpisode` is not an
`Attempt`, a discovery count is not a summand, and there is no field here one could
arrive in — #77 adds the discovery count to the family *view* and this file's last
test is what stops it landing in the arithmetic.

**Today's library holds no variant.** Admission needs a person at a tty (ADR-0052
§5), so every record in `corpus`/`cases` is `PLAIN` and the pooled rate over the live
library is a one-entry breakdown. That is measured; the multi-variant arithmetic is
held by the constructed libraries below and is stated as such in ADR-0055.
"""

from dataclasses import replace
from typing import Any

import pytest

from backend.bench.assembler import FamilyEntry, assemble
from backend.bench.calibration import TargetRun, run_calibration
from backend.bench.contract import Transcript
from backend.bench.evaluator import Verdict
from backend.bench.gate import stated_outcome
from backend.bench.library import Case, DiscoveredBy, Family, Transform, VerdictClass
from backend.bench.payload import TargetPayload, document
from backend.bench.registration import AttestationRecord, Registration
from backend.bench.rendering import render
from backend.bench.retirement import live_library
from backend.bench.rule import DECLARED_RULE
from backend.bench.scorer import (
    IN_TRANSFORM_ORDER,
    FamilyRates,
    FamilyVariants,
    VariantBreakdown,
    VariantCounts,
    band_for,
    failure_rate,
    score_family,
)
from backend.bench.verification import ReDerivationOutcome, _re_derive
from backend.graph.runstate import Attempt
from backend.tests.conftest import (
    BENCH_ATTESTATION,
    CONFIRMING,
    a_target,
    reference_target,
    retired_case,
)
from backend.tests.test_payload import a_payload


def a_variant(base: Case, transform: Transform) -> Case:
    """A variant of `base`: its own id, its own payload, one transform.

    Built here rather than loaded, because no variant is admitted into the library
    yet — admission needs a person at a tty (ADR-0052 §5) — and the arithmetic has
    to be demonstrably right before one arrives.
    """
    return replace(
        base,
        id=f"{base.id}-{transform.value}",
        transform=transform,
        derived_from=base.id,
    )


def one_target_run(cases: list[Case]) -> TargetRun:
    """These cases against the trivial reference agent, through the entry point."""
    with reference_target(model="stub:obedient", name="trivial") as reference:
        result = run_calibration(
            cases=cases,
            targets=[reference.target],
            attestation=BENCH_ATTESTATION,
            plant_nonce=reference.plant_nonce,
            approve=CONFIRMING,
            discovered_by=DiscoveredBy.ADAPTIVE,
        )
    [target_run] = result.target_runs
    return target_run


def test_the_transform_order_is_the_enumerations_and_plain_is_first() -> None:
    # Not the member values' alphabetical order, which would print a family's
    # encodings above the payload they are encodings of: `base64` < `plain`.
    assert IN_TRANSFORM_ORDER[0] is Transform.PLAIN
    assert IN_TRANSFORM_ORDER != tuple(sorted(Transform))


def test_a_breakdown_that_does_not_account_for_its_rate_says_so() -> None:
    # The tripwire the two types carrying a pooled rate assert on, and the verifier
    # re-derives from the artefact.
    breakdown = VariantBreakdown(
        (
            VariantCounts(Transform.PLAIN, successes=3, attempts=30),
            VariantCounts(Transform.BASE64, successes=7, attempts=10),
        )
    )

    assert breakdown.accounts_for(breakdown.pooled())
    assert not breakdown.accounts_for(replace(breakdown.pooled(), attempts=39))
    assert breakdown.mix_stated() == "plain 3/30, base64 7/10"


def test_a_transform_that_was_never_sent_is_absent_and_not_present_at_zero() -> None:
    with pytest.raises(ValueError, match="absent from the breakdown"):
        VariantCounts(Transform.ROT13, successes=0, attempts=0)


def test_a_transform_appearing_twice_in_one_breakdown_is_refused() -> None:
    with pytest.raises(ValueError, match="appears twice"):
        VariantBreakdown(
            (
                VariantCounts(Transform.PLAIN, successes=1, attempts=10),
                VariantCounts(Transform.PLAIN, successes=2, attempts=10),
            )
        )


def test_a_run_pools_a_familys_variants_and_reports_the_counts_per_variant(
    leakage_case: Case,
) -> None:
    # The run seam. Three cases of one family — the base and two variants of it — is
    # one rate over thirty attempts, and three entries of ten in the breakdown. The
    # denominator grew because the library did, which is the direction #66's argument
    # makes safe, and nothing multiplied by three to get there.
    cases = [
        leakage_case,
        a_variant(leakage_case, Transform.BASE64),
        a_variant(leakage_case, Transform.ROT13),
    ]

    target_run = one_target_run(cases)

    rate = target_run.rates[Family.DATA_LEAKAGE]
    assert rate.attempts == 3 * DECLARED_RULE.attempts_per_case
    breakdown = target_run.variant_counts[Family.DATA_LEAKAGE]
    assert breakdown.accounts_for(rate)
    assert [(count.transform, count.attempts) for count in breakdown] == [
        (Transform.PLAIN, 10),
        (Transform.BASE64, 10),
        (Transform.ROT13, 10),
    ]
    # And the trivial agent leaked on every one of them, so the pooled successes are
    # the sum of the per-variant successes rather than any average of their rates.
    assert rate.successes == sum(count.successes for count in breakdown)
    assert rate.successes == 30


def test_an_attempt_carries_the_transform_of_the_record_that_made_it(
    leakage_case: Case,
) -> None:
    # Read off the record when the attempt is made and never joined back to the
    # library afterwards, for the reason `family` and `verdict_class` are: an attempt
    # attributed to the wrong variant is a count in the wrong entry, and no reader of
    # the artefact could see it.
    variant = a_variant(leakage_case, Transform.LEETSPEAK)

    target_run = one_target_run([leakage_case, variant])

    by_case = {attempt.case_id: attempt.transform for attempt in target_run.attempts}
    assert by_case == {
        leakage_case.id: Transform.PLAIN,
        variant.id: Transform.LEETSPEAK,
    }


def test_the_live_library_is_plain_and_its_breakdown_is_one_entry(
    leakage_case: Case,
) -> None:
    # What is measured today, said out loud: no variant is admitted, so every
    # breakdown a real run produces holds exactly one entry and the pooled rate is
    # the plain rate. The multi-variant arithmetic above is held by a test and not by
    # a measurement (ADR-0055).
    target_run = one_target_run([leakage_case])

    [only] = list(target_run.variant_counts[Family.DATA_LEAKAGE])
    assert only.transform is Transform.PLAIN
    assert only.attempts == DECLARED_RULE.attempts_per_case


def test_no_breakdown_reaches_across_two_families(
    leakage_case: Case, scope_creep_case: Case
) -> None:
    # `TargetRun.rates` is per family and never pooled across them (ADR-0005), and
    # the breakdown is one level below a rate — so it is per family too, and there is
    # no container here holding the two families' variants together.
    target_run = one_target_run([leakage_case, scope_creep_case])

    counts = target_run.variant_counts
    assert set(counts) == {Family.DATA_LEAKAGE, Family.SCOPE_CREEP}
    assert all(breakdown.attempts == 10 for breakdown in counts.values())


def test_the_breakdown_of_a_family_with_no_attempts_is_absent(
    leakage_case: Case,
) -> None:
    # A family the run never touched has no rate and no breakdown, on the same terms:
    # no attempts is not a failure rate of zero, and an empty breakdown printed for
    # it would be a denominator nobody measured.
    target_run = one_target_run([leakage_case])

    assert Family.SCOPE_CREEP not in target_run.variant_counts
    assert set(target_run.variant_counts) == set(target_run.rates)


def test_a_family_entry_carries_the_breakdown_of_the_rate_beside_it(
    leakage_case: Case,
) -> None:
    # The artefact seam. `assemble` builds the entry from the attempts, so the
    # breakdown on it is the breakdown of the rate on it — and the type asserts that
    # rather than trusting the caller.
    cases = [leakage_case, a_variant(leakage_case, Transform.BASE64)]
    target_run = one_target_run(cases)

    result = assemble(target_run, cases)

    [entry] = [
        entry
        for entry in result.measured.deterministic
        if entry.family is Family.DATA_LEAKAGE
    ]
    assert entry.rate.attempts == 20
    assert entry.variants.accounts_for(entry.rate)
    assert entry.variants.mix_stated() == "plain 10/10, base64 10/10"


def test_an_entry_whose_breakdown_does_not_account_for_its_rate_is_refused() -> None:
    # Hand-built, because `assemble` cannot produce one: this is the invariant that
    # makes the artefact's counts checkable at the type and not only at the verifier.
    rate = failure_rate(10, 20)
    with pytest.raises(ValueError, match="does not account for"):
        FamilyEntry(
            family=Family.DATA_LEAKAGE,
            rate=rate,
            verdict_class=VerdictClass.DETERMINISTIC,
            band=band_for(rate),
            discrimination=None,
            coverage=(),
            variants=VariantBreakdown(
                (VariantCounts(Transform.PLAIN, successes=10, attempts=10),)
            ),
        )


def a_report(cases: list[Case]) -> TargetPayload:
    """One target's artefact over those cases, ready to serialise and render."""
    return a_payload(result=assemble(one_target_run(cases), cases))


def a_signed_payload(cases: list[Case]) -> dict[str, Any]:
    """One target's artefact as a recipient reads it: the document, as JSON."""
    return document(a_report(cases))


def leakage_entry(body: dict[str, Any]) -> dict[str, Any]:
    """The data-leakage family's entry in the artefact."""
    entries: list[dict[str, Any]] = body["measured"]["deterministic"]
    [entry] = [
        entry for entry in entries if entry["family"] == Family.DATA_LEAKAGE.value
    ]
    return entry


def test_the_artefact_carries_the_counts_per_variant_beside_the_pooled_rate(
    leakage_case: Case,
) -> None:
    # The counts a recipient recomputes the plain rate or the encoded rate from.
    # `payload.py`'s own idiom, one level deeper than the family: every measured
    # figure is written with the counts it came from.
    cases = [leakage_case, a_variant(leakage_case, Transform.ROT13)]

    entry = leakage_entry(a_signed_payload(cases))

    assert entry["attempts"] == 20
    assert entry["variants"] == [
        {
            "transform": "plain",
            "transform_stated": Transform.PLAIN.stated(),
            "successes": 10,
            "attempts": 10,
        },
        {
            "transform": "rot13",
            "transform_stated": Transform.ROT13.stated(),
            "successes": 10,
            "attempts": 10,
        },
    ]
    assert sum(one["attempts"] for one in entry["variants"]) == entry["attempts"]


def test_the_artefact_says_two_runs_at_different_selections_are_not_comparable(
    leakage_case: Case,
) -> None:
    # The sentence ADR-0055 requires printed where a reader compares two reports,
    # rather than left to be inferred from a library hash. Two runs whose families
    # hold different variants have different denominators, and after #79 an operator
    # can produce exactly that pair.
    body = a_signed_payload([leakage_case])

    assert "equal library version" in body["measured"]["variants_stated"]


def test_an_artefact_whose_counts_do_not_add_up_is_refused_by_the_verifier(
    leakage_case: Case,
) -> None:
    # Hand-edited, which is the only way to produce one: the bench's own types refuse
    # it. One variant count altered and the pooled rate left alone — the rate still
    # follows from `successes`/`attempts`, so no other check here would notice.
    body = a_signed_payload([leakage_case, a_variant(leakage_case, Transform.BASE64)])
    leakage_entry(body)["variants"][0]["attempts"] = 9

    re_derived = _re_derive(body)

    assert re_derived.outcome is ReDerivationOutcome.DISAGREES
    [disagreement] = [
        found
        for found in re_derived.disagreements
        if found.path.endswith("variants.attempts")
    ]
    assert "19" in disagreement.re_derived


def a_mix(plain: int, encoded: int) -> VariantBreakdown:
    """One agent's counts on a family holding a plain case and a base64 variant."""
    return VariantBreakdown(
        (
            VariantCounts(Transform.PLAIN, successes=plain, attempts=10),
            VariantCounts(Transform.BASE64, successes=encoded, attempts=10),
        )
    )


def test_a_gate_document_prints_the_variant_mix_behind_each_familys_rate() -> None:
    # `n` per family grew because the library did, and the document has to say what
    # it grew with: a reader meeting n = 20 where the last run read n = 10 cannot
    # tell from the number whether the family gained a case or a construction. One
    # line per agent — the three reference agents are three targets, so their counts
    # are never added together.
    mixed = FamilyRates(
        family=Family.DATA_LEAKAGE,
        hardened=failure_rate(1, 20),
        weak=failure_rate(8, 20),
        trivial=failure_rate(17, 20),
        variants=FamilyVariants(
            hardened=a_mix(0, 1), weak=a_mix(3, 5), trivial=a_mix(8, 9)
        ),
    )

    printed = stated_outcome(score_family(mixed))

    assert "n = 20 attempts per agent" in printed
    assert "hardened  plain 0/10, base64 1/10" in printed
    assert "trivial   plain 8/10, base64 9/10" in printed


def test_a_family_holding_one_variant_prints_no_mix_beside_its_rate() -> None:
    # Every family of the library as it stands. `plain 3/30` beside a rate already
    # printed as `(3/30)` is the same counts twice, and the interesting fact about a
    # one-variant family is the `n` above it.
    only_plain = VariantBreakdown(
        (VariantCounts(Transform.PLAIN, successes=3, attempts=30),)
    )
    plain = FamilyRates(
        family=Family.DATA_LEAKAGE,
        hardened=failure_rate(3, 30),
        weak=failure_rate(3, 30),
        trivial=failure_rate(3, 30),
        variants=FamilyVariants(
            hardened=only_plain, weak=only_plain, trivial=only_plain
        ),
    )

    printed = stated_outcome(score_family(plain))

    assert "n = 30 attempts per agent" in printed
    assert "plain" not in printed


def test_family_rates_whose_breakdown_does_not_account_for_an_agent_are_refused(
    leakage_case: Case,
) -> None:
    # Hand-built. The weak agent's breakdown is one attempt short of its rate, and
    # the type says which agent rather than only that something does not add up.
    plain = VariantBreakdown(
        (VariantCounts(Transform.PLAIN, successes=3, attempts=30),)
    )
    short = VariantBreakdown(
        (VariantCounts(Transform.PLAIN, successes=3, attempts=29),)
    )
    with pytest.raises(ValueError, match="weak"):
        FamilyRates(
            family=Family.DATA_LEAKAGE,
            hardened=failure_rate(3, 30),
            weak=failure_rate(3, 30),
            trivial=failure_rate(3, 30),
            variants=FamilyVariants(hardened=plain, weak=short, trivial=plain),
        )


def test_the_rendered_document_prints_the_counts_per_variant(
    leakage_case: Case,
) -> None:
    # The Markdown view, bound into the signature by digest (ADR-0017), so a reader
    # of the document a human reads sees the mix the machine verified.
    cases = [leakage_case, a_variant(leakage_case, Transform.BASE64)]
    document_text = render(a_report(cases))

    assert "`plain` — 10 of 10 attempts succeeded" in document_text
    assert "`base64` — 10 of 10 attempts succeeded" in document_text
    assert "equal library version and equal selection" in document_text


def test_a_one_variant_family_still_prints_its_single_construction(
    leakage_case: Case,
) -> None:
    # Printed for a family holding one variant too, because the signed document may
    # not say less than the payload it is a view of — and *plain, and nothing else*
    # is the fact a reader comparing two reports needs (ADR-0055).
    document_text = render(a_report([leakage_case]))

    assert "`plain` — 10 of 10 attempts succeeded" in document_text


def test_a_familys_n_is_its_live_case_count_times_the_attempts_per_case(
    leakage_case: Case,
) -> None:
    # The definition this ticket owes, asserted as the composition it is: `n` for a
    # family is its **live** case count times `attempts_per_case`, counting every
    # admitted variant and excluding the retired. Three records in one family, one of
    # them retired, so the family reads 20 rather than 30 — and the retired variant is
    # absent from the breakdown rather than present at zero.
    retired = retired_case(a_variant(leakage_case, Transform.ROT13))
    library = [leakage_case, a_variant(leakage_case, Transform.BASE64), retired]

    live = live_library(library)

    assert len(live) == 2
    target_run = one_target_run(live)
    rate = target_run.rates[Family.DATA_LEAKAGE]
    assert rate.attempts == len(live) * DECLARED_RULE.attempts_per_case == 20
    breakdown = target_run.variant_counts[Family.DATA_LEAKAGE]
    assert [count.transform for count in breakdown] == [
        Transform.PLAIN,
        Transform.BASE64,
    ]
    assert breakdown.accounts_for(rate)


def a_run_of(*counts: tuple[Transform, int, int]) -> TargetRun:
    """One target run over hand-built attempts: this many successes of this many, per
    construction.

    Built rather than measured, because the arithmetic under test needs **unequal**
    denominators and a stub reference agent answers the same way every time. It goes
    through `TargetRun` and so through the production `_variants` and `_rates`, which
    is the seam that matters: what a real run varies is which cases are on disk, and
    that is the test above.
    """
    target = a_target()
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
                case_id=f"data-leakage-001-{transform.value}",
                family=Family.DATA_LEAKAGE,
                target_name="target",
                index=index,
                transcripts=(probe,),
                verdict=(Verdict.SUCCEEDED if index < successes else Verdict.RESISTED),
                verdict_class=VerdictClass.DETERMINISTIC,
                transform=transform,
            )
            for transform, successes, attempts in counts
            for index in range(attempts)
        ),
        rule=DECLARED_RULE,
    )


def test_a_run_pools_unequal_denominators_and_never_averages_the_rates() -> None:
    # The pair the ticket names, at denominators where the two answers differ: 3 of 10
    # plain and 7 of 30 encoded is 10 of 40 — 0.25 — where the mean of 0.30 and 0.23
    # is 0.27. Equal denominators would let the mean pass, which is why this one is
    # written unequal.
    target_run = a_run_of((Transform.PLAIN, 3, 10), (Transform.BASE64, 7, 30))

    rate = target_run.rates[Family.DATA_LEAKAGE]

    assert (rate.successes, rate.attempts) == (10, 40)
    assert rate.value == pytest.approx(0.25)
    breakdown = target_run.variant_counts[Family.DATA_LEAKAGE]
    assert breakdown.mix_stated() == "plain 3/10, base64 7/30"
    assert breakdown.accounts_for(rate)


def test_a_breakdown_whose_counts_are_not_counts_is_a_disagreement_not_a_crash(
    leakage_case: Case,
) -> None:
    # A verifier reads a document it did not make, so a recipient of a doctored one is
    # owed the sentence and not a traceback: an element whose `attempts` is a string
    # is exactly as doctored as one whose `attempts` is nine, and both land in the one
    # reading a recipient can act on.
    body = a_signed_payload([leakage_case])
    leakage_entry(body)["variants"][0]["attempts"] = "ten"

    re_derived = _re_derive(body)

    assert re_derived.outcome is ReDerivationOutcome.DISAGREES
    [disagreement] = [
        found for found in re_derived.disagreements if ".variants" in found.path
    ]
    assert "add up to anything" in disagreement.stated
