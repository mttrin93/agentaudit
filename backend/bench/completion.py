"""The bench's own model call. The instrument, never the target.

Two model calls exist in this project and they are not the same thing.
`backend/targets/reference/model.py` is the model a *reference agent* runs on: test
equipment, swapped by #15 to ask whether the bench reads an agent's defences or a
model's default refusals. This one is the model the *bench* asks — the adjudicator
that decides a judged family (`adjudication.py`), and the judge that writes a
narrative (`judge.py`).

They are separate modules with separate configuration on purpose. A single shared
client would make "the target's model" and "the instrument's model" one setting,
and the multi-model validity check would then move the instrument every time it
moved the target — which would make its own result unreadable.

Nothing here decides anything or is decided by anything: it returns text. Both
instruments take a `Completion` as an argument rather than building one, so the
constraints ADR-0004 holds in their signatures stay held (no precedent, no target
identity, no endpoint of their own), and every test in the suite drives them with a
stub instead of a network call.
"""

import functools
import os
from enum import StrEnum

from openai import OpenAI

from backend.bench.adjudication import Completion

DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

DEFAULT_ADJUDICATOR_MODEL = "openrouter:openai/gpt-4.1-mini"
"""The model that decides the two judged families, and what κ measured it at.

**Measured, no longer provisional** (#11, `uv run python -m
scripts.measure_reliability`). Against the thirty-transcript gold set this model
reads disclosure denial at κ = 0.86 to 1.00 across readings and wrongful commitment
at κ = 0.59 to 0.73 — so it is fit to decide the first family and, on three of four
readings, **not fit to report the second** (ADR-0004's κ < 0.6 rule). The figure, the
four readings and the three transcripts every disagreement lands on are in
`docs/validation.md`; the number is a property of this string, so changing it
invalidates them.

It is a *declared* input either way, printed beside the run that used it, because a
rate is not readable without knowing which instrument produced it (ADR-0004).

Deliberately not the reference agents' model. It is a stronger model than the one
under the agents because it is doing a harder job than they are, and keeping the
two settings apart is what lets #15 move one without moving the other.
"""


DEFAULT_ATTACKER_MODEL = "openrouter:openai/gpt-4.1-mini"
"""The model the adaptive attacker runs on, and a third declared setting.

Not the adjudicator's, although the string is the same today, and not the
reference agents'. Three instruments, three settings, for the reason #15 needs:
moving the model under the agents must not move the model deciding a judged
family, and neither of those may move the attacker — an adaptive layer whose
attacker changed with the target's model would make `A_break` unreadable
(ADR-0011).

The attacker is a declared input of a run on the same terms as the adjudicator: an
episode is not readable without knowing which instrument produced it, which is why
the alternative — a run silently taking the deterministic stand-in of
`backend/bench/adaptive/scripted.py` — is a thing the entry point never does.
"""


class Provider(StrEnum):
    OPENROUTER = "openrouter"


def completion_for(spec: str) -> Completion:
    """The bench's model call, from a `<provider>:<model>` configuration string.

    A string rather than a client, so the model an instrument used is a value a run
    can record and print. Parsed against a closed set of providers, like every other
    enumeration in the bench: an unrecognised provider fails here rather than at the
    first call.
    """
    provider, _, name = spec.partition(":")
    if not provider or not name:
        raise ValueError(
            f"a bench model configuration reads '<provider>:<model>', got {spec!r}"
        )
    match Provider(provider):
        case Provider.OPENROUTER:
            return _openrouter_completion(name)


def _openrouter_completion(name: str) -> Completion:
    # The client is built here rather than on the first call, so a missing
    # credential is a refusal at configuration time. A run that reached its first
    # judged attempt before discovering it had no instrument would already have
    # spent the operator's budget on attempts nothing can score.
    client = _client()

    def complete(system_prompt: str, message: str) -> str:
        answered = client.chat.completions.create(
            model=name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ],
        )
        return answered.choices[0].message.content or ""

    return complete


@functools.lru_cache(maxsize=1)
def _client() -> OpenAI:
    return OpenAI(
        base_url=os.environ.get("OPENROUTER_BASE_URL", DEFAULT_OPENROUTER_BASE_URL),
        api_key=os.environ["OPENROUTER_API_KEY"],
    )
