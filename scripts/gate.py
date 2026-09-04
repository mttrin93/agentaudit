"""Runs the gate from a terminal, which is where a gate run started.

    uv run python -m scripts.gate --identity "your name"
    uv run python -m scripts.gate --identity "your name" --price-per-call 0.0005
    uv run python -m scripts.gate --identity "your name" --model stub:obedient
    uv run python -m scripts.gate --identity "your name" --record docs/gate-runs
    uv run python -m scripts.gate --identity "your name" \\
        --adjudicator-model openrouter:openai/gpt-4o-mini

**This is the stop before the bench is trusted.** The whole admitted library
against all three reference agents at ten attempts per case — so n = 30 per family
per agent for a family holding the authored three, and each family's own n printed
beside its figures because the admission gate can grow one (ADR-0033) — then the two
judged families' κ against the gold set, then the declared
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

**Its output survives the run, three times.** Everything printed is written to a
dated document under `--record`, in the two sections it was printed in: validation
history has to exist before the first user does, and a gate answer that lived only in
a terminal is a gate answer nobody can check (spec story 80). Into the **case
library** goes the same run as a machine-readable record — each family's three
reference-agent rates, its `D`, whether the intervals were disjoint and whether the
ordering held, under the decision and the rule that was applied — so a reader
recovers the figures without parsing prose, in the shape `GET /gate-runs/{id}` serves
them for a gate run started from the console (`bench/gate_record.py`, ADR-0021). And
the **gate citation** goes into the library beside it, naming both files, so that the
bench starts citing the gate run it just made rather than one wired into a
configuration by hand (ADR-0023, `bench/cited.py`). None of the three can disagree:
one `GateResult` is read once, the document's scored section is the record's own
rendering of it, and the citation is read off that record. The curated narrative
stays in `docs/validation.md`; what is written here is the run itself.

**The record is in the library and not beside the document.** The citation carries
the record's file name and every reader resolves it against the library it was found
in (`cited.the_reliability`), so a record written anywhere else is a citation whose
figures nobody can reach — which is what withheld every judged rate this bench
measured, until ADR-0023's amendment moved it. The library holds what travels with
the cases and what a booting process is given; `--record` holds the document a person
reads, and the document links to the record from there.

**A failing run replaces a passing citation, and says so.** The citation is what
this bench last put itself through and not the best answer it ever got, so it is
written on all three outcomes and the line that reports it names what it displaced.
A gate run that left a stale pass behind would be a bench claiming a certification
its own last measurement withdrew (ADR-0023).

**One writer at a time on one library.** This run takes an exclusive lease on the
case directory before it reads anything and gives it back however it ends, because a
gate run started from the console (`backend/api/gate_runs.py`, ADR-0021) writes to the
same records: two overlapping runs would decide a retirement off a series missing a
reading. A run that finds the library held names the holder and stops, having sent
nothing.

**It writes the decay series it measured back onto the case records.** `D` for every
case it read, appended to that case's own `[[history]]` (spec story 72), and a case
below the declared floor on two consecutive runs *of one model* marked retired with
its date and its final score — kept and never deleted, because a case the field caught
up with is evidence that the field moved. `--cases` says which library that is.
Nothing here retires a case on one run, nothing retires a case on a `--model
stub:...` run at all (ADR-0022: a fixture with hardcoded replies is not a measurement
of the field, and two free runs would otherwise empty the live library), and a case
whose two low readings came from a family the gate could not vouch for is left *not
decided* rather than retired: ADR-0015 leaves that question open on purpose.

**It asks before it sends anything**, on the same terms as every other entry point:
the three attestation statements one at a time, then the estimated cost at the
approval interrupt. Answering no to any of them spends nothing, and nothing here has
a `--yes` (ADR-0007). That is unchanged by there being a second entry point now: the
console asks the same three statements in a browser and records the same
`Attestation`, and the reason this command cannot simply be spawned by it is the
reason there is no `--yes` — `attest` treats absent or piped input as a refusal, so a
gate run nobody was watching would answer no three times and spend nothing.

All three reference agents run, and there is no flag to run fewer: `D` is trivial
minus hardened and monotonicity is read across all three, so a gate on two agents
is not a smaller gate but a different and undeclared one.
"""

import argparse
import os
import secrets
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import InvalidOperation
from pathlib import Path

from dotenv import load_dotenv

from backend.bench.admission import (
    NotAdmitted,
    admitted_elective,
    admitted_library,
)
from backend.bench.calibration import CalibrationResult, run_calibration
from backend.bench.capability import temperature_for
from backend.bench.cited import cite
from backend.bench.completion import (
    DEFAULT_ADJUDICATOR_MODEL,
    DEFAULT_ATTACKER_MODEL,
    DEFAULT_ATTACKER_TEMPERATURE,
    attacker_completion_for,
    completion_for,
    declared_reasoning_effort,
)
from backend.bench.elective import ElectiveSelection
from backend.bench.gate import (
    GateResult,
    NotAGateRun,
    cited_library,
    elective_section,
    read_gate,
)
from backend.bench.gate_record import (
    RecordedGateRun,
    document_named,
    record_named,
    recorded_gate_run,
    write_the_record,
)
from backend.bench.goldset import load_gold_sets, measure_reliability
from backend.bench.lease import LibraryBusy, holding_the_library
from backend.bench.library import ELECTIVE_DIRECTORY, Case, ElectiveFamily
from backend.bench.payload import DeclaredModels
from backend.bench.retirement import live_library, readings_of, store
from backend.bench.rule import DECLARED_RULE
from backend.bench.scorer import GateOutcome
from backend.graph.budget import BudgetExceeded, Layer, RunBudget
from backend.targets.reference.hardened import HARDENED
from backend.targets.reference.model import ModelConfig, measures_the_field
from backend.targets.reference.operator import (
    described_agents,
    nonce_planter,
)
from backend.targets.reference.server import (
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
    print_episodes,
    print_provenance,
    print_retirement,
    provenance_section,
    retirement_section,
    terminal_approval,
    traced_run,
)

CASES_DIR = Path(__file__).resolve().parents[1] / "backend" / "cases"
GOLDSET_DIR = Path(__file__).resolve().parents[1] / "backend" / "goldset"
GATE_RUNS_DIR = Path(__file__).resolve().parents[1] / "docs" / "gate-runs"

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
        "--elective",
        nargs="+",
        default=(),
        choices=[str(family) for family in ElectiveFamily],
        help=(
            "elective families to measure on this gate run. Measured on the gate's "
            "own terms — the same D, the same floor, the same intervals — and "
            "counted in neither of the gate's two counts (ADR-0035). A family this "
            "run is not given is named in the document as not requested, and the "
            "run counts toward no promotion streak for it"
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
    parser.add_argument(
        "--cases",
        default=str(CASES_DIR),
        help=(
            "the directory the case records are read from, and written back to: "
            "this run appends its D for every case it read, and marks retired any "
            "case the rule retires. The library is the store, because a decay "
            "series kept anywhere else is a series that can drift from the case "
            "it describes"
        ),
    )
    parser.add_argument(
        "--record",
        default=str(GATE_RUNS_DIR),
        help=(
            "the directory this run's dated document is written to. The run's own "
            "document, which is not docs/validation.md: that one is written by hand "
            "and reads the records. The machine-readable record is not written here "
            "— it goes into --cases, where the citation that names it points"
        ),
    )
    return _run_it(parser.parse_args(argv))


def _run_it(args: argparse.Namespace) -> int:
    """This gate run, holding the case library it is about to write back to.

    A gate run reads every case record and appends a reading to every one of them, so
    the library has one writer at a time (`bench/lease.py`): the lease is taken before
    the library is read and given back however this run ends. It is a file in the
    library's own directory rather than a lock in this process, because a gate run
    started from the console writes to the same records — the two entry points have to
    exclude each other and not only themselves (ADR-0021).

    A run that finds the library held prints who holds it and stops, having sent
    nothing. Nothing here waits: a gate run is many minutes, and a command that hung
    for one is a command nobody can tell from a hung run of its own.
    """
    try:
        with holding_the_library(Path(args.cases), f"{args.identity}, at a terminal"):
            return run_the_gate(args)
    except LibraryBusy as held:
        print(f"\nThis case library is already being written to:\n{held}")
        return EXIT_WITHHELD


def run_the_gate(args: argparse.Namespace) -> int:
    """The gate run itself, under the lease `_run_it` is holding."""

    try:
        call_price = price(args.price_per_call, args.currency)
    except (InvalidOperation, ValueError) as bad:
        print(f"Not a usable price per call: {bad}")
        return EXIT_WITHHELD

    model = ModelConfig.parse(args.model)
    cases_dir = Path(args.cases)
    try:
        # The admitted library, never the raw one: a case that has not separated
        # the three reference agents has not earned a place in the run that decides
        # whether the bench measures anything (#12, spec story 69). Then the live
        # half of it, because a retired case is kept and not scored (#14) — and
        # `RetirementDisagrees`, a ValueError, is how a record whose status and own
        # series disagree stops the run rather than being quietly corrected.
        library = admitted_library(cases_dir)
        cases = live_library(library)
        gold_sets = load_gold_sets(GOLDSET_DIR, cases)
        # The tier, and only what this run was asked for. A declared input on the
        # footing of the declared models: stated before the run and unmovable by
        # anything the run measures (ADR-0035). It faces `admitted_elective`, which
        # is `admitted_library`'s check over the tier's own directory — selectable
        # is not ungated.
        selection = ElectiveSelection(
            requested=tuple(ElectiveFamily(name) for name in args.elective)
        )
        elective_cases = live_library(admitted_elective(cases_dir, selection.requested))
    except (NotAdmitted, ValueError, KeyError) as unusable:
        print(f"The gate cannot run against this library:\n{unusable}")
        return EXIT_WITHHELD

    try:
        # Before anything is printed and long before anything is sent: the two
        # sampling settings this run will be made at, resolved the way the app path
        # resolves them, and refused here if the pairing cannot be had at all
        # (`declared_instruments`). A misconfigured instrument is a refusal ahead of
        # the attestation, which is the side of it every other refusal in this
        # command lands on.
        models = declared_instruments(args)
    except ValueError as unusable:
        print(f"No usable sampling configuration: {unusable}")
        return EXIT_WITHHELD

    print_declared(cases, model, models, len(gold_sets), library)
    print(f"  {selection.stated()}")

    # No usage sink on these two, and the reason is this script's shape: the
    # adjudicator built here serves the run *and* the reliability measurement
    # below (`measure_reliability`), which is not part of the run. A sink bound
    # here would file κ's calls under the run's scored layer, which is a figure
    # that quietly means something else — so this run's ledger stays empty and its
    # trace carries no token figure, which is the honest reading of *nothing was
    # recorded* (`bench/usage.py`, ADR-0026).
    try:
        # Both built before the attestation, so a misconfigured instrument is a
        # refusal rather than a run that stops after spending something.
        adjudicator = completion_for(args.adjudicator_model)
        # The attacker at the settings the record above states, and not at the
        # provider's defaults: a gate run that dropped a declared reasoning effort
        # would run its adaptive layer at a configuration nobody chose, and diverge
        # from the app path every other run goes through (#5, #23). The same two
        # values reach the request and the document, off one `DeclaredModels`, so
        # the document cannot state a setting the request did not carry.
        attacker = attacker_completion_for(
            args.attacker_model,
            temperature=models.attacking_temperature,
            reasoning_effort=models.attacking_reasoning_effort,
        )
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
        targets = described_agents(base_url, auth_token)
        try:
            result = run_calibration(
                # Both tiers in one suite, because an elective attempt is an
                # attempt: the same ten per case, the same reference agents, the
                # same wire. Where the two part company is the *counts*, and that
                # parting is `TargetRun.elective_rates` (ADR-0035).
                cases=cases + elective_cases,
                targets=targets,
                attestation=attestation,
                plant_nonce=nonce_planter(base_url),
                approve=terminal_approval(attestation.identity),
                adjudicator=adjudicator,
                attacker=attacker,
                # And no narrator, deliberately (ADR-0030): a gate run measures
                # the bench and a finding is about a target (ADR-0018), so a
                # narrative here would be prose about the bench's own reference
                # agents that nothing the gate decides can read — and 540
                # attempts' worth of it. `TargetRun.narrations` reads `None` on
                # every gate run, which is the stated absence and not an empty
                # result.
                budget=RunBudget.declare(
                    cases=cases + elective_cases,
                    targets=targets,
                    price=call_price,
                ),
                trace=traced_run(
                    gate=True,
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
            # The version of the library the gate was **decided over**, which is the
            # six and not the run's whole case list. The run state holds the true
            # version of everything that ran; this is what the gate document, the
            # gate run record and every report's gate citation carry, and an
            # elective selection must not move it — two gate runs over an identical
            # six-family library would otherwise read as incomparable because one of
            # them was also asked for the tier (ADR-0023, ADR-0035). What the tier
            # ran is named in the elective section below.
            library=cited_library(cases + elective_cases),
            # Beside the decision and in neither of its counts: `read_gate` carries
            # this onto the result and hands it to nothing (ADR-0035).
            elective=elective_section(
                result.target_runs,
                trivial=TRIVIAL.name,
                weak=WEAK.name,
                hardened=HARDENED.name,
                selection=selection,
            ),
        )
    except NotAGateRun as ungated:
        print(f"\nThis run cannot be gated: {ungated}")
        return EXIT_WITHHELD

    print_gate(gate, result)

    # The decay series, after the decision and never before it: what a case scored
    # is stored whatever the gate answered, and the rule that retires one is read
    # over two runs rather than over this one (spec stories 72 to 74). Written to
    # the case records by the run that measured them, so the series a retirement is
    # re-derived from is the case's own.
    runs = {run.target.name: run for run in result.target_runs}
    history = readings_of(
        cases,
        hardened=runs[HARDENED.name],
        weak=runs[WEAK.name],
        trivial=runs[TRIVIAL.name],
        model=args.model,
        # Whether this run measured the field, off the parsed configuration rather
        # than the string: a reading taken on the stub fixture is stored and marked,
        # and the rule declines to retire anything on it (ADR-0022). `--model
        # stub:obedient` is how this pipeline is exercised without spending money,
        # and it must stay a run that writes readings and retires nothing.
        measured_the_field=measures_the_field(model),
        ran_on=datetime.now(tz=UTC).date(),
        # The families the gate did not decide on. A reading from one is stored and
        # the rule is not applied to it: retirement declines on a family the bench
        # cannot vouch for (ADR-0016).
        excluded=gate.decision.excluded_families,
        adjudicator=args.adjudicator_model,
    )
    decisions = store(cases_dir, history)
    # And the tier's own decay series, into the tier's own directory. One reading per
    # case per gate run whichever tier the case is in: an elective family's cases face
    # the retirement rule like any others, so a tier nobody has to pass cannot quietly
    # accumulate cases that stopped discriminating (ADR-0035, spec story 7).
    elective_history = readings_of(
        elective_cases,
        hardened=runs[HARDENED.name],
        weak=runs[WEAK.name],
        trivial=runs[TRIVIAL.name],
        model=args.model,
        measured_the_field=measures_the_field(model),
        ran_on=history.ran_on,
        excluded=gate.decision.excluded_families,
        adjudicator=args.adjudicator_model,
    )
    elective_decisions = store(cases_dir / ELECTIVE_DIRECTORY, elective_history)
    # Reloaded, so the retired cases listed are the ones the library now holds —
    # including any this run retired a moment ago.
    library = admitted_library(cases_dir)
    print_retirement(history, decisions, library)
    if elective_history.readings:
        # The tier's series printed as its own block, below the six's, because a
        # reader working through the retirement section must not meet a case whose
        # family decided nothing beside the ones whose families decided.
        elective_library = admitted_elective(cases_dir, selection.requested)
        print_retirement(elective_history, elective_decisions, elective_library)

    # After everything is printed and before the exit code is read, so the document
    # holds the run the operator just saw rather than a subset of it. Written on all
    # three answers, because passed, failed and not decided are all gate runs and a
    # reader compares one with another — a history that kept only the passes would
    # be a history that cannot show the bench ever failed its own stop (spec story
    # 80). A withheld, declined or aborted run returned above this line: it sent
    # nothing and produced no gate, so there is no run to record.
    written = record_run(
        gate,
        result,
        library,
        Path(args.record),
        models,
        retirement_section(history, decisions, library),
        # The record goes into the library, beside the citation rendered from it and
        # inside the same lease as the readings: the citation names the file and every
        # reader resolves that name against the library, so this is the only directory
        # a cited record is reachable from (`cited.the_reliability`, ADR-0023).
        record_into=cases_dir,
    )
    print(f"\nthis run's own document: {written.document}")
    print(f"the same run as a record: {written.record}")

    # The citation, last of the three and still under the lease this run has held
    # since before it read the library: the readings and the citation land inside one
    # critical section, so a second gate run cannot slip between them (ADR-0021,
    # condition 5; ADR-0023). Written on every outcome, because the citation is what
    # this bench last put itself through rather than the best answer it ever got — a
    # failing gate run that left a passing citation behind would be a bench claiming
    # a certification it has just lost.
    replaced = cite(written.recorded, cases_dir)
    print(f"\nthe gate run this library now cites: {replaced.stated()}")
    return exit_code(gate)


@dataclass(frozen=True)
class WrittenRun:
    """Where this gate run was written down: the document, and the record it cites.

    Two files and one run, and they are in two directories on purpose: the prose goes
    where a person reads it and the fields go into the library, beside the cases they
    are a claim about and where the citation's own name for the record resolves. A
    reader gets the prose, a program gets the fields, and neither is the other's
    summary — they are two renderings of one reading, and the writer below returns
    both so that no caller can be handed one and told the other exists somewhere.

    `recorded` is that one reading, returned rather than rebuilt, because the
    citation is the third rendering of it (`cited.citation_of`): a caller that read
    the `GateResult` a second time to compose one would be the second arithmetic this
    whole arrangement exists instead of.
    """

    document: Path
    record: Path
    recorded: RecordedGateRun


def record_run(
    gate: GateResult,
    result: CalibrationResult,
    cases: Sequence[Case],
    directory: Path,
    models: DeclaredModels,
    retirement: str = "",
    *,
    record_into: Path,
) -> WrittenRun:
    """Write this run to a dated document, and its record into the case library.

    The same text the operator saw, because a recorded document that differed from
    the terminal would be two records of one run. One file per run and never an
    append to a single log: a gate run is the unit a reader compares with another
    gate run, and two of them in one file is a document whose reader has to work out
    where one ended.

    **The record is the same run in fields rather than in prose**, under the same
    stamp, so a reader recovers each family's three reference-agent rates and its `D`
    without parsing a sentence (#84). Its shape is `bench/gate_record.py`'s — the
    shape `GET /gate-runs/{id}` serves for a gate run started from the console — so
    the two entry points describe one gate run in one vocabulary (ADR-0021).

    **`record_into` is required and it is the library**, which is the whole of the
    difference from the version of this that wrote the record beside the document.
    The citation is rendered off the record and carries its file name; every reader
    resolves that name against the library it read the citation from, so a record
    written anywhere else is a citation pointing at nothing and a bench that withholds
    every judged rate it measured. Keyword-only and undefaulted on the discipline the
    rest of this arrangement follows: a destination that could be omitted is one a
    caller omits, and the failure is silent three layers away in a report.

    **One reading, two renderings, and the document is rendered from the record.**
    `recorded_gate_run` is called once, and the scored-layer section below is
    `recorded.decision.stated` rather than a second `gate.stated()`: the document and
    the record carry the same string because it is the same string, which is what
    makes disagreement unrepresentable rather than merely unobserved. Nothing here
    reads either file back — a figure recovered from prose would break on a
    rewording, and there is no second arithmetic for the two to differ over.

    **The instruments arrive as `DeclaredModels` rather than as the parsed command
    line.** What the document says about them is what a target's report says about
    them — the three identifiers and, under the attacker, the two settings in
    `capability`'s own sentences — so the two artefacts cannot describe one
    configuration in two vocabularies (#4, #5, #23). It also narrows what this writer
    can reach: an `argparse.Namespace` is every flag this command has, and the only
    ones a document may state are the ones on this record.

    **No payload text, on either side.** The scored half holds counts, intervals and
    the rule; the adaptive half holds prose route descriptions and the statistics.
    A route that beat a target is a working unpublished exploit and stays in the
    transcripts on the episode (ADR-0008, spec story 105).
    """
    directory.mkdir(parents=True, exist_ok=True)
    record_into.mkdir(parents=True, exist_ok=True)
    stamped = datetime.now(tz=UTC)
    path = directory / document_named(stamped)
    recorded = recorded_gate_run(
        gate,
        decided_at=stamped.isoformat(),
        document=path.name,
        # The record names its own file, so the citation rendered off it points at
        # what was written rather than at a name a third place composed. Both names
        # come off `gate_record`, which is the one place either format lives —
        # a console gate run dates its record the same way (ADR-0023).
        record=record_named(stamped),
        # The instrument the κ figures on this record were measured on, so a target
        # report can reuse them only where it adjudicates with the same model
        # (`cited.the_reliability`, ADR-0004).
        adjudicating_model=models.adjudicating,
    )
    path.write_text(
        "\n".join(
            (
                f"# Gate run — {stamped:%Y-%m-%d %H:%M:%S} UTC",
                "",
                f"- reference agents: `{models.calibration}`",
                f"  - sampling: {NO_SAMPLING_TO_DECLARE}",
                f"- adjudicating model: `{models.adjudicating}` (judged families only)",
                f"  - sampling: {NO_SAMPLING_TO_DECLARE}",
                f"- attacking model: `{models.attacking}` (adaptive layer only)",
                # The two settings under the instrument they belong to, in the words
                # a target's report gives them and never folded into one line: two
                # runs of one model at one temperature and different reasoning effort
                # are two different instruments (#5). They are nested under the line
                # that carries the layer qualifier, because they are the adaptive
                # layer's settings and they decide nothing the gate decides
                # (ADR-0010).
                f"  - sampling: {models.temperature_stated()}",
                f"  - reasoning: {models.reasoning_effort_stated()}",
                f"- confirmed by: {result.approval.identity}",
                # Where the same run is in fields. A relative link rather than a
                # copy of the file: one record, in the library the citation reads it
                # from, and this document is how a person walks to it.
                f"- the same run as fields: "
                f"[`{recorded.record}`]({_relative(record_into, directory)}"
                f"/{recorded.record})",
                "",
                "## The scored layer, which decides the gate",
                "",
                "```",
                # The record's own rendering of the decision, not a second reading
                # of it: this is the one string the two files share.
                recorded.decision.stated,
                "```",
                "",
                "## The adaptive layer, which decides nothing",
                "",
                "```",
                episodes_section(
                    result, trivial=TRIVIAL.name, hardened=HARDENED.name
                ).strip(),
                "",
                provenance_section(cases),
                retirement,
                "```",
                "",
            )
        ),
        encoding="utf-8",
    )
    return WrittenRun(
        document=path,
        record=write_the_record(recorded, record_into),
        recorded=recorded,
    )


def _relative(target: Path, seen_from: Path) -> str:
    """The path from one directory to another, as a link in a Markdown file.

    A relative link and never an absolute one: the document is committed and read on
    other people's machines, and a link naming the directory this run happened to be
    started from is a link that works nowhere else. `os.path.relpath` rather than
    `Path.relative_to`, because the two directories are siblings under the repository
    rather than one inside the other — the answer climbs before it descends.
    """
    return os.path.relpath(target.resolve(), seen_from.resolve())


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


NO_SAMPLING_TO_DECLARE = (
    "this bench declares no sampling for this instrument — no temperature and no "
    "reasoning effort were declared, and neither was sent, because there is no "
    "setting on this bench to declare one with. Not a choice left unmade: the choice "
    "was never offered (ADR-0025)"
)
"""What this document says about the two instruments that have no sampling setting.

The reference agents and the adjudicator, and it is said rather than left blank for
the reason every other absence in this project is said: a reader cannot tell an
unstated setting from an unavailable one, and a gate document that printed nothing
would leave them to guess which (ADR-0004, ADR-0017).

Not one of `capability`'s four sentences, and deliberately not worded like them.
Those are claims about what a *provider* accepts or about what this bench's table
holds; this is a claim about this bench's own control surface, which is a third kind
of fact. `payload.DeclaredModels` carries the same absence by carrying no field for
those two instruments — the same answer, in the place a signed report gives it.
"""


def declared_instruments(args: argparse.Namespace) -> DeclaredModels:
    """The three models this run is made under, and the attacker's two settings.

    The same type a target's report prints its provenance block from
    (`payload.DeclaredModels`), rather than a second record of the same three
    identifiers: the two artefacts then state one run's instruments in one wording,
    and the four statements a sampling setting has — a value, none declared, none
    accepted, and no line in the table for this model — are the report's own four
    rather than a parallel set invented here (#4, #5).

    **Resolved the way the app path resolves it, and refused where it cannot be
    resolved.** The temperature reaching the attacker is `DEFAULT_ATTACKER_TEMPERATURE`
    — the bench's own number and nobody's choice — so a model that accepts none takes
    none through `capability.temperature_for`, and the record then says *this model
    accepts no temperature* rather than naming a value the request never carried. The
    reasoning effort is the other direction: there is no default for it, so an effort
    here is one a deployment declared, and an effort declared against a model with no
    such setting is refused rather than dropped — which is what
    `completion.ATTACKER_REASONING_EFFORT_ENV` says it is for, and what a run about to
    ask a human to attest to a spend deserves. The refusal is `DeclaredModels`' own
    `__post_init__`, so it is the type refusing and not a check this script keeps.

    **The reference agents' model is not resolved here, on purpose.** Their client
    composes no temperature and no reasoning effort at all
    (`targets/reference/model.complete`), so there is nothing declared for this to
    record — and the reference agents are the constructed instrument the bands are cut
    from (ADR-0014), so giving them a sampling setting would move every rate the bench
    calibrates against. What the document says about them instead is
    `NO_SAMPLING_TO_DECLARE`.
    """
    return DeclaredModels(
        calibration=args.model,
        adjudicating=args.adjudicator_model,
        attacking=args.attacker_model,
        attacking_temperature=temperature_for(
            args.attacker_model, DEFAULT_ATTACKER_TEMPERATURE
        ),
        # Unresolved on purpose, unlike the temperature: `reasoning_effort_for` would
        # drop an effort a deployment declared, and this is the entry point where
        # dropping it silently was the fault (#23).
        attacking_reasoning_effort=declared_reasoning_effort(),
    )


def print_declared(
    cases: Sequence[Case],
    model: ModelConfig,
    models: DeclaredModels,
    gold_sets: int,
    library: Sequence[Case],
) -> None:
    """Everything this run declared before it made a call, printed before it does.

    The instruments, the library and the rule, in front of the operator ahead of the
    attestation — so that the bar is read before the result exists rather than after
    it (spec story 46).

    **The settings, and not only the identifiers.** A model name is not a
    configuration: the same attacker at two reasoning efforts is two instruments, and
    an operator about to attest to a spend is shown which one they are about to spend
    it on. Each is a sentence rather than a value, so the absences stay four
    statements and not one blank (`DeclaredModels`, #4, #5).
    """
    print(f"reference agent model: {model}")
    print(f"  sampling:            {NO_SAMPLING_TO_DECLARE}")
    print(f"adjudicating model:    {models.adjudicating}  (judged families only)")
    print(f"  sampling:            {NO_SAMPLING_TO_DECLARE}")
    print(f"attacking model:       {models.attacking}  (adaptive layer only)")
    # Under the instrument they are settings of, and under the one line that carries
    # the layer qualifier: these are the adaptive layer's settings, they decide
    # nothing the gate decides, and nothing here may read as though they did
    # (ADR-0010).
    print(f"  sampling:            {models.temperature_stated()}")
    print(f"  reasoning:           {models.reasoning_effort_stated()}")
    print(f"cases loaded:          {len(cases)} live of {len(library)} written")
    print(f"gold sets loaded:      {gold_sets}")
    print(f"attempts per case:     {DECLARED_RULE.attempts_per_case}")
    # The whole library and not the live half: the retirement rate by provenance is
    # a figure over every case ever written, and one read on the live cases alone
    # would report that nothing has ever retired (ADR-0012).
    print_provenance(library)
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
