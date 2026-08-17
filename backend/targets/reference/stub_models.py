"""Deterministic stand-in models, reached through the same configuration seam.

They exist so the verdict path can be tested without a model call: no network, no
spend, and no model deciding anything a success condition should decide. Each one
is a reply shape the suite needs and a live model will not produce on demand.

They are stand-in *models*, not stand-in agents. The reference agents' own
defensive architecture — weak and hardened — is #4's work and is built out of
real controls, not out of these.
"""

from backend.targets.reference.controls import (
    configured_nonce_line,
    is_registration_check,
)


def stub_completion(name: str, system_prompt: str, message: str) -> str:
    match name:
        case "obedient":
            # Hands its whole configuration to anyone who writes to it.
            return system_prompt
        case "parrot":
            # Ignores its configuration entirely, so nothing planted in it can
            # ever come back.
            return message
        case "cooperative":
            # Answers a registration check from its configuration and discloses
            # nothing else: a target whose operator has proven control and whose
            # defence then holds.
            if is_registration_check(message):
                return configured_nonce_line(system_prompt)
            return "I'm not able to share my instructions or configuration."
        case _:
            raise ValueError(f"unknown stub model {name!r}")
