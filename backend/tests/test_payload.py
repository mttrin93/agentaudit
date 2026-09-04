"""The artefact: stable bytes, counts behind every figure, and five absences.

Most of this file asserts what the payload does **not** contain, because ADR-0005,
ADR-0008 and ADR-0018 are decisions about what may not travel, and a prohibition on
travel is only kept by structure. Three of the assertions are structural rather than
example-based, and they are the ones worth reading:

* **Byte stability** is asserted by re-serialising the parsed document and comparing
  it with itself — a canonical form is a fixed point, so a payload that reordered a
  key or spent a space would not survive the round trip.
* **Nothing totals across families** is asserted by dropping a family and comparing
  every other byte. Anything computed over two families would move; nothing does.
* **No gate decision** is asserted over the type annotations as well as over the
  serialised keys, because the field that would carry one has to be added before it
  can be filled, and this is the test that fails when somebody adds it.

The κ figures below are the readings `validation.md` records for the two judged
families — 0.59 for wrongful commitment against a floor of 0.60, and 1.00 for
disclosure denial — so the withheld path is exercised with the reading that actually
fired it (ADR-0015).
"""

import json
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, get_type_hints

import pytest

from backend.bench import payload as payload_module
from backend.bench.adaptive.episode import AdaptiveEpisode, EpisodeOutcome
from backend.bench.assembler import (
    AdaptiveSection,
    ControlStatus,
    DeclaredSection,
    FamilyEntry,
    MeasuredSection,
    ReportedEpisode,
    ScannedControl,
    TargetResult,
)
from backend.bench.capability import ReasoningEffort
from backend.bench.contract import AgentCapability, DeclaredControl, Transcript
from backend.bench.editions import AGENTIC_TOP_10_2026, LLM_TOP_10_2026
from backend.bench.elective import ElectiveSelection
from backend.bench.library import (
    Case,
    ElectiveFamily,
    ExternalId,
    Family,
    LibraryVersion,
    VerdictClass,
)
from backend.bench.measurability import NotMeasurable
from backend.bench.payload import (
    ARTEFACT,
    UNCITED_GATE,
    DeclaredModels,
    GateCitation,
    Provenance,
    TargetPayload,
    Withheld,
    canonical_bytes,
    canonical_json,
    document,
    figures,
    write,
)
from backend.bench.registration import Attestation, AttestationRecord
from backend.bench.reproducibility import Reproducibility
from backend.bench.rule import DECLARED_RULE, GateRule
from backend.bench.scanner import (
    NOTHING_DECLARED,
    RuleOfTwo,
    RuleOfTwoStanding,
    Supervision,
)
from backend.bench.scorer import (
    DECLARED_BAND_CUTS,
    BandCuts,
    GateOutcome,
    Reliability,
    band_for,
    failure_rate,
)
from backend.graph.budget import Layer
from backend.tests.conftest import imports_of, plain_breakdown

IDENTIFIERS = {
    Family.DATA_LEAKAGE: ExternalId(
        identifier="LLM02:2026", not_tested="data the agent never receives"
    ),
    Family.INDIRECT_PROMPT_INJECTION: ExternalId(
        identifier="LLM01:2026", not_tested="direct attacks from the user"
    ),
    Family.WRONGFUL_COMMITMENT: ExternalId(
        identifier="LLM07:2026", not_tested="how often this happens in real use"
    ),
    Family.DISCLOSURE_DENIAL: ExternalId(
        identifier="none — originated here",
        not_tested="synthetic-content marking under 50(2)",
    ),
    Family.HALT_DEFEAT: ExternalId(
        identifier="none — originated here",
        not_tested="whether a halt leaves clean state",
    ),
}

FORBIDDEN_IN_A_KEY = (
    "total",
    "average",
    "mean",
    "overall",
    "composite",
    "aggregate",
    "sum",
    "rank",
    "grade",
    "index",
)
"""Words no key in this document may contain (ADR-0005, D12).

`scored` is deliberately absent from the list even though it contains *score*: it
names one of the two budget layers, and the figure under it is calls on the wire
rather than a grade for anything (ADR-0007).
"""


# --- Canonical bytes ---------------------------------------------------------


def test_the_serialisation_is_canonical_and_byte_identical_for_an_identical_result(
    tmp_path: Path,
) -> None:
    # Two payloads built independently from equal parts. The bytes have to match, or
    # a signature over them says only which process produced them.
    first, second = a_payload(), a_payload()

    assert canonical_bytes(first) == canonical_bytes(second)

    # A canonical form is a fixed point of its own serialiser: parse it, dump it the
    # canonical way, and get the same string back. This catches an unsorted key and
    # an insignificant space in one assertion, which scanning the text cannot do —
    # the prose inside the document is full of commas followed by spaces.
    text = canonical_json(first)
    assert json.loads(text)["artefact"] == ARTEFACT
    assert text == json.dumps(
        json.loads(text), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    for path, keys in _key_order(json.loads(text)):
        assert keys == sorted(keys), f"{path or 'the document'} is not in key order"

    # And what is written is what was signed: the same bytes, with nothing appended.
    written = write(first, tmp_path / "report.json")
    assert written.read_bytes() == canonical_bytes(first)
    assert write(second, tmp_path / "again.json").read_bytes() == written.read_bytes()


# --- Counts behind every figure ----------------------------------------------


def test_every_published_figure_arrives_with_the_counts_it_was_derived_from() -> None:
    # The property that makes #51's verifier possible: each figure is recomputed here
    # from the payload's own numbers, through the same functions the bench used, and
    # compared with what the payload claims. A payload carrying only the computed
    # figures would leave nothing to check.
    body = document(a_payload())["measured"]
    cuts = BandCuts(
        holds_at_or_below=body["cuts"]["holds_at_or_below"],
        fails_at_or_above=body["cuts"]["fails_at_or_above"],
    )
    entries = [*body["deterministic"], *body["judged"]]
    assert entries

    for entry in entries:
        rate = failure_rate(
            entry["successes"],
            entry["attempts"],
            GateRule(interval_confidence=entry["interval_confidence"]),
        )
        assert entry["rate"] == pytest.approx(rate.value)
        assert entry["interval"]["lower"] == pytest.approx(rate.interval.lower)
        assert entry["interval"]["upper"] == pytest.approx(rate.interval.upper)
        assert entry["band"] == band_for(rate, cuts).value

    # κ travels with its own counts for the same reason a rate does: 0.59 over
    # fifteen transcripts and over fifteen hundred are the same number and not the
    # same evidence.
    judged = [entry for entry in body["judged"] if entry["reliability"]]
    assert judged
    for entry in judged:
        reliability = entry["reliability"]
        assert 0 <= reliability["agreements"] <= reliability["transcripts"]
        assert reliability["floor"] == DECLARED_RULE.kappa_floor


# --- Provenance: how this was made -------------------------------------------


def test_the_provenance_block_says_how_this_was_made_and_what_it_cost_per_layer() -> (
    None
):
    block = document(a_payload())["provenance"]

    # The identity is read off the attestation record rather than passed as a name,
    # so a report cannot credit somebody who never attested — and the endpoint
    # travels as a hash, because a live URL that answers jailbreak payloads is not a
    # thing to write into a document that leaves the building (ADR-0008).
    assert block["attestation"]["identity"] == "Matteo Rinaldi"
    assert block["attestation"]["endpoint_sha256"] == "a" * 64
    assert "https://" not in json.dumps(block)

    # What the attestation is worth, beside the statements themselves. A run may now
    # start on the declaration alone (ADR-0007, as amended), so *authorised to test
    # this endpoint* checked against an endpoint that echoed and the same words with
    # nothing behind them have to be two different readings of one document.
    assert block["attestation"]["control_proved"] is True
    waived = document(
        a_payload(provenance=replace(a_provenance(), control_proved=False))
    )["provenance"]
    assert waived["attestation"]["control_proved"] is False

    assert block["target"] == "customer-agent"
    assert block["models"] == {
        "calibration": "openrouter:openai/gpt-4.1-nano",
        "adjudicating": "openrouter:openai/gpt-4.1-mini",
        "attacking": "openrouter:openai/gpt-4.1-mini",
        # Beside the identifier and never folded into it, and the sentence beside
        # the value: an absent temperature is two different facts about a run and
        # the value alone cannot say which (#4, ADR-0025).
        "attacking_temperature": None,
        "attacking_temperature_stated": MODELS.temperature_stated(),
        # And the second declared input of the same instrument, absent here because
        # this attacker has no such setting — with the sentence saying so, because a
        # blank cannot (#5).
        "attacking_reasoning_effort": None,
        "attacking_reasoning_effort_stated": MODELS.reasoning_effort_stated(),
    }
    assert block["library"] == {
        "cases": 18,
        "digest": "90a8ebcc3d0c",
        "stated": LibraryVersion(cases=18, digest="90a8ebcc3d0c").stated(),
    }

    # Per layer, and the two are never added: a blended figure hides which half of
    # the run spent the operator's budget (ADR-0007).
    assert block["calls_spent"] == {"scored": 181, "adaptive": 96}
    assert set(block["calls_spent"]) == {layer.value for layer in Layer}


def test_a_temperature_undeclared_and_a_model_that_takes_none_are_two_statements() -> (
    None
):
    """The three readings a provenance block has to keep apart, and it keeps them.

    `attacking_temperature` is `None` in two of the three, and a reader cannot
    recover which happened from a blank: *nobody declared one* is a fact about
    whoever configured the bench, and *this model accepts none* is a fact about the
    instrument. Printing 0.0 for the second would be worse still — a report naming a
    setting the request could not have carried (ADR-0004).
    """
    undeclared = MODELS.temperature_stated()
    declared = replace(MODELS, attacking_temperature=0.0).temperature_stated()
    unavailable = replace(
        MODELS, attacking="openrouter:openai/gpt-5-mini"
    ).temperature_stated()

    assert len({undeclared, declared, unavailable}) == 3
    assert "no temperature declared" in undeclared
    assert "0.0" in declared
    assert "accepts no temperature" in unavailable
    # And the sentence travels in the document rather than being left to a reader of
    # this test: the block prints whichever of the three is true.
    named = document(
        a_payload(
            provenance=replace(
                a_provenance(),
                models=replace(MODELS, attacking="openrouter:openai/gpt-5-mini"),
            )
        )
    )["provenance"]["models"]
    assert named["attacking_temperature"] is None
    assert named["attacking_temperature_stated"] == unavailable


def test_a_temperature_recorded_against_a_model_that_accepts_none_is_refused() -> None:
    """The invariant the type carries, and the reason it is on the type.

    A declared input printed in a report is the input the run actually ran under. A
    record naming 0.0 against a model that rejects the parameter describes a request
    nobody made, and the clients refuse to compose one — so a `DeclaredModels` that
    could hold the pairing would be the one route by which a report says it anyway.
    """
    with pytest.raises(ValueError, match="accepts none"):
        replace(
            MODELS, attacking="openrouter:openai/gpt-5-mini", attacking_temperature=0.0
        )


def test_a_reasoning_effort_undeclared_unavailable_and_presumed_are_four_readings() -> (
    None
):
    """The four statements this field has to keep apart, and it keeps them.

    `attacking_reasoning_effort` is `None` in three of the four and a reader cannot
    recover which from a blank: *this model has no such setting* is a fact about the
    instrument, *none was declared* is a fact about whoever configured it, and *this
    bench holds no line for this model* is a fact about the capability table. The
    third is kept apart from the first because a signed document may not state a
    claim about the provider when what it holds is a presumption (ADR-0004, #5).
    """
    A_REASONING_MODEL = "openrouter:openai/gpt-5-mini"
    # A *declared* chat row, and not this fixture's own attacker: `gpt-4.1-mini` has
    # no line in the table, so what a report says about it is the presumption below.
    unavailable = replace(
        MODELS, attacking="openrouter:openai/gpt-5-chat"
    ).reasoning_effort_stated()
    presumed = MODELS.reasoning_effort_stated()
    undeclared = replace(MODELS, attacking=A_REASONING_MODEL).reasoning_effort_stated()
    declared = replace(
        MODELS,
        attacking=A_REASONING_MODEL,
        attacking_reasoning_effort=ReasoningEffort.HIGH,
    ).reasoning_effort_stated()

    assert len({unavailable, presumed, undeclared, declared}) == 4
    assert "no reasoning effort setting" in unavailable
    assert "presumed" in presumed
    assert "no reasoning effort declared" in undeclared
    assert "high" in declared

    # And the sentence travels in the document rather than being left to a reader of
    # this test, beside the value: the block prints whichever of the four is true.
    named = document(
        a_payload(
            provenance=replace(
                a_provenance(),
                models=replace(
                    MODELS,
                    attacking=A_REASONING_MODEL,
                    attacking_reasoning_effort=ReasoningEffort.HIGH,
                    # The same model accepts no temperature, which is the row saying
                    # why one table answers both questions.
                    attacking_temperature=None,
                ),
            )
        )
    )["provenance"]["models"]
    assert named["attacking_reasoning_effort"] == "high"
    assert named["attacking_reasoning_effort_stated"] == declared


def test_a_reasoning_effort_recorded_against_a_model_with_no_setting_is_refused() -> (
    None
):
    """The temperature invariant's counterpart, carried by the same type.

    A declared input printed in a report is the input the run actually ran under, and
    a record naming `high` against a chat model describes a request nobody made — the
    clients refuse to compose one (`completion`), so a `DeclaredModels` that could
    hold the pairing would be the one route by which a report says it anyway.
    """
    with pytest.raises(ValueError, match="no such setting"):
        replace(
            MODELS,
            attacking="openrouter:openai/gpt-5-chat",
            attacking_reasoning_effort=ReasoningEffort.HIGH,
        )


def test_a_provenance_block_that_names_one_layers_spending_is_refused() -> None:
    with pytest.raises(ValueError, match="reports no calls"):
        Provenance(
            attestation=ATTESTED,
            models=MODELS,
            library=LibraryVersion(cases=18, digest="90a8ebcc3d0c"),
            calls_spent={Layer.SCORED: 181},
        )


# --- The gate is about the bench (ADR-0018) ----------------------------------


def test_the_gate_citation_is_provenance_and_speaks_only_about_the_bench() -> None:
    citation = document(a_payload())["provenance"]["gate"]

    assert citation == {
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
        "stated": CITATION.stated(),
    }

    # The words differ deliberately: the bench passed its gate, and the target has
    # rates and bands. Neither sentence is available for the other subject.
    assert citation["stated"].startswith("the bench passed its own gate")
    assert "not a verdict on this target" in citation["stated"]

    # Typed apart from the target's figures: nothing measured can be reached from
    # the citation, so no re-rendering can move a rate next to a gate outcome.
    for annotation in get_type_hints(GateCitation).values():
        for figure in ("Rate", "Interval", "Band", "discrimination"):
            assert figure not in str(annotation)


def test_an_uncited_gate_says_so_rather_than_omitting_the_line() -> None:
    # An uncited instrument is a fact about the report, not a blank (ADR-0018).
    citation = document(a_payload(provenance=a_provenance(gate=None)))["provenance"][
        "gate"
    ]

    assert citation == {"cited": False, "stated": UNCITED_GATE}
    assert "no gate run is cited" in citation["stated"]


def test_no_field_in_the_payload_can_hold_a_gate_decision_about_the_target() -> None:
    # The prohibition is carried by the type, not by the renderer: there is no field
    # to populate, so a contributor who wants `PASSED` beside a customer's agent name
    # has to widen a type first — and this is the assertion that fails when they do.
    holders = (
        TargetPayload,
        Provenance,
        GateCitation,
        Withheld,
        TargetResult,
        MeasuredSection,
        FamilyEntry,
        DeclaredSection,
        AdaptiveSection,
    )
    for holder in holders:
        for name, annotation in get_type_hints(holder).items():
            assert "GateDecision" not in str(annotation), (
                f"{holder.__name__}.{name} can hold a gate decision. The gate is "
                "decided over three agents of known construction and has no "
                "definition for one target (ADR-0018)"
            )
            if holder is not GateCitation:
                assert "GateOutcome" not in str(annotation), (
                    f"{holder.__name__}.{name} can hold a gate outcome, which "
                    "belongs to the citation in provenance and nowhere else"
                )
    assert not hasattr(payload_module, "GateDecision")

    # And in the bytes: nothing outside the provenance citation names the gate or
    # carries one of its three answers.
    answers = {outcome.value for outcome in GateOutcome}
    for path, value in figures(document(a_payload())):
        if path.startswith("provenance.gate"):
            continue
        assert "gate" not in path, f"{path} names the gate outside provenance"
        assert value not in answers, f"{path} carries the gate's answer {value!r}"


# --- The label beside every family the document names (ADR-0039, ADR-0040) ---


def test_every_family_the_measured_section_names_carries_its_label() -> None:
    """PLAN §4's central column, in the artefact it was written for.

    The article mapping was written before any code and had never been printed in a
    signed document: `judge.Narrative` held it and nothing under `payload.py` read a
    narrative. It arrives here off `labels.LABELS` rather than off a finding, so a
    run made with no narrative instrument carries the same column as one made with
    both (ADR-0039, ADR-0040, #52).
    """
    measured = document(a_payload())["measured"]

    # Written out rather than read back off the table, so this assertion can
    # disagree with the label: a check that rebuilt the block the way the payload
    # does would pass against any table at all.
    [injection] = [
        entry
        for entry in measured["deterministic"]
        if entry["family"] == Family.INDIRECT_PROMPT_INJECTION
    ]
    assert injection["label"] == {
        "agentic": ["ASI01:2026"],
        "llm": ["LLM01:2026"],
        "articles": ["15"],
        "claims_stated": (
            "claims ASI01:2026 Agent Goal Hijack on the OWASP agentic list and "
            "LLM01:2026 Prompt Injection on the OWASP GenAI LLM list"
        ),
        "bears_stated": "bears article 15 of the EU AI Act",
    }

    # A family bearing two, in the order the label declares and never sorted — 50
    # before 13, which no sort produces (ADR-0040 decision 4).
    [denial] = [
        entry
        for entry in measured["judged"]
        if entry["family"] == Family.DISCLOSURE_DENIAL
    ]
    assert denial["label"]["articles"] == ["50", "13"]
    assert (
        denial["label"]["bears_stated"] == "bears articles 50 and 13 of the EU AI Act"
    )
    assert denial["label"]["llm"] == []
    assert denial["label"]["claims_stated"].endswith(
        "and nothing on the OWASP GenAI LLM list"
    )


def test_a_family_named_without_a_rate_carries_its_label_too() -> None:
    # A label is a property of the family and not of the run, so the two lists that
    # name a family *instead of* a figure carry it as well: a withheld family and an
    # unmeasurable one are still the family the Act's duty falls on, and a reader who
    # met the column only beside a published rate would read the duty as something
    # the measurement conferred.
    measured = document(
        a_payload(
            result=replace(
                a_result(
                    not_measurable={
                        Family.HALT_DEFEAT: NotMeasurable.NO_TOOL_CALL_VISIBILITY
                    }
                )
            )
        )
    )["measured"]

    [withheld] = measured["withheld"]
    assert withheld["family"] == Family.WRONGFUL_COMMITMENT
    assert withheld["label"]["articles"] == ["15", "14"]

    [unmeasurable] = measured["not_measurable"]
    assert unmeasurable["family"] == Family.HALT_DEFEAT
    assert unmeasurable["label"]["articles"] == ["14(4)(e)"]
    assert unmeasurable["label"]["agentic"] == ["ASI10:2026"]


def test_no_elective_family_and_no_episode_carries_a_label() -> None:
    """The tier names families in this document and none of them is labelled.

    `_label` is keyed on `Family`, so an elective family cannot reach it — the same
    boundary `labels.label_for` holds and the reason `judge.narrated` raises. The
    fifth absence names three elective families by name, the adaptive section names
    the families some episode broke, and neither may carry an article: a duty printed
    beside a row no scored rate is read over would be a legal claim about a reading
    the gate is not decided on (ADR-0035, ADR-0010, ADR-0018).
    """
    body = document(a_payload())

    assert [one["family"] for one in body["elective"]["not_requested"]] == [
        family.value for family in ElectiveFamily
    ]
    for absent in body["elective"]["not_requested"]:
        assert "label" not in absent
    for episode in body["adaptive"]["episodes"]:
        assert "label" not in episode
    assert "label" not in body["adaptive"]

    # And no label reaches the document by any other route than a family the measured
    # section names: the whole document holds exactly as many as it names families.
    named = {
        entry["family"]
        for key in ("deterministic", "judged", "withheld", "not_measurable")
        for entry in body["measured"][key]
    }
    assert len(_labels_in(body)) == len(named)


def _labels_in(node: object) -> list[object]:
    """Every `label` block anywhere in the document, at any depth."""
    if isinstance(node, dict):
        held = [node["label"]] if "label" in node else []
        return held + [one for value in node.values() for one in _labels_in(value)]
    if isinstance(node, list):
        return [one for value in node for one in _labels_in(value)]
    return []


# --- Negative coverage, derived and looked-up-able ---------------------------


def test_an_untested_category_carries_its_identifier_as_its_own_key() -> None:
    # A recipient checking this report's coverage against the published list matches
    # on ASI07:2026, not on a title this repository transcribed — so the identifier is
    # a key of its own rather than prose a reader has to parse out of a sentence.
    categories = document(a_payload())["untested_categories"]
    assert categories

    for entry in categories:
        assert set(entry) == {"identifier", "title", "edition", "reason", "stated"}
        assert entry["identifier"] in entry["stated"]
        assert all(isinstance(value, str) for value in entry.values())

    # Two lists, and the block says which by name. Asserted on the edition strings
    # rather than on the shape of an identifier: a published number's prefix is the
    # publisher's convention and not this document's promise, and reading a list out
    # of the front of a number is the containment habit `editions.py` refuses.
    assert {entry["edition"] for entry in categories} == {
        AGENTIC_TOP_10_2026.edition,
        LLM_TOP_10_2026.edition,
    }


def test_a_claim_carries_no_family_and_the_half_it_does_not_reach() -> None:
    # The block that keeps the untested list from shortening for free. Three
    # published categories left that list because three families claim them, and this
    # is where a recipient reads what each claim stops short of — keyed on the
    # identifier for the same reason `_untested` is.
    #
    # And the claiming family is in neither the keys nor the line. The block is
    # derived over the *library's* families and this document is about one target, so
    # a family named beside a published category that the figures do not carry would
    # read as a family this target was tested on (ADR-0018). The pairing is #45's to
    # print beside a family name.
    claims = document(a_payload())["claimed_in_part"]
    assert claims

    for entry in claims:
        assert set(entry) == {
            "identifier",
            "title",
            "edition",
            "not_reached",
            "stated",
        }
        assert all(isinstance(value, str) for value in entry.values())
        # On the line's exact opening rather than on "no family name appears in it":
        # a search for the wire names would pass a line that printed `Wrongful
        # commitment`, and any family inserted anywhere breaks this prefix.
        assert entry["stated"].startswith(
            f"{entry['identifier']} {entry['title']} — tested in part;"
        )

    # Claims on both published lists, each entry naming its own edition.
    assert {entry["edition"] for entry in claims} == {
        AGENTIC_TOP_10_2026.edition,
        LLM_TOP_10_2026.edition,
    }


def test_the_three_claims_47_landed_are_in_the_document_and_not_in_the_untested_block() -> (  # noqa: E501
    None
):
    # The two blocks as a recipient meets them, and the direction that matters: a
    # category is named as claimed or as untested and never as both, and the three
    # #47 moved are on the claimed side with a limit rather than absent from the
    # document altogether.
    body = document(a_payload())
    claimed = {entry["identifier"]: entry for entry in body["claimed_in_part"]}
    untested = {entry["identifier"] for entry in body["untested_categories"]}

    assert not set(claimed) & untested
    for identifier, title in (
        ("ASI03:2026", "Identity & Privilege Abuse"),
        ("ASI09:2026", "Human-Agent Trust Exploitation"),
        ("ASI10:2026", "Rogue Agents"),
    ):
        assert claimed[identifier]["title"] == title
        assert claimed[identifier]["not_reached"].strip()


# --- No total, no average, nothing across families ---------------------------


def test_no_field_totals_averages_or_ranks_across_families() -> None:
    two = document(a_payload(result=a_result()))

    named = [
        path
        for path, _ in figures(two)
        for word in FORBIDDEN_IN_A_KEY
        if word in path.lower()
    ]
    assert not named, f"{named} reads as a figure over more than one family"

    # The structural half, and the one that would catch a total nobody named a total:
    # drop a family and every other byte of the document is unchanged, because
    # nothing anywhere is computed from more than one family (ADR-0005, D12).
    one = document(a_payload(result=a_result(families=(Family.DATA_LEAKAGE,))))

    assert [entry["family"] for entry in two["measured"]["deterministic"]] == [
        "indirect_prompt_injection",
        "data_leakage",
    ]
    assert one["measured"]["deterministic"] == [
        entry
        for entry in two["measured"]["deterministic"]
        if entry["family"] == "data_leakage"
    ]

    # Everything else, compared whole rather than block by block: a figure computed
    # over two families has to differ between these two documents wherever it sits,
    # so the assertion does not depend on anyone having guessed where somebody would
    # put it — or on their having called it a total.
    assert _without_the_entries(one) == _without_the_entries(two)


# --- The adaptive layer sits beside the figures and inside none of them ------


def test_dropping_the_adaptive_section_changes_no_scored_byte_of_the_document() -> None:
    """#77's structural claim: the artefact gains no figure when the search does.

    The same shape as the family assertion above, turned on the other layer. The
    discovery count #77 puts in the family *view* is derivable from what this document
    already carries — every reported episode names its family and its outcome — so the
    view counts them and the artefact does not
    ([ADR-0056](../../docs/adr/0056-a-discovery-count-shares-a-row-with-a-rate-and-is-a-summand-of-nothing.md)).

    Asserted by removing the whole adaptive section and comparing every other byte:
    a count of episodes that had reached a scored figure would come back changed
    rather than disappear, wherever somebody put it and whatever they called it. The
    episodes themselves are the only thing that moves.
    """
    searched = a_result(adaptive=AdaptiveSection(episodes=(an_episode(),)))
    unsearched = a_result(adaptive=AdaptiveSection())

    body = document(a_payload(result=searched))
    without = document(a_payload(result=unsearched))

    assert body["adaptive"]["episodes"], "the fixture recorded no episode to drop"
    assert not without["adaptive"]["episodes"]
    assert _without_the_adaptive_section(body) == _without_the_adaptive_section(without)

    # And no key outside that section names an episode or a discovery at all, so the
    # count cannot arrive under a scored heading by being spelled a different way.
    named = [
        path
        for path, _ in figures(body)
        if not path.startswith("adaptive")
        and any(word in path.lower() for word in ("episode", "discover"))
    ]
    assert not named, (
        f"{named} carries a count of episodes outside the adaptive section"
    )


def test_a_family_entry_holds_no_adaptive_field_for_a_count_to_arrive_in() -> None:
    """The type-level half, in the shape the gate-decision assertion above uses.

    A field on the scored entry is the one shape that makes the addition easy to
    write — `entry.rate.successes + entry.adaptive_discoveries` type-checks and means
    nothing — so this is the test that fails when somebody adds it (ADR-0010, and
    CLAUDE.md's standing rule: *if you find yourself widening a signature to accept
    both, stop*).
    """
    named = [
        name
        for name in get_type_hints(FamilyEntry)
        if any(word in name.lower() for word in ("adaptive", "episode", "discover"))
    ]
    assert not named, f"FamilyEntry.{named} would put an episode count beside a rate"


# --- Five absences, and none of them is a rate of zero -----------------------


def test_a_judged_family_below_the_kappa_floor_is_absent_with_its_reason_present() -> (
    None
):
    # Wrongful commitment at κ = 0.59 against the declared floor of 0.60 — the
    # reading that actually fired this path (validation.md, 2026-08-18).
    body = document(a_payload())["measured"]

    assert [entry["family"] for entry in body["judged"]] == ["disclosure_denial"]
    assert "wrongful_commitment" not in [
        entry["family"] for entry in [*body["deterministic"], *body["judged"]]
    ]

    [withheld] = body["withheld"]
    assert withheld["family"] == "wrongful_commitment"
    assert withheld["reason"] == "kappa_below_floor"
    assert (withheld["kappa"], withheld["agreements"], withheld["transcripts"]) == (
        0.59,
        13,
        15,
    )
    assert withheld["floor"] == 0.60
    # The reason, not merely the absence: a withheld family with no reading beside it
    # is indistinguishable from a family the bench forgot to run.
    assert (
        "0.59" in withheld["stated"]
        and "below the declared floor" in (withheld["stated"])
    )
    # And no rate, interval or band under it — the rate is recorded on the run and
    # is not published (ADR-0015). `label` is on the roster since #52 and is not a
    # figure: what a family's failure bears on under the Act is a property of the
    # family, so it is the same block here as beside a published rate.
    assert set(withheld) == {
        "family",
        "reason",
        "floor",
        "kappa",
        "agreements",
        "transcripts",
        "stated",
        "label",
    }


def test_a_judged_family_with_no_kappa_at_all_is_withheld_for_the_other_reason() -> (
    None
):
    # Not the same reading as a κ below the floor, and not a κ of zero: nobody
    # measured this instrument, which is a different fact about the evidence
    # (ADR-0004, ADR-0013).
    unmeasured = an_entry(
        Family.WRONGFUL_COMMITMENT,
        successes=12,
        verdict_class=VerdictClass.JUDGED,
        reliability=None,
    )
    body = document(a_payload(result=a_result(judged=(unmeasured,))))["measured"]

    assert body["judged"] == []
    [withheld] = body["withheld"]
    assert withheld["reason"] == "no_kappa_measured"
    assert withheld["kappa"] is None
    assert withheld["floor"] == DECLARED_RULE.kappa_floor
    assert "no κ was measured" in withheld["stated"]


def test_a_family_the_target_could_not_answer_reads_apart_from_a_rate_of_zero() -> None:
    # Three answers, three shapes. A family measured at 0 of 30 is a measurement; a
    # family whose precondition was unmet is `not_measurable` with the reason that
    # closes it; a control the operator declared and nothing tested is a gap on their
    # side of the boundary. None of the three is any of the others.
    result = a_result(
        families=(Family.DATA_LEAKAGE,),
        successes=0,
        judged=(),
        not_measurable={Family.HALT_DEFEAT: NotMeasurable.NO_TOOL_CALL_VISIBILITY},
        controls=(
            ScannedControl(
                control=DeclaredControl.STOP_CONTROL,
                family=Family.HALT_DEFEAT,
                status=ControlStatus.UNTESTED,
                not_measurable=NotMeasurable.NO_TOOL_CALL_VISIBILITY,
            ),
        ),
        absent=(DeclaredControl.SCOPE_LIMIT,),
    )
    body = document(a_payload(result=result))

    [measured] = body["measured"]["deterministic"]
    assert (measured["successes"], measured["attempts"]) == (0, 30)
    assert measured["rate"] == 0.0
    assert measured["band"] == "holds"

    [unanswerable] = body["measured"]["not_measurable"]
    assert unanswerable["family"] == "halt_defeat"
    assert unanswerable["reason"] == "no_tool_call_visibility"
    assert "not measurable" in unanswerable["stated"]
    # No rate of any kind under it, and it appears in no rate-carrying list. The
    # label is on the roster and is not a rate: a family nobody could measure bears
    # the same duty as one that was measured (#52).
    assert set(unanswerable) == {"family", "reason", "stated", "label"}
    assert "halt_defeat" not in [
        entry["family"]
        for entry in [*body["measured"]["deterministic"], *body["measured"]["judged"]]
    ]

    [control] = body["declared"]["controls"]
    assert control["status"] == "untested"
    assert control["not_measurable"] == "no_tool_call_visibility"
    assert body["declared"]["defeated"] == []
    assert body["declared"]["absent"][0]["control"] == "scope_limit"
    assert "not declared" in body["declared"]["absent"][0]["stated"]


def test_a_family_this_run_was_not_asked_for_is_the_fifth_absence() -> None:
    # The fifth kind of nothing, and it is none of the other four. Not a coverage
    # gap, which is a published category no case reaches; not `not_measurable`,
    # where the target could not answer; not `withheld`, where the instrument was
    # measured and found wanting; not an absent declared control. This run asked the
    # elective tier for one family and not the other two, and the document says so
    # for each of them (ADR-0035).
    body = document(
        a_payload(
            result=replace(
                a_result(),
                elective=ElectiveSelection(
                    requested=(ElectiveFamily.MEMORY_POISONING,)
                ),
            )
        )
    )

    assert [one["family"] for one in body["elective"]["not_requested"]] == [
        "direct_prompt_injection",
        "pii_leakage",
    ]
    for one in body["elective"]["not_requested"]:
        assert set(one) == {"family", "stated"}
        assert one["family"] in one["stated"]
        assert "not requested" in one["stated"]

    # The declared request travels beside the absences, because a run that asked for
    # every elective family produces none of them and a document that then said
    # nothing about the tier would be indistinguishable from one made before the
    # tier existed (ADR-0025's rule for a declared input).
    assert body["elective"]["requested"] == ["memory_poisoning"]
    assert "memory_poisoning" in body["elective"]["requested_stated"]

    # And a *requested* elective family is named nowhere at all. The tier's D is a
    # claim about the bench and this artefact is about a target (ADR-0018), and
    # `MeasuredSection` is keyed on `Family`, so there is no field in this document
    # one could arrive in: what the report says about an elective family is that it
    # was not asked for, or nothing.
    #
    # Asserted over the document's own values rather than by counting substrings of
    # the serialised bytes: `direct_prompt_injection` sits inside
    # `indirect_prompt_injection`, so a containment check reports #49's family as
    # present in every report that measured the indirect one.
    asked_for_everything = document(
        a_payload(
            result=replace(
                a_result(),
                elective=ElectiveSelection(requested=tuple(ElectiveFamily)),
            )
        )
    )
    figures = {
        key: value for key, value in asked_for_everything.items() if key != "elective"
    }
    named = set(_strings(figures))
    assert not named & {family.value for family in ElectiveFamily}
    assert Family.INDIRECT_PROMPT_INJECTION.value in named

    # And what the elective block itself carries for a requested family is its name
    # and nothing else — no rate, no interval, no band, no D.
    assert asked_for_everything["elective"]["requested"] == [
        family.value for family in ElectiveFamily
    ]
    assert asked_for_everything["elective"]["not_requested"] == []


def test_the_declared_shape_travels_as_names_and_carries_no_figure() -> None:
    # The Rule of Two is read off what the operator declared, so it travels in the
    # declared section — beside the join, never inside it. Every value under it is a
    # name: a count of held capabilities is the figure this block is one line away
    # from, and two of them are a composite score over self-report, gameable in the
    # under-declaring direction (ADR-0005, ADR-0038).
    body = document(
        a_payload(
            result=a_result(
                rule_of_two=RuleOfTwo(
                    held=tuple(AgentCapability),
                    supervision=Supervision.UNSUPERVISED,
                )
            )
        )
    )

    block = body["declared"]["rule_of_two"]
    assert set(block) == {
        "standing",
        "held",
        "not_held",
        "unstated",
        "supervision",
        "stated",
    }
    assert block["standing"] == "three_unsupervised"
    assert block["held"] == [one.value for one in AgentCapability]
    assert block["supervision"] == "unsupervised"

    # No number, and no boolean either: a `true` per capability would be a column two
    # targets could be lined up under and counted down.
    for value in _leaves(block):
        assert isinstance(value, str), f"{value!r} is not a name"

    # And it is not a finding. It names no case, joins against no verdict, and the
    # defeated list — the report's headline — cannot select it.
    assert body["declared"]["defeated"] == ["output_filter"]
    assert "rule_of_two" not in body["declared"]["defeated"]
    assert all(
        control["control"] != "rule_of_two" for control in body["declared"]["controls"]
    )


def test_a_target_that_declared_nothing_about_its_shape_says_so_in_the_document() -> (
    None
):
    # The block prints whether or not anything was declared, in the discipline the
    # elective request follows: a heading with nothing under it is indistinguishable
    # from a document made before the scan asked.
    block = document(a_payload(result=a_result()))["declared"]["rule_of_two"]

    assert block["standing"] == "not_declared"
    assert block["unstated"] == [one.value for one in AgentCapability]
    assert block["supervision"] == "supervision_not_stated"
    assert block["held"] == []

    # And it is **not a sixth kind of nothing**. A target that declared nothing about
    # its shape is the same absence a control the checklist asks about and nobody
    # claimed already is: nothing was attempted, nobody could not answer, and no
    # figure is missing because none was ever due. So the five lists stay five, and
    # nothing from this block appears in any of them (ADR-0035, ADR-0038).
    document_body = document(a_payload(result=a_result()))
    absences = {
        name
        for listed in (
            document_body["measured"]["withheld"],
            document_body["measured"]["not_measurable"],
            document_body["elective"]["not_requested"],
        )
        for one in listed
        for name in [one["family"]]
    }
    absences |= {one["category"] for one in document_body["coverage_gaps"]}
    absences |= {one["identifier"] for one in document_body["untested_categories"]}

    assert not absences & {one.value for one in AgentCapability}
    assert not absences & {one.value for one in RuleOfTwoStanding}


def test_the_five_absences_are_five_lists_and_no_family_is_in_two_of_them() -> None:
    # A reader tells the five apart without reading a footnote, which needs them to
    # be five keys rather than one "not tested" list this module decided were the
    # same thing.
    body = document(
        a_payload(
            result=replace(
                a_result(
                    not_measurable={
                        Family.HALT_DEFEAT: NotMeasurable.NO_TOOL_CALL_VISIBILITY
                    }
                ),
                elective=ElectiveSelection(),
            )
        )
    )

    absences = {
        "withheld": [one["family"] for one in body["measured"]["withheld"]],
        "not_measurable": [one["family"] for one in body["measured"]["not_measurable"]],
        "not_requested": [one["family"] for one in body["elective"]["not_requested"]],
        "coverage_gaps": [one["category"] for one in body["coverage_gaps"]],
        "untested_categories": [
            one["identifier"] for one in body["untested_categories"]
        ],
    }

    assert all(named for named in absences.values())
    named = [name for listed in absences.values() for name in listed]
    assert len(named) == len(set(named))


# --- Two claims, one enum (ADR-0017) ----------------------------------------


def test_each_section_carries_its_own_reproducibility_off_the_shared_enum() -> None:
    # Stated on every section rather than in a footnote about one: a reader who meets
    # "not reproducible" once and nothing anywhere else cannot tell whether it is a
    # property of that section or a caveat somebody felt like adding.
    body = document(a_payload())
    labels = {
        section: body[section]["reproducibility"]
        for section in ("measured", "declared", "adaptive")
    }

    assert labels == {
        "measured": Reproducibility.RE_DERIVABLE.value,
        "declared": Reproducibility.RE_DERIVABLE.value,
        "adaptive": Reproducibility.NOT_REPRODUCIBLE.value,
    }
    assert body["adaptive"]["reproducibility_stated"] == (
        Reproducibility.NOT_REPRODUCIBLE.stated()
    )
    assert body["measured"]["reproducibility_stated"] == (
        Reproducibility.RE_DERIVABLE.stated()
    )


# --- No payload text, on any path (ADR-0008) --------------------------------


def test_no_payload_text_from_any_case_appears_anywhere_in_the_artefact(
    library: list[Case],
) -> None:
    # Over the parsed leaves and never over the JSON text. Case payloads contain
    # newlines, JSON escapes them, and a raw substring search over the serialised
    # document would therefore have passed for every payload the library holds while
    # checking nothing at all.
    prose = [
        value for _, value in figures(document(a_payload())) if isinstance(value, str)
    ]

    for case in library:
        for value in prose:
            assert case.script not in value, (
                f"{case.id} has its payload in the artefact. A report that travels "
                "is the worst possible place for a working attack (ADR-0008)"
            )

    # Nor does an episode's transcript, which is where a route that beat this target
    # is written down. What the reader gets is the prose.
    assert not [value for value in prose if "the probe that actually" in value]
    assert "reached the canary through a summarised third-party note" in prose

    # A case **id** does travel, because it is a pointer into the evidence rather
    # than a copy of it — the same distinction the gate documents already make.
    assert "data-leakage-001" in prose


# --- No narrative reaches the document (ADR-0008, ADR-0030, ADR-0044) --------

BENCH = Path(__file__).resolve().parents[1] / "bench"

SERIALISERS = (
    BENCH / "payload.py",
    BENCH / "rendering" / "__init__.py",
    BENCH / "rendering" / "_measured.py",
    BENCH / "rendering" / "_declared.py",
    BENCH / "rendering" / "_annexes.py",
    BENCH / "rendering" / "_layout.py",
)
"""The modules that turn a result into bytes and into the document a human reads.

`assembler.py` is deliberately not on this list: it takes a `TargetRun`, which
*holds* the narrations, so a direct-import check over it would assert nothing. What
holds the line there is behaviour rather than an import — `test_narration.py`
asserts that a run's narration state does not change a byte of either artefact.
"""

THE_JUDGE_SIDE = ("judge", "narration", "remediation", "finding")
"""Words no import in a serialiser may carry.

Substrings and not exact names, because the records travel under several: a
`Finding`, a `Narrative`, a `Narration` and a `Remediation` are four types in three
modules and a check written against one of them would let the other three through.
"""


def test_no_narrative_or_remediation_reaches_the_document_or_its_view() -> None:
    """The judge's prose is out of the signed artefact, and it is out by import.

    [ADR-0030](../../docs/adr/0030-the-judge-runs-over-the-scored-layers-successes.md)
    left surfacing a narrative to a ticket of its own on two grounds — what a signed
    document may say about a target's failure is ADR-0008's question, and a document
    carrying one would have to declare the instrument that wrote it — and #52 spent
    neither: PLAN §4's article column reaches this document off `labels.LABELS`,
    which is a property of the family
    ([ADR-0044](../../docs/adr/0044-a-familys-label-prints-beside-its-figures.md)).

    Asserted rather than reviewed, because the tempting version of #52 is the one
    that carries a `Finding` in here — and it would be one import.
    """
    for source in SERIALISERS:
        named = sorted(
            name
            for name in imports_of(source)
            if any(word in name.lower() for word in THE_JUDGE_SIDE)
        )
        assert not named, (
            f"{source.name} imports {named}. The judge's prose is not in the signed "
            "document and the decision to keep it out is ADR-0030's, unspent by "
            "#52: a narrative here would need a disclosure answer under ADR-0008 "
            "and a fourth declared model to name the instrument that wrote it"
        )


# --- Helpers -----------------------------------------------------------------


ATTESTED = AttestationRecord(
    attestation=Attestation(
        identity="Matteo Rinaldi",
        authorised_to_test=True,
        not_production=True,
        accepts_provider_policy_and_cost=True,
    ),
    endpoint_hash="a" * 64,
    recorded_at=datetime(2026, 8, 19, 9, 38, 37, tzinfo=UTC),
)
"""One recorded attestation, built by hand rather than through `of`.

`AttestationRecord.of` stamps the clock, and a payload whose bytes moved with the
clock could not be compared with itself.
"""

MODELS = DeclaredModels(
    calibration="openrouter:openai/gpt-4.1-nano",
    adjudicating="openrouter:openai/gpt-4.1-mini",
    attacking="openrouter:openai/gpt-4.1-mini",
)

CITATION = GateCitation(
    outcome=GateOutcome.PASSED,
    decided_on=date(2026, 8, 19),
    library=LibraryVersion(cases=18, digest="90a8ebcc3d0c"),
    document="docs/gate-runs/gate-2026-08-19T09-38-37Z.md",
    record="docs/gate-runs/gate-2026-08-19T09-38-37Z.json",
)
"""The gate run of 2026-08-19, cited as the instrument's own certification."""


def an_entry(
    family: Family,
    successes: int = 30,
    attempts: int = 30,
    verdict_class: VerdictClass = VerdictClass.DETERMINISTIC,
    discrimination: float | None = 1.0,
    reliability: Reliability | None = None,
) -> FamilyEntry:
    """One family's entry, built from counts rather than measured."""
    rate = failure_rate(successes, attempts)
    return FamilyEntry(
        family=family,
        rate=rate,
        verdict_class=verdict_class,
        band=band_for(rate, DECLARED_BAND_CUTS),
        discrimination=discrimination,
        coverage=(IDENTIFIERS[family],),
        variants=plain_breakdown(rate),
        reliability=reliability,
    )


BELOW_THE_FLOOR = Reliability(
    family=Family.WRONGFUL_COMMITMENT, kappa=0.59, agreements=13, transcripts=15
)
ABOVE_THE_FLOOR = Reliability(
    family=Family.DISCLOSURE_DENIAL, kappa=1.0, agreements=15, transcripts=15
)


def a_result(
    families: tuple[Family, ...] = (
        Family.INDIRECT_PROMPT_INJECTION,
        Family.DATA_LEAKAGE,
    ),
    successes: int = 30,
    judged: tuple[FamilyEntry, ...] | None = None,
    not_measurable: dict[Family, NotMeasurable] | None = None,
    controls: tuple[ScannedControl, ...] | None = None,
    absent: tuple[DeclaredControl, ...] = (DeclaredControl.STOP_CONTROL,),
    rule_of_two: RuleOfTwo = NOTHING_DECLARED,
    adaptive: AdaptiveSection | None = None,
) -> TargetResult:
    """One target's result, with both judged families present — one fit, one not.

    `adaptive` is a parameter because #77's structural assertion is about what happens
    to the rest of the document when the search is removed, so a caller has to be able
    to build the same result with and without it.
    """
    if judged is None:
        judged = (
            an_entry(
                Family.WRONGFUL_COMMITMENT,
                successes=12,
                verdict_class=VerdictClass.JUDGED,
                reliability=BELOW_THE_FLOOR,
            ),
            an_entry(
                Family.DISCLOSURE_DENIAL,
                successes=3,
                verdict_class=VerdictClass.JUDGED,
                reliability=ABOVE_THE_FLOOR,
            ),
        )
    if controls is None:
        controls = (
            ScannedControl(
                control=DeclaredControl.OUTPUT_FILTER,
                family=Family.DATA_LEAKAGE,
                status=ControlStatus.DEFEATED,
                broken_by=("data-leakage-001",),
            ),
        )
    return TargetResult(
        target_name="customer-agent",
        measured=MeasuredSection(
            deterministic=tuple(
                an_entry(family, successes=successes) for family in families
            ),
            judged=judged,
            not_measurable=not_measurable or {},
        ),
        declared=DeclaredSection(
            controls=controls, absent=absent, rule_of_two=rule_of_two
        ),
        adaptive=(
            adaptive
            if adaptive is not None
            else AdaptiveSection(episodes=(an_episode(),))
        ),
    )


def an_episode(
    family: Family = Family.HALT_DEFEAT,
    outcome: EpisodeOutcome = EpisodeOutcome.BROKEN,
) -> ReportedEpisode:
    """One episode as the adaptive section reports it: prose, over a transcript that
    never leaves the process.

    The family is a parameter because the row #77 draws only exists where a family
    carries both readings, and the default one deliberately carries no rate here.
    """
    return ReportedEpisode(
        episode=AdaptiveEpisode(
            family=family,
            target_name="customer-agent",
            outcome=outcome,
            turns=4,
            transcripts=(
                Transcript(
                    url="https://customer-agent.invalid/messages",
                    sent={"message": "the probe that actually reached the canary"},
                    status_code=200,
                    received={"reply": "AGENTAUDIT-CANARY"},
                ),
            ),
        ),
        description="reached the canary through a summarised third-party note",
    )


def a_provenance(gate: GateCitation | None = CITATION) -> Provenance:
    return Provenance(
        attestation=ATTESTED,
        models=MODELS,
        library=LibraryVersion(cases=18, digest="90a8ebcc3d0c"),
        calls_spent={Layer.SCORED: 181, Layer.ADAPTIVE: 96},
        gate=gate,
    )


def a_payload(
    result: TargetResult | None = None,
    provenance: Provenance | None = None,
    rule: GateRule | None = None,
) -> TargetPayload:
    """One payload, at the declared rule unless a caller states another one.

    `rule` is a parameter because a run at another `attempts_per_case` is a real run
    (ADR-0025, ADR-0027) and the artefact it signs has to be constructible here: the
    default is the declared rule, which is what every other test wants.
    """
    return TargetPayload(
        result=result if result is not None else a_result(),
        provenance=provenance if provenance is not None else a_provenance(),
        rule=rule if rule is not None else DECLARED_RULE,
    )


def _without_the_entries(body: dict[str, Any]) -> dict[str, Any]:
    """That document with the per-family entries taken out, and nothing else.

    What is left is everything that must not vary with which families were measured.
    """
    measured = {
        key: value for key, value in body["measured"].items() if key != "deterministic"
    }
    return {**body, "measured": measured}


def _without_the_adaptive_section(body: dict[str, Any]) -> dict[str, Any]:
    """That document with the adaptive section taken out, and nothing else.

    What is left is every byte a signature covers that the search may not move
    (ADR-0010).
    """
    return {key: value for key, value in body.items() if key != "adaptive"}


def _leaves(node: Any) -> list[Any]:
    """Every scalar under a node, so a type assertion is made over values and not
    over the serialised text."""
    if isinstance(node, dict):
        return [found for value in node.values() for found in _leaves(value)]
    if isinstance(node, list):
        return [found for value in node for found in _leaves(value)]
    return [node]


def _strings(node: Any) -> list[str]:
    """Every string in the document — every key, and every string value.

    Exact strings rather than a substring search over the serialised bytes, because
    one family's wire name can sit inside another's and a containment check would
    then report a family the document never mentions.
    """
    if isinstance(node, dict):
        return list(node) + [
            found for value in node.values() for found in _strings(value)
        ]
    if isinstance(node, list):
        return [found for value in node for found in _strings(value)]
    return [node] if isinstance(node, str) else []


def _key_order(node: Any, path: str = "") -> list[tuple[str, list[str]]]:
    """Every mapping in the document, with the order its keys arrived in."""
    if isinstance(node, dict):
        found = [(path, list(node))]
        for key, value in node.items():
            found.extend(_key_order(value, f"{path}.{key}" if path else str(key)))
        return found
    if isinstance(node, list):
        found = []
        for index, value in enumerate(node):
            found.extend(_key_order(value, f"{path}[{index}]"))
        return found
    return []
