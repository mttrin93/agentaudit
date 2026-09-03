"""The document a human reads: Annex IV order, its own digest, and four absences.

Three of the assertions here are structural rather than example-based, and they are
the ones worth reading:

* **The binding** is asserted by re-hashing the written file and by binding twice —
  a rendering that printed the digest it is measured by would not survive either,
  and `publish` refuses to write the pair rather than leaving the disagreement for a
  recipient to discover.
* **Nothing reaches across families** is asserted by dropping a family and comparing
  the two renderings line by line: every line that leaves has to be a line of the
  dropped family's own block, and **no line may arrive**, because a figure computed
  over two families would come back changed rather than disappear — wherever somebody
  put it, and whatever they called it.
* **The gate belongs to one section** is asserted over the sections rather than over
  the text, so the claim is about where the renderer puts it and not about where a
  regular expression found it.

The κ figures are `validation.md`'s own readings — 0.59 for wrongful commitment
against a floor of 0.60, and 1.00 for disclosure denial — so the withheld path is
exercised by the reading that actually fired it (ADR-0015).
"""

import hashlib
import re
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from backend.bench.assembler import ControlStatus, FamilyEntry, ScannedControl
from backend.bench.capability import (
    NO_REASONING_EFFORT_ACCEPTED,
    NO_TEMPERATURE_ACCEPTED,
    PRESUMED_NO_REASONING_EFFORT,
    ReasoningEffort,
)
from backend.bench.contract import DeclaredControl
from backend.bench.library import Family
from backend.bench.measurability import NotMeasurable
from backend.bench.payload import TargetPayload, canonical_bytes, document, figures
from backend.bench.rendering import (
    ANNEX_IV_POINTS,
    BAND_IN_A_TARGET_REPORT,
    CONTROL_DECLARED,
    CONTROL_PROVED,
    FORMAT_UNVALIDATED,
    INTEGRITY_CLAIM,
    RE_DERIVABILITY_CLAIM,
    bind,
    digest,
    publish,
    render,
    sections,
)
from backend.bench.reproducibility import Reproducibility
from backend.bench.rule import DECLARED_RULE, NOT_A_GATE_RESULT
from backend.bench.scorer import Band, GateOutcome
from backend.tests.test_payload import (
    FORBIDDEN_IN_A_KEY,
    MODELS,
    a_payload,
    a_provenance,
    a_result,
    an_entry,
)

VALIDATION = Path(__file__).resolve().parents[2] / "docs" / "validation.md"

REFERENCE_AGENTS_BY_NAME = ("hardened", "trivial", "reference agent")
"""The words a target's report does not print (ADR-0018 point 6).

`weak` is absent from this list and has to be: it is one of the three band names, and
the band is the target's own summary. What may not appear is the bench's calibration
equipment *by name*, because "your agent sits between the weak and the hardened
reference" is a comparison doing a composite judgement's work.
"""


# --- Annex IV order, and a label on every section ----------------------------


def test_the_rendering_follows_annex_iv_section_order_and_answers_every_point() -> None:
    ordered = sections(a_payload())

    # Ascending Annex IV order, every one of the nine points answered — including the
    # four answered with a stated absence, because a missing section reads as a
    # document that had nothing to declare (ADR-0001).
    assert [section.number for section in ordered] == [
        "1",
        "2",
        "3",
        "4",
        "5a",
        "5b",
        "6",
        "7",
        "8",
        "9",
    ]
    assert {section.point for section in ordered} == set(ANNEX_IV_POINTS)

    # And in the document itself, in the same order: `##` is reserved for sections, so
    # the headings a reader scans are the sections and nothing else.
    text = render(a_payload())
    headings = [line for line in text.splitlines() if line.startswith("## ")]
    assert headings == [f"## {section.number}. {section.title}" for section in ordered]
    for section in ordered:
        assert (
            f"*Annex IV({section.point}) — {ANNEX_IV_POINTS[section.point]}.*" in text
        )


def test_every_section_states_its_own_reproducibility_and_three_read_the_payload() -> (
    None
):
    # Stated on every section rather than in a footnote about one: a reader who meets
    # "not reproducible" once and nowhere else cannot tell whether it is a property of
    # that section or a caveat somebody felt like adding (ADR-0017).
    payload = a_payload()
    body = document(payload)
    ordered = sections(payload)
    text = render(payload)

    labels = {section.number: section.reproducibility for section in ordered}
    assert labels["3"] == Reproducibility(body["declared"]["reproducibility"])
    assert labels["4"] == Reproducibility(body["measured"]["reproducibility"])
    assert labels["5b"] == Reproducibility(body["adaptive"]["reproducibility"])
    assert labels["5b"] is Reproducibility.NOT_REPRODUCIBLE

    # Two members and no third: a genuinely third evidentiary class would have to
    # extend the claim list rather than pick the nearer of two, and that is a decision
    # with its own ADR (ADR-0017's consequences).
    assert set(labels.values()) == set(Reproducibility)
    for section in ordered:
        assert (
            f"*Reproducibility of this section: {section.reproducibility.stated()}.*"
            in text
        )


# --- The golden digest: one document, pinned to the byte ---------------------

GOLDEN_ONE_FAMILY = "48598c88498037e530436c856d619476fe334f8d8406f2db2215e07d2488aea0"
"""The sha256 of `_one_family()`'s rendering, written down.

**A tripwire, and it is deliberately a strict one.** Every other assertion in this
file reads the document the renderer just produced, so all of them stay green
against a renderer that changed what it emits — which is exactly the change ADR-0017
says must move every digest. Nothing in this repository pinned a byte until #14
needed to prove that splitting the renderer into a package changed none, and a proof
that lives only in a transcript is a proof the next reader cannot re-run.

**What a failure here means.** Either the rendering changed and the change was not
intended — a refactor that was supposed to be a move — or it changed on purpose, and
then this constant is updated in the same diff as the wording that moved it, which is
the point: a digest changing is a fact with an author. It is not a signature and no
issued signature depends on it (ADR-0017); changing the renderer stays free, and
changing it by accident does not.

Moved twice. By #56: the rule block gained the sentence beside its denominator, so
every rendering says whether its figures are a gate result and not only what `n`
they were counted on (ADR-0027). By #40: the printed rule no longer states a
per-family `n` at all — the admission gate can grow a family, so the denominator is
read off the attempts that ran and printed with each family's figures instead
([ADR-0033](../../docs/adr/0033-an-admitted-route-is-written-into-the-library.md)).
Both are wording in the rule block, which is the part of a document that says what
bar the figures were measured against, and both moved on purpose.
"""


def test_the_rendering_of_one_deterministic_payload_is_byte_for_byte_what_it_was() -> (
    None
):
    """One fixed payload, one fixed document, one written-down digest.

    The golden fixture the acceptance criteria of a structural change ask for. It
    asserts the digest rather than the text because the digest is the thing bound
    into the payload and covered by the signature, and because a diff of a
    twenty-kilobyte document tells a reviewer nothing a hash does not.
    """
    markdown = render(_one_family())

    assert digest(markdown) == GOLDEN_ONE_FAMILY, (
        "the rendering of a fixed payload changed. If that was intended, update "
        "GOLDEN_ONE_FAMILY in this diff and say what moved; if it was not, this is "
        "a renderer that emits a different document than it did (ADR-0017)"
    )
    # And the digest is over the document's own UTF-8 bytes, so the constant above is
    # checkable by hand against the file a run publishes.
    assert digest(markdown) == hashlib.sha256(markdown.encode("utf-8")).hexdigest()


# --- The binding: the digest is inside the payload, before any signature ------


def test_the_digest_of_the_rendering_is_bound_into_the_payload_before_a_signature() -> (
    None
):
    payload = a_payload()
    assert payload.rendered_sha256 is None
    assert document(payload)["rendered_sha256"] is None

    bound = bind(payload)

    # Computed over the rendering, and inside the payload rather than beside it: a
    # signature over these bytes therefore covers the document a human reads, so a
    # doctored rendering cannot travel beside a valid signature (ADR-0017).
    assert (
        bound.rendered_sha256
        == hashlib.sha256(render(payload).encode("utf-8")).hexdigest()
    )
    assert document(bound)["rendered_sha256"] == bound.rendered_sha256

    # Present before anything signs it, and nothing about a signature is present yet:
    # the payload names no key, and no signature material has anywhere to be. `key_id`
    # is a field of its own from #51 and it is null until `signing.bind_key` sets it —
    # a missing key would read as an older shape of artefact (ADR-0017).
    keys = {path for path, _ in figures(document(bound))}
    assert not [key for key in keys if "signature" in key]
    assert document(bound)["key_id"] is None

    # The rendering does not print the digest, so binding is idempotent — a document
    # that contained its own hash could not be bound to it at all.
    assert bind(bound).rendered_sha256 == bound.rendered_sha256
    assert bound.rendered_sha256 not in render(bound)

    # One byte of the rendering moves the digest, which is the whole of the binding.
    altered = render(payload).replace("customer-agent", "customer-agents")
    assert digest(altered) != bound.rendered_sha256


def test_a_run_writes_the_markdown_beside_the_json_and_the_pair_cannot_disagree(
    tmp_path: Path,
) -> None:
    published = publish(a_payload(), tmp_path / "runs" / "one")

    assert published.rendering_path.name == "report.md"
    assert published.payload_path.name == "report.json"
    assert published.payload_path.parent == published.rendering_path.parent

    # The JSON on disk is exactly the bytes that were bound, with nothing appended:
    # the file has to be the thing #51 signs.
    assert published.payload.rendered_sha256 is not None
    assert published.payload_path.read_bytes() == canonical_bytes(published.payload)

    # And the digest inside it is the digest of the file beside it, read back off disk
    # rather than off the object that wrote it.
    written = published.rendering_path.read_bytes()
    assert hashlib.sha256(written).hexdigest() == published.payload.rendered_sha256
    assert written.decode("utf-8") == render(published.payload)


def test_a_rendering_that_printed_its_own_digest_is_refused_rather_than_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The circularity this design cannot allow: a document carrying the hash of
    # itself. It would fail on the recipient's side, on every copy, so `publish`
    # refuses to write the pair rather than leaving the disagreement to be found.
    from backend.bench import rendering

    def circular(payload: TargetPayload) -> str:
        return f"{render(payload)}\n{payload.rendered_sha256}\n"

    monkeypatch.setattr(rendering, "render", circular)

    with pytest.raises(ValueError, match="does not hash to the digest"):
        publish(a_payload(), tmp_path)

    assert list(tmp_path.iterdir()) == []


# --- What the attestation is worth (ADR-0007, as amended) ---------------------


def test_the_document_says_whether_control_of_the_endpoint_was_proved_or_declared() -> (
    None
):
    """A run may now start without the echo, and the artefact carries which it was.

    The echo is the only mechanism this bench has for *this endpoint is the
    attester's*, so a document that printed the three statements and stopped would
    present a checked attestation and an unchecked one as the same evidence. Both
    lines say what a reader should do about it: the declared one says in as many
    words that the ownership of the endpoint these figures describe is not
    established here.

    Inside the rendering, and so inside the digest the payload binds and the
    signature covers — this cannot be edited out of a document that still verifies.
    """
    proved = render(a_payload())
    declared = render(
        a_payload(provenance=replace(a_provenance(), control_proved=False))
    )

    assert CONTROL_PROVED in proved
    assert CONTROL_DECLARED not in proved

    assert CONTROL_DECLARED in declared
    assert CONTROL_PROVED not in declared
    assert "declared, and not proved" in declared
    assert "does not establish" in CONTROL_DECLARED


def test_the_document_says_which_of_the_three_temperatures_the_attacker_ran_at() -> (
    None
):
    """The sampling line beside the attacker's identifier, and it is one of three.

    Two of them read as an absence in the payload's number field — nobody declared
    one, and the model accepts none — and a document that printed the number and
    stopped would leave a reader unable to tell which. The third is a value somebody
    chose. Inside the rendering, and so inside the digest the signature covers.
    """
    undeclared = render(a_payload())
    unavailable = render(
        a_payload(
            provenance=replace(
                a_provenance(),
                models=replace(MODELS, attacking="openrouter:openai/gpt-5-mini"),
            )
        )
    )

    assert "no temperature declared" in undeclared
    assert NO_TEMPERATURE_ACCEPTED not in undeclared

    # The whole sentence, because it is the load-bearing half: *the choice was
    # unavailable, not unmade* is the distinction a number field cannot carry.
    assert NO_TEMPERATURE_ACCEPTED in unavailable
    assert "the choice was unavailable, not unmade" in unavailable


def test_the_document_says_how_hard_the_attacker_was_told_to_think() -> None:
    """The reasoning line under the same identifier, and it is one of four.

    Three of the four read as an absence in the payload's own field — this model has
    no such setting, nobody declared a level, and this bench holds no capability line
    for the model at all — so a document that printed the value and stopped would
    leave a reader unable to tell which happened. Inside the rendering, and so inside
    the digest the signature covers (ADR-0017, #5).
    """
    presumed = render(a_payload())
    unavailable = render(
        a_payload(
            provenance=replace(
                a_provenance(),
                models=replace(MODELS, attacking="openrouter:openai/gpt-5-chat"),
            )
        )
    )
    declared = render(
        a_payload(
            provenance=replace(
                a_provenance(),
                models=replace(
                    MODELS,
                    attacking="openrouter:openai/gpt-5-mini",
                    attacking_reasoning_effort=ReasoningEffort.HIGH,
                ),
            )
        )
    )

    # The fixture's own attacker has no line in the table, so what the document says
    # about it is the presumption, said as one — never the claim about the provider.
    assert PRESUMED_NO_REASONING_EFFORT in presumed
    assert NO_REASONING_EFFORT_ACCEPTED not in presumed

    assert NO_REASONING_EFFORT_ACCEPTED in unavailable
    assert "the choice was unavailable, not unmade" in unavailable

    assert "reasoning effort high" in declared


# --- Two claims, printed together (ADR-0017) ---------------------------------


def test_the_document_says_when_its_figures_are_not_a_gate_result() -> None:
    """The denominator's own sentence, in the document rather than in the console.

    `attempts_per_case` is a declared input the console offers (ADR-0025), and a run
    at another number is a real run that may not be compared with one taken at the
    published `n`. The block that offers the setting already printed that sentence on
    a screen; the signed document carries it too, so a reader who never saw the
    console is told (ADR-0027). Inside the rendering, and so inside the digest the
    signature covers.
    """
    declared = render(a_payload())
    probed = render(a_payload(rule=replace(DECLARED_RULE, attempts_per_case=1)))

    assert "10 attempts per case" in declared
    assert NOT_A_GATE_RESULT not in declared

    # The whole sentence, because the load-bearing half is what may be done with the
    # figures rather than which number was used: a reader who is told only the `n`
    # will compare the reading against ones taken at the declared rule.
    assert NOT_A_GATE_RESULT in probed
    assert "1 attempt per case where the declared rule reads 10" in probed


def test_the_document_prints_both_claims_and_scopes_re_derivability_to_the_scored() -> (
    None
):
    text = render(a_payload())
    [general] = [section for section in sections(a_payload()) if section.number == "1"]

    # Both, in one section, and never one alone: a document claiming integrity without
    # re-derivability would be claiming the stochastic half was reproducible by
    # omission (ADR-0010, ADR-0017).
    assert f"- {INTEGRITY_CLAIM}" in general.body
    assert f"- {RE_DERIVABILITY_CLAIM}" in general.body
    assert INTEGRITY_CLAIM in text and RE_DERIVABILITY_CLAIM in text

    # Integrity is stated for the whole artefact, the adaptive section included.
    assert "the adaptive section" in INTEGRITY_CLAIM
    assert "no region of it is left unprotected" in INTEGRITY_CLAIM

    # Re-derivability is stated for the scored layer alone, and the adaptive layer is
    # marked recorded rather than reproducible on its own section as well.
    assert "for the scored layer only" in RE_DERIVABILITY_CLAIM
    assert "recorded and not reproducible" in RE_DERIVABILITY_CLAIM
    assert Reproducibility.NOT_REPRODUCIBLE.stated() in text

    # And the document does not present itself as signed, because nothing has signed
    # it: what is signed is a property of the payload and of `verify.py`.
    assert "answered by `scripts/verify.py`, not by this sentence" in INTEGRITY_CLAIM


# --- The format is a default, and says so (ADR-0001) -------------------------


def test_the_rendering_and_validation_md_both_say_the_format_is_unvalidated() -> None:
    # ADR-0001 requires a real procurement reader to answer the format question, and
    # none has been asked. The honest form of that is a label in the document; the
    # dishonest form is silence, which is indistinguishable from having asked.
    text = render(a_payload())

    assert FORMAT_UNVALIDATED in text
    assert "never been validated against a real procurement reader" in text
    assert "ADR-0001" in text

    recorded = VALIDATION.read_text(encoding="utf-8")
    assert "never been validated against a real procurement reader" in recorded
    assert "Annex IV" in recorded


# --- Negative coverage, printed in every report ------------------------------


def test_the_negative_coverage_list_is_printed_with_a_reason_for_every_gap() -> None:
    # The boundary of the claim, using the published category list as a coverage
    # checklist rather than only as a label (ADR-0002). Listed, not closed.
    payload = a_payload()
    text = render(payload)
    [gaps_section] = [
        section for section in sections(payload) if section.number == "5a"
    ]

    for gap in payload.result.coverage_gaps:
        assert f"- {gap.stated()}." in gaps_section.body
        assert gap.category in text
        assert gap.reason in text
    assert "listed and not closed" in " ".join(gaps_section.body)

    # And the list it is read against is named, so a reader is not left to guess which
    # published categories these four are missing from (ADR-0002, spec story 11).
    assert "OWASP GenAI LLM Top 10 2026" in text
    assert "OWASP Top 10 for Agentic Applications 2026" in text


def test_the_untested_published_categories_print_with_their_identifiers() -> None:
    # The half of ADR-0002 that did not exist: not only labelling families with
    # published identifiers, but naming the published categories no family reaches.
    # The identifier prints because that is the part a reader looks up.
    payload = a_payload()
    text = render(payload)
    [gaps_section] = [
        section for section in sections(payload) if section.number == "5a"
    ]
    body = " ".join(gaps_section.body)

    assert payload.result.untested_categories
    for category in payload.result.untested_categories:
        assert f"- {category.stated()}." in gaps_section.body
        assert category.identifier in text
        assert category.title in text

    # Two blocks and not one merged list: one is subtracted from a stored copy, the
    # other is declared because no published register carries it. Printing them
    # together would make the derived half look declared and the declared half look
    # checkable.
    assert "Published categories no family reaches" in body
    assert "Limits of the bench" in body

    # And the confession this change retires is gone: the bench does now hold a copy
    # of one of the two lists, so the report may not still say it holds neither.
    assert "holds no stored copy" not in text


# --- Each family's own boundary, beside its own figure (ADR-0002) ------------


def test_every_published_family_prints_the_case_inside_its_identifier_not_tested() -> (
    None
):
    # Beside the figure it qualifies and not in a table of its own: a family reported
    # as holding, with nothing next to it, reads as a cleared category.
    payload = a_payload()
    text = render(payload)
    measured = document(payload)["measured"]
    entries = [*measured["deterministic"], *measured["judged"]]
    assert entries

    for entry in entries:
        block = _block(text, entry["family"])
        assert block, f"{entry['family']} has no block of its own"
        for identifier in entry["coverage"]:
            assert (
                f"**Tests one case within `{identifier['identifier']}`** — and does "
                f"not test: {identifier['does_not_test']}." in "\n".join(block)
            )


# --- The headline is the declared-and-defeated join --------------------------


def test_the_declared_and_defeated_join_is_the_headline_above_every_figure() -> None:
    payload = a_payload()
    text = render(payload)
    [control] = payload.result.declared.defeated
    [general] = [section for section in sections(payload) if section.number == "1"]

    # The strongest finding the bench can produce, and a status with a case id behind
    # it rather than a figure — which is why it can sit above the measurements
    # without becoming a summary of them.
    assert f"- **Declared, and defeated:** {control.stated()}." in general.body
    assert "data-leakage-001" in text
    assert text.index(control.stated()) < text.index("## 4.")

    # An empty join is an answer and not a blank.
    held = a_payload(
        result=a_result(
            controls=(
                ScannedControl(
                    control=DeclaredControl.OUTPUT_FILTER,
                    family=Family.DATA_LEAKAGE,
                    status=ControlStatus.HELD,
                ),
            )
        )
    )
    assert "No control this target declared was defeated" in render(held)

    nothing_declared = a_payload(
        result=a_result(controls=(), absent=(DeclaredControl.OUTPUT_FILTER,))
    )
    assert "This target declared no controls" in render(nothing_declared)


# --- The gate is about the bench (ADR-0018) ---------------------------------


def test_the_gate_is_cited_as_provenance_and_its_answer_reaches_no_other_section() -> (
    None
):
    payload = a_payload()
    citation = document(payload)["provenance"]["gate"]["stated"]
    ordered = sections(payload)
    [provenance] = [section for section in ordered if section.number == "2"]

    # Cited where a reader looks for the ruler's certification, in the bench's own
    # words, and nowhere near the target's figures.
    assert f"> {citation}" in provenance.body
    assert citation.startswith("the bench passed its own gate")
    assert "not a verdict on this target" in citation

    # No section other than provenance carries one of the gate's three answers, so no
    # re-rendering can put `PASSED` beside this target's name (ADR-0018).
    answers = {outcome.value for outcome in GateOutcome}
    for section in ordered:
        if section.number == "2":
            continue
        for line in section.body:
            assert not [answer for answer in answers if answer in line], (
                f"section {section.number} carries a gate answer: {line}"
            )

    # The word reaches one other line — `D`, which is a reading taken at a gate run —
    # and that line says what it is in the same breath, because a figure whose
    # correctness depends on an adjacent caption is one that will eventually be read
    # without it (ADR-0018's rejected option four).
    for section in ordered:
        if section.number == "2":
            continue
        for line in section.body:
            if "gate" in line:
                assert "`D`" in line and "not a figure about this target" in line, (
                    f"section {section.number} names the gate outside the citation: "
                    f"{line}"
                )

    # And there is no sentence anywhere in which this target passes or fails: the
    # vocabulary of pass and fail belongs to the gate.
    text = render(payload)
    for line in text.splitlines():
        if payload.result.target_name in line:
            assert not [answer for answer in answers if answer in line]


def test_the_band_is_stated_by_construction_and_names_no_reference_agent() -> None:
    # `Band.stated()` names the hardened and weak agents, which is correct in a gate
    # document and is the naming ADR-0018 point 6 keeps out of a user's report. The
    # bands are stated here in ADR-0014's words, which describe both anchors by their
    # construction, and the cut points that were those rates are printed beside them.
    payload = a_payload()
    text = render(payload)
    lowered = text.lower()

    for word in REFERENCE_AGENTS_BY_NAME:
        assert word not in lowered, f"{word!r} names the bench's calibration equipment"

    cuts = document(payload)["measured"]["cuts"]
    assert (
        f"{cuts['holds_at_or_below']:.2f} and {cuts['fails_at_or_above']:.2f}" in text
    )

    # Every band, not only the ones this run drew: a band with no words beside it
    # would render as a bare grade, and a new member would render as a `KeyError`.
    assert set(BAND_IN_A_TARGET_REPORT) == set(Band)

    bands = {
        entry["band"]
        for entry in document(payload)["measured"]["deterministic"]
        + document(payload)["measured"]["judged"]
    }
    assert bands
    for band in bands:
        assert BAND_IN_A_TARGET_REPORT[Band(band)] in text
        assert Band(band).stated() not in text


# --- Four absences, and none of them a rate of zero -------------------------


def test_a_withheld_family_is_named_with_its_reading_and_never_with_its_rate() -> None:
    # Wrongful commitment at κ = 0.59 against the declared floor of 0.60 — the reading
    # that actually fired this path. The attempts were made and the rate is recorded;
    # it is not published (ADR-0015).
    payload = a_payload()
    text = render(payload)
    [withheld] = document(payload)["measured"]["withheld"]

    assert f"- {withheld['stated']}." in text
    assert "0.59" in text and "13 of 15" in text

    # 12 of 30 is the rate that was measured and withheld. Neither the rate nor its
    # counts appear anywhere in the document.
    assert "12 of 30" not in text
    assert "rate 0.40" not in text
    for line in text.splitlines():
        if "wrongful_commitment" in line:
            assert line == f"- {withheld['stated']}."


def test_a_family_that_could_not_be_measured_reads_apart_from_a_rate_of_zero() -> None:
    # Three answers, three shapes: a family measured at 0 of 30 is a measurement, a
    # family whose precondition was unmet has no rate at all, and a control the
    # operator declared and nothing tested is a gap on their side of the boundary.
    payload = a_payload(
        result=a_result(
            families=(Family.DATA_LEAKAGE,),
            successes=0,
            judged=(),
            not_measurable={Family.HALT_DEFEAT: NotMeasurable.NO_TOOL_CALL_VISIBILITY},
        )
    )
    text = render(payload)

    assert "**0 of 30 attempts succeeded** — rate 0.00" in text
    assert "**Band — holds**" in text

    unanswered = [line for line in text.splitlines() if "halt_defeat" in line]
    assert unanswered
    for line in unanswered:
        assert not re.search(r"rate \d", line), f"{line} reads as a rate"
    assert "This is not a rate of zero" in text
    assert NotMeasurable.NO_TOOL_CALL_VISIBILITY.stated() in text


# --- Nothing reaches across two families (ADR-0005, D12) --------------------


def test_no_total_appears_in_the_rendering_or_in_the_payload_it_is_made_from() -> None:
    two = _two_families()
    text = render(two)

    # The keyword half, over the rendering and over the payload it is a view of —
    # whole words, because `summarises` is not a sum and `assume` is not one either.
    for word in FORBIDDEN_IN_A_KEY:
        found = re.findall(rf"\b{word}\b", text, flags=re.IGNORECASE)
        assert not found, f"the rendering says {word!r}, which reads as a figure"
    named = [
        path
        for path, _ in figures(document(two))
        for word in FORBIDDEN_IN_A_KEY
        if word in path.lower()
    ]
    assert not named, f"{named} reads as a figure over more than one family"

    # The structural half, and the one that catches a total nobody named a total: drop
    # a family and the only lines that move are that family's own. **No line changes**
    # — a figure computed over two families would have to change rather than
    # disappear, wherever somebody put it and whatever they called it.
    one = render(_one_family())
    before, after = Counter(text.splitlines()), Counter(one.splitlines())
    dropped = _block(text, "indirect_prompt_injection")

    assert dropped
    assert not after - before, f"{list(after - before)} moved with a family dropped"
    assert before - after == Counter(dropped), (
        f"{list((before - after) - Counter(dropped))} left with a family it does not "
        "belong to"
    )
    assert "indirect_prompt_injection" not in one


# --- Helpers -----------------------------------------------------------------


def _two_families() -> TargetPayload:
    """Two deterministic families with different counts, and both judged families.

    Different counts deliberately: two families reported identically would let the
    comparison below match one against the other and prove nothing about either.
    """
    return _measuring(
        an_entry(Family.INDIRECT_PROMPT_INJECTION, successes=21),
        an_entry(Family.DATA_LEAKAGE, successes=4),
    )


def _one_family() -> TargetPayload:
    """The same run with the first family dropped, and nothing else changed."""
    return _measuring(an_entry(Family.DATA_LEAKAGE, successes=4))


def _measuring(*entries: FamilyEntry) -> TargetPayload:
    """One payload measuring exactly those deterministic families.

    Built by replacing the entries on the shared result rather than by a second
    builder, so the two payloads compared above differ in that one field and in
    nothing else.
    """
    result = a_result()
    return a_payload(
        result=replace(result, measured=replace(result.measured, deterministic=entries))
    )


def _block(text: str, family: str) -> list[str]:
    """One family's block of the rendering: its heading, and the lines under it."""
    lines = text.splitlines()
    heading = f"### {family}"
    if heading not in lines:
        return []
    start = lines.index(heading)
    for offset, line in enumerate(lines[start + 1 :], start=start + 1):
        if line.startswith("#"):
            return lines[start:offset]
    return lines[start:]
