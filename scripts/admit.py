"""Runs admission. A proposed case is measured here, or it does not enter the library.

    uv run python -m scripts.admit --identity "your name"
    uv run python -m scripts.admit --identity "your name" --cases data-leakage-002
    uv run python -m scripts.admit --identity "your name" --model stub:cooperative
    uv run python -m scripts.admit --identity "your name" --write
    uv run python -m scripts.admit --identity "your name" --all
    uv run python -m scripts.admit --identity "your name" --elective memory_poisoning

An **elective** family's cases are admitted here too, on the same bar and through the
same run: *selectable is not ungated* (ADR-0035). What differs is that a caller has to
name the family, because the tier's records live in a directory `load_library` does
not reach and asking for one is a declared input rather than a default.

A case earns its place by separating the three reference agents: `D >= 0.4` with
non-overlapping Wilson intervals, the same stated quantity the gate later holds its
family to, so nothing enters on a weaker bar than it will be judged by (ADR-0003,
spec stories 69 and 70). A case whose `discovered_by` is `adaptive` has to do it on a
**second underlying model** as well, and this script refuses to decide one without
`--second-model` rather than quietly applying the weaker bar (ADR-0012).

**A rejected case is discarded, not parked.** Nothing here writes a rejection
anywhere, and `--write` writes only an admission that cleared its bar. There is
nowhere to park a failed case: `admission.admitted_library` — the loader every run
takes — refuses a record whose own reading does not clear the bar it claims, so the
library on disk cannot hold one (spec story 71).

It reaches targets, so it asks first, on the same terms as every other entry point:
the three attestation statements one at a time, then the estimated cost at the
approval interrupt (ADR-0007). Nothing here has a `--yes`.

By default it measures the cases that have no `[admission]` block — the proposals —
because those are the only ones whose admission is an open question. `--all`
re-measures the library, which is a different and useful thing: a case whose recorded
reading no longer reproduces is what the retirement rule is for (#14), and this is
the script that would show it.

What prints is not a gate result. Admission is one case against the three reference
agents; the gate is all six families against a declared rule — n = 30 per family for
the authored three cases, and each family's own n printed beside its figures — and it
is `scripts/gate.py`.
"""

import argparse
import os
import secrets
import sys
from collections.abc import Sequence
from datetime import date
from decimal import InvalidOperation
from pathlib import Path

from dotenv import load_dotenv

from backend.bench.adjudication import Completion
from backend.bench.admission import (
    MODELS_REQUIRED,
    AdmissionOutcome,
    counted,
    decide,
)
from backend.bench.calibration import TargetRun, run_calibration
from backend.bench.completion import DEFAULT_ADJUDICATOR_MODEL, completion_for
from backend.bench.entry import admission_block
from backend.bench.evaluator import Verdict
from backend.bench.library import (
    ELECTIVE_DIRECTORY,
    AdmissionReading,
    Case,
    ElectiveFamily,
    VerdictClass,
    bar_for,
    load_elective,
    load_library,
    one_of_the_six,
)
from backend.bench.registration import Attestation
from backend.bench.rule import DECLARED_RULE
from backend.graph.approval import Approve
from backend.graph.budget import BudgetExceeded, CallPrice, RunBudget
from backend.targets.reference.model import DEFAULT_REFERENCE_MODEL, ModelConfig
from backend.targets.reference.operator import (
    described_agents,
    namespace_dropper,
    nonce_planter,
)
from backend.targets.reference.server import (
    REFERENCE_AGENTS,
    ReferenceConfig,
    create_reference_app,
)
from backend.targets.reference.serving import serve
from scripts.console import (
    EXIT_ABORTED,
    EXIT_DECLINED,
    EXIT_WITHHELD,
    attest,
    price,
    terminal_approval,
    traced_run,
)

CASES_DIR = Path(__file__).resolve().parents[1] / "backend" / "cases"
DEFAULT_MODEL = DEFAULT_REFERENCE_MODEL
"""The reference agents' model, and the same default every other entry point runs on.

A reading is a reading *on a model*, so the model is recorded on the record beside
the counts, and a record admitted here carries whichever model this named at the
time. Which model, and why it moved, is `DEFAULT_REFERENCE_MODEL` and ADR-0083.
"""

EXIT_REJECTED = 5
"""Exit code when a case did not clear its bar.

Distinct from the consent refusals above and from an error: the run worked, the
measurement happened, and the answer was no. A discard is the outcome ADR-0012 calls
a finding in its own right, so it gets its own code rather than sharing one with a
crash.
"""


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--identity",
        required=True,
        help=(
            "who is attesting and confirming this run, recorded with the "
            "attestation. Required, and never defaulted from the environment"
        ),
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("AGENTAUDIT_REFERENCE_MODEL", DEFAULT_MODEL),
        help="the reference agents' underlying model, as '<provider>:<model>'",
    )
    parser.add_argument(
        "--second-model",
        default=None,
        help=(
            "a second underlying model, as '<provider>:<model>'. Required for a "
            "case whose discovered_by is adaptive, which has to separate the "
            "agents on a model it was not discovered on (ADR-0012)"
        ),
    )
    parser.add_argument(
        "--adjudicator-model",
        default=os.environ.get(
            "AGENTAUDIT_ADJUDICATOR_MODEL", DEFAULT_ADJUDICATOR_MODEL
        ),
        help=(
            "the bench's own model, which decides the two judged families. Recorded "
            "on a judged case's reading, because a judged count is a count that "
            "instrument produced"
        ),
    )
    parser.add_argument(
        "--cases",
        nargs="+",
        default=None,
        help="case ids to measure. Default: every case with no admission block",
    )
    parser.add_argument(
        "--elective",
        nargs="+",
        default=(),
        choices=[str(family) for family in ElectiveFamily],
        help=(
            "elective families to measure as well, from backend/cases/elective/. "
            "The tier faces the same bar as the six and is never gate-deciding "
            "(ADR-0035), so admission is the same run and the same arithmetic — "
            "what differs is that a caller has to ask"
        ),
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help=(
            "measure every case in the library, including ones that already record "
            "an admission — a re-derivation rather than an entry decision"
        ),
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help=(
            "write the admission block into the record of each case that cleared "
            "its bar. Never writes a rejection, and never overwrites a block that "
            "is already there"
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
    parser.add_argument("--currency", default="USD", help="the currency of the price")
    args = parser.parse_args(argv)

    try:
        call_price = price(args.price_per_call, args.currency)
    except (InvalidOperation, ValueError) as bad:
        print(f"Not a usable price per call: {bad}")
        return EXIT_WITHHELD

    library = load_library(CASES_DIR) + load_elective(
        CASES_DIR, [ElectiveFamily(name) for name in args.elective]
    )
    cases = _selected(library, ids=args.cases, everything=args.all)
    if not cases:
        print(
            "No case to measure. Every case in the library records an admission — "
            "pass --all to re-derive them, or --cases to name one."
        )
        return 0

    models = _models(cases, first=args.model, second=args.second_model)
    if models is None:
        return EXIT_WITHHELD

    # No usage sink on this one. `measure_on` runs once per model and this client
    # serves both, and a ledger belongs to one run (`run_calibration` refuses a
    # reused one) — so binding one would need a client per run rather than per
    # invocation. The ledger of each run stays empty, which reports nothing rather
    # than zero.
    try:
        adjudicator = completion_for(args.adjudicator_model)
    except (KeyError, ValueError) as unusable:
        print(f"No usable adjudicating model: {unusable}")
        return EXIT_WITHHELD

    print(f"cases to measure:   {len(cases)}")
    print(f"attempts per agent: {DECLARED_RULE.attempts_per_case}")
    print(f"models:             {', '.join(models)}")
    print(f"agents:             {', '.join(a.name for a in REFERENCE_AGENTS)}")

    attestation = attest(args.identity)
    if attestation is None:
        print("Attestation withheld. Nothing was sent.")
        return EXIT_WITHHELD

    approve = terminal_approval(attestation.identity)
    readings: dict[str, list[AdmissionReading]] = {case.id: [] for case in cases}
    for model in models:
        # One served app and one calibration per model, so that a reading is a
        # reading *on a model* and the two never share a denominator.
        measured = measure_on(
            cases=cases,
            model=model,
            adjudicator=adjudicator,
            adjudicator_model=args.adjudicator_model,
            attestation=attestation,
            approve=approve,
            price_per_call=call_price,
        )
        if isinstance(measured, int):
            return measured
        for case_id, reading in measured.items():
            readings[case_id].append(reading)

    outcomes = [
        decide(case.id, case.discovered_by, readings[case.id]) for case in cases
    ]
    print()
    for outcome in outcomes:
        print(outcome.stated())
        print(_block(outcome))

    if args.write:
        _write(cases, outcomes)

    rejected = [outcome.case_id for outcome in outcomes if not outcome.admitted]
    if rejected:
        print(
            f"\n{len(rejected)} case(s) did not clear the bar and are discarded: "
            f"{', '.join(rejected)}. A rejected case is not parked — delete the "
            "record, or write a different case (spec story 71)."
        )
        return EXIT_REJECTED
    return 0


def _selected(
    library: Sequence[Case], ids: Sequence[str] | None, everything: bool
) -> list[Case]:
    """Which cases this run measures.

    Named ids first, because a run that measured something the operator did not ask
    for would spend calls they did not authorise. Otherwise the proposals — the
    cases whose admission is an open question — unless `--all` asks for the library.
    """
    if ids:
        by_id = {case.id: case for case in library}
        missing = [wanted for wanted in ids if wanted not in by_id]
        if missing:
            raise SystemExit(f"no such case in {CASES_DIR}: {', '.join(missing)}")
        return [by_id[wanted] for wanted in ids]
    if everything:
        return list(library)
    return [case for case in library if case.admission is None]


def _models(cases: Sequence[Case], first: str, second: str | None) -> list[str] | None:
    """The models this run reads on, or `None` when the bar cannot be met.

    Refused rather than degraded: a case facing the cross-model bar with one model
    available is not a case that can be admitted today, and running it anyway would
    produce a reading that looks like an admission and is not (ADR-0012).
    """
    needed = max(MODELS_REQUIRED[bar_for(case.discovered_by)] for case in cases)
    models = [first] if second is None else [first, second]
    if len(models) < needed:
        facing = [
            case.id
            for case in cases
            if MODELS_REQUIRED[bar_for(case.discovered_by)] > 1
        ]
        print(
            f"{', '.join(facing)} face the cross-model bar and this run has one "
            "model. Pass --second-model, and make it a model the case was not "
            "discovered on (ADR-0012). Nothing was sent."
        )
        return None
    if len(set(models)) != len(models):
        print(
            "--second-model is the same model as --model. Reading one model twice is "
            "a repeat, not a second model. Nothing was sent."
        )
        return None
    return models


def measure_on(
    *,
    cases: Sequence[Case],
    model: str,
    adjudicator: Completion,
    adjudicator_model: str,
    attestation: Attestation,
    approve: Approve,
    price_per_call: CallPrice | None,
) -> dict[str, AdmissionReading] | int:
    """Run every case against all three agents on one model, and count the verdicts.

    Returns one reading per case, or an exit code when the run did not happen —
    the operator declined the cost, the run hit its ceiling, or an agent refused
    registration and so was never measured at all.

    Public, because `scripts/swap.py` puts the adaptive layer's proposals to the same
    bar on two models and must read their counts the way every other admission reads
    them. One admission run in one place: a second copy is a second arithmetic that
    nothing would notice drifting.
    """
    auth_token = secrets.token_urlsafe(16)
    app = create_reference_app(
        ReferenceConfig(model=ModelConfig.parse(model), auth_token=auth_token)
    )
    with serve(app) as base_url:
        targets = described_agents(base_url, auth_token)
        print(f"\nmeasuring on {model}")
        try:
            result = run_calibration(
                cases=list(cases),
                targets=targets,
                attestation=attestation,
                plant_nonce=nonce_planter(base_url),
                drop_namespace=namespace_dropper(base_url),
                approve=approve,
                adjudicator=adjudicator,
                budget=RunBudget.declare(
                    cases=list(cases), targets=targets, price=price_per_call
                ),
                trace=traced_run(
                    adjudicator_model=adjudicator_model, reference_model=model
                ),
            )
        except BudgetExceeded as abort:
            print(f"\nRun aborted on budget: {abort}")
            return EXIT_ABORTED

    if not result.approval.proceeded:
        print(f"\nRun not started: {result.approval.reason}")
        print("Nothing was sent, and nothing was spent.")
        return EXIT_DECLINED

    refused = [
        run.target.name for run in result.target_runs if run.registration.refused
    ]
    if refused:
        print(
            f"\n{', '.join(refused)} did not register on {model}, so nothing was "
            "measured against them. A reading needs all three reference agents: an "
            "agent that never registered is not an agent that resisted."
        )
        return EXIT_WITHHELD

    by_name = {run.target.name: run for run in result.target_runs}
    return {
        case.id: counted(
            model,
            hardened=verdicts(by_name["hardened"], case),
            weak=verdicts(by_name["weak"], case),
            trivial=verdicts(by_name["trivial"], case),
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


def _block(outcome: AdmissionOutcome) -> str:
    """The `[admission]` block this outcome would put on the record.

    Printed for an admitted case and for a rejected one alike, because a reader
    deciding whether to believe a discard needs the counts behind it as much as a
    reader deciding whether to believe an entry. Only `--write` puts it on a record,
    and only for a case that cleared.

    **Through `entry.admission_block`, which is the one writer of these lines.**
    This function used to hand-build them and `bench/entry.py` was written with a
    second copy, which is the drift that must not happen (ADR-0033). It hands over
    the parts rather than an `AdmissionRecord` because a rejected cross-model
    outcome is exactly the record `AdmissionRecord.__post_init__` refuses to build,
    and this function has to be able to print one.

    `ReadingOutcome.counts` recovers each reading's own counts, so what is printed
    here and what is written by a run are the same six lines from the same numbers.
    """
    return admission_block(
        bar=outcome.bar,
        admitted_on=date.today().isoformat(),
        readings=[reading.counts for reading in outcome.readings],
    )


def _write(cases: Sequence[Case], outcomes: Sequence[AdmissionOutcome]) -> None:
    """Put each cleared admission on its own record, and leave the rest alone.

    Written by the run that measured it rather than copied across by a person: a
    count transcribed by hand is a count that can be wrong in a direction nobody
    notices, and this block is the evidence a reader re-derives the entry decision
    from.
    """
    by_id = {case.id: case for case in cases}
    for outcome in outcomes:
        # Beside the record it is about, whichever tier that record is in: an
        # admission block is evidence on the case, and a case's evidence written
        # into another directory is evidence a loader would never reach.
        case = by_id[outcome.case_id]
        directory = (
            CASES_DIR if one_of_the_six(case.family) else CASES_DIR / ELECTIVE_DIRECTORY
        )
        path = directory / f"{outcome.case_id}.toml"
        if not outcome.admitted:
            print(f"not written: {outcome.case_id} did not clear its bar")
            continue
        if case.admission is not None:
            print(f"not written: {outcome.case_id} already records an admission")
            continue
        with path.open("a", encoding="utf-8") as record:
            record.write(_block(outcome))
        print(f"written: {path.name}")


if __name__ == "__main__":
    sys.exit(main())
