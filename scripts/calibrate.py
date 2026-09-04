"""Runs the calibration. One entry point, no web layer involved.

    uv run python -m scripts.calibrate
    uv run python -m scripts.calibrate --model stub:obedient
    uv run python -m scripts.calibrate --agents trivial hardened
    uv run python -m scripts.calibrate --identity "your name"
    uv run python -m scripts.calibrate --identity "your name" --price-per-call 0.0005
    uv run python -m scripts.calibrate --adjudicator-model openrouter:openai/gpt-4o-mini
    uv run python -m scripts.calibrate --attacker-model openrouter:openai/gpt-4o-mini

The reference agents are served locally over real HTTP for the duration of the
run, and the script plants the registration nonce in each target's system prompt
the way an operator would by hand. It prints what was measured: a failure rate
with its Wilson interval per agent, and the discrimination score between the
trivial and hardened ends of the family.

**It asks before it sends anything, and the asking is the point.** The reference
agents satisfy the attestation and the approval interrupt like any other target
(ADR-0007), so the run stops for the three statements one at a time, then stops
again at the graph interrupt with the estimated cost in front of you. Answering no
to any of them spends nothing. Nothing here has a `--yes`: a consent mechanism
with a flag to skip it is a convenience feature after all, which is the one thing
ADR-0007 says this must not become.

`--identity` is required and `--price-per-call` is not. The first is the liability
record and must be a person rather than whatever `$USER` happens to be; the second
is the operator's own figure from their own provider, and a run without it says
*not priced* rather than showing a number the bench made up.

That reading is not a gate result. The gate is decided over all six families
against a stated rule — n = 30 per family for the authored three cases — and it is
`scripts/gate.py`; what prints here is
one family's worth of evidence — often one case's — which is why nothing below says
pass or fail.
"""

import argparse
import os
import secrets
import sys
from collections.abc import Sequence
from decimal import InvalidOperation
from pathlib import Path

from dotenv import load_dotenv

from backend.bench.admission import (
    NotAdmitted,
    admitted_library,
)
from backend.bench.calibration import CalibrationResult, TargetRun, run_calibration
from backend.bench.completion import (
    DEFAULT_ADJUDICATOR_MODEL,
    DEFAULT_ATTACKER_MODEL,
    attacker_completion_for,
    completion_for,
    narrator_for,
)
from backend.bench.library import Case, Family, VerdictClass
from backend.bench.rule import DECLARED_RULE
from backend.bench.scorer import discrimination
from backend.bench.usage import UsageLedger
from backend.graph.budget import BudgetExceeded, Layer, RunBudget
from backend.targets.reference.hardened import HARDENED
from backend.targets.reference.model import ModelConfig
from backend.targets.reference.operator import (
    described_agents,
    nonce_planter,
)
from backend.targets.reference.server import (
    REFERENCE_AGENTS,
    ReferenceConfig,
    create_reference_app,
)
from backend.targets.reference.serving import serve
from backend.targets.reference.trivial import TRIVIAL
from scripts.console import (
    EXIT_ABORTED,
    EXIT_DECLINED,
    EXIT_WITHHELD,
    attest,
    excerpt,
    price,
    print_episodes,
    print_findings,
    print_precedent,
    print_provenance,
    rate_line,
    terminal_approval,
    traced_run,
)

CASES_DIR = Path(__file__).resolve().parents[1] / "backend" / "cases"
# The reference agents need a model that will actually run them as built. A model
# that refuses the trivial agent's payloads is reporting its own defences, not the
# agent's absent ones — the confound #15 exists to measure. See docs/validation.md.
DEFAULT_MODEL = "openrouter:openai/gpt-4.1-nano"

# The attestation, the approval interrupt, the exit codes and the rate format live
# in `scripts.console`, shared with `probe_target.py`. One consent mechanism, asked
# the same way whichever target a run points at (ADR-0007).


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        default=os.environ.get("AGENTAUDIT_REFERENCE_MODEL", DEFAULT_MODEL),
        help="the reference agents' underlying model, as '<provider>:<model>'",
    )
    parser.add_argument(
        "--adjudicator-model",
        default=os.environ.get(
            "AGENTAUDIT_ADJUDICATOR_MODEL", DEFAULT_ADJUDICATOR_MODEL
        ),
        help=(
            "the bench's own model, which decides the two judged families. Not the "
            "reference agents' model and deliberately a separate setting: one is "
            "the instrument and the other is what is being measured"
        ),
    )
    parser.add_argument(
        "--attacker-model",
        default=os.environ.get("AGENTAUDIT_ATTACKER_MODEL", DEFAULT_ATTACKER_MODEL),
        help=(
            "the model the adaptive attacker runs on. A third setting, separate "
            "from the agents' and from the adjudicator's, and named here rather "
            "than defaulted inside the run: a run that quietly took the "
            "deterministic stand-in would report an agent's search it never made"
        ),
    )
    parser.add_argument(
        "--agents",
        nargs="+",
        default=[agent.name for agent in REFERENCE_AGENTS],
        help="which reference agents to calibrate against",
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
        "--price-per-call",
        default=None,
        help=(
            "what one call to the target costs you, from your own provider. "
            "Omitted, the run reports its cost as not priced rather than as zero"
        ),
    )
    parser.add_argument(
        "--currency",
        default="USD",
        help="the currency --price-per-call is in",
    )
    args = parser.parse_args(argv)

    try:
        call_price = price(args.price_per_call, args.currency)
    except (InvalidOperation, ValueError) as bad:
        print(f"Not a usable price per call: {bad}")
        return EXIT_WITHHELD

    model = ModelConfig.parse(args.model)
    try:
        # The admitted library, never the raw one: a case that has not separated the
        # three reference agents has not earned a place in a run, and the loader is
        # where that is enforced rather than remembered (#12, spec story 69).
        cases = admitted_library(CASES_DIR)
    except NotAdmitted as unearned:
        print(f"The library holds a case that did not earn its place:\n{unearned}")
        return EXIT_WITHHELD
    auth_token = secrets.token_urlsafe(16)

    # One ledger for this run, and the instruments below are built to report
    # into it. Bound here rather than inside the run because the sink an instrument
    # records through is fixed when its client is built, which is before a run
    # exists (`usage.UsageLedger.for_layer`, `run_calibration`). Which layer a sink
    # belongs to is the caller's to declare: an attacker's tokens counted into the
    # scored layer would be an adaptive figure inside a scored one (ADR-0010).
    ledger = UsageLedger()
    try:
        # Both built before the attestation, so a misconfigured instrument is a
        # refusal rather than a run that stops after spending something.
        adjudicator = completion_for(
            args.adjudicator_model, usage=ledger.for_layer(Layer.SCORED)
        )
        attacker = attacker_completion_for(
            args.attacker_model, usage=ledger.for_layer(Layer.ADAPTIVE)
        )
        # And the pair that explains what the run finds, off the adjudicator's
        # declared string and into the scored layer. Why one string serves both
        # the verdict instrument and the narrative ones is ADR-0030's, and
        # `narrator_for` is where it is turned into the pair.
        narrator = narrator_for(args.adjudicator_model, ledger.for_layer(Layer.SCORED))
    except (KeyError, ValueError) as unusable:
        print(f"No usable bench model: {unusable}")
        return EXIT_WITHHELD

    attestation = attest(args.identity)
    if attestation is None:
        print("Attestation withheld. Nothing was sent.")
        return EXIT_WITHHELD

    app = create_reference_app(ReferenceConfig(model=model, auth_token=auth_token))
    with serve(app) as base_url:
        by_name = {agent.name: agent for agent in REFERENCE_AGENTS}
        targets = described_agents(
            base_url, auth_token, [by_name[name] for name in args.agents]
        )
        try:
            result = run_calibration(
                cases=cases,
                targets=targets,
                attestation=attestation,
                plant_nonce=nonce_planter(base_url),
                approve=terminal_approval(attestation.identity),
                adjudicator=adjudicator,
                narrator=narrator,
                attacker=attacker,
                usage=ledger,
                budget=RunBudget.declare(
                    cases=cases, targets=targets, price=call_price
                ),
                trace=traced_run(
                    adjudicator_model=args.adjudicator_model,
                    attacker_model=args.attacker_model,
                    reference_model=args.model,
                ),
            )
        except BudgetExceeded as abort:
            print(f"\nRun aborted on budget: {abort}")
            return EXIT_ABORTED

    if not result.approval.proceeded:
        print(f"\nRun not started: {result.approval.reason}")
        print("Nothing was sent, and nothing was spent.")
        return EXIT_DECLINED

    _print_result(result, model, args.adjudicator_model, args.attacker_model, cases)
    refused = [run for run in result.target_runs if run.registration.refused]
    return 1 if refused else 0


def _print_result(
    result: CalibrationResult,
    model: ModelConfig,
    adjudicator_model: str,
    attacker_model: str,
    cases: Sequence[Case],
) -> None:
    print(f"reference agent model: {model}")
    print(f"adjudicating model:    {adjudicator_model}  (judged families only)")
    print(f"attacking model:       {attacker_model}  (adaptive layer only)")
    print(f"cases loaded:          {len(cases)}")
    print(f"attempts per case:     {DECLARED_RULE.attempts_per_case}")
    print_provenance(cases)

    for target_run in result.target_runs:
        registration = target_run.registration
        status = "complete" if registration.complete else "REFUSED — nonce not echoed"
        print(f"\ntarget {target_run.target.name} ({target_run.target.url})")
        print(f"  registration: {status}")
        print(f"  nonce:        {registration.nonce}")
        print(f"  echo reply:   {excerpt(registration.probe.reply_text)}")
        # The two classes are printed as two sections and never added: a judged
        # rate carries a wider stated limit and a κ figure beside it, and the
        # deterministic families carry the report's weight (ADR-0004).
        for family, rate in target_run.deterministic_rates.items():
            print(f"  failure rate, {family}: {rate_line(rate)}  [deterministic]")
        for family, rate in target_run.judged_rates.items():
            print(
                f"  failure rate, {family}: {rate_line(rate)}  [judged — κ not yet "
                "measured (#11); reported apart from the four above and never "
                "summed with them]"
            )
        # Printed beside the rates and never as one of them: a refusal to
        # measure is a third outcome, not a rate of zero (ADR-0004).
        for family, reason in target_run.not_measurable.items():
            print(f"  {family}: {reason.stated()}")
        # And a fourth: a case this target was never sent, because it was not
        # written for its agent type. Not a rate, not a refusal to measure, and
        # never counted as a pass (`applicability.py`, spec story 16).
        for skipped in target_run.not_applicable:
            print(f"  {skipped.stated()}")
        if not target_run.rates:
            print("  failure rate: not measured — no attempt was made")

        for attempt in target_run.attempts:
            reached = (
                "from the success condition"
                if attempt.verdict_class is VerdictClass.DETERMINISTIC
                else "adjudicated"
            )
            print(f"  attempt {attempt.case_id} #{attempt.index}")
            print(f"    verdict: {attempt.verdict}  ({reached})")
            print(f"    reply:   {excerpt(attempt.transcript.reply_text)}")

        # Printed after the attempts and never among them: an attempt is the unit
        # of the denominator and a finding is a verdict plus its narrative, and
        # the two are counted apart (CONTEXT.md).
        print_findings(target_run)

    # Per run and after every target, because that is where the write happens
    # (ADR-0031).
    print_precedent(result)

    print_episodes(result, trivial=TRIVIAL.name, hardened=HARDENED.name)

    print()
    for family in _families_run(result.target_runs):
        print(
            f"discrimination, {family}: {_discrimination(result.target_runs, family)}"
        )

    run_state = result.run_state
    budget = result.budget
    print(
        f"run state: position={run_state.position} "
        f"succeeded={len(run_state.succeeded_attempts)}"
    )
    # Per layer, never blended: a single figure would hide which half of the run
    # is spending the operator's inference budget (ADR-0007).
    for layer in Layer:
        print(
            f"calls spent, {layer} layer: {run_state.spent_in(layer)} "
            f"of a declared ceiling of {budget.ceiling(layer)}"
        )
    print(f"confirmed by: {result.approval.identity}")


def _families_run(target_runs: Sequence[TargetRun]) -> list[Family]:
    """Every family some target was attempted on, in the order families are declared."""
    measured = {family for run in target_runs for family in run.rates}
    return [family for family in Family if family in measured]


def _discrimination(target_runs: Sequence[TargetRun], family: Family) -> str:
    """D for one family, or why it could not be read.

    Per family, because that is what `D` is: the six families measure six
    different failures and a score pooled across them is not a quantity.

    Named by its two ends rather than by position, because `D` is not symmetric:
    a run that measured only one end has no score, and saying so is the honest
    answer rather than reporting the one rate it has.
    """
    rates = {run.target.name: run.rates.get(family) for run in target_runs}
    trivial, hardened = rates.get(TRIVIAL.name), rates.get(HARDENED.name)
    if trivial is None or hardened is None:
        return f"not read — D needs both {TRIVIAL.name} and {HARDENED.name} measured"
    score = discrimination(trivial=trivial, hardened=hardened)
    return (
        f"D = {score:.2f} ({TRIVIAL.name} {trivial.value:.2f} − "
        f"{HARDENED.name} {hardened.value:.2f}) — not a gate result"
    )


if __name__ == "__main__":
    sys.exit(main())
