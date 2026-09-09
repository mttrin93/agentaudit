"""Runs the multi-model validity check. The same library, twice, on two models.

    uv run python -m scripts.swap --identity "your name" \\
        --model openrouter:openai/gpt-4.1-mini \\
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
was made exits zero whatever it *found*, and the non-zero codes are all refusals — a
withheld attestation, a declined cost, an aborted budget, and since ADR-0033 a library
a gate run was holding when the write came. Inventing a collapse threshold here would
be declaring a bar nobody agreed, at the one point in the build where the result is
already in front of us.

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

**A proposal that clears both models is written into the library, and that is where
the loop closes** (ADR-0033). `promote` returns the case with the admission block
that let it in and `bench/entry.py` files it as a `.toml` record under the library
lease, so the library the next run loads is different because of it. One route is one
record — keyed by the family and a digest of the probe — so a route this attacker
rediscovers next run does not grow the family's `n` twice, and a route the library
already holds is reported as held rather than written again.

Three things that write does not do. It does not decide: the cross-model bar decided,
and a case whose own reading does not clear it is refused at the write rather than
filed. It does not re-date: the admission block carries the day the three reference
agents were run, which for a route read out of the admission memory is a day on an
earlier run (ADR-0032). And it moves no figure anything already recorded — what it
does move is the library version, so the gate run this library cites is recorded as
superseded on the citation itself, because a citation is a claim about a version.

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
from backend.bench.adaptive.proposal import ProposedRoute
from backend.bench.adjudication import Completion
from backend.bench.admission import (
    CrossModelRejections,
    NotAdmitted,
    admitted_library,
)
from backend.bench.admitting import cross_model_bar
from backend.bench.calibration import CalibrationResult, run_calibration
from backend.bench.completion import (
    ADJUDICATOR_MODEL_ENV,
    ATTACKER_MODEL_ENV,
    DEFAULT_ADJUDICATOR_MODEL,
    DEFAULT_ATTACKER_MODEL,
    REFERENCE_MODEL_ENV,
    attacker_completion_for,
    completion_for,
)
from backend.bench.crossmodel import ModelReading, ModelSwap, NotASwap, compare
from backend.bench.decided import (
    Consultation,
)
from backend.bench.entry import Entry, enter
from backend.bench.gate import NotAGateRun, read_gate
from backend.bench.goldset import load_gold_sets, measure_reliability
from backend.bench.lease import LibraryBusy
from backend.bench.library import Case, Family
from backend.bench.registration import Attestation
from backend.bench.retirement import live_library
from backend.bench.rule import DECLARED_RULE
from backend.bench.scorer import Reliability
from backend.graph.approval import Approve
from backend.graph.budget import BudgetExceeded, CallPrice, RunBudget
from backend.targets.reference.hardened import HARDENED
from backend.targets.reference.model import ModelConfig
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
from backend.targets.reference.trivial import TRIVIAL
from backend.targets.reference.weak import WEAK
from scripts.admit import measure_on
from scripts.console import (
    EXIT_ABORTED,
    EXIT_DECLINED,
    EXIT_WITHHELD,
    attest,
    episodes_section,
    price,
    provenance_section,
    terminal_approval,
    traced_run,
)
from scripts.gate import CASES_DIR, DEFAULT_MODEL, GOLDSET_DIR

EXIT_NOT_WRITTEN = 6
"""Exit code when a route cleared the bar and the library could not be written.

Distinct from the three consent refusals and from an abort, because everything above
the write happened: both suites ran, the bar was put to every route, the document was
recorded. What did not happen is the write, because a gate run held the library
(`bench/lease.py`) — and a run that reported that as success would be a run whose
caller believes a route entered the library when none did.

**Not returned by a run that had nothing to write.** A held library and no admitted
route is a run that changed nothing and was never going to, which is the ordinary
outcome of every run to date; an exit code for it would report the lease rather than
the run.

Distinct from `EXIT_WITHHELD` for the same reason `scripts/admit.py` gives its own
rejection a code: that one means nothing was sent, and by this point a great deal has
been.
"""

SWAP_RUNS_DIR = Path(__file__).resolve().parents[1] / "docs" / "swap-runs"

SECOND_REFERENCE_MODEL_ENV = "AGENTAUDIT_SECOND_REFERENCE_MODEL"
"""Where a deployment declares the model the library is re-run on.

This script's own variable and not one of the three `completion.py` names, because
nothing else in the bench has a second reference model: a gate run, an admission and
an adaptive run each measure one, and only a swap measures two.
"""

DEFAULT_SECOND_MODEL = "openrouter:openai/gpt-4o-mini"
"""The second model, and it is a deliberate choice rather than a spare string.

`gpt-4o-mini` refused the published extraction payload on all four of the tracer
bullet's runs *while running the trivial agent* — an agent with no defences at all —
which is exactly why it was not chosen as the reference agents' first model
(docs/validation.md, 2026-08-17). The fact that disqualified it as run-one equipment
is what makes it the informative second model: a model whose refusals are visibly its
own is the one worth asking whether the bench has been reading.

A model that will not host the trivial agent at all is no use here either.
`claude-haiku-4.5` reads the trivial system prompt as an injection and declines to
echo the nonce, so it never registers and nothing is ever measured against it.
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
        default=os.environ.get(REFERENCE_MODEL_ENV, DEFAULT_MODEL),
        help="the reference agents' first underlying model, as '<provider>:<model>'",
    )
    parser.add_argument(
        "--second-model",
        default=os.environ.get(SECOND_REFERENCE_MODEL_ENV, DEFAULT_SECOND_MODEL),
        help=(
            "the model the library is re-run on. The one setting that moves between "
            "the two runs, and it has to be a different model: two runs of one model "
            "measure this bench's run-to-run variation and not a swap"
        ),
    )
    parser.add_argument(
        "--adjudicator-model",
        default=os.environ.get(ADJUDICATOR_MODEL_ENV, DEFAULT_ADJUDICATOR_MODEL),
        help=(
            "the bench's own model, which decides the two judged families and is the "
            "instrument κ is measured on. Never a reference agent's model, and "
            "measured once for both runs"
        ),
    )
    parser.add_argument(
        "--attacker-model",
        default=os.environ.get(ATTACKER_MODEL_ENV, DEFAULT_ATTACKER_MODEL),
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

    # No usage sink on these two. One build serves several runs here — the whole
    # library on a model, then `admit.measure_on` twice — and a ledger is one run's
    # (`run_calibration` refuses a reused one). Binding one would need a client per
    # run, which is a change to `measure_on`'s contract and not this ticket's.
    try:
        adjudicator = completion_for(args.adjudicator_model)
        attacker = attacker_completion_for(args.attacker_model)
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

    # The extra admission run ADR-0012 costs: one proposed case against three agents
    # on each model. It is paid for here rather than in #12 because it protects *this*
    # check's interpretability — a library grown by a mechanism that may itself be
    # model-specific makes a collapse on swap uninterpretable, since it could no
    # longer be told apart from a library built by the first model. The path itself is
    # `bench/admitting.py`, called rather than copied: a second code path to a
    # reference agent is what ADR-0105 §5 refuses.
    refused = cross_model_bar(
        proposals=[proposal for run in runs for proposal in run.proposals],
        models=[run.reading.model for run in runs],
        attestation=attestation,
        approve=approve,
        adjudicator=adjudicator,
        adjudicator_model=args.adjudicator_model,
        price_per_call=call_price,
        measure=measure_on,
        say=print,
    )
    if isinstance(refused, int):
        return refused
    rejected, promotions, consulted = refused
    print()
    print(rejected.stated())
    print(provenance_section(cases))
    # Through the consultation, so that a promotion whose counts came from an earlier
    # run says so on its own lines rather than only in the block above (ADR-0032).
    print(consulted.reported(promotions))
    admitted = [
        promotion.case for promotion in promotions if promotion.case is not None
    ]
    entry: Entry | None
    try:
        entry = enter(
            admitted,
            cases_dir,
            holder=f"{attestation.identity}, admitting a route at a terminal",
        )
    except LibraryBusy as held:
        # Everything above this line has already been measured, printed and paid
        # for, so this is a refusal to *write* and not a refusal to run: the
        # comparison is recorded, and the routes are re-proposed on the next run
        # against the counts the memory now holds (ADR-0032).
        print(f"\nThis case library is already being written to:\n{held}")
        print(
            "The comparison above stands. "
            + (
                "No route entered the library."
                if admitted
                else "No route cleared the cross-model bar, so this run had "
                "nothing to write into it."
            )
        )
        entry = None
    if entry is not None:
        print()
        print(entry.stated())

    written = record_swap(
        swap=swap,
        adaptive=adaptive,
        rejected=rejected,
        consulted=consulted,
        entry=entry,
        directory=Path(args.record),
        identity=first.result.approval.identity,
        adjudicator_model=args.adjudicator_model,
        attacker_model=args.attacker_model,
        runs=runs,
        cases=cases,
    )
    print(f"\nthis comparison's own document: {written}")
    # Non-zero only where a route that cleared the bar did not reach the library.
    # A held library and nothing to put in it is a run that changed nothing and was
    # never going to, which is the ordinary outcome and not a refusal.
    return 0 if entry is not None or not admitted else EXIT_NOT_WRITTEN


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
        targets = described_agents(base_url, auth_token)
        print(f"\nrunning the whole library on {model}")
        try:
            result = run_calibration(
                cases=list(cases),
                targets=targets,
                attestation=attestation,
                plant_nonce=nonce_planter(base_url),
                drop_namespace=namespace_dropper(base_url),
                approve=approve,
                adjudicator=adjudicator,
                attacker=attacker,
                budget=RunBudget.declare(
                    cases=list(cases), targets=targets, price=price_per_call
                ),
                trace=traced_run(reference_model=str(model)),
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


def record_swap(
    *,
    swap: ModelSwap,
    adaptive: AdaptiveSwap | None,
    rejected: CrossModelRejections,
    consulted: Consultation,
    entry: Entry | None,
    directory: Path,
    identity: str,
    adjudicator_model: str,
    attacker_model: str,
    runs: Sequence[ModelRun],
    cases: Sequence[Case],
) -> Path:
    """Write this comparison to a dated document, in the sections it was printed in.

    One file per comparison and never an append to a single log: a swap is the unit a
    reader compares with another swap, and two of them in one file is a document
    whose reader has to work out where one ended. The same discipline — and the same
    reason — as `scripts/gate.py`'s own record.

    **No payload text, on any side.** The scored half holds counts, intervals, `D`
    and the rule; the adaptive half holds the statistics and the attacker's own prose;
    the admission half holds counts and the digest of a probe. A route that beat a
    target is a working unpublished exploit and stays in the transcripts on the
    episode (ADR-0008).

    **The admission half says which of its counts this run measured.** Since #39 a
    route the gate already decided is reported from memory, so a document that
    printed the rejection counts alone would present a figure no run in front of the
    reader paid for as one it did (ADR-0032).

    **And it says what entered the library, including *nothing*.** Since ADR-0033 a
    proposal that clears the bar becomes a record, so this document is the account of
    a run that changed the library it was made against — which record was written,
    which route was already held, and the version the library now stands at. `entry`
    is `None` for a run whose write was refused because a gate run held the library,
    and that is written down as the refusal it is rather than left as an absent
    section.
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
                # How many of the counts above this run measured, and how many it
                # read from the admission memory. In the block with them rather than
                # in a section of its own, because a count a reader cannot tell
                # apart from a fresh measurement is the one thing #39 could cost
                # this document (ADR-0032).
                consulted.stated(),
                # The other half of ADR-0012's accounting, on the run that put the
                # bar to work: how far the live library has drifted towards routes
                # fitted to these three agents, and the retirement rate by
                # provenance beside it.
                provenance_section(cases),
                "```",
                "",
                "## What entered the library",
                "",
                "```",
                (
                    entry.stated()
                    if entry is not None
                    else (
                        "not written — a gate run held this case library, so nothing "
                        "entered it. The comparison above stands: it was measured "
                        "before the write was attempted, and a route refused here is "
                        "re-proposed on the next run against the counts the admission "
                        "memory now holds (ADR-0032, ADR-0033)"
                    )
                ),
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
