"""What every reference agent is: a system prompt, a planted nonce, a model, and controls.

The reference agents are test equipment and never reach a user (D7). They differ
from each other only in defensive architecture — that difference is the axis the
bench claims to measure, so it is the only thing that varies here. The trivial
and weak agents carry `NO_CONTROLS` and differ only in what their prompt asks
for; the hardened agent carries the four pieces in `controls.py`.

One reply path serves all three, so no agent gets a code route the others do not
have, and a control that is absent is absent rather than skipped.
"""

from dataclasses import dataclass

from backend.targets.reference.controls import (
    NO_CONTROLS,
    Controls,
    is_registration_check,
)
from backend.targets.reference.model import ModelConfig, complete

NO_NONCE = "(no registration nonce configured)"


@dataclass(frozen=True)
class ReferenceAgent:
    name: str
    system_prompt_template: str
    controls: Controls = NO_CONTROLS

    def system_prompt(self, nonce: str) -> str:
        return self.system_prompt_template.format(nonce=nonce or NO_NONCE)

    def reply(self, message: str, nonce: str, model: ModelConfig) -> str:
        """One turn: the controls that hold get to stop it, and the model does the rest."""
        controls = self.controls
        configuration = self.system_prompt(nonce)

        # First, and before the registration path: a stop control that can be
        # reached only by getting past the other checks is not a stop control.
        if controls.stop_control is not None:
            if halt := controls.stop_control.stops(message):
                return halt

        # The one exemption, and it is a named piece rather than a condition
        # hidden here. An agent that refuses the echo probe never registers, and
        # an agent that never registers cannot be measured.
        if controls.registration_echo is not None and is_registration_check(message):
            return controls.registration_echo.answer(configuration)

        if controls.input_check is not None:
            if refusal := controls.input_check.stops(message):
                return refusal

        if controls.scope_limit is not None:
            if refusal := controls.scope_limit.stops(message):
                return refusal

        reply = complete(model, configuration, message)

        if controls.output_filter is not None:
            withheld = controls.output_filter.stops(
                reply, protected=(nonce,), configuration=configuration
            )
            if withheld:
                return withheld

        return reply
