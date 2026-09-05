"""Writes a variant record: one library case, one published transform, one argument.

    uv run python -m scripts.variant --base data-leakage-001 --transform base64 \
        --argument notes/base64.md
    uv run python -m scripts.variant --base data-leakage-001 --transform rot13 \
        --argument notes/rot13.md --write

**This is the only place a transform is applied** — once, here, with the result
committed in the record's `payload`, whether it respells that payload or escalates
over a ladder of turns (`transforms.derived_payload`, ADR-0054)
([ADR-0052](../../docs/adr/0052-a-transform-is-a-committed-function-and-no-judged-family-gets-a-variant.md)
§1). Why a variant is a record at all is
[ADR-0051](../../docs/adr/0051-a-variant-is-a-case-and-the-transform-is-a-function-it-names.md).
The functions and their citations are
`backend/bench/transforms.py`.

**What it writes is a proposal, and a proposal is not a case.** There is no
`[admission]` block, because the measurement has not happened: the record has to
clear ADR-0003's single-model bar against the three reference agents, through
`scripts/admit.py`, and `admission.admitted_library` — the loader every run takes —
refuses a record that has not. So a written record is uncommittable until it has been
measured, and a variant that does not clear the bar is deleted rather than parked
(`scripts/admit.py`, *a rejected case is discarded*). That is the deliverable of #73
and this script is upstream of it.

**It sends nothing, so it asks nothing.** No target is reached, no model is called
and no money is spent, which is why this is the one entry point in `scripts/` with
no attestation and no approval interrupt (ADR-0007 authorises messages on the wire,
and there are none here).

**The argument is required and is not generated.** ADR-0008's amendment ships a
payload derived from a published technique *with its citation* and requires the
classification argued **per record, in the record's header**. A paragraph this script
composed would be that argument asserted once, in a script, which is what the ADR
says it is not. So `--argument` takes a file a person wrote and there is no default:
what it should say is which technique this is, where it was published, and why the
words may ship — the form three `wrongful-commitment` records already show for the
opposite conclusion. For `scripted_crescendo` it also has to say why the family that
technique is most obviously *for* gets no ladder: wrongful commitment is judged, and a
judged variant is a separate ticket that opens by saying what happens to κ (ADR-0052
§2, ADR-0054 §3). An omission a reader has to notice is not a classification.

**Three bases are refused**, each because the variant would carry something into a
place the base case's own invariants keep it out of: a judged case (κ, and
`rule.gold_transcripts_per_family`), a retrieved case (ADR-0047's notice would not
travel with the derivative) and the identity (a second copy of a case is not a
variant of it). The reasons are on the refusals below.

**And a pairing nobody wrote a framing for is refused too**, one level down, in the
construction: a framing is one prefix round a payload that passes through verbatim,
so it is written per **family** against the mechanism that family tests, and a
transform with no framing for the base's family composes nothing at all
([ADR-0074](../../docs/adr/0074-a-framing-is-written-per-family-and-an-unframed-pairing-is-refused.md)).
That refusal is `transforms.framing_for`'s rather than one of the three below,
because it is about the transform against the family and not about the base — and it
arrives here as a `ValueError` `main` prints like every other way of getting a
variant wrong.
"""

import argparse
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from backend.bench.entry import CASE_SUFFIX, case_record
from backend.bench.library import (
    Case,
    CaseStatus,
    DiscoveredBy,
    Precondition,
    Transform,
    Trigger,
    VerdictClass,
    load_case,
    load_library,
)
from backend.bench.transforms import CITATIONS, derived_payload

CASES_DIR = Path(__file__).resolve().parents[1] / "backend" / "cases"
"""The library `scripts/admit.py` reads a proposal from, and the default here."""

ADR_0008_ARGUMENT_REQUIRED = (
    "a variant record needs the argument for shipping its words, in its header"
)
"""Why an empty `--argument` is a refusal and not a formatting choice.

ADR-0008 as amended: the classification is stated in the record's header, with the
argument, so it is auditable per case rather than asserted once. A variant is the
shape the amendment withholds — a wrapper whose wording is the working part — and
what carries it is the other half of the same ADR. That is an argument about one
record, and a script cannot make it.
"""

EXIT_REFUSED = 1
"""The record was not written: the base is wrong for a variant, or one is there."""


def variant_of(base: Case, transform: Transform, *, added_on: date) -> Case:
    """That base case's variant under that transform, as a proposal.

    Every field is either the transform's, the base case's or fixed:

    **The payload and the citation are the transform's.** The payload is applied
    once, here, through the one entry point that dispatches both kinds of construction
    — a respelling of the base payload, or the crescendo ladder built from the base
    record (`transforms.derived_payload`, ADR-0054 §1); the citation is the address the
    technique was published at, which is the field ADR-0008 requires beside a
    published payload and the reason this record may be committed at all.

    The construction is also where a **pairing** is refused: the framing a single-turn
    transform adds is written per family, so a base whose family this transform has no
    framing for gets no payload and therefore no record (ADR-0074 §2).

    **`SESSION_RETENTION` is added when the payload came back a script, and it is the
    one field this function does not simply copy.** Escalation across turns means
    nothing against an endpoint that forgets the previous one, so a record with more
    than one turn has to declare it (ADR-0053 §5) — and the base case of a crescendo
    is single-turn and therefore does not. Added rather than replacing what the base
    requires: the halt-defeat ladder still reads its verdict off a tool trace, so that
    variant needs both and is the case that will report *not measurable* most often,
    which is correct and is not a defect (CONTEXT.md, **not measurable**).

    **The family, the criterion and the coverage bound are the base case's.** A
    transform changes how a payload is spelled and never which failure it tests, so
    re-authoring `external_id.not_tested` would be a second coverage claim about one
    case, and two claims only have to disagree once. `load_library` refuses a variant
    in another family for the same reason.

    **The trigger, the provenance and the absent admission are fixed.**
    `NEW_TECHNIQUE_PUBLISHED` is what every variant in this group is (ADR-0051 §5);
    `AUTHORED` is what a person writing from a published technique is, and it selects
    ADR-0003's single-model bar rather than ADR-0012's cross-model one, which is
    ADR-0051 §5's second point; and there is no admission block, no history and no
    retirement because nothing has been measured yet.

    **The status is `ACTIVE` and not the base case's.** A variant of a **retired**
    case is a new proposal about a payload nobody has measured in that spelling, so
    it starts where every proposal starts; copying `RETIRED` across would also build
    a record `Case.__post_init__` refuses for a reason — no retirement date — that
    has nothing to do with what the caller got wrong.

    `added_on` is a parameter and not a clock reading, on `entry`'s terms: the day a
    record was written is a fact about the record, and a caller passing it is what
    lets the suite build one without asking today's date what it is.
    """
    if transform is Transform.PLAIN:
        raise ValueError(
            "plain is the identity, and a variant of a case under the identity is a "
            "second copy of that case: the same payload with its own id, its own "
            "admission and its own place in the denominator. `PLAIN` is a member so "
            "that every record says how it attacks, and never so that a record can "
            "derive from one (ADR-0051 §2)"
        )
    if base.verdict_class is VerdictClass.JUDGED:
        raise ValueError(
            f"{base.id} is judged, and no judged case gets a variant here. A judged "
            "verdict is reached through an adjudicator whose κ rests on fifteen "
            "hand-labelled transcripts per family (`rule.gold_transcripts_per_"
            "family`), all of them single-turn plain text, so a transformed payload "
            "would enter a κ-bearing denominator the gold set has no counterpart "
            "for. A judged variant is a separate ticket and it starts by saying what "
            "happens to κ"
        )
    if base.discovered_by is DiscoveredBy.RETRIEVED:
        raise ValueError(
            f"{base.id} is retrieved, and a variant of a retrieved case is not "
            "written here. Its payload is somebody else's published text and three "
            "things travel with it — the row, the licence and the notice (ADR-0047) "
            "— which are a `[retrieval]` block on that record and not on a "
            "derivative of it. Whether a derivative may carry the block is a "
            "decision about attribution, and it is not this one"
        )
    payload = derived_payload(transform, base)
    requires = base.requires
    if len(payload) > 1 and Precondition.SESSION_RETENTION not in requires:
        requires = (*requires, Precondition.SESSION_RETENTION)
    return Case(
        id=f"{base.id}-{transform.value}",
        family=base.family,
        external_id=base.external_id,
        payload=payload,
        success_condition=base.success_condition,
        verdict_class=base.verdict_class,
        applies_to=base.applies_to,
        requires=requires,
        added_on=added_on,
        trigger=Trigger.NEW_TECHNIQUE_PUBLISHED,
        discovered_by=DiscoveredBy.AUTHORED,
        transform=transform,
        derived_from=base.id,
        status=CaseStatus.ACTIVE,
        citation=CITATIONS[transform],
        judged_condition=base.judged_condition,
        planting=base.planting,
    )


def record_for(case: Case, *, argument: str) -> str:
    """That case as a record, with the person's argument as its header.

    The record body is `entry.case_record`, which is the writer `enter` reads back
    and refuses to leave a record on disk that does not load equal — so there is no
    second serialiser here, only the header. The header is the paragraph a person
    wrote, as TOML comments, and it is refused empty
    (`ADR_0008_ARGUMENT_REQUIRED`).
    """
    written = argument.strip()
    if not written:
        raise ValueError(
            f"{case.id}: {ADR_0008_ARGUMENT_REQUIRED}. The transform is published "
            "and its words are the working part, so what lets the payload ship is "
            "ADR-0008's other half — republishing what is already published "
            "protects nobody — and that is an argument about this record. Write it "
            "and pass the file"
        )
    header = "\n".join(f"# {line}".rstrip() for line in written.splitlines())
    return f"{header}\n\n{case_record(case)}"


def _write_once(path: Path, record: str, intended: Case) -> None:
    """Write the record, exclusively, and refuse to leave one that does not load back.

    Two disciplines borrowed from `entry._written`, which is the writer this script
    is not allowed to use — `enter` refuses a case with no admission, and a proposal
    has none by definition.

    **Exclusive creation**, because a record holds an argument a person wrote and,
    once admitted, a decay series a gate run wrote, and regenerating over either
    loses evidence this script cannot put back. `"x"` rather than a prior `exists`
    check, so nothing can be written in the gap between the two.

    **Read back**, because a record `load_case` cannot read is not a bad record, it
    is a library no run can load at all — and the header this script prepends is
    prose a person wrote, which is the part most likely to break one. A record that
    does not load equal is removed rather than left behind.
    """
    try:
        with path.open("x", encoding="utf-8") as opened:
            opened.write(record)
    except FileExistsError as already:
        raise FileExistsError(
            f"{path} is already there and is not overwritten. A record holds an "
            "argument a person wrote and, once admitted, a decay series a gate run "
            "wrote; regenerating over either loses evidence this script cannot put "
            "back. Delete it deliberately if that is what you mean"
        ) from already
    reloaded = load_case(path)
    if reloaded != intended:
        path.unlink()
        raise ValueError(
            f"{path} did not load back as the case it was written from, so it was "
            "removed. A record `load_case` cannot read as what it says is a library "
            "no run can load; the likeliest cause is the header paragraph"
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base", required=True, help="the id of the case this variant transforms"
    )
    parser.add_argument(
        "--transform",
        required=True,
        choices=[transform.value for transform in Transform],
        help="the published technique to apply",
    )
    parser.add_argument(
        "--argument",
        required=True,
        type=Path,
        help="a file holding the header paragraph ADR-0008 requires per record",
    )
    parser.add_argument(
        "--library",
        type=Path,
        default=CASES_DIR,
        help=(
            "the directory the base case is read from and a record is written to. "
            "scripts/admit.py reads backend/cases/ and nothing else, so a record "
            "written elsewhere has to be moved there before it can be measured"
        ),
    )
    parser.add_argument(
        "--added-on",
        type=date.fromisoformat,
        default=None,
        help="the day this record was written (default: today)",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="write the record into the library as a proposal, rather than print it",
    )
    args = parser.parse_args(argv)

    # Today read here rather than as the parser's default, which is evaluated when
    # the parser is built: a long-lived process would hand every record the date it
    # started on.
    added_on = args.added_on or date.today()
    held = {case.id: case for case in load_library(args.library)}
    base = held.get(args.base)
    if base is None:
        print(
            f"{args.base} is not in {args.library}. A variant's reading is a claim "
            "against the plain payload's, so the base has to be a case the library "
            "holds",
            file=sys.stderr,
        )
        return EXIT_REFUSED

    # The argument file is read inside the `try` with the two refusals, so that a
    # path that is not there prints a line and an exit code like every other way of
    # getting this wrong, rather than a traceback.
    try:
        variant = variant_of(base, Transform(args.transform), added_on=added_on)
        record = record_for(variant, argument=args.argument.read_text(encoding="utf-8"))
    except (ValueError, OSError) as refused:
        print(str(refused), file=sys.stderr)
        return EXIT_REFUSED

    if not args.write:
        print(record)
        return 0

    written = args.library / f"{variant.id}{CASE_SUFFIX}"
    try:
        _write_once(written, record, variant)
    except (OSError, ValueError) as refused:
        print(str(refused), file=sys.stderr)
        return EXIT_REFUSED
    print(f"{written} written — a proposal, with no [admission] block")
    print(
        "It is not a case yet and the suite will not load a library holding it. "
        f"Measure it: uv run python -m scripts.admit --identity 'your name' "
        f"--cases {variant.id} --write. If it does not clear the bar, delete the "
        "file — a rejected case is discarded, not parked — and record the reading "
        "in docs/validation.md, where an encoding the hardened agent decodes and "
        "refuses is a finding about that agent's decoder."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
