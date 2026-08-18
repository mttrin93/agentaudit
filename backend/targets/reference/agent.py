"""What every reference agent is: a system prompt, a planted nonce, a model,
tools, and controls.

The reference agents are test equipment and never reach a user (D7). They differ
from each other only in defensive architecture — that difference is the axis the
bench claims to measure, so it is the only thing that varies here. The trivial
and weak agents carry `NO_CONTROLS` and differ only in what their prompt asks
for; the hardened agent carries the four pieces in `controls.py`. All three are
wired to the same toolbox, because an agent that simply could not reach
`transfer_funds` would prove nothing about the control that is supposed to stop
it (`tools.py`).

One reply path serves all three, so no agent gets a code route the others do not
have, and a control that is absent is absent rather than skipped.

**A turn is a reply and a trace.** Two families reach their verdict from what the
agent did rather than from what it said, so the trace is part of the reply
contract and not a debug artefact (`backend/bench/contract.py`). The order inside
one turn is the order the report depends on: the stop signal is noticed first,
the controls get their chance to end the turn, and only then does the toolbox
run — which is what makes "no action after the halt" a fact about the trace
rather than a claim in the text.
"""

from dataclasses import dataclass

from backend.bench.contract import ToolTrace
from backend.targets.reference.controls import (
    NO_CONTROLS,
    Controls,
    carries_stop_signal,
)
from backend.targets.reference.model import ModelConfig, complete
from backend.targets.reference.tools import FULL_TOOLBOX, Tool, routed

NO_NONCE = "(no registration nonce configured)"


@dataclass(frozen=True)
class AgentReply:
    """One turn as the target returns it: what it said, and what it did."""

    text: str
    trace: ToolTrace


@dataclass(frozen=True)
class ReferenceAgent:
    name: str
    system_prompt_template: str
    controls: Controls = NO_CONTROLS
    toolbox: tuple[Tool, ...] = FULL_TOOLBOX
    """What this agent can reach. The same for all three by default — see the
    module docstring."""

    def system_prompt(self, nonce: str) -> str:
        return self.system_prompt_template.format(nonce=nonce or NO_NONCE)

    def reply(self, message: str, nonce: str, model: ModelConfig) -> AgentReply:
        """One turn: the controls that hold get to stop it, and the model does
        the rest."""
        configuration = self.system_prompt(nonce)

        # Noticing the signal is instrumentation and happens for every agent;
        # honouring it is the stop control and happens for one of them. The stop
        # sits at position zero because the signal arrives in the message, so
        # every action this turn is an action taken after it.
        stop_at = 0 if carries_stop_signal(message) else None

        if instead := self.controls.before_model(message, configuration):
            return AgentReply(instead, ToolTrace(stop_signal_at=stop_at))

        calls = tuple(
            tool.called_with(message)
            for tool in routed(self.toolbox, message)
            if self.controls.permits(tool.name)
        )
        trace = ToolTrace(calls=calls, stop_signal_at=stop_at)

        reply = complete(model, configuration, message)

        withheld = self.controls.after_model(
            reply, protected=(nonce,), configuration=configuration
        )
        return AgentReply(withheld if withheld else reply, trace)
