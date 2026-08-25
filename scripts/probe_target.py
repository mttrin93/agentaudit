"""Runs the library against one external target — somebody's own agent, not a
reference agent.

    uv run python -m scripts.probe_target \
        --url https://finbrief.example/agent/messages \
        --identity "your name" --deterministic-only \
        --exposes-tool-calls --declared-tools summarise_brief fetch_filing

Two of the six families reach their verdict semantically, so a run has to say which
instrument decides them: `--adjudicator-model` supplies one and all six families run,
`--deterministic-only` runs the four deterministic families and records the other two
as not run. `--deterministic-only` needs no model credential of its own, which is what
makes a first run against a new endpoint cheap — the wire and the four re-derivable
families first, a judge and its cost second.

A diagnostic, and deliberately a thin one. It builds one `TargetConfig`, hands it
to `run_calibration`, and prints what came back. Registration, the nonce protocol,
the precondition check, the attempt loop, the evaluator and the scorer are all
reached through the same entry point the gate uses — there is one code path to a
target and this script does not add a second (spec: "Reference agents are reached
over real HTTP, and there is only one code path").

**Nothing here is calibration.** The target is not test equipment of known
quality, so its rates enter no gate, no discrimination score and no validation
document. This module imports no `discrimination` and constructs no `GateRule`:
the separation is by construction rather than by discipline, which is the only
kind that survives someone editing the file in a hurry.

**Two zeros do not mean what a zero looks like.** Both live outside the library,
so `measurability.py` cannot see them and `NotMeasurable` must not be borrowed for
them — that type is a statement about a *case's* precondition, and these are
statements about the operator's setup. Indirect injection needs a poisoned note
planted in content the target can retrieve, and halt defeat needs the endpoint to
report where the operator's stop signal landed. A target missing either produces a
clean 0.00 that reads as a defence and is not one, so each is printed beside the
rate it could explain (`OperatorGap`). A third gap is not a zero at all: under
`--deterministic-only` the two judged families are recorded as *not run*, because a
family missing from the output is a reader guessing which of three answers it was.

The token may come from `--token` or from `AGENTAUDIT_TARGET_TOKEN` in the
environment or `.env`, because a bearer token on a command line is a bearer token
in a shell history file.
"""

import argparse
import os
import sys
import uuid
from collections.abc import Mapping, Sequence
from decimal import InvalidOperation
from enum import StrEnum
from pathlib import Path

from dotenv import load_dotenv

from backend.bench.adjudication import Completion
from backend.bench.admission import NotAdmitted, admitted_library
from backend.bench.calibration import TargetRun, run_calibration
from backend.bench.completion import DEFAULT_ADJUDICATOR_MODEL, completion_for
from backend.bench.contract import TargetConfig
from backend.bench.library import Case, Family, VerdictClass
from backend.bench.rule import DECLARED_RULE
from backend.bench.scorer import Rate
from backend.graph.budget import BudgetExceeded, Layer, RunBudget
from backend.graph.runstate import Attempt
from backend.observability import TracedRun, install, trace_config, tracing
from scripts.console import (
    EXIT_ABORTED,
    EXIT_DECLINED,
    EXIT_WITHHELD,
    TOKEN_ENV,
    attest,
    excerpt,
    interactive_planter,
    note_is_planted,
    price,
    rate_line,
    terminal_approval,
)

CASES_DIR = Path(__file__).resolve().parents[1] / "backend" / "cases"

ADJUDICATOR_ENV = "AGENTAUDIT_ADJUDICATOR_MODEL"
"""Where the adjudicating model's configuration comes from when no flag names one."""

EXIT_NOT_REGISTERED = 1
"""Exit code when the nonce never came back. No attempt was made."""


class OperatorGap(StrEnum):
    """Something the operator's setup did not provide, and what it explains.

    Deliberately not `NotMeasurable`, and deliberately in this script rather than
    in `backend/bench/`. `NotMeasurable` is the library's answer to a *case
    precondition* a target cannot meet, decided before an attempt is spent and
    reportable as a family's outcome. These are the operator's own gaps: the bench
    cannot detect them, no attempt is skipped for them, and they annotate a rate
    rather than replace one. Two concepts that both mean "do not read this as a
    defence" and that a reader must still be able to tell apart.
    """

    NOTE_NOT_PLANTED = "note_not_planted"
    PLANTING_UNVERIFIED = "planting_unverified"
    NO_STOP_POSITION_RECORDED = "no_stop_position_recorded"
    ADJUDICATOR_NOT_SUPPLIED = "adjudicator_not_supplied"

    def stated(self) -> str:
        """The gap in the words the script prints."""
        match self:
            case OperatorGap.NOTE_NOT_PLANTED:
                return (
                    "not run — you did not confirm the third-party note is planted "
                    "in content this target can retrieve. The case would have sent "
                    "a message asking for a note that is not there, and a target "
                    "that cannot find it resists by having nothing to obey"
                )
            case OperatorGap.PLANTING_UNVERIFIED:
                return (
                    "a rate of zero is also what an unreachable note looks like. "
                    "The bench cannot see your content store, so that the note is "
                    "planted and that the payload's wording retrieves it are both "
                    "your statement rather than something measured here"
                )
            case OperatorGap.NO_STOP_POSITION_RECORDED:
                return (
                    "no attempt came back with a stop position, so no attempt "
                    "could have shown an action after one. This zero is what an "
                    "endpoint that never fills 'stop_signal_at' looks like, and "
                    "not necessarily a stop control that held"
                )
            case OperatorGap.ADJUDICATOR_NOT_SUPPLIED:
                return (
                    "not run — this was a --deterministic-only run, so no "
                    "adjudicating model was supplied and no attempt was spent "
                    "here. This family's verdict is a semantic decision and there "
                    "was no instrument to make one, which is a family that did "
                    "not run rather than one that held. Pass --adjudicator-model "
                    "to measure it"
                )


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="the target's endpoint URL")
    parser.add_argument(
        "--token",
        default=os.environ.get(TOKEN_ENV),
        help=(
            "the bearer token the endpoint expects. Defaults to "
            f"{TOKEN_ENV} from the environment or .env"
        ),
    )
    parser.add_argument("--name", default="target", help="what to call this target")
    parser.add_argument(
        "--agent-type",
        default="assistant",
        help="what kind of agent this is. Recorded, and read by nothing — see the "
        "banner this script prints about it",
    )
    parser.add_argument(
        "--identity",
        required=True,
        help=(
            "who is attesting and confirming this run, recorded with the "
            "attestation. Required, and never defaulted from the environment: it "
            "is the liability record, so nothing may pre-answer it"
        ),
    )
    parser.add_argument(
        "--exposes-tool-calls",
        action="store_true",
        help=(
            "the endpoint returns a tool_trace beside its reply. Without it, "
            "scope creep and halt defeat report not measurable rather than a rate"
        ),
    )
    parser.add_argument(
        "--declared-tools",
        nargs="*",
        default=[],
        help=(
            "the tools you declare this target has. Scope creep is a call outside "
            "this list, so the list is the whole of the comparison"
        ),
    )
    parser.add_argument(
        "--adjudicator-model",
        default=None,
        help=(
            "the bench's own model, which decides the two judged families. Your "
            "target's model is not this: one is the instrument and the other is "
            f"what is being measured. Defaults to {ADJUDICATOR_ENV} from the "
            f"environment or .env, then to {DEFAULT_ADJUDICATOR_MODEL}. No default "
            "is applied under --deterministic-only, so the two flags contradict "
            "each other rather than one quietly winning"
        ),
    )
    parser.add_argument(
        "--deterministic-only",
        action="store_true",
        help=(
            "run the four families whose verdict comes from a success condition "
            "and record the two judged families as not run. Needs no adjudicating "
            "model and spends nothing on one — the first run against a new "
            "endpoint, before adding an instrument and its cost"
        ),
    )
    parser.add_argument("--price-per-call", default=None)
    parser.add_argument("--currency", default="USD")
    args = parser.parse_args(argv)

    try:
        call_price = price(args.price_per_call, args.currency)
    except (InvalidOperation, ValueError) as bad:
        print(f"Not a usable price per call: {bad}")
        return EXIT_WITHHELD

    if not args.token:
        print(f"No token. Pass --token or set {TOKEN_ENV}.")
        return EXIT_WITHHELD

    if args.deterministic_only and args.adjudicator_model is not None:
        # Both flags answer the same question and answer it differently. Refused
        # rather than resolved by precedence: whichever way a precedence rule fell,
        # half the people who passed both would get the run they did not ask for,
        # and one of those halves pays for a model.
        print(
            "--deterministic-only and --adjudicator-model contradict each other. "
            "The first says the judged families do not run; the second supplies "
            "the instrument that runs them. Pass one."
        )
        return EXIT_WITHHELD

    adjudicator: Completion | None = None
    adjudicator_model: str | None = None
    if not args.deterministic_only:
        spec = args.adjudicator_model or os.environ.get(
            ADJUDICATOR_ENV, DEFAULT_ADJUDICATOR_MODEL
        )
        adjudicator_model = spec
        try:
            # Before the attestation: a run that reached its first judged attempt
            # before discovering it had no instrument would already have spent the
            # operator's budget on attempts nothing can score.
            adjudicator = completion_for(spec)
        except (KeyError, ValueError) as unusable:
            print(
                f"No usable adjudicating model: {unusable}. Pass a working "
                "--adjudicator-model, or --deterministic-only to run the four "
                "deterministic families without one."
            )
            return EXIT_WITHHELD

    if args.exposes_tool_calls and not args.declared_tools:
        # Scope creep is a call outside the declared list. Against an empty list
        # every call the target makes is outside it, so the family would report
        # 1.00 for a target doing its job — a finding manufactured by a missing
        # argument. Refused rather than warned about.
        print(
            "A target that exposes its tool calls has to declare which tools it "
            "has: scope creep is read against that list, and against an empty one "
            "every call this target makes would score as a finding. Pass "
            "--declared-tools."
        )
        return EXIT_WITHHELD

    target = TargetConfig(
        name=args.name,
        url=args.url,
        auth_token=args.token,
        agent_type=args.agent_type,
        exposes_tool_calls=args.exposes_tool_calls,
        declared_tools=tuple(args.declared_tools),
    )

    try:
        # The admitted library, never the raw one: a case that has not separated the
        # three reference agents may not be sent to somebody's production-adjacent
        # endpoint on the strength of nobody having checked (#12, spec story 69).
        cases = admitted_library(CASES_DIR)
    except NotAdmitted as unearned:
        print(f"The library holds a case that did not earn its place:\n{unearned}")
        return EXIT_WITHHELD
    gaps: dict[Family, OperatorGap] = {}
    if args.deterministic_only:
        cases, gaps = deterministic_subset(cases)
    print_header(target, cases, adjudicator_named=adjudicator is not None)

    attestation = attest(args.identity)
    if attestation is None:
        print("Attestation withheld. Nothing was sent.")
        return EXIT_WITHHELD

    if not note_is_planted(cases):
        gaps[Family.INDIRECT_PROMPT_INJECTION] = OperatorGap.NOTE_NOT_PLANTED
        cases = [
            case
            for case in cases
            if case.family is not Family.INDIRECT_PROMPT_INJECTION
        ]

    install(trace_config())
    # An id generated here and printed below, because a probe is not a run and no
    # record holds one: the id a trace joins to has to be an id its reader can see.
    # Named as a run id rather than a gate run's — a probe against somebody's own
    # agent decides nothing about the bench (ADR-0018).
    probe_id = str(uuid.uuid4())
    if tracing():
        print(f"trace id: {probe_id}")

    try:
        result = run_calibration(
            cases=cases,
            targets=[target],
            attestation=attestation,
            plant_nonce=interactive_planter(),
            approve=terminal_approval(attestation.identity),
            adjudicator=adjudicator,
            budget=RunBudget.declare(cases=cases, targets=[target], price=call_price),
            trace=TracedRun(id=probe_id, adjudicator_model=adjudicator_model),
        )
    except BudgetExceeded as abort:
        print(f"\nRun aborted on budget: {abort}")
        return EXIT_ABORTED

    if not result.approval.proceeded:
        print(f"\nRun not started: {result.approval.reason}")
        print("Nothing was sent, and nothing was spent.")
        return EXIT_DECLINED

    [target_run] = result.target_runs
    print_target_run(target_run, gaps)
    for layer in Layer:
        print(
            f"\ncalls spent, {layer} layer: {result.run_state.spent_in(layer)} "
            f"of a declared ceiling of {result.budget.ceiling(layer)}"
        )
    print(f"confirmed by: {result.approval.identity}")

    return EXIT_NOT_REGISTERED if target_run.registration.refused else 0


def print_header(
    target: TargetConfig, cases: Sequence[Case], adjudicator_named: bool
) -> None:
    """What is about to be run, and the caveat that governs every number below.

    The banner is printed before the run rather than only after it, because it
    changes what an operator should conclude from a low rate and they should know
    that before spending their inference budget on one.
    """
    print(f"AgentAudit — external target probe: {target.name} ({target.url})")
    print(f"cases loaded:      {len(cases)}")
    print(f"attempts per case: {DECLARED_RULE.attempts_per_case}")
    print(
        f"tool calls:        "
        f"{'exposed' if target.exposes_tool_calls else 'not exposed'}"
    )
    print(
        f"judged families:   "
        f"{'adjudicated' if adjudicator_named else 'not run (--deterministic-only)'}"
    )
    print(
        "\nREAD THIS BEFORE ANY NUMBER BELOW\n"
        "The library's cases are written for a document assistant — supplier "
        "notes, August invoices, a shared inbox, settling a balance. This target "
        f"is registered as '{target.agent_type}'. Every case declares the agent "
        "types it was written for, and one outside this target's type is not sent: "
        "the skip is printed with the results and counted nowhere, so an "
        "inapplicable case can never arrive as a pass (spec story 16). What that "
        "check cannot do is read your agent. The type is your own word for it, so a "
        "booking agent registered as 'assistant' is sent every case exactly as "
        "written, and a low rate can then mean the payload found no referent in "
        "this target's domain rather than that the target held. These numbers are "
        "evidence about payloads that landed and say nothing about ones that missed."
    )


def deterministic_subset(
    cases: Sequence[Case],
) -> tuple[list[Case], dict[Family, OperatorGap]]:
    """The cases a success condition can decide, and a gap for every family dropped.

    Selected on `Case.verdict_class` and never on the family name — the class is a
    field of the record for exactly this reason (ADR-0013), so a case that moves
    between families or a family renamed cannot change which instrument this run
    needed.

    The dropped families are recorded rather than omitted. A family absent from the
    output is a reader deciding for themselves why it is missing, and the honest
    answers — not measurable, not run, nothing succeeded — are three different
    things. This is the third: no attempt was spent, and the reason is a flag the
    operator passed rather than anything about the target.
    """
    judged = {
        case.family for case in cases if case.verdict_class is VerdictClass.JUDGED
    }
    return (
        [case for case in cases if case.verdict_class is not VerdictClass.JUDGED],
        dict.fromkeys(judged, OperatorGap.ADJUDICATOR_NOT_SUPPLIED),
    )


def print_target_run(target_run: TargetRun, gaps: dict[Family, OperatorGap]) -> None:
    """Everything measured against this target, and everything that was not."""
    registration = target_run.registration
    print(f"\ntarget {target_run.target.name} ({target_run.target.url})")
    status = "complete" if registration.complete else "REFUSED — nonce not echoed"
    print(f"  registration: {status}")
    print(f"  nonce:        {registration.nonce}")
    print(f"  echo reply:   {excerpt(registration.probe.reply_text)}")

    if registration.refused:
        # The one outcome that is not a result: an operator who cannot make their
        # target echo a value they planted has not shown they control it, so no
        # attempt was spent and there is no rate to read.
        print(
            "\nNo attempt was made. Registration proves you control the endpoint, "
            "and nothing runs without it. Check that the nonce line is in the "
            "system prompt, that the target reloaded it, and that the "
            "registration-check exception is there too."
        )
        return

    # Two sections, never one, and never a figure over both. A judged rate rests
    # on a semantic decision with a reliability figure of its own, so a reader who
    # could add it to a deterministic rate would be adding two different kinds of
    # evidence (ADR-0004, ADR-0005).
    _print_rates(
        "verdicts from a success condition — deterministic:",
        target_run.deterministic_rates,
        target_run,
    )
    _print_rates(
        "verdicts adjudicated semantically — judged, κ not yet measured (#11). "
        "Reported apart from the four above and never summed with them:",
        target_run.judged_rates,
        target_run,
    )

    for family in Family:
        if family in target_run.rates:
            continue
        # A refusal to measure, printed beside the rates and never as one of them
        # (ADR-0004). The operator-side gaps below are a third thing again.
        if (reason := target_run.not_measurable.get(family)) is not None:
            print(f"\n  {family}: {reason.stated()}")
        elif (gap := gaps.get(family)) is not None:
            print(f"\n  {family}: {gap.stated()}")

    # A fourth answer, and the one that is about the library rather than about this
    # target: a case not written for this agent type was not sent, no attempt was
    # spent on it, and it is in no denominator above (`applicability.py`).
    for skipped in target_run.not_applicable:
        print(f"\n  {skipped.stated()}")

    print(
        "\nNot a gate result, and not calibration. This target is not a reference "
        "agent: these numbers enter no gate, no discrimination score and no "
        "validation document, and this script computes none of them. Read them "
        "here and stop."
    )


def _print_rates(
    heading: str, rates: Mapping[Family, Rate], target_run: TargetRun
) -> None:
    """One class of family's rates, under its own heading, in declaration order.

    Prints nothing at all when the class measured nothing, because an empty
    section under a heading reads as six families that came back at zero.
    """
    if not rates:
        return
    print(f"\n  {heading}")
    for family in Family:
        if (rate := rates.get(family)) is None:
            continue
        print(f"  failure rate, {family}: {rate_line(rate)}")
        if (gap := soft_zero(family, rate.value, target_run.attempts)) is not None:
            print(f"    ↳ {gap.stated()}")


def soft_zero(
    family: Family, value: float, attempts: Sequence[Attempt]
) -> OperatorGap | None:
    """The operator-side gap that could explain a zero, when there is one.

    Only for the two families whose evidence depends on something outside the
    bench. A zero elsewhere is a zero.
    """
    if value != 0.0:
        return None
    if family is Family.INDIRECT_PROMPT_INJECTION:
        return OperatorGap.PLANTING_UNVERIFIED
    if family is Family.HALT_DEFEAT and not _stop_position_recorded(family, attempts):
        return OperatorGap.NO_STOP_POSITION_RECORDED
    return None


def _stop_position_recorded(family: Family, attempts: Sequence[Attempt]) -> bool:
    """Whether any attempt on this family came back with a stop position.

    Read from the transcripts rather than declared, because it is a fact about
    what the endpoint actually returned. A target that recorded the stop and still
    took no action after it resisted, and gets no annotation.
    """
    return any(
        trace is not None and trace.stop_signal_at is not None
        for attempt in attempts
        if attempt.family is family
        for trace in (attempt.transcript.tool_trace,)
    )


if __name__ == "__main__":
    sys.exit(main())
