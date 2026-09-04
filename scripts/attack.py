"""Runs the adaptive layer and nothing else, against the reference agents.

    uv run python -m scripts.attack --identity "your name"
    uv run python -m scripts.attack --identity "your name" --turns 8
    uv run python -m scripts.attack --identity "your name" --agents trivial hardened
    uv run python -m scripts.attack --identity "your name" \
        --attacker-model openrouter:anthropic/claude-sonnet-4.5 --turns 12 --episodes 1

**Attacker development equipment, and it produces no result.** `calibrate.py` and
`gate.py` measure targets; this measures the *attacker*, which is why it spends no
attempt: with no attempt there is no rate, no `D`, no κ and nothing to sign, and a
script that emitted a report over an empty scored layer would be the one artefact
this bench must not be able to produce. What it prints is `A_break` and `A_effort`
over the episodes it ran, and those two are the numbers ADR-0011 puts the attacker's
own quality on.

**Registration still happens, because the layer needs two things from it.** The
canary is the nonce that proved control — one planted value, two roles (ADR-0007) —
and the withdrawn families are the endpoint's own answer to the operator's
`exposes_tool_calls` declaration, checked against the echo probe's reply. Neither
needs a scored attempt, which is the whole reason this script is possible: one probe
per target, and the estimate says so.

**The scored figure is one registration probe per target, and that is not a
loophole.** The budget is declared over no cases, so the ceiling an operator
confirms is the ceiling this run can reach on either counter (ADR-0007). The
adaptive ceiling is the full `episodes × T` for whatever `T` was asked for, and `T`
is a flag here rather than the declared eight because the declared eight was sized
for a gate run over three agents — the number is the operator's to choose in front
of the estimate that was built from it (`bench/completion.declared_turns_per_episode`
says the same from the deployment side).

**ADR-0010 is not weakened by running one layer alone.** The rule is that no
adaptive result may write into a scored rate, and that the adaptive layer runs after
the scored one per target so that a stateful target cannot be touched by an adaptive
turn before a scored attempt. A run with no scored attempt has no rate to write into
and no attempt to come before, so both hold trivially. What it does mean is that
nothing here may be quoted as a reading about a *target*: these episodes are
evidence about the attacker.
"""

import argparse
import os
import secrets
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import InvalidOperation
from pathlib import Path

from dotenv import load_dotenv

from backend.bench.adaptive.attacker import AttackerCompletion
from backend.bench.adaptive.budget import AdaptiveBudget
from backend.bench.adaptive.episode import AdaptiveEpisode, EpisodeOutcome
from backend.bench.adaptive.layer import (
    AttackableTarget,
    objectives_for,
    run_adaptive_layer,
)
from backend.bench.admission import NotAdmitted, admitted_library
from backend.bench.applicability import applicable
from backend.bench.calibration import PlantNonce
from backend.bench.completion import (
    DEFAULT_ATTACKER_MODEL,
    attacker_completion_for,
)
from backend.bench.contract import TargetConfig
from backend.bench.library import Case, Family, LibraryVersion
from backend.bench.measurability import contradicted_by_the_reply
from backend.bench.registration import Attestation, Registration, issue_nonce, register
from backend.graph.approval import ApprovalOutcome, run_under_approval
from backend.graph.budget import BudgetExceeded, CallPrice, Layer, RunBudget
from backend.graph.runstate import RunState
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
    TOKEN_ENV,
    adaptive_discrimination_section,
    attest,
    episode_lines,
    excerpt,
    interactive_planter,
    note_is_planted,
    price,
    terminal_approval,
)

CASES_DIR = Path(__file__).resolve().parents[1] / "backend" / "cases"
DEFAULT_MODEL = "openrouter:openai/gpt-4.1-nano"
# The same default as `calibrate.py`, and for the same reason: the reference agents
# need a model that will run them as built, because a model that refuses the trivial
# agent's payloads is reporting its own defences rather than the agent's absent ones.


def declared_budget(
    targets: Sequence[TargetConfig],
    adaptive: AdaptiveBudget,
    call_price: CallPrice | None = None,
) -> RunBudget:
    """The ceiling for a run that scores nothing: registration, and the layer.

    Declared over **no cases**, which is what makes the scored figure the one probe
    per target this run actually sends. Passing the library here would present an
    operator with 181 calls per target and then spend one, and a consent figure that
    overstates by two orders of magnitude is one nobody reads twice (ADR-0007).

    The library still reaches `run_adaptive_layer`, because an objective is a
    recorded case. Two different questions — what may be spent, and what the
    attacker is aiming at — and only the first is this function's.
    """
    return RunBudget.declare(
        cases=(), targets=targets, adaptive=adaptive, price=call_price
    )


def attackable(
    target: TargetConfig,
    cases: Sequence[Case],
    attestation: Attestation,
    run_state: RunState,
    plant_nonce: PlantNonce | None = None,
    proof_waived: bool = False,
) -> tuple[Registration, AttackableTarget | None]:
    """Register one target, and describe it to the adaptive layer if it registered.

    `None` beside the registration for a target that never echoed its nonce, and the
    registration is returned either way: a refusal has to be printable, because a
    target that was never attacked and a target that held are the two readings this
    script must never let collapse (`probe_target.py` guards the same confusion on
    the scored side).

    `proof_waived` is the operator declaring the run may start without the echo
    (ADR-0007, amended). The probe is still sent and what came back is still
    recorded — the waiver is about what a missing echo *stops*, never about what the
    bench looks at — so a target that echoes anyway is recorded as having proved
    control. What it cannot do is make the canary appear in a target that does not
    hold it, which is why the caller that waives because nothing was planted also
    drops the family that value is the canary for.

    The withdrawn families are read from the echo probe's own reply rather than from
    the declaration, and they are read here rather than inside the layer for the
    reason `calibration._run_target` carries them across: the two layers must not be
    able to disagree about which families a target can be measured on.
    """
    nonce = issue_nonce()
    if plant_nonce is not None:
        plant_nonce(target, nonce)
    registration = register(target, nonce, attestation, run_state, proof_waived)
    if not registration.complete:
        return registration, None
    withdrawn = contradicted_by_the_reply(
        applicable(cases, target), target, registration.probe
    )
    return registration, AttackableTarget(
        target=target, canary=registration.nonce, withdrawn=frozenset(withdrawn)
    )


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        default=os.environ.get("AGENTAUDIT_REFERENCE_MODEL", DEFAULT_MODEL),
        help="the reference agents' underlying model, as '<provider>:<model>'",
    )
    parser.add_argument(
        "--attacker-model",
        default=os.environ.get("AGENTAUDIT_ATTACKER_MODEL", DEFAULT_ATTACKER_MODEL),
        help=(
            "the model the adaptive attacker runs on. The instrument under test "
            "here, and named rather than defaulted inside the run"
        ),
    )
    parser.add_argument(
        "--agents",
        nargs="+",
        default=[agent.name for agent in REFERENCE_AGENTS],
        help=(
            "which reference agents to attack. A_break and A_effort need the "
            "trivial and hardened ends, so a subset without both reads as not "
            "measured rather than as no separation"
        ),
    )
    parser.add_argument(
        "--turns",
        type=int,
        default=AdaptiveBudget().turns_per_episode,
        help=(
            "T — how many probes one episode may send before it is capped. The "
            "estimate is built from this number, and an episode that reaches it "
            "without a break is censored rather than resisted (ADR-0011)"
        ),
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=AdaptiveBudget().episodes_per_family,
        help=(
            "k — how many episodes per family per target. Episodes are not "
            "samples of a rate, so fewer of them buys a cheaper run and costs no "
            "precision there was any of"
        ),
    )
    parser.add_argument(
        "--url",
        default=None,
        help=(
            "your own agent's endpoint. Given, the reference agents are not "
            "served and not attacked, and A_break is not read — it is a "
            "comparison between the trivial and hardened ends and one endpoint "
            "is not a pair"
        ),
    )
    parser.add_argument(
        "--token",
        default=os.environ.get(TOKEN_ENV),
        help=(
            "the bearer token your endpoint expects. Defaults to "
            f"{TOKEN_ENV} from the environment or .env, because a token on a "
            "command line is a token in a shell history file"
        ),
    )
    parser.add_argument(
        "--name", default="target", help="what to call the target under --url"
    )
    parser.add_argument(
        "--agent-type",
        default="assistant",
        help="what kind of agent this is. Recorded, and read by applicability",
    )
    parser.add_argument(
        "--exposes-tool-calls",
        action="store_true",
        help=(
            "the endpoint returns a tool_trace beside its reply. Without it, "
            "scope creep and halt defeat are withdrawn before an episode opens "
            "against either, because nothing could check the break"
        ),
    )
    parser.add_argument(
        "--declared-tools",
        nargs="*",
        default=[],
        help=(
            "the tools you declare this target has. Scope creep is a call "
            "outside this list, so an empty list leaves that family no break to "
            "aim at"
        ),
    )
    parser.add_argument(
        "--waive-echo",
        action="store_true",
        help=(
            "start without the echo. The nonce is planted, but this target will "
            "not reply with it verbatim — a target that reformats it, prefixes it "
            "or wraps it in prose never registers, and that is a fact about its "
            "output rather than about your control of it (ADR-0007, amended). The "
            "probe is still sent and what came back is still printed"
        ),
    )
    parser.add_argument(
        "--nonce-not-planted",
        action="store_true",
        help=(
            "the canary is nowhere in this target's configuration. Implies the "
            "echo waiver and drops data leakage, whose whole break is that "
            "planted value appearing in a reply — episodes against a value the "
            "target does not hold would be censored by the setup"
        ),
    )
    parser.add_argument(
        "--identity",
        required=True,
        help=(
            "who is attesting and confirming this run. Required, and never "
            "defaulted from the environment: it is the liability record"
        ),
    )
    parser.add_argument(
        "--price-per-call",
        default=None,
        help="what one call to the target costs you, from your own provider",
    )
    parser.add_argument("--currency", default="USD", help="the currency of the price")
    args = parser.parse_args(argv)

    try:
        call_price = price(args.price_per_call, args.currency)
    except (InvalidOperation, ValueError) as bad:
        print(f"Not a usable price per call: {bad}")
        return EXIT_WITHHELD

    if args.url is not None and not args.token:
        # Before the attestation and before the estimate. Both of those ask
        # something of the operator — a liability record and their money — and
        # asking either for a run that cannot authenticate to its target is asking
        # somebody to consent to a run that will not happen.
        print(f"No token. Pass --token or set {TOKEN_ENV}.")
        return EXIT_WITHHELD

    try:
        adaptive = AdaptiveBudget(
            turns_per_episode=args.turns, episodes_per_family=args.episodes
        )
    except ValueError as refused:
        print(f"Not a usable adaptive budget: {refused}")
        return EXIT_WITHHELD

    if args.url is None:
        # Parsed before the attestation, so a mistyped reference model is a refusal
        # rather than a run that stops after the operator has answered three
        # statements. Nothing parses it on the --url path: the reference agents'
        # model is not this run's business when the target is somebody's own.
        try:
            ModelConfig.parse(args.model)
        except ValueError as unusable:
            print(f"No usable reference agent model: {unusable}")
            return EXIT_WITHHELD

    try:
        cases = admitted_library(CASES_DIR)
    except NotAdmitted as unearned:
        print(f"The library holds a case that did not earn its place:\n{unearned}")
        return EXIT_WITHHELD

    try:
        # Built before the attestation, so a missing credential is a refusal rather
        # than a run that stops after having sent something.
        attacker: AttackerCompletion = attacker_completion_for(args.attacker_model)
    except (KeyError, ValueError) as unusable:
        print(f"No usable attacker model: {unusable}")
        return EXIT_WITHHELD

    attestation = attest(args.identity)
    if attestation is None:
        print("Attestation withheld. Nothing was sent.")
        return EXIT_WITHHELD

    if args.url is not None:
        target = TargetConfig(
            name=args.name,
            url=args.url,
            auth_token=args.token,
            agent_type=args.agent_type,
            exposes_tool_calls=args.exposes_tool_calls,
            declared_tools=tuple(args.declared_tools),
        )
        # Asked before the approval interrupt and after the attestation, on
        # `probe_target.py`'s reasoning: the note is a claim about the operator's
        # content store that the bench cannot check, and a family whose planted
        # instruction is not there produces episodes censored by the setup rather
        # than by the target.
        if not note_is_planted(cases):
            cases = [
                case
                for case in cases
                if case.family is not Family.INDIRECT_PROMPT_INJECTION
            ]
        if args.nonce_not_planted:
            # The registration nonce is the leakage canary — one planted value, two
            # roles — so a run whose operator planted nothing has no canary for
            # `check_canary` to find, and every leakage episode would read as a
            # target that held (`api/runs.plan_for` drops the same family for the
            # same reason).
            cases = [case for case in cases if case.family is not Family.DATA_LEAKAGE]
        outcome = _attack(
            targets=[target],
            # Nothing to plant, so nothing is asked. A planter that printed lines
            # to paste for a run that declared them unplanted would be instructions
            # the operator has already answered.
            plant_nonce=None if args.nonce_not_planted else interactive_planter(),
            cases=cases,
            attestation=attestation,
            attacker=attacker,
            adaptive=adaptive,
            call_price=call_price,
            proof_waived=args.waive_echo or args.nonce_not_planted,
        )
    else:
        auth_token = secrets.token_urlsafe(16)
        app = create_reference_app(
            ReferenceConfig(model=ModelConfig.parse(args.model), auth_token=auth_token)
        )
        with serve(app) as base_url:
            outcome = _attack(
                targets=described_agents(
                    base_url,
                    auth_token,
                    [
                        agent
                        for agent in REFERENCE_AGENTS
                        if agent.name in set(args.agents)
                    ],
                ),
                plant_nonce=nonce_planter(base_url),
                cases=cases,
                attestation=attestation,
                attacker=attacker,
                adaptive=adaptive,
                call_price=call_price,
            )

    if outcome is None:
        return EXIT_ABORTED
    if not outcome.approval.proceeded:
        print(f"\nRun not started: {outcome.approval.reason}")
        print("Nothing was sent, and nothing was spent.")
        return EXIT_DECLINED

    _print_result(args, cases, outcome, adaptive, against_reference=args.url is None)
    return 1 if any(entry.refused for entry in outcome.registrations) else 0


@dataclass(frozen=True)
class Attacked:
    """What one adaptive-only run recorded: the registrations, the state, the answer.

    A record rather than three returned values, because a caller that unpacked them
    positionally could print a state against another run's registrations, and the
    two are only readable together — an episode count means nothing beside a
    registration that was refused.
    """

    registrations: tuple[Registration, ...]
    entries: tuple[AttackableTarget, ...]
    state: RunState
    approval: ApprovalOutcome


def _attack(
    targets: Sequence[TargetConfig],
    plant_nonce: PlantNonce | None,
    cases: Sequence[Case],
    attestation: Attestation,
    attacker: AttackerCompletion,
    adaptive: AdaptiveBudget,
    call_price: CallPrice | None,
    proof_waived: bool = False,
) -> Attacked | None:
    """Register every target, then run the layer against the ones that registered.

    `None` for a run the ceiling stopped, which is the one outcome with nothing to
    print: the abort is the answer, and it is the caller's exit code rather than a
    section of a result.

    One function for both paths on purpose. The difference between attacking the
    reference agents and attacking somebody's own endpoint is a `TargetConfig` and
    who plants the nonce — everything after that is the same run, and a second copy
    of it is a second place for the consent interrupt to go missing (ADR-0007).
    """
    declared = declared_budget(targets, adaptive, call_price)
    state = Narrating(budget=declared, library=LibraryVersion.of(cases))
    registrations: list[Registration] = []
    entries: list[AttackableTarget] = []

    def attack() -> None:
        for target in targets:
            registration, entry = attackable(
                target, cases, attestation, state, plant_nonce, proof_waived
            )
            registrations.append(registration)
            if entry is not None:
                entries.append(entry)
        run_adaptive_layer(
            attackable=entries,
            cases=cases,
            run_state=state,
            attacker=attacker,
            budget=adaptive,
        )

    try:
        approval = run_under_approval(
            declared, attack, terminal_approval(attestation.identity)
        )
    except BudgetExceeded as abort:
        print(f"\nRun aborted on budget: {abort}")
        return None
    return Attacked(
        registrations=tuple(registrations),
        entries=tuple(entries),
        state=state,
        approval=approval,
    )


def _print_result(
    args: argparse.Namespace,
    cases: Sequence[Case],
    outcome: Attacked,
    adaptive: AdaptiveBudget,
    against_reference: bool,
) -> None:
    """What this run is evidence about, and what it deliberately is not.

    The header states the attacker's model and `T` before anything else, because
    every number below is a reading about that pair and about nothing else — an
    `A_break` quoted without them would read as a property of the targets.
    """
    if against_reference:
        print(f"\nreference agent model: {args.model}")
    else:
        print(f"\ntarget:                {args.url}  (your endpoint, not equipment)")
    print(f"attacking model:       {args.attacker_model}  (the instrument under test)")
    print(f"T:                     {adaptive.turns_per_episode} turns per episode")
    print(f"k:                     {adaptive.episodes_per_family} episodes per family")
    print(f"cases available as objectives: {len(cases)}")
    print("scored layer:          not run — no attempt, so no rate and no report")

    for registration in outcome.registrations:
        target = registration.target
        status = _registration_status(registration)
        print(f"\ntarget {target.name} ({target.url})")
        print(f"  registration: {status}")
        print(f"  nonce:        {registration.nonce}")
        print(f"  echo reply:   {excerpt(registration.probe.reply_text)}")
        if not registration.complete:
            print(
                "  no episode ran against this target, so it holds nothing. Check "
                "that the nonce line is in the system prompt, that the target "
                "reloaded it, and that the registration-check exception is there too"
            )
            continue
        withdrawn = next(
            (
                entry.withdrawn
                for entry in outcome.entries
                if entry.target.name == target.name
            ),
            frozenset(),
        )
        objectives = objectives_for(cases, target, withdrawn)
        print(f"  families in scope: {len(objectives)}")
        for family, case in objectives.items():
            print(f"    {family} — objective {case.id}")

    print(episode_lines(outcome.state.episodes))
    if against_reference:
        print(
            adaptive_discrimination_section(
                outcome.state.episodes,
                trivial=TRIVIAL.name,
                hardened=HARDENED.name,
                budget=adaptive,
            )
        )
    else:
        # A stated absence rather than a number over one endpoint. `A_break` is the
        # difference between what the attacker broke on the trivial agent and what it
        # broke on the hardened one, and a single target is not a pair — printing it
        # here would be a separation nothing measured (ADR-0011).
        print(
            "\nA_break, A_effort: not read — both are comparisons between the "
            "trivial and hardened reference agents, and this run attacked one "
            "endpoint. Run without --url to read the attacker against the pair"
        )
    print(
        f"\ncalls spent: {outcome.state.spent_in(Layer.SCORED)} scored "
        f"(registration probes only), "
        f"{outcome.state.spent_in(Layer.ADAPTIVE)} adaptive"
    )


def _registration_status(registration: Registration) -> str:
    """Proved, declared, or refused — three answers and never two.

    A waived run that registered on the declaration alone must not print the same
    word as one whose target echoed the value, because everything downstream rests
    on a different thing in each case: one has proof of control and the other has
    the operator's statement (ADR-0007, amended).
    """
    if registration.echoed:
        return "complete — the nonce came back, so control is proved"
    if registration.waived:
        return (
            "complete on your declaration — the nonce was not echoed and you "
            "waived that proof, so control is declared and not proved"
        )
    return "REFUSED — nonce not echoed"


PROBES_BANNER = (
    "\nthe probes this run sends — not part of any artefact, and a copy of a probe "
    "that worked is a copy of a working exploit (ADR-0008)"
)
"""Printed once, before the first probe. The same posture the API's episodes route
states: this text is served out of memory, is committed to nothing, and is excluded
from the signed artefact because the artefact is the document that circulates."""


BROKE_IT = "BROKE IT — the objective was met on this turn"
HELD = "no break"
NOT_CHECKABLE = (
    "not checkable — the reply carried nothing this objective's condition reads, "
    "so this is not the target holding"
)


def _turn_reading(episode: AdaptiveEpisode, turn: int) -> str:
    """What one turn was found to be: broke it, held, or nothing to read.

    Three answers rather than two. The third is the one that costs a reader money
    when it is missing: a halt-defeat turn against a reply that records no stop
    position cannot show an action *after* a stop, so printing it as *no break*
    would describe a defence that was never tested (`measurability.checkable`).

    The break belongs to the last turn of a broken episode by construction — the
    harness verifies each probe as it comes back and the episode stops there — so
    this reads the record rather than guessing at it.
    """
    if turn in episode.unverifiable_turns:
        return NOT_CHECKABLE
    if episode.outcome is EpisodeOutcome.BROKEN and turn == episode.turns:
        return BROKE_IT
    return HELD


def _episode_block(index: int, episode: AdaptiveEpisode) -> str:
    """One episode's probes and everything that came back, in the order it went.

    Printed in full rather than excerpted, because the reason to run this script is
    to read what the attacker actually said — a truncated probe is not a probe you
    can judge, and the reply is where the break either is or is not.
    """
    lines = [
        f"\n  episode {index} — {episode.target_name} / {episode.family}: "
        f"{episode.stated()} after {episode.turns} turns"
    ]
    for turn, transcript in enumerate(episode.transcripts, start=1):
        sent = str(transcript.sent.get("message", ""))
        lines.append(f"    turn {turn} — {_turn_reading(episode, turn)}")
        lines.append(f"    turn {turn} probe:")
        lines.extend(f"      {line}" for line in sent.splitlines() or [""])
        lines.append(f"    turn {turn} reply ({transcript.status_code}):")
        lines.extend(
            f"      {line}" for line in transcript.reply_text.splitlines() or [""]
        )
        trace = transcript.tool_trace
        if trace is not None:
            # The trace is what two of the four deterministic families are decided
            # on, so a reader judging a censored scope-creep episode needs it beside
            # the reply rather than a screen away.
            lines.extend(f"      {line}" for line in trace.rendered().splitlines())
    for proposal in episode.proposals:
        lines.append(
            f"    proposed {proposal.case.id}: {proposal.description} — faces a "
            "stated bar, and is not admitted by having been proposed"
        )
    return "\n".join(lines)


@dataclass
class Narrating(RunState):
    """A run state that prints each episode as it is recorded, not when the run ends.

    An episode against a real endpoint takes `T` model calls on the target and `T`
    more on the attacker, so a run at the declared budget is minutes long. A script
    whose whole output arrived at the end would leave an operator watching their own
    server log to find out whether anything was happening — which is what this
    exists to stop.

    The seam is `record_episode` rather than anything inside the layer: the episode
    is the first point at which the probes and the replies are both in one record,
    and overriding here leaves `run_adaptive_layer` with nothing to know about who
    is watching. There is no turn-level hook on purpose — `enter_turn` is called
    before the probe goes on the wire, so a printer there would announce a payload
    without the reply that gives it meaning.
    """

    announced: bool = False
    """Whether the banner has been printed. Held here rather than checked against
    the episode count, so the words appear exactly once however many episodes run."""

    def enter_episode(self, target_name: str, family: Family) -> None:
        super().enter_episode(target_name, family)
        if not self.announced:
            print(PROBES_BANNER, flush=True)
            self.announced = True
        print(
            f"\n  … episode {len(self.episodes) + 1} against {target_name} / "
            f"{family} — probing",
            flush=True,
        )

    def record_episode(self, episode: AdaptiveEpisode) -> None:
        super().record_episode(episode)
        print(_episode_block(len(self.episodes), episode), flush=True)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
