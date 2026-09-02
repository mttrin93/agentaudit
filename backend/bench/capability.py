"""What each model will accept in a request, declared in one place.

A `<provider>:<model>` string is all the bench holds about an instrument, and until
now every model got the same request. `temperature` was sent whenever one was
declared — and `DEFAULT_ATTACKER_TEMPERATURE` means one always is for the attacker,
because a report with a field for it must not print *not declared* for a run nobody
chose a default for. The GPT-5 family accepts only the provider's own default and
errors on an explicit `temperature`, so a model on the console's own list could not
run the attacker at all, and the bench found that out at the first call of a run —
which is the moment `_client()` is built eagerly to get ahead of.

**A declared table, not a probe and not a denylist.** A rule that discovers a
capability by trying it spends a call to learn it, and spends it after the operator
has attested and confirmed a budget. A denylist goes stale the first time a provider
ships a model nobody added a line for. So capability is *declared* here, per model,
consulted before a request is composed, and read by every seam that composes one:
`backend/bench/completion.py` for the bench's own two instruments, and
`backend/api/app.py` where an operator sets them (ADR-0025).

**The fallback is stated, and it is the full set.** A model this table has never
heard of is presumed to accept what the API documents as standard, and
`ModelCapabilities.declared` records that the answer was a presumption. That is the
conservative direction *for the artefact*, which is the thing being protected: a
capability wrongly sent is refused by the provider, loudly, with no figure printed;
a capability wrongly withheld is a run whose provenance block says *this model takes
no temperature* about a model that takes one, which is a false sentence inside a
signed document (ADR-0004). Failing towards the loud error is the same direction
`unfinished.COMPLETE_FINISH_REASONS` fails in, for the same reason.

**A guarded temperature is not a dropped temperature.** Nothing here drops a
parameter behind a caller's back. `temperature_for` resolves a *default* against the
table and hands back what may be sent, so the caller can record which of the two
declarations it ended up making; and a caller that composes a request with a
temperature the model will not take is refused by `TemperatureNotAccepted` at
configuration time. The three states a report has to keep apart — *nobody declared
one*, *this run was sampled at 0.0*, *this model accepts none* — are three
statements, and `payload.DeclaredModels` prints whichever one is true.

**A second parameter, and the reason this is a record and not a boolean.**
`reasoning_effort` is the same question asked the other way round: the reasoning family
is the half of the table that takes one, and a chat model refuses it exactly as GPT-5
refuses a temperature. It is a declared input of a run on the same terms — two runs of
one model at one temperature and different effort are two different instruments, and a
report that cannot tell them apart is a report nobody can repeat a run from (#5). So it
is a second field on `ModelCapabilities` rather than a second table, and the three
statements a temperature has (*a value*, *none declared*, *none available*) it has too.

**Tools are not in the table.** #2 gave the attacker its five tools as provider
schemas, which is a second per-model capability question — but a model that accepts
no `tools` array cannot be the adaptive attacker at all, which is a refusal about
the instrument rather than a parameter to withhold, and no model this console offers
is one. A row would be a claim this bench has not measured; the absence is recorded
here instead.
"""

from dataclasses import dataclass
from enum import StrEnum

NO_TEMPERATURE_ACCEPTED = (
    "this model accepts no temperature — it samples at the provider's own default "
    "and refuses the parameter, so none was sent. Not the same statement as no "
    "temperature declared: the choice was unavailable, not unmade"
)
"""What a run says about a temperature the model would not have taken.

A third statement beside *none declared* and a number, because the two absences are
different facts about the run and a reader cannot recover which one from a blank
(ADR-0004, ADR-0025).
"""


NO_REASONING_EFFORT_ACCEPTED = (
    "this model has no reasoning effort setting — it is not a reasoning model, so "
    "none was sent and none could have been. Not the same statement as no reasoning "
    "effort declared: the choice was unavailable, not unmade"
)
"""What a run says about a reasoning effort the model has no setting for.

The counterpart of `NO_TEMPERATURE_ACCEPTED`, and needed for the same reason in the
other direction: a chat model refuses `reasoning_effort` the way a reasoning model
refuses `temperature`, and a blank field cannot say which of the two absences a
reader is looking at (ADR-0004, #5).
"""

PRESUMED_NO_REASONING_EFFORT = (
    "no line in the capability table for this model, so the standard chat set is "
    "presumed and it has no reasoning effort — a presumption stated as one, and not "
    "a measurement of what the provider would accept"
)
"""What a run says about a model this table has never heard of.

Said rather than collapsed into `NO_REASONING_EFFORT_ACCEPTED`, because the two are
not the same fact: one is a declared row and the other is this bench admitting it has
no row. The presumption direction is the module's stated one — the standard set — and
`reasoning_effort` is not in it.
"""


class ReasoningEffort(StrEnum):
    """How hard a reasoning model may think, as a closed set.

    Three levels and not the provider's whole list. `minimal` is a GPT-5-only level
    that the o-series refuses, so offering it would put a *per-model level* table
    underneath this one — a second capability question this bench has no reading on
    and no need for. Three levels every reasoning model on the console's own list
    accepts, and a level a model would refuse is not offered rather than declared and
    then withheld.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class ModelCapabilities:
    """What one model will accept, as this bench declares it.

    Two parameters and one presumption flag. It is a record rather than a bare
    boolean so that the next parameter a provider makes conditional is a field here
    and not a second table somewhere else — the whole point of the module is that
    there is one place to look, and `reasoning_effort` arriving as a field rather
    than as a second module is that promise being kept (#5).
    """

    accepts_temperature: bool
    """Whether an explicit `temperature` may be sent at all.

    False is the reasoning family: OpenAI's o-series and the GPT-5 models sample at
    their own default and error on the parameter rather than ignoring it.
    """

    accepts_reasoning_effort: bool
    """Whether an explicit `reasoning_effort` may be sent at all.

    True is the reasoning family and nothing else: the parameter exists because those
    models have a thinking budget to spend, and a chat model refuses it the way a
    reasoning model refuses a temperature. The two fields are declared per row rather
    than derived from each other, and `NEITHER_SETTING` is why: `openai/gpt-5.2-chat`
    takes neither, so a bench deriving the second answer from the first would offer it
    a thinking budget the provider refuses. A model taking both would be a row here on
    the same terms and not a rewrite.
    """

    declared: bool = True
    """Whether this answer is a line in the table or the presumption below it.

    Carried rather than inferred from the absence of a row, so a caller that wants
    to say *presumed* can say it. Nothing branches on it inside the bench: the
    presumption and a declared full set compose the same request.
    """

    def stated(self) -> str:
        """What this reading is, in the words a refusal or a record uses."""
        accepted = (
            "accepts an explicit temperature"
            if self.accepts_temperature
            else "accepts no explicit temperature"
        )
        thinks = (
            "accepts a reasoning effort"
            if self.accepts_reasoning_effort
            else "accepts no reasoning effort"
        )
        how = (
            "a line in the capability table"
            if self.declared
            else "no line in the capability table, so the standard set is presumed"
        )
        return f"{accepted}, {thinks} — {how}"


REASONING_FAMILY = ModelCapabilities(
    accepts_temperature=False, accepts_reasoning_effort=True
)
"""Models that sample at the provider's default and reject the parameter.

The same models that take a `reasoning_effort`, which is the row saying why the two
questions belong in one table: the family that refuses the first is the family that
accepts the second, and a bench answering them from two places would eventually
answer them about two different models.
"""

NEITHER_SETTING = ModelCapabilities(
    accepts_temperature=False, accepts_reasoning_effort=False
)
"""Models that take neither: no explicit temperature, and no thinking budget.

The combination the other three rows imply is impossible and the provider ships
anyway. `openai/gpt-5.2-chat` is the non-reasoning member of the 5.2 line and it did
not inherit the chat set with it: the provider lists neither `temperature` nor
`reasoning_effort` among the parameters it supports. Declared rather than left to the
`openai/gpt-5` prefix above it, because that prefix would offer it a thinking budget
it refuses — the provider's error arriving at the first call of a run whose budget is
already moving, which is the arrangement #4 replaced.

It is a row and not a fourth flag on the record: the two questions were always
independent, and this is the row that proves the record was right not to derive one
from the other.
"""

TAKES_A_TEMPERATURE = ModelCapabilities(
    accepts_temperature=True, accepts_reasoning_effort=False
)
"""Models that take one, declared rather than presumed. They have no thinking budget
to set, and `reasoning_effort` is refused rather than ignored."""

PRESUMED = ModelCapabilities(
    accepts_temperature=True, accepts_reasoning_effort=False, declared=False
)
"""What a model with no line in the table is taken to accept.

The standard set, and the module docstring says why that is the conservative
direction: the failure it allows is a provider's loud refusal before any figure
exists, and the failure it refuses is a signed document stating a capability nobody
checked.

`reasoning_effort` is not in the standard set, so the presumption withholds it — and
because that is a presumption rather than a reading, a run against such a model says
`PRESUMED_NO_REASONING_EFFORT` and not *this model has no such setting*. There is no
default effort for it to withhold either: nothing is sent unless somebody declared
one, so the presumption costs a run nothing it asked for.
"""

CAPABILITIES: tuple[tuple[str, ModelCapabilities], ...] = (
    # Ordered, first match wins, and the exception comes before the family it is an
    # exception to: `gpt-5-chat` is the non-reasoning member of the GPT-5 line and
    # takes a temperature like any other chat model, so a plain prefix match on
    # `openai/gpt-5` would withhold a parameter it accepts. `gpt-5.2-chat` is the
    # same exception one version on and it does not take one either, which is why
    # each chat variant is a row of its own rather than a rule about the word.
    ("openai/gpt-5-chat", TAKES_A_TEMPERATURE),
    ("openai/gpt-5.2-chat", NEITHER_SETTING),
    ("openai/gpt-5", REASONING_FAMILY),
    ("openai/o1", REASONING_FAMILY),
    ("openai/o3", REASONING_FAMILY),
    ("openai/o4", REASONING_FAMILY),
)
"""The declared table: a model-name prefix, and what that model accepts.

Prefixes rather than exact names, because a provider slug carries versions and
variants a table cannot enumerate — `openai/gpt-5-mini`, `openai/gpt-5-mini:online`
and a dated snapshot of it are one model as far as this question goes. Ordered so an
exception can precede its family, which is the only reason a mapping is not used.

Names are the part after the provider: the same string `completion` passes to the
SDK, so what is matched here is what is sent there.
"""


class TemperatureNotAccepted(ValueError):
    """A request was composed with a temperature the model refuses.

    A `ValueError`, so it lands where every other unusable model configuration lands:
    a `RuntimeError` that stops the boot in `app._declared`, and a 422 that names the
    setting in the route an operator sets it from. Raised at configuration time, on
    the strength of the table, rather than discovered at the first call of a run whose
    budget is already moving.
    """

    def __init__(self, model: str, temperature: float) -> None:
        self.model = model
        self.temperature = temperature
        super().__init__(
            f"{model} takes no explicit temperature, so temperature={temperature} "
            f"cannot be sent. {NO_TEMPERATURE_ACCEPTED}"
        )


class ReasoningEffortNotAccepted(ValueError):
    """A request was composed with a reasoning effort the model has no setting for.

    `TemperatureNotAccepted`'s counterpart, and a `ValueError` for the same reason: it
    lands where every other unusable model configuration lands — a `RuntimeError` that
    stops the boot in `app._declared`, and a 422 that names the setting in the route an
    operator sets it from. Raised at configuration time on the strength of the table,
    rather than at the first call of a run whose budget is already moving.
    """

    def __init__(self, model: str, reasoning_effort: "ReasoningEffort") -> None:
        self.model = model
        self.reasoning_effort = reasoning_effort
        super().__init__(
            f"{model} has no reasoning effort setting, so "
            f"reasoning_effort={reasoning_effort} cannot be sent. "
            f"{NO_REASONING_EFFORT_ACCEPTED}"
        )


def capabilities_of(model: str) -> ModelCapabilities:
    """What this model accepts — a declared row, or the stated presumption.

    Takes either a `<provider>:<model>` configuration string or the bare model name,
    because both are held in this project: `completion` has parsed the provider off
    by the time it composes a request, and `app` holds the whole string it will
    print in a provenance block. One function for both, so the two cannot consult
    different answers about one model.
    """
    for prefix, capabilities in CAPABILITIES:
        if _named(model).startswith(prefix):
            return capabilities
    return PRESUMED


def accepts_temperature(model: str) -> bool:
    """Whether an explicit temperature may be sent to this model at all."""
    return capabilities_of(model).accepts_temperature


def accepts_reasoning_effort(model: str) -> bool:
    """Whether an explicit reasoning effort may be sent to this model at all."""
    return capabilities_of(model).accepts_reasoning_effort


def reasoning_effort_for(
    model: str, declared: ReasoningEffort | None
) -> ReasoningEffort | None:
    """The reasoning effort to send this model, given what a deployment declared.

    `temperature_for`'s counterpart and the same seam, with one difference worth
    stating: there is no `DEFAULT_ATTACKER_REASONING_EFFORT`, because a thinking
    budget this bench invented would be a setting a report named and nobody chose,
    and unlike a temperature there is no field that would otherwise have to read
    *not declared* for a run nobody chose a default for — *not declared* is the
    honest reading of a run nobody declared one for.

    So `None` in is `None` out, always, and the resolution only ever has work to do
    when a deployment declared an effort for a model that has no setting for it.
    """
    if declared is None or accepts_reasoning_effort(model):
        return declared
    return None


def temperature_for(model: str, declared: float | None) -> float | None:
    """The temperature to send this model, given what a deployment declared.

    `None` where the model accepts none, which is what the caller then records — a
    default resolved against the table, never a choice quietly discarded. The
    distinction matters because the two callers are different: a deployment's
    `DEFAULT_ATTACKER_TEMPERATURE` is the bench's own number and resolving it is the
    honest thing to do with a model that will not take it, whereas an operator who
    typed one into the console chose it and is told it cannot be had
    (`TemperatureNotAccepted`, ADR-0025).
    """
    if declared is None or accepts_temperature(model):
        return declared
    return None


def _named(model: str) -> str:
    """The model name, with a provider prefix stripped if there was one.

    A provider slug carries `/` and a configuration string carries `:`, so which
    half is the name is not ambiguous.
    """
    provider, separator, name = model.partition(":")
    return name if separator else provider
