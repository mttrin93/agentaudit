"""The document a human reads: Annex IV order, its own digest, and five absences.

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
from backend.bench.contract import AgentCapability, DeclaredControl
from backend.bench.editions import AGENTIC_TOP_10_2026, LLM_TOP_10_2026
from backend.bench.elective import ElectiveSelection
from backend.bench.library import ElectiveFamily, Family
from backend.bench.measurability import NotMeasurable
from backend.bench.payload import TargetPayload, canonical_bytes, document, figures
from backend.bench.rendering import (
    ANNEX_IV_POINTS,
    BAND_IN_A_TARGET_REPORT,
    CONTROL_DECLARED,
    CONTROL_PROVED,
    FORMAT_UNVALIDATED,
    INTEGRITY_CLAIM,
    PUBLISHED_RULE_OF_TWO,
    RE_DERIVABILITY_CLAIM,
    bind,
    digest,
    publish,
    render,
    sections,
)
from backend.bench.reproducibility import Reproducibility
from backend.bench.rule import DECLARED_RULE, NOT_A_GATE_RESULT
from backend.bench.scanner import RuleOfTwo, Supervision
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

GOLDEN_ONE_FAMILY = "a0c1893ced05064602bee68ab6d2d73529a3425acde3cbc9909db49d186d8eb6"
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

Moved a third time, by #43, and this one is a new block rather than a rewording:
section 4 gained the elective tier's declared selection and the fifth absence — the
elective families the run was not asked to test — under one heading beside the four
already there
([ADR-0035](../../docs/adr/0035-the-elective-family-tier-is-never-gate-deciding.md)).
Every report gains it, because the tier is declared and a run that requested nothing
from it is a run whose figures are the six and says so.

Moved a fourth time, by #47, and it is the negative-coverage section that moved:
three published categories left the untested list because three families now claim
them, a third block prints each claimed category beside the half of it the claiming
family does not reach, and the section is retitled for what it now holds
([ADR-0037](../../docs/adr/0037-a-claimed-category-is-claimed-in-part.md)). A
coverage claim getting wider is the one direction nobody checks, so the digest moving
here is the intended noise: the section says less about what is untested and more
about where what is claimed stops. The claim lines name no family, which is why the
title moved and no line naming a family did.

Moved a fifth time, by #51, and it is section 3 that grew: the declared-controls
section gained the Agents Rule of Two under a heading of its own, the published rule
stated above one line naming what this target declared about its own shape
([ADR-0038](../../docs/adr/0038-the-rule-of-two-is-a-declared-property.md)). Every
report gains it, including a report about a target that declared nothing — the
absence of the four declarations is what the block then says, and a heading that
appeared only when somebody answered would be indistinguishable from a document made
before the scan asked. It is a declaration and not a finding, so it moved this digest
and moved nothing in section 4.

Moved a sixth time, by #45, and it is the negative-coverage section again. The GenAI
LLM list is now subtracted from as well as the agentic one, so the untested block
gains five entries and the claimed block five more, every published identifier in the
section names its edition, and the paragraph that said the second copy "is not
subtracted from here" is gone because it is no longer true
([ADR-0039](../../docs/adr/0039-a-familys-label-is-one-record.md)). The section gets
longer in both derived blocks at once, which is what a second subtraction costs: five
categories are named as unreached with a reason and five as reached-in-part with a
limit, and no figure anywhere moved.

Moved a seventh time, by #48, and it is one sentence in the negative-coverage section.
`ASI06` Memory & Context Poisoning is still listed as untested and the *reason* beside
it changed: the old one said the elective family carrying its label had no cases on
disk, which stopped being true the day memory poisoning got three. The entry did not
move to the claimed block, because the tier is requested rather than run — a category
printed as covered in every report would be a coverage claim widened on runs that
never asked for the family — ADR-0035, and
[ADR-0018](../../docs/adr/0018-the-report-is-about-a-target-the-gate-is-about-the-bench.md).
Nothing else in the document changed and no figure moved.

Moved an eighth time, by #50, and it is one sentence again — this time in the
*claimed* half of the coverage section rather than the untested half. `LLM02:2026`
Sensitive Information Disclosure is claimed by `data_leakage` and was already printed
as tested in part; what changed is the limit beside it, which said a third party's
data would need a corpus this bench does not put in front of a target and now names
the elective family that holds that half. The entry did not move and no second family
joined the claim, for the reason #48 gave `ASI06`: this block is derived over the
library and printed in every report, including runs never asked for the tier —
ADR-0035, ADR-0018, and
[ADR-0043](../../docs/adr/0043-the-canary-a-nonce-cannot-be-confused-with.md)
decision 4. Nothing else in the document changed and no figure moved.

Moved a ninth time, by #52, and this one is section 4 rather than the coverage
section: **every family the document names now prints the article its failure bears
on under the EU AI Act, and the entries it claims on the two published lists**
([ADR-0044](../../docs/adr/0044-a-familys-label-prints-beside-its-figures.md)). Two
lines inside each family's block, one clause on each withheld family and one on each
unmeasurable one. This is the first time PLAN §4's central column has appeared in the
artefact it was written for — it lived on `judge.Narrative`, which nothing under
`rendering/` reads — so the digest moves for something that was missing rather than
for something reworded. Each claimed entry prints with the title its stored copy
carries, transcribed rather than paraphrased (ADR-0036), and both halves print beside
a family named without a rate as well as beside one with figures: the signed document
travels, so it may not be the surface that says less than the payload it is a view
of. **No figure moved**: the label is read off `labels.LABELS`,
which is a property of the family and not of the run, and `test_narration.py` asserts
that a run's three narration states render to one document.
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


def test_a_claimed_category_prints_beside_the_half_it_does_not_reach() -> None:
    # The block #47 added, and the reason it had to be added: three categories left
    # the untested list because three families claim them, and a document that only
    # dropped them would have made its coverage claim wider and said nothing. Each
    # claimed category prints with the half of it the claiming family does not reach,
    # and never with that family's name (ADR-0037).
    payload = a_payload()
    text = render(payload)
    [gaps_section] = [
        section for section in sections(payload) if section.number == "5a"
    ]

    assert payload.result.claimed_in_part
    for claim in payload.result.claimed_in_part:
        assert f"- {claim.stated()}." in gaps_section.body
        assert claim.identifier in text
        assert claim.not_reached in text
        # And no claim names the family that carries it. This block is derived over
        # the library's families and this document is about one target, which
        # measured two of them here: a family named in the coverage section that the
        # figures above do not carry would read as a family this target was tested on
        # (ADR-0018). The pairing is #45's to print beside a family name.
        #
        # Asserted on the line's exact opening, because a search for the six wire
        # names would pass a line that printed `Wrongful commitment` instead.
        assert claim.stated().startswith(
            f"{claim.identifier} {claim.title} — tested in part;"
        )

    # And the three the file used to argue against are on the claimed side of the
    # section rather than absent from the document: each prints its published title,
    # and none of them is in the untested block. The second assertion reads the
    # payload's own list rather than the untested block's sentence shape, so it does
    # not go quietly true if that sentence is reworded.
    printed = " ".join(gaps_section.body)
    untested = {category.identifier for category in payload.result.untested_categories}
    for identifier, title in (
        ("ASI03:2026", "Identity & Privilege Abuse"),
        ("ASI09:2026", "Human-Agent Trust Exploitation"),
        ("ASI10:2026", "Rogue Agents"),
    ):
        assert f"{identifier} {title} — tested in part" in printed
        assert identifier not in untested


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

    # Both lists are stored (ADR-0036) and both are now subtracted from (#45), so the
    # untested block carries entries from each. Asserted on the payload's own records
    # rather than on the section's prose: the sentence that used to say the LLM copy
    # "is not subtracted from here" was true when it was written, is false now, and an
    # assertion pinned to a phrase goes quietly true the day somebody rewords it.
    assert "no stored copy" not in text
    assert {category.edition for category in payload.result.untested_categories} == {
        AGENTIC_TOP_10_2026.edition,
        LLM_TOP_10_2026.edition,
    }
    # Both editions print off their own copy and neither is spelled out here, so a
    # copy replaced by a later edition cannot leave a report naming the older one.
    assert AGENTIC_TOP_10_2026.edition in body
    assert LLM_TOP_10_2026.edition in body


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


# --- The label beside the family name (ADR-0039, ADR-0040) -------------------


def test_every_family_the_document_names_prints_its_label_beside_the_name() -> None:
    """PLAN §4's central column, in the document it was written for.

    The article had never appeared in a signed report: it lived on
    `judge.Narrative` and nothing under `rendering/` reads a narrative. It prints
    beside the family name, which is where #42 and ADR-0039 said it belonged and
    where `published.ClaimedInPart.stated` already says it is not — the coverage
    section names no family on purpose (ADR-0037 §6), so the pairing happens here,
    where the run's own figures are.

    Asserted inside each family's own block rather than over the whole document,
    because the family names nest as text and a containment check over the page
    would let one family's line answer for another's.
    """
    payload = a_payload()
    text = render(payload)

    injection = "\n".join(_block(text, Family.INDIRECT_PROMPT_INJECTION))
    assert "this family bears article 15 of the EU AI Act" in injection
    assert (
        "it claims ASI01:2026 Agent Goal Hijack on the OWASP agentic list and "
        "LLM01:2026 Prompt Injection on the OWASP GenAI LLM list" in injection
    )

    # True of one article and of two, in the order the label declares: 50 before 13
    # is what no sort produces (ADR-0040 decision 4).
    denial = "\n".join(_block(text, Family.DISCLOSURE_DENIAL))
    assert "this family bears articles 50 and 13 of the EU AI Act" in denial
    assert (
        "it claims ASI09:2026 Human-Agent Trust Exploitation on the OWASP agentic "
        "list and nothing on the OWASP GenAI LLM list" in denial
    )

    # Every family the figures publish, and not only the two read above.
    entries = [
        *document(payload)["measured"]["deterministic"],
        *document(payload)["measured"]["judged"],
    ]
    assert len(entries) == 3
    for entry in entries:
        own = "\n".join(_block(text, entry["family"]))
        assert f"this family {entry['label']['bears_stated']}," in own
        assert f"it {entry['label']['claims_stated']}," in own


def test_a_family_named_without_a_rate_prints_the_duty_it_still_bears() -> None:
    """The two lists that name a family instead of a figure carry the column too.

    A withheld family and one the target could not be measured on are named in this
    document and have no block of their own, and a reader who met the article only
    beside a published rate would read the duty as something the measurement
    conferred. It is a property of the family (CONTEXT.md, **article**).
    """
    text = render(
        a_payload(
            result=replace(
                a_result(
                    not_measurable={
                        Family.HALT_DEFEAT: NotMeasurable.NO_TOOL_CALL_VISIBILITY
                    }
                )
            )
        )
    )

    # Wrongful commitment is the fixture's withheld family — κ 0.59 against a floor
    # of 0.60 — and it bears two articles, in the order opposite to scope creep's.
    [withheld] = [
        line for line in text.splitlines() if line.startswith("- wrongful_commitment:")
    ]
    assert "bears articles 15 and 14 of the EU AI Act" in withheld
    # And both halves, because the signed document is the surface that travels and
    # may not be the one that says less than the payload it is a view of.
    assert "claims ASI03:2026 Identity & Privilege Abuse" in withheld

    [unmeasurable] = [
        line for line in text.splitlines() if line.startswith("- **halt_defeat**:")
    ]
    assert "bears article 14(4)(e) of the EU AI Act" in unmeasurable
    assert "claims ASI10:2026 Rogue Agents" in unmeasurable


def test_no_elective_family_and_no_episode_is_given_an_article() -> None:
    """The tier is named in this document and never labelled.

    An elective family's label is a table of its own that nothing shortening a
    printed coverage claim reads (ADR-0039), the tier is never gate-deciding
    (ADR-0035), and an episode is not an attempt (ADR-0010). So the three sentences
    that name a family the six do not hold — the fifth absence, and the families some
    episode broke — carry no duty: an article printed there would be a legal claim
    resting on a reading no scored rate is taken over.
    """
    text = render(a_payload())

    # Anchored on the line's own opening and never on containment, because the two
    # enumerations nest as text: `direct_prompt_injection` sits inside
    # `indirect_prompt_injection`, so `family in line` matches one of the six's own
    # heading and would report the wrong line as the tier's.
    absent = [
        line
        for line in text.splitlines()
        for family in ElectiveFamily
        if line.startswith(f"- {family}:")
    ]
    assert len(absent) == len(ElectiveFamily), (
        "no line in this document names an elective family, so the assertions below "
        "would pass over an empty list"
    )
    for line in absent:
        assert "EU AI Act" not in line, line
        assert "claims " not in line, line

    [broken] = [
        line for line in text.splitlines() if "Families some episode broke" in line
    ]
    assert "EU AI Act" not in broken
    assert "halt_defeat" in broken


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


def test_the_declared_shape_prints_beside_the_controls_and_never_as_a_finding() -> None:
    # The Rule of Two is a property of what the operator declared, so it prints in
    # the section that holds declarations — beside the join, under its own heading,
    # and above nothing (ADR-0038). What a reader must not be able to do is read it
    # as a finding: it names no case, it is not in the headline, and the sentence
    # says in its own words that nothing was measured.
    payload = a_payload(
        result=a_result(
            rule_of_two=RuleOfTwo(
                held=tuple(AgentCapability), supervision=Supervision.UNSUPERVISED
            )
        )
    )
    text = render(payload)
    rule = document(payload)["declared"]["rule_of_two"]
    [controls] = [section for section in sections(payload) if section.number == "3"]

    assert "### The Agents Rule of Two, as this target declares itself" in text
    assert f"- {rule['stated']}." in controls.body
    # The published rule itself, above the line that reads this target against it. A
    # shape named without it reads as the next finding down the page.
    assert PUBLISHED_RULE_OF_TWO in controls.body
    assert "Nothing was sent to establish any of this" in text
    assert "three_unsupervised" not in text, (
        "the standing prints as the sentence a reader reads and not as its wire name"
    )

    # Under one heading, in section 3, and after the join rather than above it: the
    # headline is a defeated control, which points at a verdict.
    heading = "### The Agents Rule of Two"
    assert text.count(heading) == 1
    assert text.index("### Declared") < text.index(heading) < text.index("## 4.")

    # No digit on the line that names the shape. A count of the held capabilities is
    # the one figure this block is a line away from, and two of them rank two
    # targets — so the standing is a sentence and the capabilities are named.
    [line] = [row for row in text.splitlines() if row.startswith("- the Agents Rule")]
    assert not re.search(r"\d", line), f"{line} carries a figure"
    for capability in AgentCapability:
        assert capability.value in rule["held"]

    # A target that declared nothing prints the block too, rather than leaving a
    # reader to tell silence from a document made before the scan asked.
    silent = render(a_payload(result=a_result()))
    assert "not declared, so the rule was not read" in silent
    named = ", ".join(str(one) for one in AgentCapability)
    assert f"not stated: {named}" in silent


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


# --- Five absences, and none of them a rate of zero -------------------------


def test_a_withheld_family_is_named_with_its_reading_and_never_with_its_rate() -> None:
    # Wrongful commitment at κ = 0.59 against the declared floor of 0.60 — the reading
    # that actually fired this path. The attempts were made and the rate is recorded;
    # it is not published (ADR-0015).
    payload = a_payload()
    text = render(payload)
    [withheld] = document(payload)["measured"]["withheld"]

    # The payload's own sentence, and the two claims the family carries after it:
    # withholding a rate alters neither (#52).
    assert f"- {withheld['stated']}. The family bears " in text
    assert "0.59" in text and "13 of 15" in text

    # 12 of 30 is the rate that was measured and withheld. Neither the rate nor its
    # counts appear anywhere in the document.
    assert "12 of 30" not in text
    assert "rate 0.40" not in text
    # Whole-line equality, not containment: the guard is that this is the *only*
    # line in the document naming the family, and that nothing else was appended to
    # it. The duty is part of that line since #52 and is asserted as part of it.
    barred = (
        f"- {withheld['stated']}. The family {withheld['label']['bears_stated']}, "
        f"and {withheld['label']['claims_stated']} — neither is altered by a rate "
        "this report does not publish."
    )
    for line in text.splitlines():
        if "wrongful_commitment" in line:
            assert line == barred


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


def test_a_family_this_run_was_not_asked_for_is_the_fifth_absence_on_the_page() -> None:
    # The fifth absence, printed in its own block beside the other four rather than
    # merged into a single "not tested" list — a family absent for five different
    # reasons is five different statements (ADR-0035).
    payload = a_payload(
        result=replace(
            a_result(),
            elective=ElectiveSelection(requested=(ElectiveFamily.MEMORY_POISONING,)),
        )
    )
    text = render(payload)
    elective = document(payload)["elective"]

    assert [one["family"] for one in elective["not_requested"]] == [
        "direct_prompt_injection",
        "pii_leakage",
    ]
    for one in elective["not_requested"]:
        assert f"- {one['stated']}." in text
    assert "### The elective families, requested and not" in text

    # The request prints too, so a run that asked for every elective family — which
    # produces no absence at all — still says what it was asked.
    assert elective["requested_stated"] in text
    assert "memory_poisoning" in elective["requested_stated"]

    asked_for_all = a_payload(
        result=replace(
            a_result(), elective=ElectiveSelection(requested=tuple(ElectiveFamily))
        )
    )
    everything = render(asked_for_all)
    assert document(asked_for_all)["elective"]["not_requested"] == []
    assert "Every elective family the bench declares was requested" in everything

    # And no figure for any of them on either page. Matched against the shapes this
    # renderer actually prints a figure in — `rate 0.40`, `D = 0.85`, `**Band —` —
    # rather than the bare words, because the absence's own sentence says "no rate,
    # no interval and no band" and a word search would read that as three figures.
    for page in (text, everything):
        for line in page.splitlines():
            if any(family.value in line for family in ElectiveFamily):
                assert not re.search(r"rate \d|D = \d|\*\*Band", line), (
                    f"{line} carries a figure for an elective family"
                )


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
