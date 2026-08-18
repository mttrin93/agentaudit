"""The attacker's five tools. Each call is a decision the model makes.

| Tool | The decision |
|---|---|
| `run_probe` | what to send next, given what came back |
| `read_tool_trace` | whether it is worth a turn to inspect what the target called |
| `check_canary` | whether the objective is met yet |
| `retrieve_precedent` | what worked against similar targets, identity-stripped |
| `propose_case` | whether this route is worth promoting |

**`run_probe` shares `send_message` with the scored layer and nothing above it.**
Not `run_attempt`, not `run_case`, not `RunState.record`: a separate function, a
separate counter and a separate store, so that the spec's single code path from the
bench to any target survives at the transport level — where it was meant — without
an adaptive turn ever reaching a denominator (ADR-0010). It is the whole of the
adaptive layer's transport, and it is four lines, so there is nowhere for a second
route to hide.

**`check_canary` wraps the evaluator and returns its answer unchanged.** The
attacker chooses *when* to look and never *what it sees*, which is how ADR-0004
holds inside the adaptive layer rather than merely around it. There is deliberately
no argument through which a caller could offer a different criterion: the objective
is the case record the episode was opened against, and the verdict comes back
untouched.

**`retrieve_precedent` strips identity at the point of return**, against the run's
blinding rather than against the store's good manners. Long-term memory is the
channel ADR-0011 names as the one that would otherwise un-blind an instrument every
other channel was closed against.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from backend.bench.adaptive.blinding import Blinding
from backend.bench.adaptive.episode import AttackerTool
from backend.bench.adaptive.precedent import Precedent, PrecedentStore
from backend.bench.contract import TargetConfig, Transcript, send_message
from backend.bench.evaluator import Verdict, evaluate
from backend.bench.library import Case, Family
from backend.graph.budget import Layer
from backend.graph.runstate import RunState

_TOOL_LINE = re.compile(r"^[ \t]*tool[ \t]*:[ \t]*([a-z_]+)[ \t]*$", re.MULTILINE)
_ARGUMENT_LINE = re.compile(r"^[ \t]*argument[ \t]*:[ \t]*(.*)\Z", re.MULTILINE | re.S)

NO_PROBE_YET = (
    "nothing has been sent to the target yet, so there is nothing to read. "
    "Send a probe first"
)
"""What the two tools that read the last turn answer before there is one.

A stated answer rather than a fabricated one: `check_canary` in particular must
never invent a verdict for a turn that did not happen, because the value it returns
is the one thing in the episode the attacker is not allowed to influence.
"""


@dataclass(frozen=True)
class ToolInvocation:
    """One tool call, as the model wrote it."""

    tool: AttackerTool
    argument: str = ""


def parse_invocation(answer: str) -> ToolInvocation | None:
    """Read a tool call out of the model's answer, or `None` if it made none.

    `None` rather than a default tool. An answer nobody can read is the model
    failing to decide, and quietly turning that into a probe would put a payload
    on the wire that no decision chose — which is the one thing separating this
    layer from a fuzzer.
    """
    named = _TOOL_LINE.search(answer)
    if named is None:
        return None
    try:
        tool = AttackerTool(named.group(1))
    except ValueError:
        return None
    argued = _ARGUMENT_LINE.search(answer)
    return ToolInvocation(tool=tool, argument=argued.group(1).strip() if argued else "")


def run_probe(
    target: TargetConfig, probe: str, run_state: RunState, session_id: str
) -> Transcript:
    """Send one attacker-composed message and record what it cost.

    Authorised against the adaptive ceiling before it goes on the wire and counted
    against the adaptive counter after, on the same terms as a scored attempt and
    against a different limit (ADR-0007). It records no `Attempt` and touches no
    position: an adaptive turn is not a unit of anything the bench divides by.
    """
    run_state.authorise_call(Layer.ADAPTIVE, target.retry.sends)
    transcript = send_message(target, probe, session_id=session_id)
    run_state.record_call(Layer.ADAPTIVE, transcript.sends)
    return transcript


def read_tool_trace(transcript: Transcript | None) -> str:
    """What the target did on the last turn, in the order it did it."""
    if transcript is None:
        return NO_PROBE_YET
    trace = transcript.tool_trace
    if trace is None:
        return (
            "this target returns no tool trace, so what it did on that turn "
            "cannot be read"
        )
    return trace.rendered()


def check_canary(
    objective: Case, transcript: Transcript, target: TargetConfig, canary: str
) -> Verdict:
    """Whether the objective is met, as the evaluator decides it.

    A pass-through with a signature and no body of its own, and that is the point:
    the verdict the attacker sees is `evaluate`'s, reached from the recorded case's
    success condition over the recorded transcript, and there is no branch here
    that could reach a different one.
    """
    return evaluate(objective, transcript, target, canary)


def retrieve_precedent(
    store: PrecedentStore, family: Family, blinding: Blinding
) -> str:
    """What has worked on this failure before, with every target identity removed."""
    routes: Sequence[Precedent] = store.for_family(family)
    if not routes:
        return f"no precedent recorded against {family} yet"
    return "\n".join(f"  - {blinding.redact(route.route)}" for route in routes)
