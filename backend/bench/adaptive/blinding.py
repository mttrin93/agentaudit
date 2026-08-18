"""What the attacker is not allowed to know about the target in front of it.

ADR-0011 delivers **label-blindness and context isolation**, and says plainly that
it cannot deliver blindness. The attacker interacts live, and the hardened agent's
replies *are* different — it refuses in its own words and its output filter leaves
a shape. Inferring *this one has an input check* within three turns is the attacker
doing its job, and `read_tool_trace` exists to make that inference better. What is
delivered instead is that no **label** reaches it: no target name, no url, and no
occurrence of `hardened`, `weak` or `trivial` anywhere in a prompt or a tool
result. The residual is stated in the report rather than claimed away, and the
falsification test for the whole claim is a negative `A_break` (#17).

**Handles are opaque and reassigned each run.** A stable mapping would be a label
by another name after the second gate run — anyone reading two runs could line the
handles up. So the pool is shuffled per run, and the handle a target wears in one
run says nothing about the one it wore in the last.

**Redaction is applied to everything that leaves the harness**, not only to the
prompt. Tool results carry the target's own words back, and a target that names
itself in a reply would un-blind the attacker through a channel the prompt never
touched — which is exactly how the judge's blinding would have failed had
precedent reached it (ADR-0004).
"""

from __future__ import annotations

import random
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from backend.bench.contract import TargetConfig

FORBIDDEN_LABELS = ("hardened", "weak", "trivial")
"""The three words that name a reference agent's construction.

Listed rather than derived from `REFERENCE_AGENTS`, because this module must not
import the agents it is blinding the attacker to: the bench attacks a user's
target through the same code, and a redaction rule that only knew about test
equipment would be a rule that stopped working the day it mattered.
"""

REDACTED = "[redacted]"
"""What a label becomes. Visible rather than deleted, so a reader of a recorded
episode can see that something was withheld instead of reading a sentence with a
hole in it."""


@dataclass(frozen=True)
class Blinding:
    """The per-run mapping from a target to the handle the attacker sees.

    Holds the mapping and the redaction together because they are one guarantee:
    a handle assigned but not enforced over tool results is a label with an extra
    step in front of it.
    """

    handles: Mapping[str, str]
    """Target name → the opaque handle it wears for this run."""

    identities: tuple[tuple[str, str], ...]
    """Every string that names a target, with the handle that replaces it.

    Longest first, so that a url is replaced before the target name inside it and
    no fragment of an endpoint survives as a clue.
    """

    @classmethod
    def over(
        cls, targets: Sequence[TargetConfig], rng: random.Random | None = None
    ) -> Blinding:
        """Assign a fresh handle to each target, in an order nobody can predict."""
        draw = rng if rng is not None else random.Random()
        pool = [f"subject-{index + 1}" for index in range(len(targets))]
        draw.shuffle(pool)
        handles = {
            target.name: handle for target, handle in zip(targets, pool, strict=True)
        }
        identities = sorted(
            (
                (naming, handles[target.name])
                for target in targets
                for naming in (target.url, target.name)
                if naming
            ),
            key=lambda pair: len(pair[0]),
            reverse=True,
        )
        return cls(handles=handles, identities=tuple(identities))

    def handle_for(self, target: TargetConfig) -> str:
        """The handle this target wears. Never its name, and never its position."""
        return self.handles[target.name]

    def redact(self, text: str) -> str:
        """The text as the attacker may see it.

        Names and urls become handles, so the attacker can still refer to what it
        is attacking; the three construction labels become `[redacted]`, because
        there is no blinded thing for them to become. Case-insensitive, because a
        target that capitalises its own name in a reply has still named itself.
        """
        for naming, handle in self.identities:
            text = re.sub(re.escape(naming), handle, text, flags=re.IGNORECASE)
        for label in FORBIDDEN_LABELS:
            text = re.sub(rf"\b{label}\b", REDACTED, text, flags=re.IGNORECASE)
        return text
