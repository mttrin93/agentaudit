"""Reads a signed report against a committed bar, and says whether the step is red.

    uv run python -m scripts.bar --bar .github/agentaudit-bar.toml
    uv run python -m scripts.bar --bar .github/agentaudit-bar.toml --report ./out

**This is the step's colour, and it is deliberately not decided in the runner.** A bar
compiled into `action.yml` would be a threshold nobody outside this repository can read
(ADR-0003), so what decides is a file in the caller's own repository, reviewed in their
own pull requests, read here against the artefact the run signed. Nothing in this
script measures anything: every figure it reads was measured by the run and signed by
it, and this is arithmetic over a document.

**Two calls, and the first one happens before the run.** Called with no `--report` it
checks the bar itself and stops — which is what `action.yml` does before the bench
sends anything, so a team whose bar names five families finds out before spending an
inference budget on a document nothing will be compared against.

**It does not check the signature.** `scripts/verify.py` is the one definition of that
check — the signature over exactly these bytes, the rendering's digest, the arithmetic
re-derived — and a second implementation here would be a second verifier, which is the
drift this project refuses everywhere it has one definition of something. The Action
runs both.

[ADR-0067](../docs/adr/0067-the-bar-is-per-family-and-a-withdrawn-family-is-not-green.md)
is the decision; `backend/bench/bar.py` is the arithmetic.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from backend.bench.bar import BarNotDeclared, Outcome, decided, read_bar

REPORT = "report.json"
"""The signed payload inside the directory a run published, under the fixed name a
recipient does not have to be told (`rendering.publish`, `scripts/verify.py`)."""

EXIT_BELOW_THE_BAR = 1
"""Exit code when a family this bar covers is worse than declared, or unmeasured.

**The one non-zero code in this project that is a figure about the target**, and the
whole reason this script exists. Everything else that stops a run — a refused
attestation, a missing key, a declined ceiling, a page that would have disclosed —
is a fact about the run or about the bench (ADR-0065 §4), and the entrypoint still
returns 0 for a completed run whatever its rates.
"""

EXIT_CANNOT_DECIDE = 2
"""Exit code when the instrument or the run did not stand, so nothing was decided.

Its own code and never `EXIT_BELOW_THE_BAR`, which is the distinction the whole
ticket turns on: two codes would collapse *your agent regressed* into *our bench is
broken*, and the second is not a finding about anybody's target (ADR-0018). On
`scripts/gate.py`'s and `scripts/verify.py`'s own precedent, both of which report a
third answer rather than a polite failure.
"""

EXIT_NO_BAR = 3
"""Exit code when the bar itself is not a bar. Nothing was decided and, in the
Action, nothing had yet been sent.

The step's fourth answer — **refused before sending** — and the reason this script
is called once before the run as well as once after it: a bar naming five of six
families is a mistake to catch before somebody's inference budget is spent, not
after.
"""


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bar",
        required=True,
        help=(
            "the committed bar: the worst band that passes for each of the six "
            "families, or the reason a family is switched off, and how old the "
            "bench's own gate run may be"
        ),
    )
    parser.add_argument(
        "--report",
        default=None,
        help=(
            "the directory holding report.json — the same directory "
            "`scripts.verify` takes. Left out, this checks the bar and decides "
            "nothing, which is what a workflow does before the run"
        ),
    )
    args = parser.parse_args(argv)

    try:
        bar = read_bar(Path(args.bar).read_text(encoding="utf-8"))
    except OSError as unreadable:
        print(f"No bar at {args.bar}: {unreadable}")
        return EXIT_NO_BAR
    except BarNotDeclared as refused:
        print(f"{args.bar} does not declare a bar:\n{refused}")
        return EXIT_NO_BAR

    if args.report is None:
        covered = ", ".join(sorted(family.value for family in bar.covers))
        print(
            f"This bar covers {covered or 'no family'}, and holds each one to the "
            f"band declared for it. It accepts a gate run up to "
            f"{bar.gate_max_age_days} days old at the time of a run. Nothing was "
            "decided here: no report was named."
        )
        for family, reason in sorted(
            bar.not_measured.items(), key=lambda pair: pair[0].value
        ):
            print(f"  {family.value}: switched off in the bar — {reason}")
        return 0

    payload = Path(args.report) / REPORT
    try:
        document = json.loads(payload.read_text(encoding="utf-8"))
    except OSError as unreadable:
        # Not `EXIT_BELOW_THE_BAR`: a run that wrote no artefact is a run that did
        # not finish, and reporting a missing file as a target's failure is exactly
        # the confusion the third code exists to prevent.
        print(f"No report at {payload}: {unreadable}\n{_UNDECIDED}")
        return EXIT_CANNOT_DECIDE
    except ValueError as unparsable:
        print(f"{payload} is not readable JSON: {unparsable}\n{_UNDECIDED}")
        return EXIT_CANNOT_DECIDE
    if not isinstance(document, dict):
        print(f"{payload} does not hold a report.\n{_UNDECIDED}")
        return EXIT_CANNOT_DECIDE

    decision = decided(document, bar)
    print(f"{payload}, against the bar declared in {args.bar}:\n")
    print(decision.stated())
    match decision.outcome:
        case Outcome.PASSED:
            return 0
        case Outcome.BELOW_THE_BAR:
            return EXIT_BELOW_THE_BAR
        case Outcome.CANNOT_DECIDE:
            return EXIT_CANNOT_DECIDE


_UNDECIDED = (
    "Nothing was decided against the bar. This is not a statement about the target: "
    "a run that left no readable artefact is a run that did not finish, and an "
    "endpoint having a bad minute must not read as an agent that defended itself."
)


if __name__ == "__main__":
    sys.exit(main())
