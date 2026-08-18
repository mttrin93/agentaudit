"""Runs the gate. One entry point, no web layer involved.

    uv run python -m scripts.gate --identity "your name"
    uv run python -m scripts.gate --identity "your name" --price-per-call 0.0005
    uv run python -m scripts.gate --identity "your name" --model stub:obedient
    uv run python -m scripts.gate --identity "your name" \\
        --adjudicator-model openrouter:openai/gpt-4o-mini

**This is the stop before the bench is trusted.** The whole admitted library
against all three reference agents at ten attempts per case — n = 30 per family per
agent — then the two judged families' κ against the gold set, then the declared
rule applied to what came back and printed beside its answer. It ends in one of
three ways and two of them stop the build: passed, failed, or **not decided**
because too few families were fit to be asked (ADR-0003, ADR-0015).

**It can fail, and a failure is a correct outcome.** Nothing here adjusts a
threshold to the result: the rule is `GateRule`, it was declared in #3 before any
result existed, and it is printed above the answer every time so that a reader can
re-derive the pass or fail rather than trust a verdict line. An implementer who
finds themselves editing `rule.py` to make this command print PASSED has inverted
the purpose of the entire spec.

**The gate is decided on the scored layer alone.** The adaptive layer runs in the
same run and against the same three agents, and it prints in a section of its own
below the decision, carrying no rate, no interval, no band and no `D` (ADR-0010).
A weak attacker cannot fail a working bench here and a lucky one cannot pass a
broken one, because `read_gate` is handed the recorded attempts and nothing else.

**It asks before it sends anything**, on the same terms as every other entry point:
the three attestation statements one at a time, then the estimated cost at the
approval interrupt. Answering no to any of them spends nothing, and nothing here
has a `--yes` (ADR-0007).

All three reference agents run, and there is no flag to run fewer: `D` is trivial
minus hardened and monotonicity is read across all three, so a gate on two agents
is not a smaller gate but a different and undeclared one.
"""

import argparse
import os
import secrets
import sys
from collections.abc import Sequence
from decimal import InvalidOperation
from pathlib import Path

from dotenv import load_dotenv

from backend.bench.admission import NotAdmitted, admitted_library
from backend.bench.calibration import CalibrationResult, run_calibration
from backend.bench.completion import (
    DEFAULT_ADJUDICATOR_MODEL,
    DEFAULT_ATTACKER_MODEL,
    completion_for,
)
from backend.bench.contract import TargetConfig
from backend.bench.gate import GateResult, NotAGateRun, read_gate
from backend.bench.goldset import load_gold_sets, measure_reliability
from backend.bench.library import Case
from backend.bench.rule import DECLARED_RULE
from backend.bench.scorer import GateOutcome
from backend.graph.budget import BudgetExceeded, Layer, RunBudget
from backend.targets.reference.hardened import HARDENED
from backend.targets.reference.model import ModelConfig
from backend.targets.reference.operator import nonce_planter
from backend.targets.reference.server import (
    REFERENCE_AGENTS,
    ReferenceConfig,
    create_reference_app,
)
from backend.targets.reference.serving import serve
from backend.targets.reference.tools import DECLARED_TOOL_NAMES
from backend.targets.reference.trivial import TRIVIAL
from backend.targets.reference.weak import WEAK
from scripts.console import (
    EXIT_ABORTED,
    EXIT_DECLINED,
    EXIT_WITHHELD,
    attest,
    price,
    print_episodes,
    print_provenance,
    terminal_approval,
)

CASES_DIR = Path(__file__).resolve().parents[1] / "backend" / "cases"
GOLDSET_DIR = Path(__file__).resolve().parents[1] / "backend" / "goldset"

DEFAULT_MODEL = "openrouter:openai/gpt-4.1-nano"
"""The reference agents' model, chosen as test equipment and recorded as such.

A model that refuses the trivial agent's payloads reports its own defences rather
than the agent's absent ones, which is the confound #15 exists to measure. See
`docs/validation.md`.
"""

EXIT_GATE_FAILED = 6
"""Exit code when the gate was decided and the answer was no.

Non-zero, because a failing gate stops the build (spec story 45). Not an error: the
measurement worked, the rule was applied, and the bench did not clear it.
"""

EXIT_NOT_DECIDED = 7
"""Exit code when too few families were fit for the rule to be put to them.

A third code rather than the failure one, because *not decided* is a third outcome
and collapsing it into a fail would report a claim the run never measured
(ADR-0015).
"""


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
            "the bench's own model, which decides the two judged families and is "
            "the instrument κ is measured on. Never a reference agent's model"
        ),
    )
    parser.add_argument(
        "--attacker-model",
        default=os.environ.get("AGENTAUDIT_ATTACKER_MODEL", DEFAULT_ATTACKER_MODEL),
        help=(
            "the model the adaptive attacker runs on. A third setting, and it "
            "decides nothing about the gate"
        ),
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
        "--currency", default="USD", help="the currency --price-per-call is in"
    )
    args = parser.parse_args(argv)

    try:
        call_price = price(args.price_per_call, args.currency)
    except (InvalidOperation, ValueError) as bad:
        print(f"Not a usable price per call: {bad}")
        return EXIT_WITHHELD

    model = ModelConfig.parse(args.model)
    try:
        # The admitted library, never the raw one: a case that has not separated
        # the three reference agents has not earned a place in the run that decides
        # whether the bench measures anything (#12, spec story 69).
        cases = admitted_library(CASES_DIR)
        gold_sets = load_gold_sets(GOLDSET_DIR, cases)
    except (NotAdmitted, ValueError, KeyError) as unusable:
        print(f"The gate cannot run against this library:\n{unusable}")
        return EXIT_WITHHELD

    print_declared(cases, model, args, len(gold_sets))

    try:
        # Both built before the attestation, so a misconfigured instrument is a
        # refusal rather than a run that stops after spending something.
        adjudicator = completion_for(args.adjudicator_model)
        attacker = completion_for(args.attacker_model)
    except (KeyError, ValueError) as unusable:
        print(f"No usable bench model: {unusable}")
        return EXIT_WITHHELD

    attestation = attest(args.identity)
    if attestation is None:
        print("Attestation withheld. Nothing was sent.")
        return EXIT_WITHHELD

    auth_token = secrets.token_urlsafe(16)
    app = create_reference_app(ReferenceConfig(model=model, auth_token=auth_token))
    with serve(app) as base_url:
        targets = reference_targets(base_url, auth_token)
        try:
            result = run_calibration(
                cases=cases,
                targets=targets,
                attestation=attestation,
                plant_nonce=nonce_planter(base_url),
                approve=terminal_approval(attestation.identity),
                adjudicator=adjudicator,
                attacker=attacker,
                budget=RunBudget.declare(
                    cases=cases, targets=targets, price=call_price
                ),
            )
        except BudgetExceeded as abort:
            print(f"\nRun aborted on budget: {abort}")
            return EXIT_ABORTED

    if not result.approval.proceeded:
        print(f"\nRun not started: {result.approval.reason}")
        print("Nothing was sent, and nothing was spent.")
        return EXIT_DECLINED

    refused = [run for run in result.target_runs if run.registration.refused]
    if refused:
        print(
            "\nA reference agent did not echo its nonce, so it was never attacked. "
            "The gate is not decided on two agents: repair the equipment and re-run."
        )
        return EXIT_WITHHELD

    # After the suite and only if it proceeded, so that a declined run spends
    # nothing at all — including on the bench's own instrument.
    print(
        f"\nmeasuring the adjudicator against {len(gold_sets)} gold set(s), "
        f"{sum(len(gold.transcripts) for gold in gold_sets)} labelled transcripts, "
        "on your key"
    )
    reliability = measure_reliability(gold_sets, adjudicator)

    try:
        gate = read_gate(
            result.target_runs,
            trivial=TRIVIAL.name,
            weak=WEAK.name,
            hardened=HARDENED.name,
            reliability=reliability,
            library=result.run_state.library,
        )
    except NotAGateRun as ungated:
        print(f"\nThis run cannot be gated: {ungated}")
        return EXIT_WITHHELD

    print_gate(gate, result)
    return exit_code(gate)


def exit_code(gate: GateResult) -> int:
    """What the shell learns from a gate run. Two of the three answers stop a build.

    A fail and a *not decided* exit differently on purpose: one says the bench was
    asked whether it discriminates and the answer was no, the other says too little
    of the instrument was fit for the question to be put, and a build that treated
    them the same would report the second as the first.
    """
    match gate.decision.outcome:
        case GateOutcome.PASSED:
            return 0
        case GateOutcome.FAILED:
            return EXIT_GATE_FAILED
        case GateOutcome.NOT_DECIDED:
            return EXIT_NOT_DECIDED


def reference_targets(base_url: str, auth_token: str) -> list[TargetConfig]:
    """All three reference agents, described the way any target is described."""
    return [
        TargetConfig(
            name=agent.name,
            url=f"{base_url}/reference/{agent.name}/messages",
            auth_token=auth_token,
            agent_type="assistant",
            # The reference agents expose their tool calls and declare the document
            # tools, which is what makes scope creep and halt defeat measurable
            # against them at all (ADR-0004).
            exposes_tool_calls=True,
            declared_tools=DECLARED_TOOL_NAMES,
        )
        for agent in REFERENCE_AGENTS
    ]


def print_declared(
    cases: Sequence[Case],
    model: ModelConfig,
    args: argparse.Namespace,
    gold_sets: int,
) -> None:
    """Everything this run declared before it made a call, printed before it does.

    The instruments, the library and the rule, in front of the operator ahead of the
    attestation — so that the bar is read before the result exists rather than after
    it (spec story 46).
    """
    print(f"reference agent model: {model}")
    print(f"adjudicating model:    {args.adjudicator_model}  (judged families only)")
    print(f"attacking model:       {args.attacker_model}  (adaptive layer only)")
    print(f"cases loaded:          {len(cases)}")
    print(f"gold sets loaded:      {gold_sets}")
    print(f"attempts per case:     {DECLARED_RULE.attempts_per_case}")
    print_provenance(cases)
    print()
    print(DECLARED_RULE.stated())
    print()


def print_gate(gate: GateResult, result: CalibrationResult) -> None:
    """The decision, then the adaptive section, then what the run spent.

    In that order and never interleaved: the two layers are printed as two blocks
    for the reason they are computed in two modules, and a reader who meets
    `A_break` inside the gate's own table has met a number that decides nothing in
    the place where everything decides something (ADR-0010, ADR-0011).
    """
    print()
    print(gate.stated())
    print_episodes(result, trivial=TRIVIAL.name, hardened=HARDENED.name)
    print()
    for layer in Layer:
        print(
            f"calls spent, {layer} layer: {result.run_state.spent_in(layer)} "
            f"of a declared ceiling of {result.budget.ceiling(layer)}"
        )
    print(f"confirmed by: {result.approval.identity}")


if __name__ == "__main__":
    sys.exit(main())
