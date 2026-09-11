"""Runs the library against one target with nobody sitting in front of it, and
leaves the three files a recipient verifies.

    uv run python -m scripts.bench \
        --url https://staging.example/agent/messages \
        --identity "$GITHUB_ACTOR" \
        --attestation-file .github/agentaudit-attestation.md \
        --max-spend 2.50 --price-per-call 0.004 \
        --out agentaudit-report --deterministic-only

**This is the same composition `POST /runs` performs, called from a `__main__`
instead of from a route.** The library, the attestation, the estimate, the halt, the
suite, the payload, the signature: every one of them is the object the API path uses,
and nothing here measures anything of its own. What is different is who answers the
two questions a run asks before it sends anything, and the answer is not a flag —
[ADR-0065](../docs/adr/0065-a-ci-attestation-is-committed-prose-by-a-named-actor.md)
is the argument, and `backend/bench/unattended.py` is the mechanism:

* **The attestation is committed prose in the caller's own repository**, naming the
  target it authorises, made by an identity the runner authenticated (`github.actor`).
  `console.attest` is untouched, still reads `input()`, and still gains no argument.
* **The halt is answered by a declared ceiling.** The estimate is presented into the
  job log exactly as it is presented to a terminal, and a run that would spend past
  what the workflow declared is **declined** — not trimmed to fit, because a suite cut
  down to a budget would sign a report over a library subset nobody chose.

**The signing key is an input, not a nicety.** It is read before the attestation is
even parsed, so a bench with no key fails before the first send rather than after the
whole suite has spent somebody's inference budget on a document it then refuses
(ADR-0020, ADR-0017).

**Nothing here re-implements the report.** `api/report.payload_for` builds the payload
this writes, because a second assembly would be a second document — the same reason
`verification.checked` has one definition. That it lives under `backend/api/` is where
the API path put it; a copy here would be the drift that module's own docstring exists
against.

Exit codes are the console's, so a workflow step reads the same numbers a terminal
run returns. **No rate decides one of them.** A run that completed returns 0 whatever
its figures say — what makes a step red on a declared bar is #90, and putting it here
would make the bar a property of the runner rather than a threshold anybody can read
(ADR-0003). Two non-zero codes a completed run can return are not results either:
the probe's own `EXIT_NOT_REGISTERED`, which says the target never echoed the value
planted in it, so nothing was measured at all; and `EXIT_DISCLOSED`, which says the
page this run was asked to write carried something a CI log may not (ADR-0008) and
so was not written. Neither is a figure about the target.

**What this run covers is declared, and what it does not cover is recorded.**
`--families` and `--attempts-per-case` are the two inputs that move a scored
denominator here, and they exist *because* every family this entrypoint does not
attempt now reaches the signed document with the reason beside it — the plan's own
gaps go into `payload_for`, so a family switched off in a workflow reads as **not
run** rather than being absent with nothing beside it
([ADR-0075](../docs/adr/0075-a-declared-gap-reaches-the-signed-artefact.md),
ADR-0058). A run below the declared ten attempts per case is a real run and not a
gate result, and the artefact says so beside every figure rather than leaving it to
the workflow that asked (ADR-0025, ADR-0027).

**`--summary` is the CI half's other half.** `scripts/summary.py` builds the page a
step leaves on a run: the signed rendering itself, the families nothing was planted
for, and where the three files went — and it refuses a page carrying payload text or
a secret, because a job log is world-readable on a public repository and outlives
the artefact's retention window
([ADR-0066](../docs/adr/0066-the-action-is-a-composite-step-in-the-callers-own-repository.md)).
"""

from __future__ import annotations

import argparse
import importlib
import os
import sys
import tomllib
from collections.abc import Mapping, Sequence
from contextlib import ExitStack
from dataclasses import replace
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dotenv import load_dotenv

from backend.api.report import ReportConfig, payload_for
from backend.api.run_config import BenchConfig, plan_for
from backend.bench.adaptive.episode import AdaptiveEpisode
from backend.bench.adjudication import Completion
from backend.bench.admission import NotAdmitted, admitted_library
from backend.bench.calibration import TargetRun, run_calibration
from backend.bench.cited import the_citation, the_reliability
from backend.bench.completion import DEFAULT_ADJUDICATOR_MODEL
from backend.bench.contract import RetryPolicy, TargetConfig
from backend.bench.declared_gap import DeclaredGap
from backend.bench.elective import NOTHING_REQUESTED
from backend.bench.evaluator import Verdict
from backend.bench.fix_standing import FixStanding
from backend.bench.library import (
    AnyFamily,
    Case,
    DiscoveredBy,
    Family,
    LibraryVersion,
    Plant,
    Precondition,
)
from backend.bench.narration import Narrator
from backend.bench.payload import DeclaredModels
from backend.bench.proving import prove_patch, standing_for
from backend.bench.queued import file_proposals
from backend.bench.rule import DECLARED_RULE, GateRule
from backend.bench.selection import EVERY_CONSTRUCTION
from backend.bench.shim import serve_callback
from backend.bench.signing import NoSigningKey, publish_signed, signing_key
from backend.bench.source_anchor import (
    SourceAnchor,
    SourceAnchorReading,
    anchor_for,
)
from backend.bench.throwaway import Patch, PatchRefused, workspace_for
from backend.bench.unattended import (
    DeclaredCeiling,
    ceiling_approval,
    committed_attestation,
)
from backend.bench.usage import UsageLedger
from backend.declaration import DeclarationRefused, everything_declared_at
from backend.graph.approval import Approval, Approve
from backend.graph.budget import (
    BudgetExceeded,
    BudgetPayload,
    CallPrice,
    Layer,
    RunBudget,
)
from backend.graph.runstate import RunState
from scripts.console import (
    EXIT_ABORTED,
    EXIT_DECLINED,
    EXIT_WITHHELD,
    TOKEN_ENV,
    instruments,
    price,
    print_precedent,
    traced_run,
)
from scripts.probe_target import (
    ADJUDICATOR_ENV,
    CASES_DIR,
    EXIT_NOT_REGISTERED,
    OperatorGap,
    deterministic_subset,
    print_target_run,
)
from scripts.summary import Disclosed, job_summary, write_summary

EXIT_DISCLOSED = 6
"""Exit code when the job summary carried something a CI log may not (ADR-0008).

**Not a rate deciding an exit code**, which is the invariant this entrypoint keeps
(ADR-0065 §4): the run completed, the three files are on disk and signed, and what
failed is the publication of a page. A red step is the only way a control that fails
closed can say so, and a page nobody wrote is the recoverable half of the pair.
"""

EXIT_NO_KEY = 5
"""Exit code when the bench holds no signing key. Nothing was sent.

Its own code and not `EXIT_WITHHELD`, because the two are different things for the
person reading a red step: one is a run somebody refused and the other is a workflow
missing a secret. Both stop before the first send.
"""

EXIT_DOUBLY_DECLARED = 7
"""Exit code when a key is declared in the committed file and passed as an input.

Its own code and not `EXIT_WITHHELD`, for `EXIT_NO_KEY`'s reason one input further
out: this is a workflow to fix and not a run somebody refused, and the two are
different jobs for the person reading the red step. Nothing was sent
([ADR-0103](../docs/adr/0103-the-action-reads-the-committed-declaration-and-a-key-declared-twice-refuses-the-run.md)
§4).

The neighbouring refusals stay `EXIT_WITHHELD`: a declaration that is not where the
workflow pointed, or that cannot be read at all, is refused by `DeclarationRefusal`
under its own name, and every refusal `main` makes on the declared inputs returns
that code. What is its own thing here is the *collision* — the one failure where the
run could have gone ahead and the reason it must not is that two documents disagree.
"""

URL_ENV = "AGENTAUDIT_TARGET_URL"
"""Where the target's endpoint comes from when no flag carries one.

Beside `NONCE_ENV` and `console.TOKEN_ENV` and for the second half of their reason:
`/proc/<pid>/cmdline` is world-readable, so a URL on a command line is a URL every
other process on the machine can read. A staging endpoint that answers jailbreak
payloads is the same kind of value as the credential for it, which is why the
artefact carries only its hash (`registration.endpoint_hash`) — and why the Action
hands it over this way (ADR-0066 §2).
"""

NONCE_ENV = "AGENTAUDIT_TARGET_NONCE"
"""Where a pre-planted registration nonce comes from when no flag carries one.

The value belongs in the caller's secret store rather than on a command line, for the
reason the bearer token does (`console.TOKEN_ENV`).
"""

UNDECLARED = "not declared"
"""What this entrypoint says about a model nobody named.

The word and not a default naming one: `report.UNDECLARED_MODEL` carries the
argument, and this is the short form a `DeclaredModels` field takes here.
"""

WAIVED = (
    "No --nonce was supplied, so this run waives the proof of control: nobody can "
    "paste a value into a system prompt inside a runner. The probe is still sent, "
    "the artefact records `control_proved` as declared and not proved, and the "
    "data-leakage family has no planted canary to read (ADR-0007, as amended). What "
    "authorises the run is the committed attestation and the target it names."
)


SHARED_WITH_THE_DECLARATION: tuple[tuple[str, str, str], ...] = (
    ("name", "name", "--name"),
    ("url", "url", f"--url (or {URL_ENV})"),
    ("token", "auth_token", f"--token (or {TOKEN_ENV})"),
    ("agent_type", "agent_type", "--agent-type"),
    ("exposes_tool_calls", "exposes_tool_calls", "--exposes-tool-calls"),
    ("declared_tools", "declared_tools", "--declared-tools"),
    ("retains_session_state", "retains_session_state", "--retains-session-state"),
    ("holds_personal_records", "holds_personal_records", "--holds-personal-records"),
    ("nonce", "nonce", f"--nonce (or {NONCE_ENV})"),
    ("note_planted", "note_planted", "--note-planted"),
    ("price_per_call", "price_per_call", "--price-per-call"),
    ("currency", "currency", "--currency"),
)
"""The keys `agentaudit.toml` and this entrypoint's inputs can both carry.

One row per key: the attribute on the parsed arguments, the key in the file, and
what a caller would have to have written for the two to collide. The third column
exists so the refusal names *the input to delete* rather than the field it landed
in — a person reading a red step is holding a workflow file, not this one.

Every input of this entrypoint that is *not* in this table stays the workflow's, and
which those are and why is
[ADR-0103](../docs/adr/0103-the-action-reads-the-committed-declaration-and-a-key-declared-twice-refuses-the-run.md)
§3. The consequence here is one line of code: the file's `[attestation]` table is
never looked at, so `--identity` and `--attestation-file` cannot collide and are
absent below.
"""

ONLY_IN_THE_DECLARATION = (
    "processes_untrusted_input",
    "reaches_private_data",
    "changes_state_or_communicates",
    "under_human_supervision",
    "sends",
)
"""The five the file can state and no input of this entrypoint can.

The four the Agents Rule of Two is read over are the reason story 3 is worth more
here than tidiness: `action.yml` has an input for none of them, so a target audited
only in CI reads `not_declared` in Annex IV section 3 for ever — ADR-0092's defect,
surviving on the surface nobody had looked at (ADR-0103 §2). No collision is
possible on any of the five, because there is nothing to collide with.
"""

THE_ENTRYPOINT_DEFAULTS = (
    ("name", "target"),
    ("agent_type", "assistant"),
    ("currency", "USD"),
)
"""Three defaults that used to live in `action.yml`'s own input table.

They are applied after the file is read rather than by argparse, because a default
argparse supplied would be indistinguishable from a value the caller typed, and the
both-given rule would then fire on every run of a workflow that declares nothing
(ADR-0103 §4). A run with no `--declaration` gets exactly the values it always got.
"""


class DoublyDeclared(ValueError):
    """A key the committed file declares and a workflow input also carries.

    An exception rather than a returned sentence, so that the two ways a declaration
    can stop a run — this and `DeclarationRefused` — are raised the same way and
    caught in one place. The sentence names every key declared twice, because one
    red step should fix the whole `with:` block rather than the first line of it.
    """


def _read_the_declaration(args: argparse.Namespace) -> None:
    """Fold the committed declaration into the parsed arguments, in place.

    **Neither the file nor the input wins**, and the argument for refusing instead of
    choosing is
    [ADR-0103](../docs/adr/0103-the-action-reads-the-committed-declaration-and-a-key-declared-twice-refuses-the-run.md)
    §4. What that costs here is this function's shape: the merge happens before the
    attestation is read and before anything is sent, and the three defaults are
    applied after it rather than by the parser.

    *Given* is the truthy value, uniformly. An unset string is empty or `None`, an
    unset flag is `False`, an unset list is empty, and no row of the table above has
    a falsy value a caller could mean.
    """
    if args.declaration:
        declaration = everything_declared_at(Path(args.declaration))
        twice = [
            written
            for attribute, key, written in SHARED_WITH_THE_DECLARATION
            if getattr(args, attribute) and key in declaration.declared_keys
        ]
        if twice:
            raise DoublyDeclared(
                f"{', '.join(twice)}: declared in {args.declaration} and passed as "
                "an input too. Neither wins — an input that overrode the committed "
                "file would audit something the pull request did not approve, and a "
                "file that overrode the input would leave a workflow line doing "
                "nothing — so the run stops here. Delete one of the two (ADR-0103)."
            )
        for attribute, key, _ in SHARED_WITH_THE_DECLARATION:
            if key in declaration.declared_keys:
                setattr(args, attribute, getattr(declaration, key))
        for attribute in ONLY_IN_THE_DECLARATION:
            setattr(args, attribute, getattr(declaration, attribute))
        # `url = ""` and `nonce = ""` are how the example file spells *this target
        # needs no such thing*, and both are `None` rather than empty everywhere
        # downstream: an empty string would leave `main` reading a target where there
        # is none, and it would count as a nonce a served callback was handed.
        args.url = args.url or None
        args.nonce = args.nonce or None
    for attribute, default in THE_ENTRYPOINT_DEFAULTS:
        setattr(args, attribute, getattr(args, attribute) or default)
    return None


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    args = _parser().parse_args(argv)

    # First, and before the attestation is even read: a bench with no key runs the
    # whole suite against somebody's endpoint and then has no document to show for it
    # (ADR-0020). The one line in this repository that reads the variable is
    # `signing.signing_key`, and this is a caller of it rather than a second reader.
    try:
        key = signing_key()
    except NoSigningKey as missing:
        print(f"{missing}\n\nNothing was sent.")
        return EXIT_NO_KEY

    # Second, and before the ceiling is read: `--currency` and `--price-per-call`
    # are two of the keys the committed file can carry, so the estimate below has to
    # be built from the merged declaration rather than from the workflow's half of
    # it (ADR-0103 §2).
    try:
        _read_the_declaration(args)
    except DoublyDeclared as collision:
        print(f"{collision}\n\nNothing was sent.")
        return EXIT_DOUBLY_DECLARED
    except DeclarationRefused as missing:
        print(f"{missing}\n\nNothing was sent.")
        return EXIT_WITHHELD
    except (KeyError, OSError, TypeError, tomllib.TOMLDecodeError) as unreadable:
        # A file that cannot be read is not a declaration whose contents can be
        # argued with, which is why `everything_declared_at` raises here rather
        # than returning a fifth refusal name — and why this prints the exception
        # rather than a sentence of its own. `OSError` is in the tuple because
        # `is_file()` passing is not the same as `read_text` succeeding.
        print(
            f"The declaration at {args.declaration} cannot be read: {unreadable}"
            "\n\nNothing was sent."
        )
        return EXIT_WITHHELD

    try:
        call_price = price(args.price_per_call, args.currency)
        ceiling = _declared_ceiling(args, call_price)
        # Beside the ceiling because they are the same kind of statement — what this
        # workflow declared about the run — and resolved here so that a mistyped
        # family name or a denominator of zero costs nothing: both are refused
        # before the attestation is read and before anything is sent (ADR-0075).
        covered = declared_families(args.families)
        rule = rule_measured_under(args.attempts_per_case)
    except (InvalidOperation, ValueError) as bad:
        print(f"The declared inputs do not describe a run: {bad}")
        return EXIT_WITHHELD

    if (args.url is None) == (args.callback is None):
        # Exactly one target, and the attestation names exactly one. Two is a run
        # whose subject depends on which resolution rule the reader assumed, and
        # zero is not a run.
        print(
            "This run has no target, or two. Pass exactly one of --url (or "
            f"{URL_ENV}, or a `url` in the declaration) and --callback: the "
            "committed attestation names one target and authorises a run against "
            "that one."
        )
        return EXIT_WITHHELD
    reference = args.url if args.url is not None else args.callback
    if args.callback is not None and args.nonce is not None:
        # Refused here rather than met as `CanaryFromTwoPlaces` inside the run: a
        # served callback is reached on a loopback port this process bound, so there
        # is no configuration an operator could have planted a value into out of
        # band, and the shim's own hook is the one provenance the read-back checks
        # (ADR-0064 §1). Two ways to supply one value is two values.
        print(
            "A served callback plants its own registration nonce through its hook, "
            "so --nonce (or "
            f"{NONCE_ENV}) has nothing to describe here: the target is a port this "
            "run bound, not a configuration anybody could edit. Pass one or the "
            "other."
        )
        return EXIT_WITHHELD
    if args.exposes_tool_calls and not args.declared_tools:
        # The same refusal `POST /runs` and `scripts/probe_target.py` both make, for
        # the same reason: scope creep is read against the declared list, and against
        # an empty one every call this target makes scores as a finding. Unattended,
        # that finding would be signed and shipped.
        print(
            "A target that exposes its tool calls has to declare which tools it "
            "has: scope creep is read against that list, and against an empty one "
            "every call this target makes would score as a finding. Pass "
            "--declared-tools."
        )
        return EXIT_WITHHELD

    if args.url is not None and not args.token:
        print(f"No token for {args.url}. Pass --token or set {TOKEN_ENV}.")
        return EXIT_WITHHELD

    try:
        document = Path(args.attestation_file).read_text(encoding="utf-8")
    except OSError as unreadable:
        print(f"No committed attestation at {args.attestation_file}: {unreadable}")
        return EXIT_WITHHELD
    try:
        attestation = committed_attestation(
            document, identity=args.identity, target=reference
        )
    except ValueError as refused:
        print(f"{refused}\n\nNothing was sent.")
        return EXIT_WITHHELD

    ledger = UsageLedger()
    adjudicator: Completion | None = None
    narrator: Narrator | None = None
    adjudicator_model: str | None = None
    if not args.deterministic_only:
        adjudicator_model = args.adjudicator_model or os.environ.get(
            ADJUDICATOR_ENV, DEFAULT_ADJUDICATOR_MODEL
        )
        try:
            # The same pair the probe builds, through the same function: an
            # instrument built two ways is two instruments (`console.instruments`).
            adjudicator, narrator = instruments(adjudicator_model, ledger)
        except (KeyError, ValueError) as unusable:
            print(f"No usable adjudicating model: {unusable}")
            return EXIT_WITHHELD

    try:
        cases = admitted_library(CASES_DIR)
    except NotAdmitted as unearned:
        print(f"The library holds a case that did not earn its place:\n{unearned}")
        return EXIT_WITHHELD
    # The whole library, held past every narrowing below, because the disclosure
    # guard reads it: a case this run withdrew is still a case whose turns may not
    # appear on a world-readable page (`scripts/summary.py`).
    library = list(cases)
    gaps: dict[Family, OperatorGap] = {}
    if args.deterministic_only:
        # The same subset `scripts/probe_target.py` takes, through the same function:
        # which cases a run without an adjudicator sends is one decision, and two
        # copies of it would be two libraries called by one flag's name.
        cases, gaps = deterministic_subset(cases)

    # The family switch, through the one function that is the authority on which of
    # the library's cases a run may attempt and why the rest are out — the same
    # `plan_for` `POST /runs` estimates against, so a family switched off in a
    # workflow reads exactly as one switched off in the console (ADR-0066 §6).
    #
    # Here rather than inside the `with` below, because it needs no target: the two
    # questions that do — whether anything was planted — are answered against the
    # target a few lines further on, and are passed to `plan_for` as already
    # answered. Answering them twice would record a plant gap this entrypoint had
    # already recorded, in the words of the wrong surface, and against a family
    # name rather than against the `Case.requires` this bench reads (ADR-0061).
    #
    # `plan_for`'s judged branch is a no-op on the line above's terms and not a
    # third answer: `deterministic_subset` already took the judged cases, so the
    # plan finds none to drop and records none — which is what leaves the reason in
    # `OperatorGap`'s words, where `print_target_run` needs it, and reaches the
    # artefact through `_declared_gaps` below. What is left for this call to decide
    # is the family switch and the construction switch, which nothing else here has.
    plan = plan_for(
        BenchConfig(cases=cases, rule=rule, adjudicator=adjudicator, families=covered),
        note_planted=True,
        nonce_planted=True,
    )
    cases = list(plan.cases)
    for switched_off, reason in plan.gaps.items():
        print(f"{switched_off}: {reason.stated()}")
    if not cases:
        # Nothing to attempt is not a narrower run. A suite with no case in it would
        # sign a document whose figures are none and whose every family is absent —
        # a report about nothing, under a signature.
        print(
            "This run has no case to send: every family the library holds was "
            "switched off, or has nothing left in it. A narrower run is a run; an "
            "empty one is a signed document about nothing."
        )
        return EXIT_WITHHELD

    withdrawn: dict[AnyFamily, OperatorGap] = {}

    with ExitStack() as serving:
        try:
            target, planter = _target(args, serving)
        except (ImportError, AttributeError, TypeError) as unusable:
            print(f"That callback cannot be served: {unusable}")
            return EXIT_WITHHELD

        # Whether *this* target has a value planted in its configuration, which is a
        # question about the target and not about how it was supplied: a URL plants
        # nothing this run can see, and a served callback plants one only where it
        # implements the hook (ADR-0061). A callback with no hook is as unregistrable
        # as an endpoint nobody pasted a nonce into, and waiving is what lets it be
        # measured at all.
        plants_its_canary = (
            target.plants is not None and Plant.CONFIG_CANARY in target.plants
        )
        waived = not plants_its_canary and args.nonce is None
        if waived:
            print(WAIVED)
        cases, unplanted = withdrawn_for_want_of_a_plant(
            cases, target, nonce=args.nonce, note_planted=args.note_planted
        )
        for family, unplanted_gap in unplanted.items():
            print(f"{family}: {unplanted_gap.stated()}")
        # The six-family half of that, because `print_target_run` reports the six and
        # an elective family's withdrawal is printed above rather than beside a rate
        # it does not have (ADR-0057, `elective.py`).
        gaps.update(
            {
                family: gap
                for family, gap in unplanted.items()
                if isinstance(family, Family)
            }
        )
        # Every family that was not attempted, elective ones included, for the page
        # a step writes: the rendering carries `not_measurable` and `withheld` and
        # has no line for a family whose cases were dropped before the run.
        # Rebuilt rather than `update(gaps)`: a `Mapping` key is invariant here, so
        # the six-family dict is not a `dict[AnyFamily, ...]` to the typechecker.
        withdrawn.update({family: gap for family, gap in gaps.items()})
        withdrawn.update(unplanted)

        # Held in a name rather than built inside the call below, because the proof
        # loop derives the workspace it patches in from this run's own id — the same
        # id the plant namespace is derived from, and derived once for the reason
        # `planting.namespace_for` gives: two names for one run is a drop that runs
        # against a directory the copy was never made under (ADR-0063 §1, ADR-0072 §1).
        trace = traced_run(adjudicator_model=adjudicator_model)
        # The ceiling and the counter, both held in a name and handed in together.
        # `run_calibration` would build the state for a caller that hands it none,
        # and a caller that let it would have no way to read the episodes back out
        # of a run that *raised* instead of returning — so the routes an aborted
        # run's attacker found would be unreachable and lost with it, which is what
        # `print_filed_routes` on the abort path below exists to prevent.
        declared = RunBudget.declare(
            cases=cases, targets=[target], rule=rule, price=call_price
        )
        state = RunState(budget=declared, library=LibraryVersion.of(cases))
        try:
            result = run_calibration(
                cases=cases,
                targets=[target],
                attestation=attestation,
                approve=_announced(ceiling_approval(args.identity, ceiling)),
                adjudicator=adjudicator,
                narrator=narrator,
                usage=ledger,
                rule=rule,
                budget=declared,
                run_state=state,
                planters={} if planter is None else {target.name: planter},
                planted_nonces=(
                    {} if args.nonce is None else {target.name: args.nonce}
                ),
                # Waived where nothing planted a value: a run in a runner has nobody
                # to paste one, and `WAIVED` above says what that costs the reading.
                proof_waived=waived,
                trace=trace,
                discovered_by=DiscoveredBy.ADAPTIVE_ON_TARGET,
            )
        except BudgetExceeded as abort:
            print(f"\nRun aborted on budget: {abort}")
            # The run ended, so its routes are filed: an episode the ceiling cut
            # short is a censored episode, and an episode that finished before it
            # bit may well have found something.
            print_filed_routes(state.episodes, trace.id)
            return EXIT_ABORTED

    if not result.approval.proceeded:
        print(f"\nRun not started: {result.approval.reason}")
        print("Nothing was sent, nothing was spent, and no artefact was written.")
        return EXIT_DECLINED

    [target_run] = result.target_runs
    # The probe's own rendering, and not a second one: the deterministic and judged
    # rates are printed in two sections that are never summed, every family that was
    # not measured says which of the answers it was, and the findings sit under the
    # rates (ADR-0004, ADR-0005). A job log reading differently from a terminal would
    # be two accounts of one run.
    print_target_run(target_run, gaps)
    print_precedent(result)
    # Beside `print_precedent`, because these are the two stores a customer run
    # writes to and a job log that reported one of them would be an account of half
    # the run.
    print_filed_routes(result.run_state.episodes, trace.id)
    # Per layer and never added, in the job log as on a terminal: a blended figure
    # would hide which half of a run is consuming the caller's budget (ADR-0007).
    for layer in Layer:
        print(
            f"\ncalls spent, {layer} layer: {result.run_state.spent_in(layer)} "
            f"of a declared ceiling of {result.budget.ceiling(layer)}"
        )
    print(f"confirmed by: {result.approval.identity}")

    # Resolved once and read twice: the proof loop needs the file to patch and the
    # report needs the file to name, and two resolutions of one anchor would be two
    # claims about one checkout (ADR-0068 §3).
    anchor = checkout_anchor(args, planter)
    standings = proven_fixes(args, target_run, cases, anchor, workspace_for(trace.id))

    published = publish_signed(
        payload_for(
            result,
            cases,
            # The rule this run was measured under, which is the declared one unless
            # `--attempts-per-case` moved the denominator — and then the artefact
            # carries `rule.NOT_A_GATE_RESULT` beside the number rather than leaving
            # the departure in the workflow that asked for it (ADR-0025, ADR-0027).
            rule,
            ReportConfig(
                signing_key=key,
                models=DeclaredModels(
                    calibration=UNDECLARED,
                    adjudicating=adjudicator_model or UNDECLARED,
                    attacking=UNDECLARED,
                    narrative=adjudicator_model or UNDECLARED,
                ),
                # The same durable path a deployed bench reads them off
                # (`app.deployed_bench`): the gate run this library cites, and the κ
                # it measured — and only where it measured it on the model these
                # runs adjudicate with (ADR-0004, ADR-0023).
                gate=the_citation(CASES_DIR),
                reliability=the_reliability(CASES_DIR).for_adjudicator(
                    adjudicator_model or UNDECLARED
                ),
                # Resolved before the run and read by nothing that decides anything:
                # it reaches the findings section and no instrument, no verdict and
                # no rate (ADR-0071 §6, D13).
                # `planter` is the served callback object itself — `_target` hands it
                # back for the planting hooks — and it is the one thing in this
                # process the interpreter can point at a file for.
                source_anchor=anchor,
                # Whether each fix the caller offered was proven, from the one
                # process in this repository that can patch anything. Empty on every
                # run that offered none, and every finding then reads *proposed*,
                # which is a fact about where this bench ran (ADR-0073 §2).
                standings=standings,
            ),
            EVERY_CONSTRUCTION,
            _declared_gaps(gaps, plan.gaps),
            # This entry point offers no elective lever, so it asks for nothing —
            # said out loud rather than defaulted, which is what makes the artefact's
            # tier block a statement this workflow made rather than a field nobody
            # filled in (ADR-0035 §5, ADR-0088 §8).
            NOTHING_REQUESTED,
        ),
        Path(args.out),
        key,
    )
    if args.summary is not None:
        try:
            write_summary(
                Path(args.summary),
                job_summary(
                    published.rendering_path.read_text(encoding="utf-8"),
                    artifact=args.artifact_name,
                    out=args.out,
                    withdrawn=withdrawn,
                ),
                cases=library,
                # The two the caller handed in and the one they planted. Refused on
                # the page on top of whatever masking their runner does for a value
                # that came out of a secret store, because the masking is theirs and
                # this is ours.
                secrets=[
                    secret for secret in (args.url, args.token, args.nonce) if secret
                ],
            )
        except Disclosed as leaked:
            print(f"\n{leaked}")
            print("The three files are written and signed. Only the page was refused.")
            return EXIT_DISCLOSED

    print(
        f"\nThree files written, under the names a recipient reads out of a "
        f"directory:\n  {published.payload_path}\n  {published.rendering_path}\n"
        f"  {published.signature_path}\n"
        f"Check them with `uv run python -m scripts.verify {args.out}`."
    )
    return EXIT_NOT_REGISTERED if target_run.registration.refused else 0


def print_filed_routes(episodes: Sequence[AdaptiveEpisode], found_in: str) -> None:
    """File what this run's attacker found, and print what was filed.

    Here rather than beside `print_precedent` in `scripts/console.py`, which the
    gate run's entry points read too: a printer there would make the filing
    *reachable* from `scripts/gate.py` and `scripts/swap.py`, and the whole of why
    this store is written from the customer-run entry points is that it is not
    (`queued.file_proposals`, ADR-0012).

    Printed zero included, for `queued.NOTHING_WAS_PROPOSED`'s reason and with one
    of this entry point's own: nobody is sitting in front of an unattended run, so
    the job log is the whole of what anybody reads.

    `date.today()` here and nowhere deeper: an entry point is where a clock may be
    read, and it is the one place that knows which day the run means
    (`queued.file_proposals`).

    `found_in` is this run's own id — the same one the plant namespace and the
    throwaway workspace are derived from, and derived once for the reason
    `planting.namespace_for` gives: two names for one run would send a reader of a
    route filed here to a record nothing was written under.
    """
    print(
        f"\n{file_proposals(episodes, today=date.today(), found_in=found_in).stated()}"
    )


def declared_families(named: Sequence[str] | None) -> frozenset[Family]:
    """The families this workflow asked for, or all six where it named none.

    **Refused rather than repaired, and refused before anything is sent.** A name
    this bench does not hold is a workflow input somebody mistyped, and the
    alternative to a refusal is a run that covers five families and signs a document
    saying the caller switched the sixth off — a narrowing nobody chose, attributed
    to them. The six are named back, because a caller reading *not a family* with no
    list beside it has to go and find one (`GateRule` is not the place it is written
    down; `Family` is).

    `None` and the empty list are the same declaration — *nothing was narrowed* — and
    it is the whole of the six rather than nothing: an absent input is not a request
    for an empty suite, and a workflow that means the empty suite is refused below.
    """
    if not named:
        return frozenset(Family)
    held = {family.value: family for family in Family}
    unknown = sorted(one for one in named if one not in held)
    if unknown:
        raise ValueError(
            f"{', '.join(repr(one) for one in unknown)} is not a family this bench "
            f"holds. The six are {', '.join(held)} — a name that is not one of them "
            "is refused rather than dropped, because a run that quietly covered "
            "fewer families would report the rest as switched off by a caller who "
            "did not switch them off (ADR-0075)"
        )
    return frozenset(held[one] for one in named)


def _declared_gaps(
    withdrawn_here: dict[Family, OperatorGap], planned: Mapping[Family, DeclaredGap]
) -> dict[Family, DeclaredGap]:
    """Every family this run did not attempt, in the words the artefact is written in.

    Two sources because this entrypoint narrows in two places and neither may be
    dropped: what it withdrew itself — the judged families of a run with no
    instrument, the plant-dependent families nothing was planted for, in
    `OperatorGap`'s terminal words — and what `plan_for` recorded, which is already a
    `DeclaredGap`. `OperatorGap.declared` is the translation and the argument for it
    ([ADR-0075](../docs/adr/0075-a-declared-gap-reaches-the-signed-artefact.md)).

    **The two sources cannot name one family, and that is by construction rather than
    by the merge.** Each narrowing removes the cases it withdrew, and each records
    only families that still had one when it ran: `deterministic_subset` takes the
    judged cases before `plan_for` sees them, so the plan finds no judged family to
    call `NO_ADJUDICATOR`; `plan_for` drops a switched-off family's cases before
    `withdrawn_for_want_of_a_plant` runs, so that pass finds nothing of it to withdraw.
    The merge is therefore a union and never a precedence rule — a family with two
    reasons beside it would be a reader choosing, and this is why there is never one.
    """
    stated = {family: gap.declared() for family, gap in withdrawn_here.items()}
    return {**dict(planned), **stated}


def rule_measured_under(attempts_per_case: int | None) -> GateRule:
    """The rule this run is measured under: the declared one, or a cheaper denominator.

    **The one number of `GateRule` a caller may set** (ADR-0025), and the second
    declared input of this entrypoint that moves a scored denominator — the first is
    `--families` above. Everything else in the record stays the declared rule, which
    is what lets `verification._declared_bar` assert the rest against `DECLARED_RULE`
    and re-derive this one from the number the payload carries (ADR-0027).

    **No upper bound is checked here, and the ceiling is the reason.** The console
    offers the setting on a screen and bounds it to what that screen can show
    (`app.ATTEMPTS_RANGE`); a workflow has no screen, and a number large enough to
    matter is a number the estimate will price and the declared ceiling will decline
    before the first send. A second range in this file would be a bound nobody
    declared, checked against a run that already has one.

    What a run below ten costs is stated in the artefact rather than here:
    `rule.denominator_stated` writes the caveat and `rule.NOT_A_GATE_RESULT` is the
    sentence, so the departure travels with the document instead of staying in the
    workflow that asked for it.
    """
    if attempts_per_case is None:
        return DECLARED_RULE
    if attempts_per_case < 1:
        raise ValueError(
            f"--attempts-per-case={attempts_per_case} is not a denominator. A case "
            "attempted no times is a case that was not sent, and a family measured "
            "over nothing is an absence rather than a rate (ADR-0003)"
        )
    return replace(DECLARED_RULE, attempts_per_case=attempts_per_case)


def withdrawn_for_want_of_a_plant(
    cases: Sequence[Case],
    target: TargetConfig,
    *,
    nonce: str | None,
    note_planted: bool,
) -> tuple[list[Case], dict[AnyFamily, OperatorGap]]:
    """Drop the cases whose artefact nothing put in place, and say which and why.

    **Only for a target that answers for nothing**, which is every URL:
    `TargetConfig.can_be_planted` reads `None` as *yes* on purpose, because reading
    it as no would withdraw both plant-dependent families from every endpoint in the
    world (ADR-0061). What that leaves is the caller's own declaration — and an
    unattended run cannot ask, so a run that declared nothing has planted nothing.

    Without this the two families are *sent*: the leakage cases go after a nonce that
    is nowhere in the target and the injection cases ask for a note nobody filed, and
    both come back 0.00. At a terminal that zero is caught by a question
    (`console.note_is_planted`) and by the operator planting the nonce by hand; here
    there is nobody to ask, so a clean zero would be signed and shipped as a defence
    that was never tested (ADR-0007 as amended, ADR-0024).

    A served callback is not touched: it answers for itself, and a hook it does not
    implement withdraws its family as `NotMeasurable` on the case's own record, which
    is the better reading of the two and the one ADR-0061 chose.
    """
    if target.plants is not None:
        return list(cases), {}
    in_place = {
        Precondition.CONFIG_CANARY_PLANT: (
            nonce is not None,
            OperatorGap.NONCE_NOT_PLANTED,
        ),
        Precondition.RETRIEVED_CONTENT_PLANT: (
            note_planted,
            OperatorGap.NOTE_NOT_PLANTED,
        ),
    }
    kept: list[Case] = []
    gaps: dict[AnyFamily, OperatorGap] = {}
    for case in cases:
        missing = [
            gap
            for requirement in case.requires
            for planted, gap in (in_place.get(requirement, (True, None)),)
            if not planted and gap is not None
        ]
        if missing:
            gaps[case.family] = missing[0]
        else:
            kept.append(case)
    return kept, gaps


def _announced(decide: Approve) -> Approve:
    """The estimate into the job log, and then the comparison.

    Printed here rather than inside `ceiling_approval` for the reason
    `console.py` exists: what a run says to a person is the script's, and what it
    decides is the bench's. The lines are the same `presented` a terminal prints,
    so a job log and a terminal show identical figures.
    """

    def approve(presented: BudgetPayload) -> Approval:
        print("\nEstimated cost of this run, before the first call:")
        for line in presented["presented"]:
            print(line)
        answer = decide(presented)
        print(
            f"\nConfirmed by {answer.identity}, against the ceiling this workflow "
            "declared."
            if answer.confirmed
            else f"\nDeclined: {answer.reason}"
        )
        return answer

    return approve


def _declared_ceiling(
    args: argparse.Namespace, call_price: CallPrice | None
) -> DeclaredCeiling:
    """What this workflow declared the run may cost, in whichever units it declared."""
    return DeclaredCeiling(
        calls=args.max_calls,
        spend=None if args.max_spend is None else Decimal(args.max_spend),
        price=call_price,
    )


def checkout_anchor(args: argparse.Namespace, callback: object | None) -> SourceAnchor:
    """Where this run's target is defined in the caller's checkout, or which absence.

    **This entrypoint is the only process in this repository that holds both a
    workspace and an object imported out of it**, which is why the resolution happens
    here and nowhere downstream — the argument is
    [ADR-0071](../docs/adr/0071-a-finding-points-at-a-file-the-bench-read.md), and the
    consequence here is that `--checkout` is read once, before the run, and handed to
    `ReportConfig` and to nothing else. It decides nothing about what is sent, and it
    reaches no instrument.
    """
    # A blank `--checkout` is no checkout and never the working directory: the action
    # interpolates an input into it, so an unset one arrives as an empty string, and
    # `Path("")` is `.` — which would point the reader at whatever directory this
    # process happens to be in (ADR-0071 §5).
    declared = (args.checkout or "").strip()
    return anchor_for(callback, checkout=Path(declared) if declared else None)


def proven_fixes(
    args: argparse.Namespace,
    target_run: TargetRun,
    cases: Sequence[Case],
    anchor: SourceAnchor,
    workspace: str,
) -> dict[str, FixStanding]:
    """Apply each fix the caller offered, re-attempt its case, and label the result.

    **The supply surface for a patch, and it is the caller's own code.** `--fix
    case-id=path` names a file the operator wrote; nothing in this bench composes one,
    and no model is asked to
    ([ADR-0072](../docs/adr/0072-a-post-patch-re-run-is-its-own-record.md) §2). What
    comes back is a label per case, and a case with no entry reads *proposed*
    ([ADR-0073](../docs/adr/0073-two-labels-on-a-fix-and-no-third.md)).

    **This entrypoint and no other**, for `checkout_anchor`'s own reason: it is the
    only process in this repository holding both a workspace and an object imported
    out of it, so it is the only one that can patch a copy of the first and re-serve
    the second. A hosted bench attacks a URL and cannot restart somebody else's
    server, which is why *proven* is unreachable there rather than merely unused.

    **It never ends the run.** Every failure below is printed and skipped, and the fix
    stays *proposed*: the run has already spent the operator's inference budget and
    holds every figure it will ever report, so ending it over the one part that
    decides nothing would be `anchor_for`'s hazard one field along (ADR-0071 §5). A
    fix that could not be applied is untested, which is what *proposed* says.
    """
    offered = _offered_once(args.fix or ())
    if not offered:
        return {}
    if anchor.reading is not SourceAnchorReading.ANCHORED or args.callback is None:
        # The one sentence this loop prints instead of a proof, and the reason it is
        # not a refusal: a target with no checkout is the ordinary case, and every
        # fix offered against one is *proposed* rather than rejected.
        print(
            f"\n{len(offered)} fix(es) offered and none can be proven: this run has "
            f"no patchable checkout ({anchor.reading.value}). Proving needs the code "
            "and the bench in the same place, and a target reached over the network "
            "is somebody else's server (ADR-0073)."
        )
        return {}
    records = {case.id: case for case in cases}
    succeeded = {
        attempt.case_id
        for attempt in target_run.attempts
        if attempt.verdict is Verdict.SUCCEEDED
    }
    checkout = Path((args.checkout or "").strip())
    _, entrypoint = callback_reference(args.callback)
    standings: dict[str, FixStanding] = {}
    for case_id, replacement in offered.items():
        case = records.get(case_id)
        if case is None or case_id not in succeeded:
            print(
                f"{case_id}: no succeeded attempt in this run, so there is nothing "
                "for a patch to close. The fix is not tested and not reported."
            )
            continue
        try:
            patch = Patch.for_anchor(anchor, Path(replacement).read_text("utf-8"))
            # The file as the bench read it, for the diff and for nothing else: the
            # patch is applied to a copy, and this text never leaves this process
            # except as the lines the change touches (ADR-0073 §3).
            replaced = (checkout / patch.path).read_text("utf-8")
        except (OSError, PatchRefused) as unusable:
            print(f"{case_id}: that fix was not applied — {unusable}")
            continue
        proof = prove_patch(
            patch,
            case,
            checkout=checkout,
            workspace=workspace,
            entrypoint=entrypoint,
            # The nonce that proved control is the canary the leakage cases read, on
            # `run_calibration`'s own terms: a re-run decided against a different
            # value would be decided by a different success condition.
            canary=target_run.registration.nonce,
        )
        standing = standing_for(proof, replaced)
        standings[case_id] = standing
        print(f"{case_id}: {standing.stated()}")
    return standings


def callback_reference(declared: str) -> tuple[str, str]:
    """`package.module:attribute`, split once for the two places that need it.

    Parsed here rather than at each site, because there are two now and they read the
    two halves: `_target` imports the module and serves the attribute, and
    `proven_fixes` re-serves that same attribute out of the patched copy
    (ADR-0072 §2). Two partitions of one string would only have to disagree once for
    the proof loop to re-serve something the run never attacked.
    """
    module_name, _, attribute = declared.partition(":")
    if not attribute:
        raise TypeError(
            f"{declared!r} is not a callback reference. It is written "
            "`package.module:attribute`, which is the module a workflow committed "
            "and the name in it that answers a message"
        )
    return module_name, attribute


def _a_fix(offered: str) -> tuple[str, str]:
    """One `--fix case-id=path`, split once at the parser and never guessed at.

    **At the parser, so that a mistyped command line costs nothing.** Refused rather
    than repaired: a value with no `=` in it is a command line the caller mistyped, and
    a value quietly re-read is a patch applied to a file nobody named. Every other
    refusal in this loop happens after the run and is printed and skipped, because by
    then the operator's inference budget is spent — this one happens before anything is
    sent, which is the only place a refusal is free (ADR-0073 §5).
    """
    case_id, sep, path = offered.partition("=")
    if not sep or not case_id.strip() or not path.strip():
        raise argparse.ArgumentTypeError(
            f"{offered!r} is not a fix. It is written "
            "`case-id=path/to/replacement.py`: the case whose failure the change is "
            "meant to close, and the whole file that replaces the one the bench "
            "anchored this run's target to (ADR-0072 §2)"
        )
    return case_id.strip(), path.strip()


def _offered_once(declared: Sequence[tuple[str, str]]) -> dict[str, str]:
    """The fixes, one per case, with a case named twice dropped and said so.

    **Not the last one wins.** Two changes offered for one case are two files, and a
    bench that quietly proved one of them would report a label earned by a change the
    caller may not have meant — which is the blur this whole ticket is about, arriving
    through a command line instead of through a word (ADR-0073 §1). Neither is tested
    and the case keeps *proposed*, which is what an untested fix says.

    Printed and skipped rather than raised, on `proven_fixes`'s own terms: this runs
    after the operator's inference budget is spent, and nothing here may end the run
    (ADR-0071 §5).
    """
    twice = {
        case_id
        for index, (case_id, _) in enumerate(declared)
        if case_id in {named for named, _ in declared[:index]}
    }
    for case_id in sorted(twice):
        print(
            f"{case_id}: named by more than one --fix, so neither change was tested. "
            "Two files offered for one case are two changes, and proving one of them "
            "would label a change the caller may not have meant (ADR-0073)."
        )
    return {case_id: path for case_id, path in declared if case_id not in twice}


def _target(
    args: argparse.Namespace, serving: ExitStack
) -> tuple[TargetConfig, object | None]:
    """The target this run attacks, and the object its plantings are performed on.

    A URL is a `TargetConfig` and nothing else. A callback is imported by the dotted
    reference the workflow named, served on loopback for the length of the run, and
    handed back as a `TargetConfig` too — `serve_callback` yields nothing more
    specific, and this entrypoint asks for nothing more specific
    ([ADR-0059](../docs/adr/0059-a-callback-target-is-served-over-the-contract.md)).
    The object comes back beside it because the planting hooks are on the callback
    rather than on the served app (ADR-0062).
    """
    if args.url is not None:
        return (
            _as_declared(
                TargetConfig(
                    name=args.name,
                    url=args.url,
                    auth_token=args.token,
                    agent_type=args.agent_type,
                    exposes_tool_calls=args.exposes_tool_calls,
                    retains_session_state=args.retains_session_state,
                    holds_personal_records=args.holds_personal_records,
                    declared_tools=tuple(args.declared_tools),
                ),
                args,
            ),
            None,
        )
    module_name, attribute = callback_reference(args.callback)
    callback = getattr(importlib.import_module(module_name), attribute)
    target = serving.enter_context(
        serve_callback(
            callback,
            name=args.name,
            agent_type=args.agent_type,
            # Forwarded, because retention is not one of the properties the shim
            # reads off the callback: a callback is handed a session id and what it
            # does with it is the operator's statement wherever the agent lives
            # (ADR-0059 §2).
            retains_session_state=args.retains_session_state,
            # Forwarded for the same reason retention is, and it is the same kind of
            # statement: what a callback holds about other people is the operator's
            # to declare wherever the agent lives, and the shim reads it off nothing
            # (ADR-0059 §2).
            holds_personal_records=args.holds_personal_records,
            declared_tools=tuple(args.declared_tools),
        )
    )
    return _as_declared(target, args), callback


def _as_declared(target: TargetConfig, args: argparse.Namespace) -> TargetConfig:
    """The five fields only the committed declaration can fill, put on the target.

    Applied to both shapes above rather than to the URL branch alone: `serve_callback`
    reads a callback's contract for what it can read off it, and these five are not
    among them — what a target does with untrusted input is the operator's statement
    wherever the agent lives, exactly as retention and personal records already are
    (ADR-0059 §2). A run with no `--declaration` leaves every one of them `None` and
    the target is the one it was.
    """
    return replace(
        target,
        processes_untrusted_input=args.processes_untrusted_input,
        reaches_private_data=args.reaches_private_data,
        changes_state_or_communicates=args.changes_state_or_communicates,
        under_human_supervision=args.under_human_supervision,
        retry=RetryPolicy(sends=args.sends) if args.sends else target.retry,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    # Not an `add_mutually_exclusive_group`, because one of the two has an
    # environment fallback and argparse's exclusion sees only what was typed: a
    # `AGENTAUDIT_TARGET_URL` left over from another job would then decide which of
    # two things a run attacked. The check is in `main`, where both are resolved.
    parser.add_argument(
        "--url",
        default=os.environ.get(URL_ENV) or None,
        help=(
            "the target's messages endpoint. Belongs in the caller's secret store "
            f"and reaches this run through {URL_ENV} rather than a command line "
            "wherever that is possible"
        ),
    )
    parser.add_argument(
        "--callback",
        default=None,
        help=(
            "a callback to serve and attack, as `package.module:attribute` — for a "
            "team whose agent is a Python object in their own repository (ADR-0059)"
        ),
    )
    # Empty rather than `target` and `assistant`, and `--currency` below the same:
    # the defaults are applied in `_the_declared_target` after the committed file has
    # been read, because a default argparse supplied is one the both-given rule
    # cannot tell from a value the caller typed (ADR-0103 §4).
    parser.add_argument("--name", default="")
    parser.add_argument("--agent-type", default="")
    parser.add_argument(
        "--declaration",
        default="",
        help=(
            "the committed `agentaudit.toml` this run is declared in — the same file "
            "the MCP server reads, so that a push-time run and an on-demand run "
            "measure the same declared target (ADR-0103). Empty by default, which "
            "declares the run from these inputs and reads no file; a path that is "
            "not there is refused rather than fallen back from. A key it declares "
            "and an input below both carry stops the run: neither wins"
        ),
    )
    parser.add_argument(
        "--checkout",
        default=None,
        help=(
            "the caller's own checkout, which the composite action passes as "
            "`github.workspace`. It is what lets a finding name a file and a line in "
            "their repository, and without one every finding says the bench could "
            "not see this target's source (ADR-0066, ADR-0071). Declared rather "
            "than guessed from the environment, and it is a path rather than a "
            "secret, so it is written on the command line where a reviewer of the "
            "workflow sees which directory the bench was pointed at. Read only: "
            "nothing in this bench writes into it"
        ),
    )
    parser.add_argument(
        "--fix",
        action="append",
        default=None,
        # Split and refused here rather than after the run, which is the whole of why
        # it is a `type=` and not a check inside the proof loop: a mistyped command
        # line is caught before a single call goes on the wire, and the loop that runs
        # after the operator's budget is spent then has nothing left it can refuse
        # (ADR-0073 §5).
        type=_a_fix,
        metavar="CASE_ID=PATH",
        help=(
            "a change to prove, as `case-id=path/to/replacement.py`. The file is the "
            "caller's own code and replaces the one this run anchored the target to; "
            "the bench copies the checkout, writes it into the copy, re-serves the "
            "entrypoint out of it and re-attempts that one case, and the copy is "
            "dropped however the run ends (ADR-0072). A case that no longer succeeds "
            "is reported as a **proven** fix, and everything else — including a "
            "change that was applied and did not close its case — as **proposed**. "
            "Repeatable, one case per fix. Without a --checkout there is nothing to "
            "patch and every fix stays proposed (ADR-0073)"
        ),
    )
    parser.add_argument("--token", default=os.environ.get(TOKEN_ENV, ""))
    parser.add_argument(
        "--nonce",
        default=os.environ.get(NONCE_ENV) or None,
        help=(
            "a registration nonce already planted in the target's configuration. "
            "Without one an unattended run waives the proof of control and says so "
            "in the artefact"
        ),
    )
    parser.add_argument("--identity", required=True, help="github.actor, or who ran it")
    parser.add_argument(
        "--attestation-file",
        required=True,
        help=(
            "the committed attestation: the three statements written out, and the "
            "target they are made against"
        ),
    )
    parser.add_argument(
        "--out",
        required=True,
        help="where report.json, report.md and report.sig are written",
    )
    parser.add_argument(
        "--max-calls",
        type=int,
        default=None,
        help="the most calls this run may be permitted to make",
    )
    parser.add_argument(
        "--max-spend",
        default=None,
        help=(
            "the most this run may be permitted to cost, in the declared currency. "
            "Needs --price-per-call: a ceiling in money on a run with no price is "
            "declined rather than ignored"
        ),
    )
    parser.add_argument("--price-per-call", default=None)
    parser.add_argument("--currency", default="")
    parser.add_argument("--adjudicator-model", default=None)
    parser.add_argument("--deterministic-only", action="store_true")
    parser.add_argument(
        "--families",
        nargs="+",
        default=None,
        metavar="FAMILY",
        help=(
            "the families this run covers, by name, space-separated. All six "
            "without it. A cheaper run and a narrower reading, and both are the "
            "caller's to choose — a family switched off is reported as **not run** "
            "in the signed artefact rather than measured at zero, so a reader of "
            "the document can tell a family that was not asked from one that held "
            "(ADR-0058, ADR-0075). A name this bench does not hold is refused "
            "before anything is sent"
        ),
    )
    parser.add_argument(
        "--attempts-per-case",
        type=int,
        default=None,
        help=(
            "how many times each case is attempted. Ten without it, which is the "
            "declared denominator of ADR-0003 and the only number a report may be "
            "compared at; a run below it is a real run and **not a gate result**, "
            "and the artefact says so beside the figures rather than leaving it to "
            "this flag's reader (ADR-0025, ADR-0027)"
        ),
    )
    parser.add_argument(
        "--note-planted",
        action="store_true",
        help=(
            "declare that the third-party note this library's indirect-injection "
            "cases carry is filed in content this target retrieves. Without it the "
            "family is withdrawn rather than sent: nobody can be asked in a runner, "
            "and a family attacking content that is not there comes back 0.00 "
            "(ADR-0024). A callback that implements the hook needs no declaration"
        ),
    )
    parser.add_argument(
        "--summary",
        default=None,
        help=(
            "a file to append the run's page to — `$GITHUB_STEP_SUMMARY` in a "
            "workflow. The signed rendering, the families nothing was planted for, "
            "and where the artefact is; refused if it carries payload text or a "
            "secret (ADR-0008)"
        ),
    )
    parser.add_argument(
        "--artifact-name",
        default="agentaudit-report",
        help="what the page calls the upload the three files were attached to",
    )
    parser.add_argument("--exposes-tool-calls", action="store_true")
    # Every scripted construction in the library requires `SESSION_RETENTION`
    # (`library.py`), so a URL target run without this flag is one the fixed
    # multi-turn half of the scored layer is skipped against, whatever the
    # selection says. A callback declares it by implementing the contract and
    # never here (ADR-0059).
    parser.add_argument("--retains-session-state", action="store_true")
    # Every case of the tier's PII leakage family requires `PERSONAL_RECORDS_HELD`
    # (`library.py`), so a target run without this flag is one that family is
    # withdrawn against before an attempt is spent, whatever the tier was asked for
    # (ADR-0043, ADR-0095).
    parser.add_argument("--holds-personal-records", action="store_true")
    parser.add_argument("--declared-tools", nargs="*", default=[])
    # No flag for any of these five, and that is the decision rather than an
    # omission: the four the Agents Rule of Two is read over and the ceiling one
    # message may go on the wire under are declared in the committed file or not at
    # all on this surface, so the workflow gains no way to claim a control in a
    # `with:` block (ADR-0103 §2). `None` on all five is *nobody said anything*,
    # which is what `TargetConfig` reads it as.
    parser.set_defaults(**dict.fromkeys(ONLY_IN_THE_DECLARATION))
    return parser


if __name__ == "__main__":
    sys.exit(main())
