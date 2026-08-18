"""Runs the calibration. One entry point, no web layer involved.

    uv run python -m scripts.calibrate
    uv run python -m scripts.calibrate --model stub:obedient
    uv run python -m scripts.calibrate --agents trivial hardened

The reference agents are served locally over real HTTP for the duration of the
run, and the script plants the registration nonce in each target's system prompt
the way an operator would by hand. It prints what was measured: a failure rate
with its Wilson interval per agent, and the discrimination score between the
trivial and hardened ends of the family.

That reading is not a gate result. The gate is decided over six families at
n = 30 each, against a stated rule, and arrives in #13; what prints here is one
family's worth of evidence — often one case's — which is why nothing below says
pass or fail.
"""

import argparse
import os
import secrets
import sys
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv

from backend.bench.calibration import CalibrationResult, TargetRun, run_calibration
from backend.bench.contract import TargetConfig
from backend.bench.library import Family, load_library
from backend.bench.rule import DECLARED_RULE
from backend.bench.scorer import Rate, discrimination
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

CASES_DIR = Path(__file__).resolve().parents[1] / "backend" / "cases"
# The reference agents need a model that will actually run them as built. A model
# that refuses the trivial agent's payloads is reporting its own defences, not the
# agent's absent ones — the confound #15 exists to measure. See docs/validation.md.
DEFAULT_MODEL = "openrouter:openai/gpt-4.1-nano"
REPLY_EXCERPT = 400


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        default=os.environ.get("AGENTAUDIT_REFERENCE_MODEL", DEFAULT_MODEL),
        help="the reference agents' underlying model, as '<provider>:<model>'",
    )
    parser.add_argument(
        "--agents",
        nargs="+",
        default=[agent.name for agent in REFERENCE_AGENTS],
        help="which reference agents to calibrate against",
    )
    args = parser.parse_args(argv)

    model = ModelConfig.parse(args.model)
    cases = load_library(CASES_DIR)
    auth_token = secrets.token_urlsafe(16)

    app = create_reference_app(ReferenceConfig(model=model, auth_token=auth_token))
    with serve(app) as base_url:
        targets = [
            TargetConfig(
                name=name,
                url=f"{base_url}/reference/{name}/messages",
                auth_token=auth_token,
                agent_type="assistant",
            )
            for name in args.agents
        ]
        result = run_calibration(
            cases=cases, targets=targets, plant_nonce=nonce_planter(base_url)
        )

    _print_result(result, model, len(cases))
    refused = [run for run in result.target_runs if run.registration.refused]
    return 1 if refused else 0


def _print_result(
    result: CalibrationResult, model: ModelConfig, case_count: int
) -> None:
    print(f"reference agent model: {model}")
    print(f"cases loaded:          {case_count}")
    print(f"attempts per case:     {DECLARED_RULE.attempts_per_case}")

    for target_run in result.target_runs:
        registration = target_run.registration
        status = "complete" if registration.complete else "REFUSED — nonce not echoed"
        print(f"\ntarget {target_run.target.name} ({target_run.target.url})")
        print(f"  registration: {status}")
        print(f"  nonce:        {registration.nonce}")
        print(f"  echo reply:   {_excerpt(registration.probe.reply_text)}")
        for family, rate in target_run.rates.items():
            print(f"  failure rate, {family}: {_rate(rate)}")
        if not target_run.rates:
            print("  failure rate: not measured — no attempt was made")

        for attempt in target_run.attempts:
            print(f"  attempt {attempt.case_id} #{attempt.index}")
            print(f"    verdict: {attempt.verdict}  (from the success condition)")
            print(f"    reply:   {_excerpt(attempt.transcript.reply_text)}")

    print()
    for family in _families_run(result.target_runs):
        print(
            f"discrimination, {family}: {_discrimination(result.target_runs, family)}"
        )

    run_state = result.run_state
    print(
        f"run state: position={run_state.position} "
        f"succeeded={len(run_state.succeeded_attempts)} "
        f"calls_spent={run_state.calls_spent}"
    )


def _rate(rate: Rate) -> str:
    interval = rate.interval
    return (
        f"{rate.value:.2f} ({rate.successes}/{rate.attempts}), "
        f"Wilson {DECLARED_RULE.interval_confidence:.0%} "
        f"[{interval.lower:.3f}, {interval.upper:.3f}]"
    )


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


def _excerpt(text: str) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= REPLY_EXCERPT:
        return collapsed
    return (
        f"{collapsed[:REPLY_EXCERPT]}… "
        f"[{len(collapsed)} chars, full transcript recorded]"
    )


if __name__ == "__main__":
    sys.exit(main())
