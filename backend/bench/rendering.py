"""The document a human reads, bound into the payload a machine verifies.

`payload.py` produces the artefact: canonical bytes a signature can cover and a
verifier can recompute the arithmetic from. Nobody reads it. This module produces the
Markdown a procurement analyst reads, and — the part that matters — writes that
document's sha256 **into the payload** as `rendered_sha256`, before anything signs
it. So a doctored rendering cannot travel beside a valid signature, and byte-stable
*rendering* never becomes a permanent obligation: change the renderer and the digest
changes with it, where signing the Markdown itself would have invalidated every
signature ever issued (ADR-0017).

**The renderer reads the serialised document and never the result.** `render` calls
`payload.document` and works from the plain data it returns, so nothing can appear in
the rendering that a recipient cannot find in the payload they verified — and nothing
that must never travel has a route here at all. An attempt's transcript, an episode's
probes and a target's endpoint are absent from the payload by construction (ADR-0008),
which makes them absent from this document by the same construction rather than by a
renderer remembering not to print them.

**Annex IV section order, and the report says the order is a default.** ADR-0001
records the report format as an open question for a real procurement reader, Track A
did not run, and no reader has been asked. So the structure is the Act's own
technical-documentation order — the nine points of Annex IV, in ascending order, with
point 5 carrying two sections because it holds two evidentiary classes — and the
document states in as many words that its format has never been validated against the
reader it is shaped for. `docs/validation.md` records the same. The dishonest form of
this is silence, which would be indistinguishable from having asked.

**Every section prints its own reproducibility label**, off the shared enum, because a
reader who meets *not reproducible* once and nothing anywhere else cannot tell whether
it is a property of that section or a caveat somebody felt like adding (ADR-0017). The
three sections built from the payload's own sections carry the payload's own label; a
section that states an absence carries *re-derivable*, because a stated absence
follows from the same record as the figures do. **No third label was invented**: a
genuinely third evidentiary class would have to extend the claim list rather than pick
the nearer of two, which is ADR-0017's own consequence and not this module's to spend.

**The gate's result is cited in one section and its answer reaches no other**
(ADR-0018). The citation sits in provenance, in the bench's own words — *the bench
passed its gate* — and no other section carries one of the gate's three answers, so no
re-rendering can put `PASSED` beside this target's name. The word *gate* appears once
more, in the per-family `D` line, because `D` is a reading taken **at** a gate run and
a figure with no provenance is worse than one with an awkward provenance. Every such
line says in the same breath that it is a fact about the instrument and not a figure
about this target, and a test holds it to that. There is no sentence anywhere in this
document in which the target passes or fails anything: the target has rates, intervals
and bands.

**The reference agents are not named here, and the band still says what it means.**
`Band.stated()` and `BandCuts.stated()` name the hardened and weak agents, which is
correct in a gate document — they are the subject there — and is exactly the naming
ADR-0018 keeps out of a user's report, because "your agent sits between the weak and
the hardened reference" is a comparison doing a composite judgement's work. So the
three bands are stated here in ADR-0014's own words, which describe the two anchors by
their **construction** — the agent built to be defended, the agent built without
controls — rather than by name. That is the same reading ADR-0014 tabulated, and the
cut points are printed beside every band they decided.

**Nothing here reaches across two families** (ADR-0005, D12). No count of families, no
rate over a run, no figure this module computes at all: every number in this document
is a number the payload already carries, printed beside the counts it came from.
"""

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from backend.bench.payload import TargetPayload, document, write
from backend.bench.published import EDITION as AGENTIC_EDITION
from backend.bench.reproducibility import Reproducibility
from backend.bench.scorer import Band

REPORT_MARKDOWN = "report.md"
"""The name of the document a human reads."""

REPORT_PAYLOAD = "report.json"
"""The name of the artefact a machine verifies.

Two fixed names in one directory per run, rather than a caller-chosen stem: a
recipient handed a directory has to know which file `verify.py` reads and which one
the digest was taken over, and a name that varies by call site is a name they have to
be told.
"""

FORMAT_UNVALIDATED = (
    "**The format of this report has never been validated against a real "
    "procurement reader.** Its section order is the Act's own technical-"
    "documentation order (Annex IV), which is a defensible default and not a "
    "finding: ADR-0001 records that the format is a question for the readers this "
    "document is shaped for, and none has been asked. A reader who needs it in "
    "another shape — a questionnaire template, SOC 2, ISO 42001 — is reading "
    "something this bench has not done, and not a claim about what they should "
    "expect. The same "
    "statement is recorded in `docs/validation.md`."
)
"""The label ADR-0001 requires, in the document rather than only in the repository.

Stated because the alternative is silence, and silence is indistinguishable from
having asked a reader and been told this shape was right.
"""

"""ADR-0017's first claim, printed beside the second and never alone.

*This reached you unaltered*, stated for the whole artefact including the adaptive
section, because a security report with an unprotected region would be a worse
artefact for a strictly worse reason. It deliberately does not say the document **is**
signed: an unsigned run must be impossible to present as signed, so this paragraph
describes what the binding makes checkable and `verify.py` is what answers whether it
checks out.
"""

INTEGRITY_CLAIM = (
    "**Integrity, for the whole document.** The canonical JSON payload beside this "
    "file carries this document's sha256 in `rendered_sha256`, so the two travel as "
    "one artefact: alter a byte of either and they no longer agree. A signature over "
    "that payload therefore covers this document whole, the adaptive section "
    "included — no region of it is left unprotected (ADR-0017). Whether these bytes "
    "*are* signed, and by which key, is a property of the payload beside them and is "
    "answered by `scripts/verify.py`, not by this sentence."
)

"""ADR-0017's second claim, and the reason the first one is not enough on its own.

A valid signature over `A_break = +0.25` invites the reading that the figure is
reproducible, and it is not: the same declared configuration produced +0.00 and +0.25
on two certified runs a day apart. So the scope of re-derivability is stated in the
document rather than left to be inferred from the presence of a signature.
"""

RE_DERIVABILITY_CLAIM = (
    "**Re-derivability, for the scored layer only.** Every figure in the scored "
    "sections follows from the recorded attempts, the case records and the rule "
    "printed below, so a reader holding those recomputes it without this bench. The "
    "adaptive layer is **recorded and not reproducible**: re-run it and the attacker "
    "takes a different path. Both claims are printed together, because a document "
    "stating one of them alone would be claiming the stochastic half was reproducible "
    "by omission (ADR-0010, ADR-0017)."
)

"""What this document refuses to be, printed in section 1 and again in section 8.

Twice on purpose, and not by an accident of reuse: a reader who arrives looking for a
badge turns to the declaration-of-conformity section, and a refusal placed only in an
introduction they skipped would tell them nothing. The most likely way this report
fails is by reading like a grade, and no one sentence is the safeguard — the safeguard
is that the page never makes a single figure easy to construct.
"""

NOT_A_CLAIM_OF_CONFORMITY = (
    "This document is evidence, not a certificate. It carries no claim of "
    "conformity, no certification, no badge, no insurance and no price, and it "
    "declares no single figure standing for this target: a reader who wants one "
    "number will build it out of whatever is on the page, so the page does not offer "
    "one (D3, ADR-0001, ADR-0005). A valid signature says these bytes are the ones "
    "that were produced and that nothing has altered them. It says nothing "
    "whatsoever about whether the agent is safe."
)

BAND_IN_A_TARGET_REPORT: Mapping[Band, str] = {
    Band.HOLDS: (
        "no worse than an agent built to be defended, and measurably better than one "
        "built without controls. Not a claim that the family cannot be broken, only "
        "that these attempts place it against the better of the two anchors"
    ),
    Band.WEAK: (
        "these counts place this family against neither anchor: the interval either "
        "sits between the two declared rates or is wide enough to span both. A "
        "reading of nothing, stated rather than rounded to the nearer answer"
    ),
    Band.FAILS: (
        "measurably worse than an agent built to be defended, and consistent with an "
        "agent that has a system prompt and no controls"
    ),
}
"""The three bands in ADR-0014's own words, which name no reference agent.

Not `Band.stated()`, and the difference is ADR-0018 point 6 rather than a style
preference: the shared wording names the hardened and weak agents because it is also
the gate's wording, and a target's report that named the bench's calibration
equipment would invite the one comparison ADR-0018 refuses. ADR-0014's table already
describes both anchors by construction, so nothing is lost but the names — and the
cut points that were those rates are printed beside every band.
"""

ANNEX_IV_POINTS: Mapping[int, str] = {
    1: "a general description of the AI system",
    2: (
        "a detailed description of the elements of the system and of the process for "
        "its development"
    ),
    3: "detailed information about the monitoring, functioning and control",
    4: "a description of the appropriateness of the performance metrics",
    5: "a detailed description of the risk management system (Article 9)",
    6: "a description of relevant changes made through the system's lifecycle",
    7: "a list of the harmonised standards applied",
    8: "a copy of the EU declaration of conformity",
    9: "a description of the post-market monitoring system (Article 72)",
}
"""The nine points of Annex IV, in the Act's order, as the section headings cite them.

Held as data so that the order is a property of this module rather than of the order
somebody wrote the functions in, and so a test can read it.
"""


def _listed(rows: Iterable[str], absence: str) -> tuple[str, ...]:
    """Those rows, or one line saying the list is empty and what that reads as.

    One shape for every list in this document, because the alternative is four
    variations on the same branch and a fifth that quietly drops the empty case — and
    a dropped empty case is a section that reads as having had nothing to declare when
    it had something to declare and no way to declare it.
    """
    listed = tuple(rows)
    return listed or (absence,)


@dataclass(frozen=True)
class Section:
    """One section of the rendering: where it sits in Annex IV, and what it claims.

    Carries its own reproducibility label rather than inheriting one from the
    document, which is the whole of ADR-0017's second claim: a section is where the
    label means something, because the two halves of a run land in different
    sections.
    """

    point: int
    """Which Annex IV point this section answers."""

    part: str = ""
    """`a` or `b` where one Annex IV point holds two sections, and empty otherwise.

    Point 5 holds two, because what the bench does not test at all and what one
    attacker found outside the recorded cases are both statements about the boundary
    of the claim, and they are not the same evidentiary class. Two labelled sections
    under one point is Annex IV's own shape — its points carry lettered sub-points —
    and it is the honest alternative to one section with two labels or one label
    covering both.
    """

    title: str = ""
    reproducibility: Reproducibility = Reproducibility.RE_DERIVABLE
    body: tuple[str, ...] = ()

    @property
    def number(self) -> str:
        """The section's number as it is printed and cited: `4`, or `5a`."""
        return f"{self.point}{self.part}"

    def rendered(self) -> str:
        """The section, its Annex IV citation, its own label, and its body."""
        return "\n".join(
            (
                f"## {self.number}. {self.title}",
                "",
                f"*Annex IV({self.point}) — {ANNEX_IV_POINTS[self.point]}.*",
                "",
                f"*Reproducibility of this section: {self.reproducibility.stated()}.*",
                "",
                *self.body,
            )
        )


def render(payload: TargetPayload) -> str:
    """The payload as the Markdown a human reads, in Annex IV section order.

    Reads `document(payload)` and nothing else, so this document is a view of the
    artefact rather than a second account of the run.

    **It does not print `rendered_sha256`**, and it must not: the digest is taken over
    these bytes, so a document containing it would have to contain its own hash.
    `publish` checks that the two agree rather than trusting this sentence.
    """
    body = document(payload)
    ordered = _sections_of(body)
    return (
        "\n".join(
            (
                *_masthead(body, ordered),
                *(f"{section.rendered()}\n" for section in ordered),
            )
        ).rstrip("\n")
        + "\n"
    )


def digest(markdown: str) -> str:
    """The sha256 of a rendering, over its UTF-8 bytes — the value that gets bound."""
    return hashlib.sha256(markdown.encode("utf-8")).hexdigest()


def bind(payload: TargetPayload) -> TargetPayload:
    """That payload with the digest of its own rendering inside it.

    The one place `rendered_sha256` is set, and it is set from the rendering rather
    than passed in: a caller that could supply the digest is a caller that could
    supply the wrong one, which is precisely the substitution the field exists to
    prevent. Binding twice yields the same digest, because the rendering does not
    print it.
    """
    return replace(payload, rendered_sha256=digest(render(payload)))


@dataclass(frozen=True)
class Binding:
    """A payload and the rendering its own digest covers, checked to agree.

    The artefact before anybody has decided where to put it. Two things carry it out
    of this process — `publish`, which writes it to a directory, and `signing.signed`,
    which hands it to a route — and they read the same record rather than each binding
    a payload to a rendering of its own. Two bindings could differ by one byte and
    only one of them would be the one a signature covers.
    """

    payload: TargetPayload
    """The **bound** payload: the one carrying the digest, and the one to sign."""

    markdown: str
    """The rendering that digest is over, so the pair cannot be assembled apart."""


def bound(payload: TargetPayload) -> Binding:
    """That payload bound to its own rendering, or a refusal if the two disagree.

    The binding and the check in one place, because they are one step: the digest
    goes in, the document comes out, and the two agree or nothing may be published.

    Raises rather than returning if they disagree, which can only happen if the
    renderer learned to print the digest it is being measured by — a circularity
    that would otherwise fail silently, leaving every verification of the pair to
    fail on the recipient's side instead.
    """
    keyed = bind(payload)
    markdown = render(keyed)
    if digest(markdown) != keyed.rendered_sha256:
        raise ValueError(
            "the rendering does not hash to the digest bound into the payload, so "
            "the two would travel disagreeing. A rendering that prints "
            "`rendered_sha256` cannot be bound to it: the digest is taken over the "
            "document, so the document cannot contain it (ADR-0017)"
        )
    return Binding(payload=keyed, markdown=markdown)


@dataclass(frozen=True)
class Published:
    """What one run left on disk: two files that cannot disagree, and the payload.

    The payload here is the **bound** one — the one carrying the rendering's digest —
    because that is the artefact #51 signs. Handing back the unbound payload a caller
    passed in would be handing back the one thing that must not be signed.
    """

    payload: TargetPayload
    payload_path: Path
    rendering_path: Path


def publish(payload: TargetPayload, directory: Path) -> Published:
    """Write the Markdown report beside the canonical JSON, bound to it by digest.

    In this order, and it is the only order available: the rendering exists, its
    digest goes into the payload, and the payload is serialised with the digest
    inside it. There is no window in which the JSON on disk describes a rendering
    other than the one beside it, and no way to write an unbound payload from here.

    Raises rather than writing if the two disagree — `bound` is where that refusal
    lives, so the check is the same one the served artefact faces (#56).
    """
    binding = bound(payload)
    rendering_path = directory / REPORT_MARKDOWN
    rendering_path.parent.mkdir(parents=True, exist_ok=True)
    rendering_path.write_text(binding.markdown, encoding="utf-8")
    return Published(
        payload=binding.payload,
        payload_path=write(binding.payload, directory / REPORT_PAYLOAD),
        rendering_path=rendering_path,
    )


def sections(payload: TargetPayload) -> tuple[Section, ...]:
    """The document's sections, in ascending Annex IV order.

    Exposed rather than private because two claims about this document are claims
    about its sections — that they follow Annex IV order and that each one states its
    own reproducibility — and a test that had to read them back out of Markdown would
    be a test of a regular expression.
    """
    return _sections_of(document(payload))


def _sections_of(body: Mapping[str, Any]) -> tuple[Section, ...]:
    """The sections of one serialised payload, sorted into Annex IV order.

    Sorted rather than written in order, so that the order is the Annex IV point on
    each section and not the order somebody happened to list the builders in.
    """
    ordered = (
        _general_description(body),
        _how_the_run_was_made(body),
        _controls(body["declared"]),
        _figures(body["measured"]),
        _not_tested_at_all(body["coverage_gaps"], body["untested_categories"]),
        _adaptive(body["adaptive"]),
        _lifecycle(),
        _standards(),
        _conformity(),
        _post_market(),
    )
    return tuple(sorted(ordered, key=lambda section: (section.point, section.part)))


# --- The masthead ------------------------------------------------------------


def _masthead(body: Mapping[str, Any], ordered: Sequence[Section]) -> tuple[str, ...]:
    """The title, what kind of artefact this is, and the sections it holds.

    The contents list is Annex IV as a table of contents, which is the point of
    following its order at all: a reader who knows the Act's technical-documentation
    structure can find the section they came for, and one who does not can see that
    every point is answered — including the four answered with a stated absence.

    `##` is reserved for the sections themselves, so what a heading means in this
    document does not depend on which heading it is.
    """
    return (
        f"# Target report — {body['target']}",
        "",
        f"`{body['artefact']}`, artefact version {body['artefact_version']}. "
        "One run against one target.",
        "",
        "**Contents** — the nine points of Annex IV in the Act's order, point 5 "
        "answered in two sections:",
        "",
        *(f"- {section.number} — {section.title}" for section in ordered),
        "",
    )


# --- 1. A general description -----------------------------------------------


def _general_description(body: Mapping[str, Any]) -> Section:
    """What this document is about, the headline finding, and the two claims.

    The declared-and-defeated join is the headline because it is the strongest
    finding the bench can produce: a control the operator declared and the bench
    empirically broke. It is a status and a case id rather than a figure, which is
    why it can sit above the measurements without becoming a summary of them.
    """
    provenance = body["provenance"]
    attestation = provenance["attestation"]
    return Section(
        point=1,
        title="The target, and the headline finding",
        body=(
            f"- **Target**: `{body['target']}`",
            f"- **Attested by**: {attestation['identity']}, "
            f"recorded {attestation['recorded_at']}",
            "- **One run, in two layers**: the recorded library at the declared "
            "attempts per case, then one adaptive attacker. Only the first is scored.",
            "",
            "### The headline finding — declared, and defeated",
            "",
            *_headline(body["declared"]),
            "",
            "### The two claims this document carries",
            "",
            f"- {INTEGRITY_CLAIM}",
            f"- {RE_DERIVABILITY_CLAIM}",
            "",
            "### What this document is not",
            "",
            NOT_A_CLAIM_OF_CONFORMITY,
            "",
            "### The shape of this document",
            "",
            FORMAT_UNVALIDATED,
        ),
    )


def _headline(declared: Mapping[str, Any]) -> tuple[str, ...]:
    """The controls this target declared and the bench broke, or the stated absence.

    An empty join is an answer and not a blank: a target whose declarations all held
    is reported as having held them, and one that declared nothing has nothing to be
    caught over-declaring.
    """
    defeated = [
        control
        for control in declared["controls"]
        if control["control"] in declared["defeated"]
    ]
    if not defeated:
        if not declared["controls"]:
            return (
                "This target declared no controls, so there is no declaration for "
                "these attempts to have broken. An absence on the operator's side, "
                "and not a finding about the agent.",
            )
        return (
            "**No control this target declared was defeated by these attempts.** "
            "Not evidence that the controls exist, only that these attempts did not "
            "get past them — the per-control rows in section 3 say which was which.",
        )
    return tuple(
        f"- **Declared, and defeated:** {control['stated']}." for control in defeated
    )


# --- 2. The elements, and the process that produced this ---------------------


def _how_the_run_was_made(body: Mapping[str, Any]) -> Section:
    """Provenance: who attested, on which models, against which library, at what cost.

    The bench's gate **result** is cited here and in no other section (ADR-0018).
    This is the part of a document that says *how this was made*, which is where a
    reader looks for the ruler's certification — not in the section carrying what the
    ruler measured.
    """
    provenance = body["provenance"]
    attestation = provenance["attestation"]
    models = provenance["models"]
    rule = provenance["rule"]
    return Section(
        point=2,
        title="How this run was made, and by what instruments",
        body=(
            "### The attestation this run required",
            "",
            f"- **Identity**: {attestation['identity']}",
            f"- **Recorded at**: {attestation['recorded_at']}",
            f"- **Endpoint**: `sha256:{attestation['endpoint_sha256']}` — the "
            "endpoint travels as a hash. A live URL that answers jailbreak payloads "
            "is not a thing to write into a document that leaves the building "
            "(ADR-0008).",
            "",
            "The three statements this run could not start without, as recorded:",
            "",
            *(f"- Attested — {wording}." for wording in attestation["statements"]),
            "",
            "### The three declared models",
            "",
            f"- **{models['calibration']}** — the model the bench's own calibration "
            "equipment ran on, and so the model its gate citation was earned on.",
            f"- **{models['adjudicating']}** — the instrument that decided the judged "
            "families, and the one κ is measured on.",
            f"- **{models['attacking']}** — the adaptive layer's model, and the "
            "adaptive layer's only. It decides nothing that is scored.",
            "",
            "### The library these attempts came from",
            "",
            f"- {provenance['library']['stated']}",
            "",
            "### What this run spent, per layer",
            "",
            *(
                f"- **{layer} layer**: {calls} calls on the wire"
                for layer, calls in provenance["calls_spent"].items()
            ),
            "- Reported per layer and never as one figure: a blended number hides "
            "which half of the run spent the operator's budget.",
            "",
            "### The rule these figures were measured under",
            "",
            f"- **{rule['attempts_per_case']} attempts per case** — the denominator "
            "behind each rate is printed beside it in section 4.",
            f"- **Wilson interval at {rule['interval_confidence']:.0%}** around every "
            "rate.",
            f"- **κ floor of {rule['kappa_floor']:.2f}** — a judged family whose "
            "adjudicator reads below it is not published, and section 4 says which.",
            "- Only the part of the declared rule that decided the figures below "
            "appears here. The rest of it decides the bench's own gate, over three "
            "agents of known construction, and has no definition for one target "
            "(ADR-0018).",
            "",
            "### The bench's own gate, cited as provenance",
            "",
            f"> {provenance['gate']['stated']}",
        ),
    )


# --- 3. Monitoring, functioning and control ----------------------------------


def _controls(declared: Mapping[str, Any]) -> Section:
    """The declared-and-defeated join in full: what was claimed, and what held.

    Statuses and case ids, and no count of either. A number in this section would be
    a measurement inside the declared half, and the first thing anyone would do with
    two of them is compare two targets on it.
    """
    return Section(
        point=3,
        title="The controls this target declared, and what the attacks made of them",
        reproducibility=Reproducibility(declared["reproducibility"]),
        body=(
            "The scan reads what the operator declared. A declared control can still "
            "be broken, and that is what the attempts are for — this section is the "
            "join, and every row points at a verdict rather than at a figure.",
            "",
            "### Declared",
            "",
            *_listed(
                (f"- {control['stated']}" for control in declared["controls"]),
                "- Nothing was declared, so nothing here was examined.",
            ),
            "",
            "### Not declared",
            "",
            *_listed(
                (f"- {absent['stated']}" for absent in declared["absent"]),
                "- The checklist asks about no control this target left undeclared.",
            ),
        ),
    )


# --- 4. The appropriateness of the performance metrics -----------------------


def _figures(measured: Mapping[str, Any]) -> Section:
    """The per-family figures, each with the counts and the limits behind it.

    Every family stands alone. Nothing here reads two of them, which is why a reader
    who wants to compare two families reads two blocks and a reader who wants one
    number does not get one (ADR-0005).

    The per-family coverage note (ADR-0002) is printed for the families whose figures
    this report publishes, and for those only: a withheld or unmeasurable family has no
    figure for the note to qualify, and the boundary of a claim printed beside an
    absent claim would read as the claim having been made.
    """
    cuts = measured["cuts"]
    return Section(
        point=4,
        title="What was measured, per family, with the counts behind it",
        reproducibility=Reproducibility(measured["reproducibility"]),
        body=(
            "Each family is reported on its own, with the counts its rate was "
            "computed from, the interval around it, and the boundary of what the "
            "family's cases claim. No figure below reaches across two families, and "
            "there is nothing on this page that combines them.",
            "",
            "**The two cut points a band is read against** are "
            f"{cuts['holds_at_or_below']:.2f} and {cuts['fails_at_or_above']:.2f} — "
            "the constructed failure rates of the two agents of known construction "
            "the bench calibrates on, declared in advance and not tuned (ADR-0014). "
            "A band is the interval's **separation** from those two anchors, never a "
            "bound clearing a threshold, and it summarises one family for one target.",
            "",
            *_family_blocks(measured),
            "### Families whose rate this report does not publish",
            "",
            *_withheld(measured["withheld"]),
            "",
            "### Families this target could not be measured on",
            "",
            *_not_measurable(measured["not_measurable"]),
        ),
    )


def _family_blocks(measured: Mapping[str, Any]) -> tuple[str, ...]:
    """One block per family whose figures this report publishes.

    Deterministic families first, then judged, in the order the payload carries them.
    The unfit judged families are already absent from it (ADR-0015), so there is no
    filtering to forget here.
    """
    entries: Sequence[Mapping[str, Any]] = [
        *measured["deterministic"],
        *measured["judged"],
    ]
    if not entries:
        return (
            "### No family's rate is published in this report",
            "",
            "This run produced no rate this report may publish. What it did produce "
            "is below — the families this target could not be measured on, and the "
            "families whose rate is withheld with the reading that barred it. "
            "Neither of those is a rate of zero, and neither says the target "
            "resisted anything.",
            "",
        )
    return tuple(line for entry in entries for line in _family_block(entry))


def _family_block(entry: Mapping[str, Any]) -> tuple[str, ...]:
    """One family: its counts, its interval, its band, its limits and its instrument.

    The coverage note sits **inside** this block rather than in a table of its own,
    because ADR-0002's disclosure is only doing its job beside the figure it
    qualifies: a family reported as holding, with nothing beside it, reads as a
    cleared category.
    """
    interval = entry["interval"]
    return (
        f"### {entry['family']}",
        "",
        f"- **{entry['successes']} of {entry['attempts']} attempts succeeded** — "
        f"rate {entry['rate']:.2f}. An attempt succeeding is this target's defence "
        "not holding.",
        f"- **Wilson interval at {entry['interval_confidence']:.0%}**: "
        f"{interval['lower']:.3f} to {interval['upper']:.3f}. The interval and never "
        "the point estimate is what the band is read from.",
        f"- **Band — {entry['band']}**: "
        f"{BAND_IN_A_TARGET_REPORT[Band(entry['band'])]}.",
        f"- **Verdict class**: {entry['verdict_class']}.",
        *_reliability(entry["reliability"]),
        *_discrimination(entry["discrimination"]),
        *_coverage(entry["coverage"]),
        "",
    )


def _reliability(reliability: Mapping[str, Any] | None) -> tuple[str, ...]:
    """How this family's verdicts were reached, and what vouches for the instrument.

    On a judged family, κ with its counts and its floor — in the payload's own words,
    printed once rather than paraphrased above a repeat of itself. On a deterministic
    family, the line says there is no instrument for a reliability figure to be about:
    a success condition is authoritative and re-derivable from the record, and a κ
    printed beside it would say the verdict needed vouching for (ADR-0004).
    """
    if reliability is None:
        return (
            "- **How the verdict was reached**: a deterministic success condition, "
            "authoritative and re-derivable from the recorded attempt. No "
            "reliability figure belongs here, because there is no instrument for one "
            "to be about (ADR-0004).",
        )
    return (
        "- **How the verdict was reached**: adjudication, which is an instrument "
        "with a reliability of its own. "
        f"{reliability['stated']} — read over transcripts hand-labelled before any "
        "target was seen (ADR-0013).",
    )


def _discrimination(reading: float | None) -> tuple[str, ...]:
    """`D` for this family at the bench's last gate — a fact about the bench.

    Stated as the instrument's reading and never as the target's, and stated as
    *unread* rather than as zero where no gate has measured it: a bench that never
    measured its discrimination on a family has to stay distinguishable from one that
    measured it at zero, and the second is a reason to distrust the family.
    """
    if reading is None:
        return (
            "- **The bench's discrimination on this family**: not read. No gate run "
            "has measured `D` here, which is not the same fact as a `D` of zero.",
        )
    return (
        f"- **The bench's discrimination on this family**: `D` = {reading:.2f} at its "
        "last gate, measured between two agents of known construction. A fact about "
        "the instrument, and not a figure about this target — `D` is a difference "
        "between two agents and has no definition for one (ADR-0018).",
    )


def _coverage(identifiers: Iterable[Mapping[str, Any]]) -> tuple[str, ...]:
    """What each published identifier this family claims does *not* cover (ADR-0002).

    A family *tests one case within* an identifier; it **is not** that identifier. An
    entry in a published list is a risk category and a family is an executable test
    with a stated criterion, and carrying the label must never imply the two are one
    object.
    """
    return tuple(
        f"- **Tests one case within `{identifier['identifier']}`** — and does not "
        f"test: {identifier['does_not_test']}."
        for identifier in identifiers
    )


def _withheld(withheld: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    """The judged families whose rate this document may not print, and why.

    The reason travels with the absence, because a withheld family with no reading
    beside it is indistinguishable from a family the bench forgot to run (ADR-0015).
    """
    return _listed(
        (f"- {one['stated']}." for one in withheld),
        "- None. Every judged family in this run reached the declared κ floor, so no "
        "family's rate is withheld.",
    )


def _not_measurable(unanswerable: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    """The families this target could not answer, with the reason that closes them.

    A third outcome beside a rate and a refused registration, and never a rate of
    zero: a target the bench never measured has to stay distinguishable from one that
    resisted everything.
    """
    return _listed(
        (
            f"- **{one['family']}**: {one['stated']}. This is not a rate of zero — "
            "nothing was measured, so there is no rate to read."
            for one in unanswerable
        ),
        "- None. Every family's precondition was met by this target, so no family is "
        "unmeasured.",
    )


# --- 5a. Risk management: what is not tested at all --------------------------


def _not_tested_at_all(
    gaps: Sequence[Mapping[str, Any]],
    untested: Sequence[Mapping[str, Any]],
) -> Section:
    """The negative-coverage list, in two blocks, because it makes two claims.

    Printed in every report, and not a defect. It uses the public category list as a
    coverage checklist rather than only as a label, which is the first thing a
    security analyst looks for — and the gaps are listed rather than closed.

    The two blocks are not the same claim and are not merged. The first names
    published categories no family in the library reaches, and it is **subtracted**
    from a stored copy of the list rather than written out by hand, so a family added
    later shortens it without anyone editing this function. The second names limits of
    the bench itself, which appear on no published register and can only be declared.
    Printing them as one bulleted list would make the derived half look declared and
    the declared half look checkable.
    """
    return Section(
        point=5,
        part="a",
        title="What this bench does not test at all",
        body=(
            "The boundary of the claim, stated rather than left to be inferred from "
            "the labels above. These are listed and not closed: new families to cover "
            "them are the lowest priority this project holds, and a gap is not a "
            "defect in this run.",
            "",
            f"**Published categories no family reaches** — {AGENTIC_EDITION}, "
            "subtracted from the stored copy of that list rather than written out "
            "here, so this block shortens by itself when a family that claims one of "
            "them is admitted (ADR-0002).",
            "",
            *(f"- {category['stated']}." for category in untested),
            "",
            "**Limits of the bench**, which no published register carries and which "
            "are therefore declared rather than subtracted.",
            "",
            *(f"- {gap['stated']}." for gap in gaps),
            "",
            "One list above is derived and one is declared, and the copy the "
            "derivation reads is a transcription rather than the source: the OWASP "
            "resource page refuses automated retrieval, so the identifiers and titles "
            "were taken from two independent readings that agreed on all ten. What "
            "that supports is agreement between two readings, and a reader who needs "
            "the authoritative wording goes to OWASP. The **OWASP GenAI LLM Top 10 "
            "2026** identifiers carried by section 4 have no stored copy at all, so "
            "that list's negative coverage is not derived and a category published on "
            "it since is missing here. The per-family notes in section 4 carry the "
            "other half of the same disclosure (ADR-0002).",
        ),
    )


# --- 5b. Risk management: what one attacker found outside the cases ----------


def _adaptive(adaptive: Mapping[str, Any]) -> Section:
    """One agent's search, in prose, marked recorded rather than re-derivable.

    Under the same Annex IV point as the negative-coverage list because both are
    statements about what the recorded cases do not reach, and in its own section
    because it is not the same evidentiary class — which is exactly what its own
    label says.
    """
    episodes = adaptive["episodes"]
    return Section(
        point=5,
        part="b",
        title="What one adaptive attacker found beyond the recorded cases",
        reproducibility=Reproducibility(adaptive["reproducibility"]),
        body=(
            "One agent's search, and not a measurement. It carries no rate, no "
            "interval, no band and no `D`, and nothing in it may be read against the "
            "sections above it (ADR-0010). The label above this paragraph is the "
            "whole of what a signature vouches for here: these bytes reached you "
            "unaltered, and re-running the layer would not reproduce them.",
            "",
            "Routes are described in prose and never as payload text: a route that "
            "beat this target is a working unpublished exploit, and this document is "
            "the one that leaves the building (ADR-0008).",
            "",
            *_listed(
                (
                    f"- {episode['stated']} (over {episode['turns']} turns)."
                    for episode in episodes
                ),
                "- No episode was recorded. That is not the same reading as an "
                "attacker that stopped without breaking the target: the first says "
                "this layer did not run, and neither says the target resisted.",
            ),
            "",
            "**Families some episode broke**: "
            + (
                ", ".join(f"`{family}`" for family in adaptive["families_broken"])
                or "none"
            )
            + ". Names, not a figure — nothing in this section may be read against "
            "the sections above it (ADR-0010).",
        ),
    )


# --- 6 to 9: the points this artefact answers with a stated absence ---------


def _lifecycle() -> Section:
    """Annex IV(6): what one run can say about change over time, which is nothing.

    Said rather than omitted. A missing section reads as a document that had nothing
    to declare, and this one has something to declare and one run to declare it from.
    """
    return Section(
        point=6,
        title="Changes through the lifecycle",
        body=(
            "**Nothing, and this document cannot say otherwise.** This is one run "
            "against one target at one time. A band that moved, a control that was "
            "added, a model that was swapped underneath the agent — none of them is "
            "visible from a single run, which is why lifecycle consistency is listed "
            "in section 5a as a category this bench does not test. Two reports of "
            "the same target, each verifiable on its own, are what a reader would "
            "compare; scheduled runs that would produce them are not part of this "
            "artefact (section 9).",
        ),
    )


def _standards() -> Section:
    """Annex IV(7): the standards applied, of which there are none that could be.

    The honest answer is a short one, and it protects the identifiers above it: no
    harmonised standard is cited in the Official Journal, so nothing in this document
    carries a presumption of conformity, however recognisable its labels look.
    """
    return Section(
        point=7,
        title="Standards applied",
        body=(
            "**None, and none is available.** No harmonised standard for Article 15 "
            "is cited in the Official Journal, so nothing in this document carries "
            "the Article 40 presumption of conformity.",
            "",
            "The published identifiers in section 4 are **secondary labels and never "
            "identity**: a family *tests one case within* an identifier; it is not "
            "that identifier. An entry in a published list is a risk category, and a "
            "family is an executable test with a stated criterion (ADR-0002). Draft "
            "European standards are not cited here at all — clause numbers move "
            "between drafts, and a stale clause number inside a signed report is "
            "worse than no reference.",
        ),
    )


def _conformity() -> Section:
    """Annex IV(8): the declaration of conformity, and why there is not one.

    The strongest single sentence in the document, in the place a reader looking for
    a badge will actually turn to.
    """
    return Section(
        point=8,
        title="Declaration of conformity",
        body=(
            "**None. There is no declaration of conformity here, and there will not "
            "be one.**",
            "",
            NOT_A_CLAIM_OF_CONFORMITY,
            "",
            "What this document does carry is the evidence a reader can check for "
            "themselves: counts behind every rate, the rule they were measured "
            "under, the instrument's own certification in section 2, and the "
            "boundary of the claim in section 5a.",
        ),
    )


def _post_market() -> Section:
    """Annex IV(9): post-market monitoring, which this artefact does not provide."""
    return Section(
        point=9,
        title="Post-market monitoring",
        body=(
            "**Not part of this artefact.** This report describes one run, made at "
            "the moment recorded in section 2. A scheduled run, a re-measured "
            "target, an alert when a band moves and delivery of a fresh report are "
            "all outside what this document covers, and a reader should treat every "
            "figure here as an observation of that moment rather than as a standing "
            "property of the agent.",
        ),
    )
