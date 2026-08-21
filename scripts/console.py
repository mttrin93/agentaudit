"""The terminal side of a run: what is asked, how it is asked, and how a rate prints.

Held in one place because there is more than one script that reaches a target —
`calibrate.py` runs the reference agents, `probe_target.py` runs somebody's own —
and the consent mechanism must not exist twice. Two copies of the attestation is
two places for a `--yes` to appear in, and ADR-0007 is explicit that a consent
mechanism with a flag to skip it is a convenience feature after all.

Nothing here decides anything. It asks, it formats, and it hands back what the
human said, so that the difference between the two scripts is which target they
point at rather than what they ask before pointing.

**The scored and adaptive blocks are both built here and never in one block.** They
are two sections with two `_section` builders and no function that returns them
joined, because they are measured on different denominators and a reader who met
`A_break` inside a table of rates would have met a number that decides nothing in
the place where everything decides something (ADR-0010, ADR-0011). Each builder
returns text so that the terminal and the durable record print the same words —
a run whose recorded document differed from what the operator saw would be two
records of one run.
"""

import sys
from collections.abc import Sequence
from decimal import Decimal

from backend.bench.adaptive.discrimination import NoFamiliesInScope, measure
from backend.bench.adaptive.episode import AdaptiveEpisode
from backend.bench.admission import library_provenance, outcome_for
from backend.bench.calibration import CalibrationResult
from backend.bench.library import Case, bar_for, trigger_counts
from backend.bench.registration import Attestation
from backend.bench.retirement import (
    RetirementDecision,
    RunHistory,
    retired_cases,
    stated_retirement,
)
from backend.bench.rule import DECLARED_RULE, GateRule
from backend.bench.scorer import Rate
from backend.graph.approval import Approval, Approve
from backend.graph.budget import BudgetPayload, CallPrice

EXIT_WITHHELD = 2
"""Exit code when the attestation was not made. Not an error — a refusal."""

EXIT_DECLINED = 3
"""Exit code when the estimated cost was not confirmed at the interrupt."""

EXIT_ABORTED = 4
"""Exit code when the run hit its declared ceiling and stopped."""

REPLY_EXCERPT = 400


def price(per_call: str | None, currency: str) -> CallPrice | None:
    """The operator's price per call, or `None` for a run they did not price."""
    if per_call is None:
        return None
    return CallPrice(per_call=Decimal(per_call), currency=currency)


def attest(identity: str) -> Attestation | None:
    """Collect the three statements, one question each.

    One question each rather than one question for all three, because the record
    has a field per statement and a single `[y/N]` cannot fill them honestly.
    Asking separately is also the only way the type's refusal is ever reached on
    the path a human takes — a partial attestation can be *given* here, and is
    then declined with the statement that was withheld named back.
    """
    if not identity.strip():
        print("An attestation records who made it, so --identity cannot be blank.")
        return None

    print(
        f"Attestation, as {identity}. All three are required before anything is sent."
    )
    answers = {
        field: confirmed(f"  · {wording}? [y/N] ")
        for field, wording in Attestation.STATEMENTS
    }

    try:
        return Attestation(identity=identity, **answers)
    except ValueError as refusal:
        print(f"\n{refusal}")
        return None


def terminal_approval(identity: str) -> Approve:
    """Answer the graph's interrupt from the terminal.

    The same halt is answered by an HTTP request at 6b. Only this function
    changes; the graph does not.
    """

    def approve(presented: BudgetPayload) -> Approval:
        print("\nEstimated cost of this run, before the first call:")
        for line in presented["presented"]:
            print(line)
        if confirmed("\nProceed and spend this? [y/N] "):
            return Approval(confirmed=True, identity=identity)
        return Approval(
            confirmed=False,
            identity=identity,
            reason="declined at the approval interrupt",
        )

    return approve


def confirmed(prompt: str) -> bool:
    """A yes, and only from a human at a terminal.

    A run that is not being watched has nobody to consent on its behalf, so a
    piped or absent stdin is a no rather than a default.
    """
    if not sys.stdin.isatty():
        print(f"{prompt}\n  no terminal to ask — treating as no")
        return False
    return input(prompt).strip().lower() in {"y", "yes"}


def pause(prompt: str) -> None:
    """Wait for a human to do something off-machine, then carry on.

    Not a consent question and deliberately not `confirmed`: what it waits for is
    an edit the bench cannot make and cannot check, so there is no answer to
    record. Without a terminal it does not block, because the run has already
    been refused by then and hanging would be the wrong failure.
    """
    if not sys.stdin.isatty():
        print(f"{prompt}\n  no terminal to wait at — carrying on")
        return
    input(prompt)


def rate_line(rate: Rate) -> str:
    """One failure rate, with the counts it came from and its interval."""
    interval = rate.interval
    return (
        f"{rate.value:.2f} ({rate.successes}/{rate.attempts}), "
        f"Wilson {DECLARED_RULE.interval_confidence:.0%} "
        f"[{interval.lower:.3f}, {interval.upper:.3f}]"
    )


def excerpt(text: str) -> str:
    """As much of a reply as a reader needs, with the full length stated."""
    collapsed = " ".join(text.split())
    if len(collapsed) <= REPLY_EXCERPT:
        return collapsed
    return (
        f"{collapsed[:REPLY_EXCERPT]}… "
        f"[{len(collapsed)} chars, full transcript recorded]"
    )


def print_episodes(result: CalibrationResult, trivial: str, hardened: str) -> None:
    """The adaptive section, printed."""
    print(episodes_section(result, trivial=trivial, hardened=hardened))


def episodes_section(result: CalibrationResult, trivial: str, hardened: str) -> str:
    """The adaptive section, in its own block and carrying no rate.

    Printed apart from the rates and never beside them: an episode has no
    denominator, `A_break` and `A_effort` are measured on families and turns rather
    than on attempts, and nothing here decides anything about the gate (ADR-0010,
    ADR-0011). Labelled *not reproducible*, because claiming a stochastic search is
    reproducible would be the overreach the judge's narrative was demoted for.
    """
    episodes = result.run_state.episodes
    lines = ["", "adaptive layer — recorded, not reproducible, and scored on nothing"]
    if not episodes:
        return "\n".join((*lines, "  no episode ran"))
    for episode in episodes:
        # The target is named here because this is the bench's own record, read by
        # the engineer who ran it. What the attacker saw was an opaque handle.
        lines.append(
            f"  {episode.target_name} / {episode.family}: {episode.stated()} "
            f"after {episode.turns} turns"
        )
        for proposal in episode.proposals:
            # Proposed, never admitted. `propose_case` drafts and the admission
            # gate decides, and an adaptive-discovered case faces the cross-model
            # bar — which needs a second underlying model and so a second run
            # (ADR-0012, `scripts/admit.py --second-model`).
            lines.append(
                f"    proposed {proposal.case.id}: {proposal.description} "
                f"— faces the {bar_for(proposal.case.discovered_by)} bar, "
                "not admitted by having been proposed"
            )
    lines.append(
        adaptive_discrimination_section(episodes, trivial=trivial, hardened=hardened)
    )
    return "\n".join(lines)


def print_adaptive_discrimination(
    episodes: Sequence[AdaptiveEpisode], trivial: str, hardened: str
) -> None:
    """The adaptive block, printed."""
    print(adaptive_discrimination_section(episodes, trivial=trivial, hardened=hardened))


def adaptive_discrimination_section(
    episodes: Sequence[AdaptiveEpisode], trivial: str, hardened: str
) -> str:
    """`A_break`, `A_effort` and the sign test, in their own block.

    Never in a `D` table and never named `D`: these are measured on episodes and
    families, and a Wilson interval on `n = 6` has no business printed beside one on
    `n = 30` (ADR-0011). The block prints the reading table whatever the outcome,
    so a reader sees what each of the four possible answers would have meant.
    """
    try:
        return measure(episodes, trivial=trivial, hardened=hardened).stated()
    except NoFamiliesInScope as unmeasured:
        # A stated refusal rather than a zero. "No separation" and "nothing was
        # measured" are the two readings that must never collapse into one number.
        return f"adaptive discrimination: not read — {unmeasured}"


def print_provenance(cases: Sequence[Case]) -> None:
    """The provenance block, printed."""
    print(provenance_section(cases))


def provenance_section(cases: Sequence[Case]) -> str:
    """Who found this library, and the bar each case entered under.

    Printed on every run, because ADR-0012 asks for the adaptive-discovered
    fraction of the *live* library rather than for a number somebody can look up:
    a library filling with routes fitted to these three agents should arrive as a
    series across runs and not as a surprise at the end of one.

    Every provenance is printed whether or not it is used, so a fraction of zero
    reads as a count rather than as an absence of the thing.
    """
    # One block and one denominator. The live counts, the adaptive-discovered share
    # of them, and the retirement rate by provenance are the two series ADR-0012
    # asks for on every gate run: how far the library has drifted towards routes
    # fitted to these three agents, and whether the drift is doing the damage the
    # cross-model bar exists to prevent.
    return "\n".join(
        (
            *(
                f"{'' if line.startswith(' ') else '  '}{line}"
                for line in library_provenance(cases).stated().splitlines()
            ),
            # The bar beside the case, so an adaptive-discovered case is
            # distinguishable from an authored one by reading the report (ADR-0012).
            *(f"  {outcome_for(case).stated()}" for case in cases),
        )
    )


def print_retirement(
    run: RunHistory,
    decisions: Sequence[RetirementDecision],
    cases: Sequence[Case],
) -> None:
    """The retirement section, printed."""
    print(retirement_section(run, decisions, cases))


def retirement_section(
    run: RunHistory,
    decisions: Sequence[RetirementDecision],
    cases: Sequence[Case],
    rule: GateRule = DECLARED_RULE,
) -> str:
    """The decay series this run stored, what the rule made of it, and what has retired.

    Its own block, below the decision and beside the provenance series, because none
    of it decides the gate: a case retires on what two runs measured and the run
    printing it has already been decided. The rule is printed above the readings for
    the reason `GateRule.stated()` is printed above the decision — a threshold nobody
    can read beside its result is a threshold that can be moved (ADR-0003).

    The retired cases are listed with the date and the final score they retired on,
    whatever their number, because "kept, never deleted" is a claim a reader should be
    able to check rather than take from a sentence (spec story 74).
    """
    retired = retired_cases(cases)
    lines = [
        "",
        "retirement — D stored for every case on this run, and nothing here decides "
        "the gate",
        f"  the rule: a case below D {rule.retirement_floor:.2f} on two consecutive "
        "gate runs on one model is marked retired, kept with its retirement date and "
        "its final score, and never deleted (ADR-0003, ADR-0022)",
        "  a run on a stub model stores its readings and retires nothing: a fixture "
        "with hardcoded replies is not a measurement of the field (ADR-0022)",
        f"  {run.stated()}",
        *(f"  {decision.stated()}" for decision in decisions),
        f"  retired so far: {len(retired)} of {len(cases)} ever written",
        *(f"    {stated_retirement(case, rule)}" for case in retired),
        "  why these cases exist — the closed set of six triggers, and how much of "
        "the library each accounts for:",
        *(
            f"    {trigger}: {count} — {trigger.stated()}"
            for trigger, count in trigger_counts(cases).items()
        ),
    ]
    return "\n".join(lines)
