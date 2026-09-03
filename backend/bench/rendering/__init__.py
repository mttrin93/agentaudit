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
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from backend.bench.payload import TargetPayload, document, write
from backend.bench.rendering._annexes import (
    _conformity,
    _lifecycle,
    _post_market,
    _standards,
)
from backend.bench.rendering._declared import (
    CONTROL_DECLARED as CONTROL_DECLARED,
)
from backend.bench.rendering._declared import (
    CONTROL_PROVED as CONTROL_PROVED,
)
from backend.bench.rendering._declared import (
    FORMAT_UNVALIDATED as FORMAT_UNVALIDATED,
)
from backend.bench.rendering._declared import (
    INTEGRITY_CLAIM as INTEGRITY_CLAIM,
)
from backend.bench.rendering._declared import (
    RE_DERIVABILITY_CLAIM as RE_DERIVABILITY_CLAIM,
)
from backend.bench.rendering._declared import (
    _controls,
    _general_description,
    _how_the_run_was_made,
)

# Re-exported, not merely imported: these five names were defined in this module
# before it became a package, and `signing.py`, `verification.py`, `app.py` and the
# suite import them from `backend.bench.rendering`. The redundant `X as X` is what
# marks a re-export to mypy under `no_implicit_reexport`.
from backend.bench.rendering._layout import (  # noqa: I001
    ANNEX_IV_POINTS as ANNEX_IV_POINTS,
)
from backend.bench.rendering._layout import (
    NOT_A_CLAIM_OF_CONFORMITY as NOT_A_CLAIM_OF_CONFORMITY,
)
from backend.bench.rendering._layout import Section as Section
from backend.bench.rendering._measured import (
    BAND_IN_A_TARGET_REPORT as BAND_IN_A_TARGET_REPORT,
)
from backend.bench.rendering._measured import _adaptive, _figures, _not_tested

REPORT_MARKDOWN = "report.md"
"""The name of the document a human reads."""

REPORT_PAYLOAD = "report.json"
"""The name of the artefact a machine verifies.

Two fixed names in one directory per run, rather than a caller-chosen stem: a
recipient handed a directory has to know which file `verify.py` reads and which one
the digest was taken over, and a name that varies by call site is a name they have to
be told.
"""


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
        _figures(body["measured"], body["elective"]),
        _not_tested(
            body["coverage_gaps"],
            body["untested_categories"],
            body["claimed_in_part"],
        ),
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


# --- 2. The elements, and the process that produced this ---------------------


# --- 3. Monitoring, functioning and control ----------------------------------


# --- 4. The appropriateness of the performance metrics -----------------------


# --- 5a. Risk management: what is not tested at all --------------------------


# --- 5b. Risk management: what one attacker found outside the cases ----------


# --- 6 to 9: the points this artefact answers with a stated absence ---------
