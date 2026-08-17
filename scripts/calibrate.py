"""Runs the calibration. One entry point, no web layer involved.

    uv run python -m scripts.calibrate
    uv run python -m scripts.calibrate --model stub:obedient

The reference agents are served locally over real HTTP for the duration of the
run, and the script plants the registration nonce in the target's system prompt
the way an operator would by hand. The gate decision itself — the rule, the
intervals, the pass or fail — arrives in #13; this prints what one attempt
measured and how it was measured.
"""

import argparse
import os
import secrets
import sys
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv

from backend.bench.calibration import CalibrationResult, run_calibration
from backend.bench.contract import TargetConfig
from backend.bench.library import load_library
from backend.targets.reference.model import ModelConfig
from backend.targets.reference.operator import nonce_planter
from backend.targets.reference.server import ReferenceConfig, create_reference_app
from backend.targets.reference.serving import serve

CASES_DIR = Path(__file__).resolve().parents[1] / "backend" / "cases"
# The trivial agent needs a model that will actually obey it, or the floor is the
# model's refusal rather than the agent's absent defences. See docs/validation.md.
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
        "--agent",
        default="trivial",
        help="which reference agent to calibrate against",
    )
    args = parser.parse_args(argv)

    model = ModelConfig.parse(args.model)
    cases = load_library(CASES_DIR)
    auth_token = secrets.token_urlsafe(16)

    app = create_reference_app(ReferenceConfig(model=model, auth_token=auth_token))
    with serve(app) as base_url:
        target = TargetConfig(
            name=args.agent,
            url=f"{base_url}/reference/{args.agent}/messages",
            auth_token=auth_token,
            agent_type="assistant",
        )
        result = run_calibration(
            cases=cases, targets=[target], plant_nonce=nonce_planter(base_url)
        )

    _print_result(result, model, len(cases))
    refused = [run for run in result.target_runs if run.registration.refused]
    return 1 if refused else 0


def _print_result(
    result: CalibrationResult, model: ModelConfig, case_count: int
) -> None:
    print(f"reference agent model: {model}")
    print(f"cases loaded:          {case_count}")

    for target_run in result.target_runs:
        registration = target_run.registration
        status = "complete" if registration.complete else "REFUSED — nonce not echoed"
        print(f"\ntarget {target_run.target.name} ({target_run.target.url})")
        print(f"  registration: {status}")
        print(f"  nonce:        {registration.nonce}")
        print(f"  echo reply:   {_excerpt(registration.probe.reply_text)}")

        for attempt in target_run.attempts:
            print(f"  attempt {attempt.case_id} #{attempt.index}")
            print(f"    verdict: {attempt.verdict}  (from the success condition)")
            print(f"    reply:   {_excerpt(attempt.transcript.reply_text)}")

    run_state = result.run_state
    print(
        f"\nrun state: position={run_state.position} "
        f"succeeded={len(run_state.succeeded_attempts)} "
        f"calls_spent={run_state.calls_spent}"
    )


def _excerpt(text: str) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= REPLY_EXCERPT:
        return collapsed
    return f"{collapsed[:REPLY_EXCERPT]}… [{len(collapsed)} chars, full transcript recorded]"


if __name__ == "__main__":
    sys.exit(main())
