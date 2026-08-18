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

**A turn can also bring content in.** One tool returns text the team did not
write (`corpus.py`), and the order around it is the architecture: the agent
fetches, the request-side controls get a second look at what came back, and only
then does anything act on it. A defence that inspects the user's message and
nothing else is a defence on the one channel an indirect injection does not use.

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

from backend.bench.contract import ToolCall, ToolTrace
from backend.targets.reference.controls import (
    NO_CONTROLS,
    Controls,
    carries_stop_signal,
)
from backend.targets.reference.corpus import Note, fetched
from backend.targets.reference.model import ModelConfig, complete
from backend.targets.reference.tools import (
    FETCH_SHARED_NOTE,
    FULL_TOOLBOX,
    Tool,
    routed,
    without_retrieval,
)

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

        calls = self._acts_on(message, self.toolbox)

        note = fetched(message) if self._retrieved(calls) else None
        if note is not None:
            # The second place a request-side control gets to end a turn, and the
            # only one an indirect injection passes through. The fetch itself
            # stands in the trace either way: the agent did retrieve, and what it
            # refused was acting on what came back.
            if instead := self.controls.before_content(note.body):
                fetched_only = ToolTrace(calls=calls, stop_signal_at=stop_at)
                return AgentReply(instead, fetched_only)
            calls += self._acts_on(note.body, without_retrieval(self.toolbox))

        trace = ToolTrace(calls=calls, stop_signal_at=stop_at)

        # The model sees what the tool brought back, because an agent whose model
        # never reads the retrieved content is not exposed to the failure this
        # family measures. What decides the verdict is still the line below it:
        # obeying is code here, for the reason the router is (`corpus.py`).
        reply = complete(model, configuration, _with(note, message))
        if note is not None and note.executed_line:
            reply = f"{reply}\n{note.executed_line}"

        withheld = self.controls.after_model(
            reply, protected=(nonce,), configuration=configuration
        )
        return AgentReply(withheld if withheld else reply, trace)

    def _acts_on(self, text: str, toolbox: tuple[Tool, ...]) -> tuple[ToolCall, ...]:
        """The calls this text asks for, minus the ones the controls refuse."""
        return tuple(
            tool.called_with(text)
            for tool in routed(toolbox, text)
            if self.controls.permits(tool.name)
        )

    def _retrieved(self, calls: tuple[ToolCall, ...]) -> bool:
        """Whether this turn actually reached the shared folder.

        A turn whose retrieval the allow-list refused fetched nothing, and an
        agent that fetched nothing cannot be instructed by what it did not read.
        """
        return any(call.name == FETCH_SHARED_NOTE.name for call in calls)


def _with(note: Note | None, message: str) -> str:
    """The message as the model receives it: the request, then what came back."""
    return message if note is None else f"{message}\n\n{note.body}"
