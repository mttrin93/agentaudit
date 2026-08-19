"""Runs the multi-model validity check. The same library, twice, on two models.

    uv run python -m scripts.swap --identity "your name" \\
        --model openrouter:openai/gpt-4.1-nano \\
        --second-model openrouter:openai/gpt-4o-mini
    uv run python -m scripts.swap --identity "your name" \\
        --model stub:obedient --second-model stub:cooperative
    uv run python -m scripts.swap --identity "your name" --record docs/swap-runs

**This answers the strongest objection anyone can raise against the bench.** Does it
measure the agent's defences, or the model's default refusals? The library, the three
reference agents, the sample size and the rule are held still; the reference agents'
underlying model is the one thing that moves. Then `D` is compared per family, and the
comparison is published whatever it shows (spec story 67).

**The swap is configuration, not code.** `--model` and `--second-model` are two
strings of the form `<provider>:<model>` that reach `create_reference_app` and nothing
else (`targets/reference/model.py`, ticket #2). Nothing below branches on which model
it is running, and the two runs differ in that one setting: same eighteen cases, same
`ReferenceConfig.agents`, same `GateRule`, one library version printed for both.

**It is not a gate, and it does not decide one.** Two gate readings are taken because
`read_gate` is how a family's three rates become a `D` a reader can re-derive, and
each is printed in full — but this command's answer is the comparison, and the check
has no declared pass rule. So there is no exit code that claims one: a comparison that
was made exits zero whatever it found, and only a refusal, a decline or an abort
exits non-zero. Inventing a collapse threshold here would be declaring a bar nobody
agreed, at the one point in the build where the result is already in front of us.

**κ is measured once, not twice.** The adjudicator is the same instrument in both
runs and the gold set is the same gold set; the reference agents' model is nowhere in
that measurement. Measuring it per model would spend the operator's money to
re-derive the same number and would let the two runs' fit sets differ, which would
confound the comparison with a change of denominator.

**The adaptive layer runs in both and prints in its own section.** `A_break` and
`A_effort` are compared across the swap in a block of their own, carrying no rate, no
interval, no band and no `D` (ADR-0010, ADR-0011). And the routes the attacker
proposed face the **cross-model admission bar**: each proposed case is measured
against all three agents on *both* models, and `promote` admits it only if it
separates on both. The rejections are counted and recorded, because a route that
separates on one model only is itself a finding about that route (ADR-0012).

**It asks before it sends anything**, on the same terms as every other entry point:
the three attestation statements one at a time, then the estimated cost of each run
at the approval interrupt. Nothing here has a `--yes` (ADR-0007).
"""

import argparse
import os
import secrets
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import InvalidOperation
from pathlib import Path

from dotenv import load_dotenv

from backend.bench.adaptive.attacker import AttackerCompletion
from backend.bench.adaptive.crossmodel import AdaptiveSwap
from backend.bench.adaptive.crossmodel import compare as compare_adaptive
from backend.bench.adaptive.discrimination import (
    AdaptiveDiscrimination,
    NoFamiliesInScope,
)
from backend.bench.adaptive.discrimination import measure as measure_adaptive
from backend.bench.adaptive.promotion import Promotion, promote
from backend.bench.adaptive.proposal import ProposedRoute
from backend.bench.adjudication import Completion
from backend.bench.admission import NotAdmitted, admitted_library, counted
from backend.bench.calibration import CalibrationResult, TargetRun, run_calibration
from backend.bench.completion import (
    DEFAULT_ADJUDICATOR_MODEL,
    DEFAULT_ATTACKER_MODEL,
    completion_for,
)
from backend.bench.crossmodel import (
    CrossModelRejections,
    ModelReading,
    ModelSwap,
    NotASwap,
    compare,
    rejections,
)
from backend.bench.evaluator import Verdict
from backend.bench.gate import NotAGateRun, read_gate
from backend.bench.goldset import load_gold_sets, measure_reliability
from backend.bench.library import AdmissionReading, Case, Family, VerdictClass
from backend.bench.registration import Attestation
from backend.bench.retirement import live_library
from backend.bench.rule import DECLARED_RULE
from backend.bench.scorer import Reliability
from backend.graph.approval import Approve
from backend.graph.budget import BudgetExceeded, CallPrice, RunBudget
from backend.targets.reference.hardened import HARDENED
from backend.targets.reference.model import ModelConfig
from backend.targets.reference.operator import nonce_planter
from backend.targets.reference.server import (
    REFERENCE_AGENTS,
    ReferenceConfig,
    create_reference_app,
)
from backend.targets.reference.serving import serve
from backend.targets.reference.trivial import TRIVIAL
from backend.targets.reference.weak import WEAK
from scripts.console import (
    EXIT_ABORTED,
    EXIT_DECLINED,
    EXIT_WITHHELD,
    attest,
    episodes_section,
    price,
    terminal_approval,
)
from scripts.gate import CASES_DIR, DEFAULT_MODEL, GOLDSET_DIR, reference_targets

SWAP_RUNS_DIR = Path(__file__).resolve().parents[1] / "docs" / "swap-runs"

DEFAULT_SECOND_MODEL = "openrouter:openai/gpt-4o-mini"
"""The second model, and it is a deliberate choice rather than a spare string.

`gpt-4o-mini` refused the published extraction payload *while running the trivial
agent* in the very first tracer bullet — an agent with no defences at all — which is
the confound this check exists to measure, seen once and never at the declared sample
size (docs/validation.md, 2026-08-17). A model that will not host the trivial agent
at all is no use here: `claude-haiku-4.5` reads the trivial system prompt as an
injection and declines to echo the nonce, so it never registers and nothing is
measured against it.
"""

ATTACKER_STAND_IN = "backend/bench/adaptive/scripted.py — the deterministic stand-in"
"""The name a run declares when it wants the scripted attacker rather than a model.

The same string `scripts/gate.py`'s own suite uses, so a record naming it says which
attacker produced the adaptive half rather than leaving a reader to infer it.
"""


@dataclass(frozen=True)
class ModelRun:
    """One model's whole run: what it scored, and what its adaptive layer did.

    Two fields, kept apart at the type level for the reason ADR-0010 gives: the
    reading feeds the scored comparison, the episodes feed the adaptive one, and
    there is no field here through which one could reach the other.
    """

    reading: ModelReading
    result: CalibrationResult

    @property
    def adaptive(self) -> AdaptiveDiscrimination | None:
        """This run's own `A_break` block, or `None` where no family was in scope."""
        try:
            return measure_adaptive(
                self.result.run_state.episodes,
                trivial=TRIVIAL.name,
                hardened=HARDENED.name,
            )
        except NoFamiliesInScope:
            return None

    @property
    def proposals(self) -> tuple[ProposedRoute, ...]:
        """Every route this run's attacker put forward, in the order it did."""
        return tuple(
            proposal
            for episode in self.result.run_state.episodes
            for proposal in episode.proposals
        )


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--identity",
        required=True,
        help=(
            "who is attesting and confirming this run, recorded with the "
            "attestation. Required, and never defaulted from the environment: it is "
            "the liability record, so nothing may pre-answer it"
        ),
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("AGENTAUDIT_REFERENCE_MODEL", DEFAULT_MODEL),
        help="the reference agents' first underlying model, as '<provider>:<model>'",
    )
    parser.add_argument(
        "--second-model",
        default=os.environ.get(
            "AGENTAUDIT_SECOND_REFERENCE_MODEL", DEFAULT_SECOND_MODEL
        ),
        help=(
            "the model the library is re-run on. The one setting that moves between "
            "the two runs, and it has to be a different model: two runs of one model "
            "measure this bench's run-to-run variation and not a swap"
        ),
    )
    parser.add_argument(
        "--adjudicator-model",
        default=os.environ.get(
            "AGENTAUDIT_ADJUDICATOR_MODEL", DEFAULT_ADJUDICATOR_MODEL
        ),
        help=(
            "the bench's own model, which decides the two judged families and is the "
            "instrument κ is measured on. Never a reference agent's model, and "
            "measured once for both runs"
        ),
    )
    parser.add_argument(
        "--attacker-model",
        default=os.environ.get("AGENTAUDIT_ATTACKER_MODEL", DEFAULT_ATTACKER_MODEL),
        help=(
            "the model the adaptive attacker runs on, in both runs. A third setting, "
            "and it decides nothing here"
        ),
    )
    parser.add_argument(
        "--price-per-call",
        default=None,
        help=(
            "what one call to a target costs you, from your own provider. Omitted, "
            "the run reports its cost as not priced rather than as zero"
        ),
    )
    parser.add_argument(
        "--currency", default="USD", help="the currency --price-per-call is in"
    )
    parser.add_argument(
        "--cases",
        default=str(CASES_DIR),
        help=(
            "the directory the case records are read from. Read and never written: "
            "the decay series is a gate run's to store, and a case's D is stored "
            "against the model the gate declares rather than against two (#14)"
        ),
    )
    parser.add_argument(
        "--record",
        default=str(SWAP_RUNS_DIR),
        help=(
            "the directory a dated record of this comparison is written to. Its own "
            "document, which is not docs/validation.md: that one is written by hand "
            "and reads the records"
        ),
    )
    args = parser.parse_args(argv)

    try:
        call_price = price(args.price_per_call, args.currency)
    except (InvalidOperation, ValueError) as bad:
        print(f"Not a usable price per call: {bad}")
        return EXIT_WITHHELD

    if args.model == args.second_model:
        print(
            f"--model and --second-model are both {args.model!r}. Reading one model "
            "twice is a repeat and not a swap: the difference between two such runs "
            "is this bench's own run-to-run variation, and reporting it as a model "
            "swap would answer this check's question with a number about something "
            "else. Nothing was sent."
        )
        return EXIT_WITHHELD

    try:
        models = [ModelConfig.parse(args.model), ModelConfig.parse(args.second_model)]
    except ValueError as unusable:
        print(f"Not a usable model configuration: {unusable}")
        return EXIT_WITHHELD

    cases_dir = Path(args.cases)
    try:
        library = admitted_library(cases_dir)
        cases = live_library(library)
        gold_sets = load_gold_sets(GOLDSET_DIR, cases)
    except (NotAdmitted, ValueError, KeyError) as unusable:
        print(f"The check cannot run against this library:\n{unusable}")
        return EXIT_WITHHELD

    print_declared(cases, models, args, len(gold_sets))

    try:
        adjudicator = completion_for(args.adjudicator_model)
        attacker = completion_for(args.attacker_model)
    except (KeyError, ValueError) as unusable:
        print(f"No usable bench model: {unusable}")
        return EXIT_WITHHELD

    attestation = attest(args.identity)
    if attestation is None:
        print("Attestation withheld. Nothing was sent.")
        return EXIT_WITHHELD
    approve = terminal_approval(attestation.identity)

    measured: list[CalibrationResult] = []
    for model in models:
        outcome = calibrate_on(
            model=model,
            cases=cases,
            attestation=attestation,
            approve=approve,
            adjudicator=adjudicator,
            attacker=attacker,
            price_per_call=call_price,
        )
        if isinstance(outcome, int):
            return outcome
        measured.append(outcome)

    # After both suites and only once. After, so that a declined run spends nothing
    # at all — including on the bench's own instrument, which is the discipline
    # `scripts/gate.py` follows. Once, because κ is the adjudicator measured against
    # the gold set and the reference agents' model is nowhere in that measurement:
    # measuring it per model would pay twice for one number and would let the two
    # runs' fit sets differ, which would confound the comparison with a change of
    # denominator.
    print(
        f"\nmeasuring the adjudicator against {len(gold_sets)} gold set(s), "
        f"{sum(len(gold.transcripts) for gold in gold_sets)} labelled transcripts, "
        "on your key"
    )
    reliability = measure_reliability(gold_sets, adjudicator)

    runs: list[ModelRun] = []
    for model, result in zip(models, measured, strict=True):
        read = read_run(model=model, result=result, reliability=reliability)
        if isinstance(read, int):
            return read
        runs.append(read)

    first, second = runs
    try:
        swap = compare(first.reading, second.reading)
    except NotASwap as ungated:
        print(f"\nThese two runs cannot be compared:\n{ungated}")
        return EXIT_WITHHELD

    print()
    print(swap.stated())

    adaptive = adaptive_swap(first, second)
    print()
    print(
        adaptive.stated()
        if adaptive is not None
        else (
            "does A_break survive the model swap? — not read: one of the two runs "
            "had no family in scope, and a zero would read as an attacker that "
            "found nothing"
        )
    )

    refused = cross_model_bar(
        runs=runs,
        attestation=attestation,
        approve=approve,
        adjudicator=adjudicator,
        adjudicator_model=args.adjudicator_model,
        price_per_call=call_price,
    )
    if isinstance(refused, int):
        return refused
    rejected, promotions = refused
    print()
    print(rejected.stated())
    for promotion in promotions:
        print(promotion.stated())

    written = record_swap(
        swap=swap,
        adaptive=adaptive,
        rejected=rejected,
        directory=Path(args.record),
        identity=first.result.approval.identity,
        adjudicator_model=args.adjudicator_model,
        attacker_model=args.attacker_model,
        runs=runs,
    )
    print(f"\nthis comparison's own document: {written}")
    return 0


def calibrate_on(
    *,
    model: ModelConfig,
    cases: Sequence[Case],
    attestation: Attestation,
    approve: Approve,
    adjudicator: Completion,
    attacker: AttackerCompletion,
    price_per_call: CallPrice | None,
) -> CalibrationResult | int:
    """Run the whole library against all three reference agents on one model.

    One served app and one calibration per model, so a reading is a reading *on a
    model* and the two never share a denominator. Returns an exit code where the run
    did not happen: the operator declined the cost, the run hit its ceiling, or a
    reference agent never registered and so was never measured.
    """
    auth_token = secrets.token_urlsafe(16)
    app = create_reference_app(ReferenceConfig(model=model, auth_token=auth_token))
    with serve(app) as base_url:
        targets = reference_targets(base_url, auth_token)
        print(f"\nrunning the whole library on {model}")
        try:
            result = run_calibration(
                cases=list(cases),
                targets=targets,
                attestation=attestation,
                plant_nonce=nonce_planter(base_url),
                approve=approve,
                adjudicator=adjudicator,
                attacker=attacker,
                budget=RunBudget.declare(
                    cases=list(cases), targets=targets, price=price_per_call
                ),
            )
        except BudgetExceeded as abort:
            print(f"\nRun aborted on budget: {abort}")
            return EXIT_ABORTED

    if not result.approval.proceeded:
        print(f"\nRun not started: {result.approval.reason}")
        print("Nothing was sent, and nothing was spent.")
        return EXIT_DECLINED

    unregistered = [
        run.target.name for run in result.target_runs if run.registration.refused
    ]
    if unregistered:
        print(
            f"\n{', '.join(unregistered)} did not echo the nonce on {model}, so "
            "nothing was measured against them. A model that will not host a "
            "reference agent cannot be one of the two: an agent that never "
            "registered is not an agent that resisted (docs/validation.md)."
        )
        return EXIT_WITHHELD
    return result


def read_run(
    *,
    model: ModelConfig,
    result: CalibrationResult,
    reliability: Mapping[Family, Reliability],
) -> ModelRun | int:
    """Read one model's run the way the gate reads one, and print it in full.

    Through `read_gate` rather than by scoring families here, so the `D` this check
    compares is the same `D` the gate is decided on — a comparison computed by its
    own arithmetic would be comparing two numbers the bench does not use.
    """
    try:
        gate = read_gate(
            result.target_runs,
            trivial=TRIVIAL.name,
            weak=WEAK.name,
            hardened=HARDENED.name,
            reliability=reliability,
            library=result.run_state.library,
        )
    except NotAGateRun as unreadable:
        print(f"\nThis run cannot be read: {unreadable}")
        return EXIT_WITHHELD

    print()
    print(gate.stated())
    print(episodes_section(result, trivial=TRIVIAL.name, hardened=HARDENED.name))
    return ModelRun(reading=ModelReading(model=str(model), result=gate), result=result)


def adaptive_swap(first: ModelRun, second: ModelRun) -> AdaptiveSwap | None:
    """The adaptive half of the comparison, or `None` where it cannot be read.

    `None` rather than a zero, for the reason `NoFamiliesInScope` is raised rather
    than answered: a run with no family in scope measured no separation, and a figure
    standing in for one would read as an attacker that found nothing.
    """
    if first.adaptive is None or second.adaptive is None:
        return None
    return compare_adaptive(
        first.adaptive,
        second.adaptive,
        first_model=first.reading.model,
        second_model=second.reading.model,
    )


def cross_model_bar(
    *,
    runs: Sequence[ModelRun],
    attestation: Attestation,
    approve: Approve,
    adjudicator: Completion,
    adjudicator_model: str,
    price_per_call: CallPrice | None,
) -> tuple[CrossModelRejections, tuple[Promotion, ...]] | int:
    """Put every proposed route to the bar, on both models, and count what it refused.

    The extra admission run ADR-0012 costs: one proposed case against three agents on
    each model. It lives here rather than in #12 because it protects *this* check's
    interpretability — a library grown by a mechanism that may itself be
    model-specific makes a collapse on swap uninterpretable, since it could no longer
    be told apart from a library built by the first model.

    Which bar applies is never decided here. `promote` reads it off the proposal's own
    `discovered_by`, and nothing in this function can name one.
    """
    proposals = tuple(proposal for run in runs for proposal in run.proposals)
    if not proposals:
        print(
            "\nNo route was proposed in either run, so the cross-model bar decided "
            "nothing. That is a fact about the attacker and not about the bar."
        )
        return rejections(()), ()

    readings: dict[str, list[AdmissionReading]] = {
        proposal.case.id: [] for proposal in proposals
    }
    for run in runs:
        measured = measure_proposals(
            proposals=proposals,
            model=run.reading.model,
            attestation=attestation,
            approve=approve,
            adjudicator=adjudicator,
            adjudicator_model=adjudicator_model,
            price_per_call=price_per_call,
        )
        if isinstance(measured, int):
            return measured
        for case_id, reading in measured.items():
            readings[case_id].append(reading)

    promotions = tuple(
        promote(proposal, readings[proposal.case.id]) for proposal in proposals
    )
    return rejections(promotion.outcome for promotion in promotions), promotions


def measure_proposals(
    *,
    proposals: Sequence[ProposedRoute],
    model: str,
    attestation: Attestation,
    approve: Approve,
    adjudicator: Completion,
    adjudicator_model: str,
    price_per_call: CallPrice | None,
) -> dict[str, AdmissionReading] | int:
    """Measure every proposed case against all three reference agents on one model.

    The same shape as `scripts/admit.py`'s own admission run, and deliberately: a
    proposal is decided on counts read the way every other admission's counts are
    read, so nothing enters the library on an arithmetic of this command's own.

    This run's own adaptive layer is ignored. A proposal made while measuring a
    proposal is not this check's finding — it has had no admission run of its own,
    and following it would be a loop with no end.
    """
    cases = [proposal.case for proposal in proposals]
    auth_token = secrets.token_urlsafe(16)
    app = create_reference_app(
        ReferenceConfig(model=ModelConfig.parse(model), auth_token=auth_token)
    )
    with serve(app) as base_url:
        targets = reference_targets(base_url, auth_token)
        print(f"\nmeasuring {len(cases)} proposed case(s) on {model}")
        try:
            result = run_calibration(
                cases=cases,
                targets=targets,
                attestation=attestation,
                plant_nonce=nonce_planter(base_url),
                approve=approve,
                adjudicator=adjudicator,
                budget=RunBudget.declare(
                    cases=cases, targets=targets, price=price_per_call
                ),
            )
        except BudgetExceeded as abort:
            print(f"\nAdmission run aborted on budget: {abort}")
            return EXIT_ABORTED

    if not result.approval.proceeded:
        print(f"\nAdmission run not started: {result.approval.reason}")
        return EXIT_DECLINED

    by_name = {run.target.name: run for run in result.target_runs}
    missing = [
        name
        for name in (HARDENED.name, WEAK.name, TRIVIAL.name)
        if name not in by_name or by_name[name].registration.refused
    ]
    if missing:
        print(
            f"\n{', '.join(missing)} did not register on {model}, so no proposal was "
            "measured against them. A reading needs all three reference agents."
        )
        return EXIT_WITHHELD

    return {
        case.id: counted(
            model,
            hardened=verdicts(by_name[HARDENED.name], case),
            weak=verdicts(by_name[WEAK.name], case),
            trivial=verdicts(by_name[TRIVIAL.name], case),
            adjudicator=(
                adjudicator_model if case.verdict_class is VerdictClass.JUDGED else None
            ),
        )
        for case in cases
    }


def verdicts(target_run: TargetRun, case: Case) -> list[Verdict]:
    """This case's verdicts against one agent, in the order the attempts ran."""
    return [
        attempt.verdict for attempt in target_run.attempts if attempt.case_id == case.id
    ]


def record_swap(
    *,
    swap: ModelSwap,
    adaptive: AdaptiveSwap | None,
    rejected: CrossModelRejections,
    directory: Path,
    identity: str,
    adjudicator_model: str,
    attacker_model: str,
    runs: Sequence[ModelRun] = (),
) -> Path:
    """Write this comparison to a dated document, in the sections it was printed in.

    One file per comparison and never an append to a single log: a swap is the unit a
    reader compares with another swap, and two of them in one file is a document
    whose reader has to work out where one ended. The same discipline — and the same
    reason — as `scripts/gate.py`'s own record.

    **No payload text, on any side.** The scored half holds counts, intervals, `D`
    and the rule; the adaptive half holds the statistics and the attacker's own prose;
    the admission half holds counts. A route that beat a target is a working
    unpublished exploit and stays in the transcripts on the episode (ADR-0008).
    """
    directory.mkdir(parents=True, exist_ok=True)
    stamped = datetime.now(tz=UTC)
    path = directory / f"swap-{stamped:%Y-%m-%dT%H-%M-%SZ}.md"
    path.write_text(
        "\n".join(
            (
                f"# Model swap — {stamped:%Y-%m-%d %H:%M:%S} UTC",
                "",
                f"- reference agents, first model: `{swap.first.model}`",
                f"- reference agents, second model: `{swap.second.model}`",
                f"- adjudicating model: `{adjudicator_model}` (judged families only, "
                "measured once for both runs)",
                f"- attacking model: `{attacker_model}` (adaptive layer only)",
                f"- confirmed by: {identity}",
                "",
                "## The scored comparison, which is what this check is for",
                "",
                "```",
                swap.stated(),
                "```",
                "",
                "## The two runs it compares",
                "",
                "```",
                *(
                    f"on {run.reading.model}:\n{run.reading.result.stated()}"
                    for run in runs
                ),
                "```",
                "",
                "## The adaptive layer, which decides nothing",
                "",
                "```",
                (
                    adaptive.stated()
                    if adaptive is not None
                    else "not read — one of the two runs had no family in scope"
                ),
                *(
                    f"on {run.reading.model}:\n"
                    + episodes_section(
                        run.result, trivial=TRIVIAL.name, hardened=HARDENED.name
                    ).strip()
                    for run in runs
                ),
                "```",
                "",
                "## The cross-model admission bar",
                "",
                "```",
                rejected.stated(),
                "```",
                "",
            )
        ),
        encoding="utf-8",
    )
    return path


def print_declared(
    cases: Sequence[Case],
    models: Sequence[ModelConfig],
    args: argparse.Namespace,
    gold_sets: int,
) -> None:
    """Everything this check declared before it made a call, printed before it does.

    The two models, the library, the instruments and the rule, in front of the
    operator ahead of the attestation — so the bar is read before the result exists
    rather than after it (spec story 46).
    """
    first, second = models
    print(f"reference agents, first model:  {first}")
    print(f"reference agents, second model: {second}")
    print(f"adjudicating model:  {args.adjudicator_model}  (judged families only)")
    print(f"attacking model:     {args.attacker_model}  (adaptive layer only)")
    print(f"cases loaded:        {len(cases)} live")
    print(f"gold sets loaded:    {gold_sets}")
    print(f"reference agents:    {', '.join(a.name for a in REFERENCE_AGENTS)}")
    print(
        "the swap moves the model and nothing else: same library, same agents, same "
        "rule, and the run below is made twice"
    )
    print()
    print(DECLARED_RULE.stated())
    print()


if __name__ == "__main__":
    sys.exit(main())
