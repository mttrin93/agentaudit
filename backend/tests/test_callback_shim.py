"""A user's function, served over the one contract, and reached the way everything is.

The seams these tests sit at are the two the shim has, and no third:

* `serve_callback`, which yields a `TargetConfig` — a description of an endpoint,
  indistinguishable in kind from the description of a user's staging URL.
* `send_message` and `run_calibration`, the paths the bench already takes to a
  target. Nothing here calls a callback directly, because nothing in the bench can.

The last two tests in the file are the ones that fail if a second path in is ever
added: one reads `contract.py`, and one sends to a target whose server has exited.
"""

from __future__ import annotations

import inspect
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path

import httpx
import pytest

from backend.bench import contract
from backend.bench.calibration import CalibrationResult, run_calibration
from backend.bench.contract import (
    TargetConfig,
    TargetFailure,
    TargetUnreachable,
    ToolCall,
    ToolTrace,
    send_message,
)
from backend.bench.library import Case, DiscoveredBy, Family
from backend.bench.registration import ECHO_PROBE
from backend.bench.rule import DECLARED_RULE
from backend.bench.shim import (
    CALLBACK_FAILED_STATUS,
    CALLBACK_RAISED,
    TextCallback,
    Turn,
    exposes_tool_calls_of,
    serve_callback,
)
from backend.tests.conftest import BENCH_ATTESTATION, CONFIRMING

IMPATIENT = contract.RetryPolicy(sends=3, backoff_seconds=0.0)
"""The declared retry policy with the waiting taken out, so a suite stays quick."""


def test_a_callback_is_reached_over_http_on_loopback() -> None:
    seen: list[tuple[str, str]] = []

    def echo(message: str, session_id: str) -> str:
        seen.append((message, session_id))
        return f"you said {message}"

    with serve_callback(echo, name="echo") as target:
        assert target.url.startswith("http://127.0.0.1:")
        transcript = send_message(target, "hello", session_id="s-1")

    assert transcript.reply_text == "you said hello"
    assert seen == [("hello", "s-1")]
    assert transcript.sends == 1
    assert transcript.url == target.url


def test_a_shim_target_carries_a_token_it_did_not_get_from_its_caller() -> None:
    with serve_callback(lambda message, session_id: "fine", name="tokened") as target:
        assert len(target.auth_token) >= 32
        wrong = replace(target, auth_token="not-the-token", retry=IMPATIENT)
        with pytest.raises(TargetUnreachable) as raised:
            send_message(wrong, "hello", session_id="s-1")

    assert raised.value.failure is TargetFailure.AUTH_REJECTED
    # The token is the shim's, not its caller's: there is no parameter for one.
    assert "auth_token" not in inspect.signature(serve_callback).parameters


def test_a_bare_string_reply_carries_no_tool_trace_key() -> None:
    with serve_callback(lambda message, session_id: "text only", name="blind") as t:
        transcript = send_message(t, "hello", session_id="s-1")

    # Absent, not null and not empty: an endpoint with no visibility says so by
    # having nothing to say, and an empty trace is a different answer.
    assert "tool_trace" not in transcript.received
    assert transcript.tool_trace is None
    assert t.exposes_tool_calls is False


def test_a_turn_carries_the_trace_the_callback_built() -> None:
    def acting(message: str, session_id: str) -> Turn:
        return Turn(
            reply="done",
            tool_trace=ToolTrace(
                calls=(ToolCall(name="send_email", arguments={"to": "ops@x"}),),
                stop_signal_at=0,
            ),
        )

    with serve_callback(acting, name="acting") as target:
        transcript = send_message(target, "hello", session_id="s-1")

    assert target.exposes_tool_calls is True
    trace = transcript.tool_trace
    assert trace is not None
    assert trace.calls == (ToolCall(name="send_email", arguments={"to": "ops@x"}),)
    assert trace.stop_signal_at == 0


def test_an_empty_trace_survives_the_wire_as_an_empty_trace() -> None:
    def idle(message: str, session_id: str) -> Turn:
        return Turn(reply="I did nothing", tool_trace=ToolTrace())

    with serve_callback(idle, name="idle") as target:
        transcript = send_message(target, "hello", session_id="s-1")

    assert transcript.tool_trace == ToolTrace()
    assert transcript.tool_trace is not None


# --- A raise is transport, and it is named ------------------------------------


def test_a_callback_that_raises_twice_costs_sends_and_not_attempts(
    leakage_case: Case,
) -> None:
    """The retries a raising callback costs are sends against one attempt."""
    failures = IMPATIENT.sends - 1
    state = PlantedState()

    def flaky(message: str, session_id: str) -> str:
        if state.failed < failures:
            state.failed += 1
            raise RuntimeError("the callback fell over")
        state.failed = 0
        # What the hook was planted with, and nothing else. A served target's
        # configuration canary has one provenance — the bench issues it and plants it
        # through the hook — so a callback that answered from anywhere else would be
        # answering with a value no plant put there (ADR-0064 §1).
        return agent.planted or ""

    # Wrapped so the target declares the config-canary planting hook, which is what
    # data leakage now requires of a served target: a callback with no hook has that
    # family withdrawn as `NotMeasurable` and there would be no rate below to read
    # (ADR-0061). The object is handed to the run as its planter, so the bench plants
    # through the hook before it registers (ADR-0062), and no `plant_nonce` stands
    # beside it: a second hand planting the same value is a read-back that checks the
    # other hand's work (ADR-0064 §1).
    agent = PlantsItsConfig(flaky)
    with serve_callback(agent, name="flaky", retry=IMPATIENT) as target:
        result = _calibrate(target, leakage_case, state, planter=agent)

    [target_run] = result.target_runs
    # The planting happened, off every counter: the hook was called with the run's
    # own nonce, and the sends below are the attempts and the probe alone.
    assert agent.planted == target_run.registration.nonce
    assert target_run.registration.complete
    rate = target_run.rates[Family(leakage_case.family)]
    assert rate.attempts == DECLARED_RULE.attempts_per_case
    assert {a.scored.sends for a in target_run.attempts} == {failures + 1}


def test_a_callback_that_always_raises_stops_the_run_under_a_named_failure(
    leakage_case: Case,
) -> None:
    state = PlantedState()
    seen: list[str] = []

    def broken(message: str, session_id: str) -> str:
        seen.append(message)
        raise RuntimeError("the callback fell over")

    with serve_callback(broken, name="broken", retry=IMPATIENT) as target:
        with pytest.raises(TargetUnreachable) as raised:
            _calibrate(target, leakage_case, state)

    assert raised.value.failure is TargetFailure.UNAVAILABLE
    assert raised.value.sends == IMPATIENT.sends
    assert contract.NOT_A_SECURITY_RESULT in str(raised.value)

    # And zero attempts recorded — proved from the callback's own side, since a run
    # that raised returns no result to count. An attempt is one execution of one
    # case, so a run with none is a run where no case payload ever went out: what
    # this callback saw was the registration echo probe, three times, and nothing
    # else. The `sends` above and this list are the same three sends.
    assert seen == [ECHO_PROBE] * IMPATIENT.sends
    assert not any(turn in message for message in seen for turn in leakage_case.payload)


def test_the_reply_to_a_raise_says_nothing_about_what_raised() -> None:
    """The body is read off the wire and not off the exception.

    `TargetUnreachable` never carries a response body, so asserting against the
    exception would pass whatever the endpoint said. This posts the contract's own
    request and reads what came back.
    """

    def broken(message: str, session_id: str) -> str:
        raise RuntimeError("token sk-hunter2 in /home/someone/secrets.py")

    with serve_callback(broken, name="broken", retry=IMPATIENT) as target:
        response = httpx.post(
            target.url,
            json={"message": "hello", "session_id": "s-1"},
            headers={"Authorization": f"Bearer {target.auth_token}"},
        )

    assert response.status_code == CALLBACK_FAILED_STATUS
    body = response.text
    assert CALLBACK_RAISED in body
    assert "hunter2" not in body
    assert "secrets.py" not in body
    assert "Traceback" not in body


# --- The derivation is a fact, because the app enforces it --------------------


def test_a_turn_callback_that_answers_in_text_is_a_transport_failure() -> None:
    """The mechanism that makes `TRACE_DECLARED_BUT_ABSENT` unreachable here.

    A shim target that declares visibility must never emit a traceless reply. If it
    could, this surface would have the same contradiction every deployed endpoint
    can have, and ADR-0059 §4's claim would be a hope.
    """

    def lying(message: str, session_id: str) -> Turn:
        return "no trace after all"  # type: ignore[return-value]

    with serve_callback(lying, name="lying", retry=IMPATIENT) as target:
        assert target.exposes_tool_calls is True
        with pytest.raises(TargetUnreachable) as raised:
            send_message(target, "hello", session_id="s-1")

    assert raised.value.failure is TargetFailure.UNAVAILABLE


def test_a_trace_from_a_target_registered_blind_is_dropped_and_not_refused() -> None:
    """The mirror direction, and deliberately not a run-ending failure.

    The two families that read a trace were withdrawn before anything was sent, so
    there is nobody to read this one. Dropping it measures nothing the registration
    did not allow; refusing it would end a run over evidence nobody wanted.
    """

    def unannotated(message: str, session_id: str):  # type: ignore[no-untyped-def]
        return Turn(reply="quietly acted", tool_trace=ToolTrace())

    with serve_callback(unannotated, name="unannotated") as target:
        assert target.exposes_tool_calls is False
        transcript = send_message(target, "hello", session_id="s-1")

    assert transcript.reply_text == "quietly acted"
    assert "tool_trace" not in transcript.received


def test_a_callable_object_is_a_callback_and_its_annotation_is_read_too() -> None:
    """The docstring on `Callback` claims a callable object satisfies it.

    The derivation reads `type(callback).__call__` for anything that is not a plain
    function or a bound method, so the claim and the derivation have to agree — an
    agent held as an object with configuration on it is the shape a real user's
    agent most often has.
    """

    class Agent:
        def __init__(self) -> None:
            self.asked = 0

        def __call__(self, message: str, session_id: str) -> Turn:
            self.asked += 1
            return Turn(reply="object", tool_trace=ToolTrace())

    agent = Agent()
    with serve_callback(agent, name="object") as target:
        assert target.exposes_tool_calls is True
        transcript = send_message(target, "hello", session_id="s-1")

    assert transcript.reply_text == "object"
    assert transcript.tool_trace == ToolTrace()
    assert agent.asked == 1


def test_an_annotation_the_bench_cannot_resolve_reads_as_no_visibility() -> None:
    """Unreadable is not visibility — the conservative direction, and reachable.

    A callback whose return annotation names a type that cannot be resolved from its
    own module. `get_type_hints` raises on it, and the answer is the default rather
    than a guess.
    """

    def unresolvable(message: str, session_id: str) -> str:
        return "fine"

    unresolvable.__annotations__["return"] = "NoSuchTypeAnywhere"
    assert exposes_tool_calls_of(unresolvable) is False


def test_a_callback_that_might_return_either_shape_is_refused_by_the_typechecker(
    tmp_path: Path,
) -> None:
    """`-> str | Turn` satisfies neither protocol, and that is the point.

    The union is what the derivation reads, so a callback that could answer either
    way would be declaring a visibility it has only sometimes — and the failure
    would arrive a turn later, as a transport failure, rather than at the call site.
    Two protocols instead of one union return type is what moves it to the call
    site, and `mypy` is where that is observable at all.
    """
    module = tmp_path / "either.py"
    module.write_text(
        "from backend.bench.shim import Turn, serve_callback\n"
        "\n"
        "def either(message: str, session_id: str) -> str | Turn:\n"
        "    return 'text'\n"
        "\n"
        "with serve_callback(either) as target:\n"
        "    pass\n"
    )
    checked = subprocess.run(
        [sys.executable, "-m", "mypy", "--no-incremental", str(module)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    assert checked.returncode != 0, checked.stdout
    assert "serve_callback" in checked.stdout


# --- There is still no in-process branch --------------------------------------


def test_the_contract_knows_nothing_about_a_callback() -> None:
    """The property the module docstring of `contract.py` is built on.

    Source-level, on `test_transport.py`'s reasoning: the regression is reachable
    by a name rather than by an argument. Design B of #82 — a `callback` field on
    `TargetConfig` and a dispatch inside `send_message` — would pass every other
    test in this file and would leave the retry policy, the named failures and the
    declared wait untested on the path a user's callback run takes.
    """
    source = Path(contract.__file__).read_text()
    assert "shim" not in source
    assert "callback" not in source.lower()

    # And nowhere for one to sit: every field of a target's description is data.
    for name, field_type in TargetConfig.__annotations__.items():
        assert "Callable" not in str(field_type), name
        assert "Protocol" not in str(field_type), name


def test_a_shim_target_is_unreachable_once_its_server_is_gone() -> None:
    """The behavioural half of the same property, and the discriminating one.

    A target whose server has exited answers nothing. Under design B — a `callback`
    field and a dispatch inside `send_message` — the second send below would still
    get a reply, because the branch does not need the port. This is the test that
    tells the two designs apart at runtime rather than by reading the source.
    """
    requests: list[str] = []

    def counting(message: str, session_id: str) -> str:
        requests.append(session_id)
        return "fine"

    with serve_callback(counting, name="counted", retry=IMPATIENT) as target:
        assert send_message(target, "hello", session_id="s-0").reply_text == "fine"

    with pytest.raises(TargetUnreachable) as raised:
        send_message(target, "hello", session_id="s-1")

    assert raised.value.failure is TargetFailure.UNREACHABLE
    assert requests == ["s-0"]


class PlantsItsConfig:
    """A text callback that also says it can be given a value in its configuration.

    The shape a user's agent has when it is a class rather than a function, and the
    only way a served target declares `Plant.CONFIG_CANARY`: `declared_plants` reads
    the hook off the object, so a plain function declares none
    (ADR-0061). It stands in front of a function here rather than being written as
    one, because a plain function cannot carry a method.
    """

    def __init__(self, answer: TextCallback) -> None:
        self._answer = answer
        self.planted: str | None = None
        self.namespace: str | None = None
        self.dropped: str | None = None

    def __call__(self, message: str, session_id: str) -> str:
        return self._answer(message, session_id)

    def plant_config_canary(self, namespace: str, canary: str) -> None:
        self.planted = canary
        self.namespace = namespace

    def teardown(self, namespace: str) -> None:
        self.dropped = namespace


@dataclass
class PlantedState:
    """What the operator's hand put where the callback can read it.

    Test equipment and deliberately not a shim feature: planting through the shim
    is #85 and #87, and this stands in for the human who edits their own target's
    configuration when the bench issues a nonce.
    """

    nonce: str = ""
    failed: int = 0
    """How many times the callback has already fallen over on the message in hand."""


def _calibrate(
    target: TargetConfig,
    case: Case,
    state: PlantedState,
    planter: object | None = None,
) -> CalibrationResult:
    def plant(planted_target: TargetConfig, nonce: str, namespace: str) -> None:
        state.nonce = nonce

    return run_calibration(
        cases=[case],
        targets=[target],
        attestation=BENCH_ATTESTATION,
        # The operator's hand, and only for the callback that has no hook of its own.
        # A target that plants its own configuration canary is refused one, because
        # the bench reads that value back out of the target and a value a second hand
        # also planted is a read-back checking somebody else's plant
        # ([ADR-0064](../../docs/adr/0064-the-harness-reads-its-own-canary-back.md)
        # §1).
        plant_nonce=None if planter is not None else plant,
        planters={} if planter is None else {target.name: planter},
        approve=CONFIRMING,
        discovered_by=DiscoveredBy.ADAPTIVE,
    )
