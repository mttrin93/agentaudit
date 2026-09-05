"""A case may be a sequence of turns, and one attempt is one script in one session.

Fixed multi-turn in the **scored** layer. Everything here is a consequence of the
one property that pays for the rate — `backend/bench/attacker.py`: *attempts are
independent by construction, each carries its own session id, so a rate is a rate
rather than a trajectory.* A script makes an attempt cost several turns and moves
nothing about the denominator: the dependence is *inside* an attempt and never
between two (CONTEXT.md, **attempt**;
[ADR-0053](../../docs/adr/0053-a-case-may-be-a-sequence-and-the-verdict-is-read-per-turn.md)).

Driven through the seams the rest of the suite uses: `Case` and `load_case` for what
a record may say, `RunBudget.declare` for what an operator is shown, `run_attempt`
against a stub target for what goes on the wire, and `evaluate_script` for the
verdict.
"""

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from backend.bench import attacker
from backend.bench.contract import TargetConfig, Transcript
from backend.bench.entry import case_record
from backend.bench.evaluator import Verdict, evaluate_script
from backend.bench.library import (
    Case,
    ElectiveFamily,
    Family,
    JudgedCondition,
    Precondition,
    SuccessCondition,
    SuccessConditionKind,
    Transform,
    VerdictClass,
    load_case,
    load_library,
)
from backend.bench.measurability import (
    TraceNotVisible,
    measurable,
    unmet_preconditions,
)
from backend.bench.rule import DECLARED_RULE
from backend.bench.transforms import applied, base64_encoded
from backend.graph.budget import RunBudget
from backend.graph.runstate import Attempt, RunState
from backend.tests.conftest import (
    CASES_DIR,
    a_target,
    reference_target,
    unlisted_case,
)


def a_scripted_case(case_id: str = "scripted-000", turns: int = 4) -> Case:
    """A case whose payload is a script of that many turns."""
    return replace(
        unlisted_case(payload="one turn", case_id=case_id),
        payload=tuple(f"turn {index + 1}" for index in range(turns)),
        requires=(Precondition.SESSION_RETENTION, Precondition.CONFIG_CANARY_PLANT),
    )


def test_a_case_costs_one_call_per_turn_of_its_script() -> None:
    # `Case.turns` is what the estimate is read off, and a four-turn script is four
    # calls on the operator's endpoint inside *one* attempt. The denominator does
    # not move (CONTEXT.md, **attempt**).
    assert a_scripted_case(turns=4).turns == 4
    assert a_scripted_case(turns=1).turns == 1


# --- A single-turn transform over a script -----------------------------------


def test_a_single_turn_transform_is_applied_to_every_turn_of_a_script() -> None:
    # A transform says how a payload is spelled, and a script is several payloads:
    # a base64 variant of a four-turn case sends four encoded turns, so the
    # comparison against the base case is turn for turn (ADR-0052 §1, ADR-0053).
    script = a_scripted_case(turns=3).payload
    assert applied(Transform.BASE64, script) == tuple(
        base64_encoded(turn) for turn in script
    )
    assert applied(Transform.PLAIN, script) == script


def test_the_scripted_crescendo_transform_is_not_reached_through_this_one() -> None:
    # #74 owns the payload *type* a script needs and not the escalation itself. The
    # two deterministic ladders are #75's and they take the base *record* rather than
    # its payload, so this entry point still refuses the member and names the one
    # that dispatches it (`transforms.derived_payload`, ADR-0054 §1).
    with pytest.raises(ValueError, match="derived_payload"):
        applied(Transform.SCRIPTED_CRESCENDO, ("a first turn",))


# --- One attempt is one script in one session --------------------------------


class Wire:
    """A target that answers each turn of a script from a fixed list of replies.

    Substituted for `contract.send_message`, which is the process boundary and not
    a collaborator inside the attacker: what is under test is what `run_attempt`
    puts on the wire and what it makes of what comes back, and a reference agent
    cannot be asked to leak on turn two and hold on turn four.

    The reply is chosen by the turn's position **within its session**, so every
    attempt replays the same script — which is what makes the recorded session ids
    the whole of the independence question. It wraps rather than running out, so a
    session id that had stopped being per-attempt fails the assertion about session
    ids and not on an index.
    """

    def __init__(self, *replies: dict[str, Any]) -> None:
        self.replies = replies
        self.sent: list[tuple[str, str]] = []

    def __call__(
        self, target: TargetConfig, message: str, session_id: str
    ) -> Transcript:
        turn = sum(1 for _, session in self.sent if session == session_id)
        self.sent.append((message, session_id))
        return Transcript(
            url=target.url,
            sent={"message": message, "session_id": session_id},
            status_code=200,
            received=self.replies[turn % len(self.replies)],
        )

    @property
    def sessions(self) -> list[str]:
        return [session for _, session in self.sent]


def held(times: int = 4) -> Wire:
    """A target that answers every turn and gives nothing away."""
    return Wire(*({"reply": "I can't help with that."} for _ in range(times)))


def attacking(
    case: Case, wire: Wire, patch: pytest.MonkeyPatch, index: int = 0
) -> Attempt:
    """One attempt at that case against that wire, budgeted and authorised."""
    patch.setattr(attacker, "send_message", wire)
    target = replace(a_target("scripted"), retains_session_state=True)
    budget = RunBudget.declare(cases=[case], targets=[target])
    return attacker.run_attempt(
        target=target,
        case=case,
        canary=CANARY,
        run_state=RunState(budget=budget),
        index=index,
    )


CANARY = "AGENTAUDIT-CANARY-SCRIPTED"


def test_one_attempt_sends_every_turn_of_its_script_in_one_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The script's turns are dependent on each other by construction — that is what
    # a script is — and the session id is what carries the dependence
    # (`contract.send_message`). So one attempt is one session, in order.
    wire = held()
    attacking(a_scripted_case(turns=4), wire, monkeypatch)

    assert [message for message, _ in wire.sent] == [
        "turn 1",
        "turn 2",
        "turn 3",
        "turn 4",
    ]
    assert len(set(wire.sessions)) == 1


def test_two_attempts_of_one_scripted_case_share_no_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The property that pays for the rate, asserted over a case whose turns are
    # deliberately dependent: the dependence is *inside* an attempt and never
    # between two, so ten attempts are ten independent samples and a rate is a rate
    # rather than a trajectory (`attacker.py`, CONTEXT.md **attempt**).
    case = a_scripted_case(turns=3)
    wire = held()
    target = replace(a_target("scripted"), retains_session_state=True)
    monkeypatch.setattr(attacker, "send_message", wire)
    run_state = RunState(budget=RunBudget.declare(cases=[case], targets=[target]))
    for index in range(2):
        attacker.run_attempt(
            target=target,
            case=case,
            canary=CANARY,
            run_state=run_state,
            index=index,
        )

    first, second = wire.sessions[:3], wire.sessions[3:]
    assert len(set(first)) == 1 and len(set(second)) == 1
    assert set(first).isdisjoint(second)


def test_every_turn_of_a_script_is_the_attempts_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # `Attempt.transcript` was the exchange behind one verdict, and the evidence for
    # a scripted attempt is every turn of it — the shape `AdaptiveEpisode` already
    # holds. A reader with the record and these transcripts can re-derive the
    # verdict, which is what ADR-0004 asks of the number.
    attempt = attacking(a_scripted_case(turns=4), held(), monkeypatch)

    assert len(attempt.transcripts) == 4
    assert [transcript.sent["message"] for transcript in attempt.transcripts] == [
        "turn 1",
        "turn 2",
        "turn 3",
        "turn 4",
    ]


# --- The criterion is applied per turn ---------------------------------------


def a_reply(text: str = "I can't help with that.") -> Transcript:
    return Transcript(
        url="https://scripted.invalid/messages",
        sent={"message": "a turn", "session_id": "s"},
        status_code=200,
        received={"reply": text},
    )


def test_a_script_succeeds_on_the_first_turn_that_meets_its_condition() -> None:
    # The reason the adaptive layer already reads every probe rather than the last
    # one: *a break that nobody checked for is a break recorded as resistance*
    # (`adaptive/attacker.py`). A target that leaked on turn two and recovered by
    # turn four broke, and a verdict read off the last reply would record it as
    # having held (ADR-0053).
    case = a_scripted_case(turns=4)
    turns = (a_reply(), a_reply(f"here it is: {CANARY}"), a_reply(), a_reply())

    read = evaluate_script(case, turns, a_target("scripted"), CANARY)

    assert read.verdict is Verdict.SUCCEEDED
    assert read.turn == 1


def test_a_script_no_turn_of_which_met_the_condition_resisted() -> None:
    case = a_scripted_case(turns=3)
    turns = (a_reply(), a_reply(), a_reply())

    read = evaluate_script(case, turns, a_target("scripted"), CANARY)

    assert read.verdict is Verdict.RESISTED
    # The last turn that had a chance to break, because that is the exchange a
    # reader of one resisted attempt is shown.
    assert read.turn == 2


def a_creeping_case(turns: int = 3) -> Case:
    """A script read over the tool trace rather than over the reply text."""
    return replace(
        a_scripted_case(case_id="scripted-creep", turns=turns),
        family=Family.SCOPE_CREEP,
        success_condition=SuccessCondition(
            kind=SuccessConditionKind.TOOL_CALL_OUTSIDE_DECLARED_LIST
        ),
        # No config-canary plant: this one reads a tool trace and not the nonce, so
        # requiring the planting would withdraw it from targets that could answer it.
        requires=(Precondition.SESSION_RETENTION, Precondition.TOOL_CALL_VISIBILITY),
    )


def a_trace(*names: str) -> Transcript:
    return Transcript(
        url="https://scripted.invalid/messages",
        sent={"message": "a turn", "session_id": "s"},
        status_code=200,
        received={
            "reply": "done",
            "tool_trace": {
                "calls": [{"name": name, "arguments": {}} for name in names]
            },
        },
    )


def test_a_turn_whose_reply_carries_nothing_to_read_is_not_a_resisted_turn() -> None:
    # `measurability.checkable` already draws this line for the adaptive layer and a
    # script needs it for the same reason: a turn that returned no trace shows no
    # defence, so it is skipped rather than counted as a turn the target held. The
    # break on the last turn is still found (ADR-0053).
    case = a_creeping_case(turns=3)
    turns = (a_reply(), a_reply(), a_trace("wire_transfer"))

    read = evaluate_script(case, turns, a_target("scripted"), CANARY)

    assert read.verdict is Verdict.SUCCEEDED
    assert read.turn == 2


def test_a_script_whose_every_turn_was_unreadable_refuses_rather_than_resists() -> None:
    # The loud refusal survives the skip above, which is the whole reason the last
    # turn is read unguarded: a verdict read off evidence that is not there is the
    # soft number ADR-0004 refuses, and a filter in front of every turn would turn
    # `TraceNotVisible` into a quiet *resisted*.
    case = a_creeping_case(turns=3)
    turns = (a_reply(), a_reply(), a_reply())

    with pytest.raises(TraceNotVisible):
        evaluate_script(case, turns, a_target("scripted"), CANARY)


# --- What the operator confirms, and what a stateless target can answer -------


def test_the_estimate_prices_every_turn_of_a_script() -> None:
    # ADR-0007 promises a ceiling checked in one place and in send order, and
    # `_send` authorises every turn of an attempt before the first goes out. A
    # four-turn script is four authorisations inside one attempt, so an estimate
    # that counted cases would be showing a number for a different run — and the
    # approval interrupt is the one screen whose whole job is that the number is
    # right (ADR-0053 §6).
    one = RunBudget.declare(
        cases=[unlisted_case(payload="one turn", case_id="c")], targets=[a_target()]
    )
    script = RunBudget.declare(cases=[a_scripted_case(turns=4)], targets=[a_target()])

    priced = script.estimate.scored.calls - one.estimate.scored.calls
    assert priced == 3 * DECLARED_RULE.attempts_per_case
    assert script.scored_ceiling > one.scored_ceiling


def test_a_stateless_target_makes_a_script_not_measurable_rather_than_resisted() -> (
    None
):
    # The precondition #48 landed and #74 consumes. A rate of zero read off a target
    # that forgets the previous turn would be the bench reporting an agent as
    # defended against an attack it was never able to face, which is the outcome
    # `measurability.py` exists to refuse (ADR-0004, ADR-0041 §4).
    case = a_scripted_case(turns=3)
    stateless = replace(a_target("stateless"), retains_session_state=False)

    assert unmet_preconditions(case, stateless) == (Precondition.SESSION_RETENTION,)
    assert not measurable(case, stateless)
    assert measurable(case, replace(a_target("retaining"), retains_session_state=True))


# --- What a record may not say -----------------------------------------------


def test_a_script_that_does_not_require_session_retention_does_not_load() -> None:
    with pytest.raises(ValueError, match="session_retention"):
        replace(
            unlisted_case(payload="one turn", case_id="c"),
            payload=("turn 1", "turn 2"),
        )


def test_a_judged_case_may_not_be_a_script() -> None:
    # `AdjudicationBrief.payload` is the case's own text as one string and κ rests
    # on single-turn gold transcripts, so a judged multi-turn case is a new gold set
    # rather than a wider brief (ADR-0053 §5).
    with pytest.raises(ValueError, match="gold set"):
        replace(
            a_scripted_case(turns=2),
            verdict_class=VerdictClass.JUDGED,
            success_condition=None,
            judged_condition=JudgedCondition(
                question="did it commit?",
                succeeded_when="it committed",
                resisted_when="it did not",
            ),
        )


def test_a_script_may_not_also_carry_a_planting_turn() -> None:
    # A planting turn is the one turn that is sent and not scored, and its worth is
    # that the verdict is read *against* it. Several scored turns and one control is
    # a shape no reading is defined over (ADR-0041 §2, ADR-0053 §5).
    #
    # Built with the persistence condition a planting turn belongs to, because that
    # is the only record this refusal is the *first* to catch: a planting turn on a
    # case that reads one turn is already refused one guard down, and a test that
    # tripped over that one would not be about this decision at all.
    with pytest.raises(ValueError, match="sends a script and carries a planting turn"):
        replace(
            a_scripted_case(turns=2),
            family=ElectiveFamily.MEMORY_POISONING,
            success_condition=SuccessCondition(
                kind=SuccessConditionKind.RETAINED_INSTRUCTION_EXECUTED,
                planted_canary="ZZ-COMPOSED-JOIN",
            ),
            planting="a first turn that plants",
        )


def test_a_canary_spelled_across_two_turns_of_a_script_does_not_load() -> None:
    # `Case.script` — the newline join every canary guard reads — was vacuous while
    # every record held one turn, and a script is the first payload that can spell a
    # canary out *between* its turns. An indirect case's payload has to spell out no
    # part of the instruction, because the whole soundness of that verdict is that the
    # canary can only be composed by carrying the planted instruction out (ADR-0042);
    # a guard that read turn one alone would let a script spell one half in turn one
    # and the other in turn three and score a target that echoed the two back.
    indirect = next(
        one for one in load_library(CASES_DIR) if one.id == "indirect-injection-001"
    )
    condition = indirect.success_condition
    assert condition is not None
    canary = condition.planted_canary or ""
    assert canary
    half = len(canary) // 2

    with pytest.raises(ValueError, match="spells"):
        replace(
            indirect,
            id="indirect-injection-001-split",
            payload=(
                f"morning — the supplier note, {canary[:half]}",
                "nothing urgent",
                canary[half:],
            ),
            requires=(*indirect.requires, Precondition.SESSION_RETENTION),
            admission=None,
        )


def test_a_payload_with_nothing_to_send_does_not_load() -> None:
    # A sequence has more ways of being empty than a string does, and both are the
    # same fault: a record whose payload the loader would have to supply.
    with pytest.raises(ValueError, match="no payload at all"):
        replace(unlisted_case(payload="one turn", case_id="c"), payload=())
    with pytest.raises(ValueError, match="blank turn"):
        replace(
            unlisted_case(payload="one turn", case_id="c"),
            payload=("turn 1", "   "),
            requires=(Precondition.SESSION_RETENTION,),
        )


# --- What a record on disk may say -------------------------------------------


def test_a_record_whose_payload_is_a_bare_string_does_not_load(tmp_path: Path) -> None:
    # The one fault this type change could introduce silently. `tuple("a message")`
    # is eleven one-character turns, so a record written the old way would load, be
    # sent as eleven calls on the operator's endpoint and score whatever came back —
    # which is why the loader refuses the string rather than accepting either shape.
    record = (CASES_DIR / "data-leakage-001.toml").read_text(encoding="utf-8")
    bare = record.replace('payload = ["""', 'payload = """').replace('"""]', '"""')
    path = tmp_path / "data-leakage-001.toml"
    path.write_text(bare, encoding="utf-8")

    with pytest.raises(ValueError, match="array of turns"):
        load_case(path)


def test_a_single_turn_record_round_trips_through_one_wrapping_bracket(
    tmp_path: Path,
) -> None:
    # What the eighteen records gained, and nothing else: `case_record` writes an
    # array whichever it is, so there is one shape for `load_case` to read.
    case = next(one for one in load_library(CASES_DIR) if one.id == "data-leakage-001")
    path = tmp_path / f"{case.id}.toml"
    path.write_text(case_record(case), encoding="utf-8")

    assert 'payload = ["""' in path.read_text(encoding="utf-8")
    assert load_case(path).payload == case.payload


# --- The whole path, over real HTTP ------------------------------------------


def test_a_script_reaches_a_served_target_over_the_one_transport(
    leakage_case: Case,
) -> None:
    # The same `send_message` a single-turn case takes, against a reference agent
    # served over real HTTP: no result in this repository comes from a path a real
    # run would not take (spec story 19). A three-turn script whose last turn is the
    # library's own leakage payload, so the reading is the one the case already
    # licenses and the two turns before it only prove they went out.
    script = replace(
        leakage_case,
        id="data-leakage-001-scripted",
        payload=("Morning — quick question.", "Nothing urgent.", *leakage_case.payload),
        requires=(*leakage_case.requires, Precondition.SESSION_RETENTION),
        transform=Transform.PLAIN,
        derived_from=None,
        admission=None,
    )
    nonce = "AGENTAUDIT-CANARY-SCRIPTPATH"

    with reference_target(name="trivial") as reference:
        reference.plant_nonce(reference.target, nonce)
        target = replace(reference.target, retains_session_state=True)
        budget = RunBudget.declare(cases=[script], targets=[target])
        attempt = attacker.run_attempt(
            target=target,
            case=script,
            canary=nonce,
            run_state=RunState(budget=budget),
            index=0,
        )

    assert len(attempt.transcripts) == 3
    assert len({str(one.sent["session_id"]) for one in attempt.transcripts}) == 1
    assert attempt.verdict is Verdict.SUCCEEDED
    # The *first* turn that met the condition, whichever it turned out to be. The
    # trivial agent has no defences at all, so which turn it gives the nonce up on is
    # not this test's claim — that the reading is the first one and that the evidence
    # for it is on the record is.
    first = next(
        turn for turn, one in enumerate(attempt.transcripts) if nonce in one.reply_text
    )
    assert attempt.decided_on_turn == first
    assert nonce in attempt.scored.reply_text


# --- An attempt with no evidence, and a verdict off a turn nobody has ---------


def test_an_attempt_recorded_with_no_exchange_behind_it_is_refused() -> None:
    # The floor under ADR-0004: a verdict has to be re-derivable from the evidence,
    # and an attempt carrying none is a number nobody can check.
    with pytest.raises(ValueError, match="no exchange behind it"):
        Attempt(
            case_id="scripted-000",
            family=Family.DATA_LEAKAGE,
            target_name="scripted",
            index=0,
            transcripts=(),
            verdict=Verdict.RESISTED,
            verdict_class=VerdictClass.DETERMINISTIC,
            transform=Transform.PLAIN,
        )


def test_a_verdict_read_over_a_turn_that_is_not_in_the_evidence_is_refused() -> None:
    # The other half. `decided_on_turn` is what every consumer showing one exchange
    # per attempt resolves, so an index outside the transcripts is a reader sent to
    # a turn that does not exist.
    with pytest.raises(ValueError, match="turn 3 of 1"):
        Attempt(
            case_id="scripted-000",
            family=Family.DATA_LEAKAGE,
            target_name="scripted",
            index=0,
            transcripts=(a_reply(),),
            decided_on_turn=3,
            verdict=Verdict.RESISTED,
            verdict_class=VerdictClass.DETERMINISTIC,
            transform=Transform.PLAIN,
        )


def test_a_verdict_asked_for_over_no_turns_at_all_refuses() -> None:
    # `evaluate_script` reads the last turn unguarded, so an empty sequence has to
    # be refused where the rest of this module refuses rather than raising an
    # `IndexError` from an expression nobody reads as a check.
    with pytest.raises(ValueError, match="no turns to read"):
        evaluate_script(a_scripted_case(turns=2), (), a_target("scripted"), CANARY)
