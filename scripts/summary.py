"""The page a CI step leaves behind, and the one document this project writes into
a world-readable place.

    python -m scripts.bench ... --summary "$GITHUB_STEP_SUMMARY"

**The page is the signed rendering, not a second account of the run.** `report.md` is
the document whose sha256 the payload carries and the signature covers, so a reader
who downloads the artefact and a reader who scrolls the run's page are reading the
same bytes. Composing a summary out of the result a second time would be a second
document with nothing binding it to the first — the drift `payload_for`'s single
caller in `scripts/bench.py` exists against, one surface further out.

**What this adds to it is the two things the rendering cannot hold.** Where the three
files went, so a recipient can fetch and verify them; and the families
`bench.withdrawn_for_want_of_a_plant` dropped before the run, which are absent from
the measured section rather than present at zero — correct in an artefact, and
unreadable on a page whose alternative reading is that the family passed.

**And it fails closed on a disclosure.** ADR-0008 keeps payload text out of the
artefact by construction: attempts are not serialised, so the rendering has no route
to a turn. That argument covers the rendering and does not cover this file — a line
added here later has nothing else standing in its way — and the surface it would leak
onto is the worst one this project has. A CI log on a public repository is
world-readable, is indexed, and outlives the artefact's retention window. So the rule
is checked here: `disclosures` reads the live library back and refuses a page that
carries a whole turn of a live case, or either of the two secrets a run was handed.

The endpoint is one of those secrets. `registration.endpoint_hash` exists because *a
live URL that answers jailbreak payloads is not a thing to write into a document that
travels*, and a job page travels further than the document does — so the URL is hashed
in the artefact and is refused here, on top of whatever masking the caller's runner
does for a value that came out of their secret store.

[ADR-0066](../docs/adr/0066-the-action-is-a-composite-step-in-the-callers-own-repository.md)
is the decision; `action.yml` is the caller of it.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path

from backend.bench.library import AnyFamily, Case
from scripts.probe_target import OperatorGap

VERIFY = "uv run python -m scripts.verify"
"""What a recipient runs over the directory, in the words the entrypoint prints."""


class Disclosed(Exception):
    """A page carried something no page may carry. Nothing was written.

    Raised rather than filtered, because a summary with a turn cut out of it is a
    document somebody has to trust the cutter of. The step goes red with the run's
    artefact already on disk and signed, which is the recoverable order: the report
    exists, and what failed is the publication of a page.
    """


def job_summary(
    rendering: str,
    *,
    artifact: str,
    out: str,
    withdrawn: Mapping[AnyFamily, OperatorGap] | None = None,
) -> str:
    """The signed rendering, under a preamble that says where to check it.

    `withdrawn` is the operator's own gaps and not the library's: a family with no
    planted artefact was never sent, so it has no rate, no `NotMeasurable` record and
    no line in the rendering. It is stated in `OperatorGap`'s own words rather than
    summarised, for the reason those words are long — a reader meeting *not run* with
    no sentence beside it is a reader guessing which of four answers it was
    (`probe_target.OperatorGap`, ADR-0004).
    """
    lines = [
        "## AgentAudit",
        "",
        f"The three files this run signed are attached to it as **{artifact}**. "
        "Check the signature over exactly the bytes that were signed, and the "
        "arithmetic against the counts they were derived from:",
        "",
        "```",
        f"{VERIFY} {out}",
        "```",
    ]
    if withdrawn:
        lines += [
            "",
            "### Families this run did not attempt",
            "",
            "Nothing was sent for these and nothing was measured, so they appear "
            "below with no rate rather than with a zero. A zero would be the one "
            "reading that is certainly wrong.",
            "",
        ]
        lines += [
            f"- **{family}** — {gap.stated()}." for family, gap in withdrawn.items()
        ]
    lines += ["", "---", "", rendering]
    return "\n".join(lines)


def disclosures(
    summary: str, *, cases: Sequence[Case], secrets: Sequence[str]
) -> tuple[str, ...]:
    """What is on this page that may not be, named without being printed.

    Two kinds, and both are compared over collapsed whitespace so that a page which
    re-wrapped a line is still caught:

    * **A whole turn of a live case.** The whole turn, never a fragment of one: a
      fragment is a phrase the library shares with ordinary English, and a guard that
      fired on those would be turned off within a week. The library's shortest turn
      is two hundred characters, so a whole-turn match is a copy and not a
      coincidence, and no length floor is needed to say so.
    * **A secret the run was handed** — the endpoint, the bearer token, the planted
      nonce. Named by
      what they are, because a disclosure report that quoted the value would be the
      disclosure.

    A tripwire and deliberately not a redactor. It catches a copy, which is the thing
    a mistake in this file would produce; it cannot catch a paraphrase, and nothing
    that reasons about what a page *means* could be trusted to.
    """
    page = _collapsed(summary)
    found = [
        f"{case.id} turn {position} appears on the page in full"
        for case in cases
        for position, turn in enumerate(case.payload, start=1)
        if _collapsed(turn) in page
    ]
    found += [
        f"a secret this run was handed appears on the page ({len(secret)} characters)"
        for secret in secrets
        if secret and _collapsed(secret) in page
    ]
    return tuple(found)


def write_summary(
    path: Path, page: str, *, cases: Sequence[Case], secrets: Sequence[str]
) -> None:
    """Append the page to the file the runner named, or refuse and say what leaked.

    Appended rather than written, because `$GITHUB_STEP_SUMMARY` is one file per job
    and a second step may have written into it already. Checked before it is opened,
    so a refusal leaves the file as it was.
    """
    if found := disclosures(page, cases=cases, secrets=secrets):
        raise Disclosed(
            "This page carries something that may not go into a CI log, which is "
            "world-readable on a public repository and outlives the artefact "
            "(ADR-0008). Nothing was written:\n"
            + "\n".join(f"  - {one}" for one in found)
        )
    with path.open("a", encoding="utf-8") as summary:
        summary.write(page if page.endswith("\n") else f"{page}\n")


def _collapsed(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
