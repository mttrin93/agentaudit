"""The weak reference agent: a system prompt that asks, and no code that enforces.

The middle of the three, and the one that decides whether the bench is measuring
anything interesting. Trivial against hardened is a difference anyone could
detect; a prompt-only agent against a controlled one is the difference a real
engineering decision makes, which is what a user is buying an answer about.

Its instructions are written the way a careful team writes them — the defence is
stated, and stated clearly. What it lacks is any code that could hold the line
when the model does not, which is exactly the gap the hardened agent fills with
`controls.py`. Nothing here inspects a message or a reply.

It shares its prompt with the hardened agent rather than paraphrasing it, so that
the gap between the two is engineering and not wording (`prompt.py`).
"""

from backend.targets.reference.agent import ReferenceAgent
from backend.targets.reference.prompt import DOCUMENT_ASSISTANT_PROMPT

WEAK = ReferenceAgent(name="weak", system_prompt_template=DOCUMENT_ASSISTANT_PROMPT)
