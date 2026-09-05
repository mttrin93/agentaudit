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
from collections.abc import Sequence
from contextlib import ExitStack
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dotenv import load_dotenv

from backend.api.report import ReportConfig, payload_for
from backend.bench.adjudication import Completion
from backend.bench.admission import NotAdmitted, admitted_library
from backend.bench.calibration import run_calibration
from backend.bench.cited import the_citation, the_reliability
from backend.bench.completion import DEFAULT_ADJUDICATOR_MODEL
from backend.bench.contract import TargetConfig
from backend.bench.library import AnyFamily, Case, Family, Plant, Precondition
from backend.bench.narration import Narrator
from backend.bench.payload import DeclaredModels
from backend.bench.rule import DECLARED_RULE
from backend.bench.selection import EVERY_CONSTRUCTION
from backend.bench.shim import serve_callback
from backend.bench.signing import NoSigningKey, publish_signed, signing_key
from backend.bench.unattended import (
    DeclaredCeiling,
    ceiling_approval,
    committed_attestation,
)
from backend.bench.usage import UsageLedger
from backend.graph.approval import Approval, Approve
from backend.graph.budget import (
    BudgetExceeded,
    BudgetPayload,
    CallPrice,
    Layer,
    RunBudget,
)
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

    try:
        call_price = price(args.price_per_call, args.currency)
        ceiling = _declared_ceiling(args, call_price)
    except (InvalidOperation, ValueError) as bad:
        print(f"The declared inputs do not describe a run: {bad}")
        return EXIT_WITHHELD

    if (args.url is None) == (args.callback is None):
        # Exactly one target, and the attestation names exactly one. Two is a run
        # whose subject depends on which resolution rule the reader assumed, and
        # zero is not a run.
        print(
            "This run has no target, or two. Pass exactly one of --url (or "
            f"{URL_ENV}) and --callback: the committed attestation names one target "
            "and authorises a run against that one."
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

        try:
            result = run_calibration(
                cases=cases,
                targets=[target],
                attestation=attestation,
                approve=_announced(ceiling_approval(args.identity, ceiling)),
                adjudicator=adjudicator,
                narrator=narrator,
                usage=ledger,
                budget=RunBudget.declare(
                    cases=cases, targets=[target], price=call_price
                ),
                planters={} if planter is None else {target.name: planter},
                planted_nonces=(
                    {} if args.nonce is None else {target.name: args.nonce}
                ),
                # Waived where nothing planted a value: a run in a runner has nobody
                # to paste one, and `WAIVED` above says what that costs the reading.
                proof_waived=waived,
                trace=traced_run(adjudicator_model=adjudicator_model),
            )
        except BudgetExceeded as abort:
            print(f"\nRun aborted on budget: {abort}")
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
    # Per layer and never added, in the job log as on a terminal: a blended figure
    # would hide which half of a run is consuming the caller's budget (ADR-0007).
    for layer in Layer:
        print(
            f"\ncalls spent, {layer} layer: {result.run_state.spent_in(layer)} "
            f"of a declared ceiling of {result.budget.ceiling(layer)}"
        )
    print(f"confirmed by: {result.approval.identity}")

    published = publish_signed(
        payload_for(
            result,
            cases,
            DECLARED_RULE,
            ReportConfig(
                signing_key=key,
                models=DeclaredModels(
                    calibration=UNDECLARED,
                    adjudicating=adjudicator_model or UNDECLARED,
                    attacking=UNDECLARED,
                ),
                # The same durable path a deployed bench reads them off
                # (`app.deployed_bench`): the gate run this library cites, and the κ
                # it measured — and only where it measured it on the model these
                # runs adjudicate with (ADR-0004, ADR-0023).
                gate=the_citation(CASES_DIR),
                reliability=the_reliability(CASES_DIR).for_adjudicator(
                    adjudicator_model or UNDECLARED
                ),
            ),
            EVERY_CONSTRUCTION,
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
            TargetConfig(
                name=args.name,
                url=args.url,
                auth_token=args.token,
                agent_type=args.agent_type,
                exposes_tool_calls=args.exposes_tool_calls,
                declared_tools=tuple(args.declared_tools),
            ),
            None,
        )
    module_name, _, attribute = args.callback.partition(":")
    if not attribute:
        raise TypeError(
            f"{args.callback!r} is not a callback reference. It is written "
            "`package.module:attribute`, which is the module a workflow committed "
            "and the name in it that answers a message"
        )
    callback = getattr(importlib.import_module(module_name), attribute)
    target = serving.enter_context(
        serve_callback(
            callback,
            name=args.name,
            agent_type=args.agent_type,
            declared_tools=tuple(args.declared_tools),
        )
    )
    return target, callback


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
    parser.add_argument("--name", default="target")
    parser.add_argument("--agent-type", default="assistant")
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
    parser.add_argument("--currency", default="USD")
    parser.add_argument("--adjudicator-model", default=None)
    parser.add_argument("--deterministic-only", action="store_true")
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
    parser.add_argument("--declared-tools", nargs="*", default=[])
    return parser


if __name__ == "__main__":
    sys.exit(main())
