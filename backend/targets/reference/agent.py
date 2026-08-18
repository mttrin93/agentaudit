"""What every reference agent is: a system prompt, a planted nonce, a model,
and controls.

The reference agents are test equipment and never reach a user (D7). They differ
from each other only in defensive architecture — that difference is the axis the
bench claims to measure, so it is the only thing that varies here. The trivial
and weak agents carry `NO_CONTROLS` and differ only in what their prompt asks
for; the hardened agent carries the four pieces in `controls.py`.

One reply path serves all three, so no agent gets a code route the others do not
have, and a control that is absent is absent rather than skipped.
"""

from dataclasses import dataclass

from backend.targets.reference.controls import NO_CONTROLS, Controls
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
        """One turn: the controls that hold get to stop it, and the model does
        the rest."""
        configuration = self.system_prompt(nonce)

        if instead := self.controls.before_model(message, configuration):
            return instead

        reply = complete(model, configuration, message)

        withheld = self.controls.after_model(
            reply, protected=(nonce,), configuration=configuration
        )
        return withheld if withheld else reply
