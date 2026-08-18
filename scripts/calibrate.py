"""Runs the calibration. One entry point, no web layer involved.

    uv run python -m scripts.calibrate
    uv run python -m scripts.calibrate --model stub:obedient
    uv run python -m scripts.calibrate --agents trivial hardened
    uv run python -m scripts.calibrate --identity "your name"
    uv run python -m scripts.calibrate --identity "your name" --price-per-call 0.0005

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
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dotenv import load_dotenv

from backend.bench.calibration import CalibrationResult, TargetRun, run_calibration
from backend.bench.contract import TargetConfig
from backend.bench.library import Family, load_library
from backend.bench.registration import Attestation
from backend.bench.rule import DECLARED_RULE
from backend.bench.scorer import Rate, discrimination
from backend.graph.approval import Approval, Approve
from backend.graph.budget import (
    BudgetExceeded,
    BudgetPayload,
    CallPrice,
    Layer,
    RunBudget,
)
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

EXIT_WITHHELD = 2
"""Exit code when the attestation was not made. Not an error — a refusal."""

EXIT_DECLINED = 3
"""Exit code when the estimated cost was not confirmed at the interrupt."""

EXIT_ABORTED = 4
"""Exit code when the run hit its declared ceiling and stopped."""


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
        price = _price(args.price_per_call, args.currency)
    except (InvalidOperation, ValueError) as bad:
        print(f"Not a usable price per call: {bad}")
        return EXIT_WITHHELD

    model = ModelConfig.parse(args.model)
    cases = load_library(CASES_DIR)
    auth_token = secrets.token_urlsafe(16)

    attestation = _attest(args.identity)
    if attestation is None:
        print("Attestation withheld. Nothing was sent.")
        return EXIT_WITHHELD

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
        try:
            result = run_calibration(
                cases=cases,
                targets=targets,
                attestation=attestation,
                plant_nonce=nonce_planter(base_url),
                approve=_terminal_approval(attestation.identity),
                budget=RunBudget.declare(cases=cases, targets=targets, price=price),
            )
        except BudgetExceeded as abort:
            print(f"\nRun aborted on budget: {abort}")
            return EXIT_ABORTED

    if not result.approval.proceeded:
        print(f"\nRun not started: {result.approval.reason}")
        print("Nothing was sent, and nothing was spent.")
        return EXIT_DECLINED

    _print_result(result, model, len(cases))
    refused = [run for run in result.target_runs if run.registration.refused]
    return 1 if refused else 0


def _price(per_call: str | None, currency: str) -> CallPrice | None:
    """The operator's price per call, or `None` for a run they did not price."""
    if per_call is None:
        return None
    return CallPrice(per_call=Decimal(per_call), currency=currency)


def _attest(identity: str) -> Attestation | None:
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
        field: _yes(f"  · {wording}? [y/N] ")
        for field, wording in Attestation.STATEMENTS
    }

    try:
        return Attestation(identity=identity, **answers)
    except ValueError as refusal:
        print(f"\n{refusal}")
        return None


def _terminal_approval(identity: str) -> Approve:
    """Answer the graph's interrupt from the terminal.

    The same halt is answered by an HTTP request at 6b. Only this function
    changes; the graph does not.
    """

    def approve(presented: BudgetPayload) -> Approval:
        print("\nEstimated cost of this run, before the first call:")
        for line in presented["presented"]:
            print(line)
        if _yes("\nProceed and spend this? [y/N] "):
            return Approval(confirmed=True, identity=identity)
        return Approval(
            confirmed=False,
            identity=identity,
            reason="declined at the approval interrupt",
        )

    return approve


def _yes(prompt: str) -> bool:
    """A yes, and only from a human at a terminal.

    A run that is not being watched has nobody to consent on its behalf, so a
    piped or absent stdin is a no rather than a default.
    """
    if not sys.stdin.isatty():
        print(f"{prompt}\n  no terminal to ask — treating as no")
        return False
    return input(prompt).strip().lower() in {"y", "yes"}


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
