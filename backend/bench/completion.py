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

MODEL_TIMEOUT_SECONDS = 60.0
"""How long one call to an instrument may wait for its answer.

Declared because the SDK's own default is ten minutes, and a run holds nothing back
while it waits: one adjudication that never returns is a suite stopped at the attempt
it was scoring, with the operator watching a position that will not move. Sixty
seconds is the same patience `contract.DEFAULT_TIMEOUT` gives an endpoint, and the
same reasoning — long enough that a slow answer still arrives, short enough that a
stalled one is a failure somebody is told about.

Measured against the declared adjudicator, a verdict comes back in 0.8 to 2.3
seconds; the narrative judge writes prose and takes longer. This is a ceiling for the
call that hangs, not a target for the call that works, so it is set for the second of
those and not the first. The SDK retries twice inside it, so a stalled call costs
three of these before it is named."""

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


REFERENCE_MODEL_ENV = "AGENTAUDIT_REFERENCE_MODEL"
"""Where a deployment declares the model its three reference agents run on."""

ADJUDICATOR_MODEL_ENV = "AGENTAUDIT_ADJUDICATOR_MODEL"
"""Where a deployment declares the instrument that decides the judged families."""

ATTACKER_MODEL_ENV = "AGENTAUDIT_ATTACKER_MODEL"
"""Where a deployment declares the model the adaptive layer's attacker runs on.

A third variable rather than a reading of either of the other two, for the reason
`DEFAULT_ATTACKER_MODEL` is a third constant: an attacker that moved with the model
under the agents, or with the one deciding a judged family, would make `A_break`
a reading about two things at once (ADR-0011). Unset is the deterministic stand-in
of `backend/bench/adaptive/scripted.py`, declared as such and never named as a model.
"""


def declared_model(variable: str) -> str | None:
    """What the environment declares under that name, or `None` for nothing.

    Here rather than in the caller because this module is where the environment is
    read: `backend/api/` imports no `os` and is asserted not to, so that a price, a
    target URL or a bearer token cannot arrive that way behind a default
    (`test_api_runs.py`). A model identifier can, and only through this function —
    it is declared configuration that every signed report already prints, and the
    scripts read these same variables.

    **Blank is nothing.** An environment variable set to the empty string is how half
    the tooling that sets one says *unset*, and a bench that treated it as a model
    identifier would fail building a client for `''`.

    **There is no default.** A model named here that the deployment did not declare
    would describe a run that did not happen, which is what `UNDECLARED_MODEL` exists
    to say instead (ADR-0004).
    """
    return os.environ.get(variable, "").strip() or None


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
        timeout=MODEL_TIMEOUT_SECONDS,
    )
