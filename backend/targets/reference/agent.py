"""What every reference agent is: a system prompt, a planted nonce, and a model.

The reference agents are test equipment and never reach a user (D7). They differ
from each other only in defensive architecture — that difference is the axis the
bench claims to measure, so it is the only thing that varies here.
"""

from dataclasses import dataclass

from backend.targets.reference.model import ModelConfig, complete

NO_NONCE = "(no registration nonce configured)"


@dataclass(frozen=True)
class ReferenceAgent:
    name: str
    system_prompt_template: str

    def system_prompt(self, nonce: str) -> str:
        return self.system_prompt_template.format(nonce=nonce or NO_NONCE)

    def reply(self, message: str, nonce: str, model: ModelConfig) -> str:
        return complete(model, self.system_prompt(nonce), message)
