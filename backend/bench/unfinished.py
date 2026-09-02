"""A model reply that did not finish, named rather than parsed.

Every model call in this project goes through a provider that says, beside the
text, *why it stopped*. A reply cut off at the length cap arrives with
`finish_reason == "length"` and a body that ends mid-sentence — and a partial body
is still a string, so every parser downstream reads it as an answer. The
consequences differ by instrument and the worst is the adjudicator's: a reply
truncated before its `verdict:` line raises, but one truncated *after* a verdict
word appeared in reasoning is read as the verdict. That is a judged family's number
decided by where a token budget happened to fall, which ADR-0004 forbids — a
verdict must be derivable from the record by a reader who has it.

So the check happens at the client, before any parser sees the text: this module
is imported by the two places that call a provider (`backend/bench/completion.py`
for the bench's own instruments, `backend/targets/reference/model.py` for the
model a reference agent runs on) and by neither of the parsers, which never get
the chance to read a partial reply.

**This is `TargetFailure`'s shape, one layer in.** `contract.TargetFailure` names
why the bench got no usable reply *from a target*; `UnfinishedReply` names why it
got no usable reply *from a model*. Both are named outcomes with a stated reason,
raised rather than returned, and neither is a `Verdict`: ADR-0004 keeps `Verdict`
at `SUCCEEDED | RESISTED`, and a third member for "the instrument broke" would put
the instrument's health on the same axis as the target's defences.

**Where it leaves the attempt: nowhere, and the run stops.** The exception is
raised out of the completion, through `adjudicate` (or the attacker's step, or the
narrative judge), and out of `attacker._score` — which abandons the span and
re-raises *before* `run_state.record`, exactly as it already does for
`AdjudicationFailed`. No `Attempt` exists, so no numerator and no denominator
moves, and there is nothing for a rate to absorb. It is deliberately not retried
here: a retry at this seam would spend the operator's budget on a call the bench
has no reason to think will come back shorter, and would hide from the operator
that their declared model cannot answer inside its cap.

On the reference-agent side the same exception becomes a 500 from that agent's own
server, which the bench then names as a `TargetFailure` and records no attempt for
— the right answer arrived at through the layer that owns it.
"""

from enum import StrEnum

COMPLETE_FINISH_REASONS = frozenset({"stop", "tool_calls", "function_call"})
"""The reasons that mean the model finished saying what it had to say.

`stop` is a model that ended its own answer. `tool_calls` is a model that ended it
by calling a tool, which is how the adaptive attacker answers at all (ADR-0011) —
absent from this set, every real attacker turn would be refused as unfinished.
`function_call` is the same fact under the SDK's older name.

Listed rather than derived by excluding the failures below, so that a reason no
version of this code has seen is refused instead of defaulting into "fine". The
bench must fail in the direction that stops a run, never in the direction that
prints a number.
"""


class UnfinishedReply(StrEnum):
    """Why a model's reply is not an answer — one named outcome per stop reason.

    **None of these is a verdict and none of them is a security result.** A
    truncated adjudication and a resisting agent are the same absence of a
    `SUCCEEDED` and opposite facts about the target, so the difference is carried
    by a type rather than by a rate that happens to look defensive.

    Named per reason rather than collapsed into one *unfinished*, because they are
    different jobs for the person reading the run: truncation is a token cap to
    raise, a content filter is a payload the provider will not carry, and a reason
    nobody declared is a provider this code has not been taught to read.
    """

    TRUNCATED = "truncated"
    """`length` — the reply hit the token cap. The mode the bench actually meets,
    and the one that reads as a decision if nothing looks."""

    FILTERED = "filtered"
    """`content_filter` — the provider withheld the answer. Common for an
    adversarial bench, and it is a fact about the provider, not about the target."""

    UNSTATED = "unstated"
    """No `finish_reason` at all. Refused rather than assumed complete: a reply
    whose provider will not say whether it finished is a reply nothing can
    certify, and assuming it finished is the failure this module exists to stop."""

    UNRECOGNISED = "unrecognised"
    """A reason this code does not know. Kept as its own outcome rather than folded
    into truncation, because guessing which failure it was is what a reader would
    then have to un-guess."""

    @classmethod
    def of(cls, finish_reason: str | None) -> "UnfinishedReply | None":
        """The named outcome for one provider stop reason, or `None` for a
        complete reply."""
        if finish_reason in COMPLETE_FINISH_REASONS:
            return None
        match finish_reason:
            case None | "":
                return cls.UNSTATED
            case "length":
                return cls.TRUNCATED
            case "content_filter":
                return cls.FILTERED
            case _:
                return cls.UNRECOGNISED

    def stated(self) -> str:
        """The outcome in the words a run prints, with what it is not."""
        match self:
            case UnfinishedReply.TRUNCATED:
                return (
                    "truncated — the model stopped at its token cap, so what came "
                    "back is the beginning of an answer and not an answer"
                )
            case UnfinishedReply.FILTERED:
                return (
                    "filtered — the provider stopped the reply itself, so what came "
                    "back is the provider's decision and not the model's"
                )
            case UnfinishedReply.UNSTATED:
                return (
                    "unstated — the provider did not say why the reply ended, so "
                    "nothing here certifies that it ended of its own accord"
                )
            case UnfinishedReply.UNRECOGNISED:
                return (
                    "unrecognised — the provider gave a reason this bench does not "
                    "read, and a reason nobody read is not a reply that finished"
                )


NOT_AN_ANSWER = (
    "No attempt is recorded, nothing is parsed out of the partial reply, and "
    "nothing here is a security result"
)
"""What every report of an unfinished reply says beside the outcome it names.

One sentence in one place, for the reason `contract.NOT_A_SECURITY_RESULT` is: it
is the load-bearing half of the message, and two copies of it are two statements
that drift.
"""


class ReplyUnfinished(RuntimeError):
    """One named stop reason, raised instead of being parsed.

    Raised rather than returned, and that is the whole of the design: a caller
    cannot forget to look at it, and there is no field on an `Attempt` for a
    half-finished reply to sit in and be counted from.
    """

    def __init__(
        self, unfinished: UnfinishedReply, model: str, finish_reason: str | None
    ) -> None:
        self.unfinished = unfinished
        self.model = model
        self.finish_reason = finish_reason
        super().__init__(
            f"{model} answered with finish_reason={finish_reason!r}: "
            f"{unfinished.stated()}. {NOT_AN_ANSWER}"
        )


def refuse_unfinished(model: str, finish_reason: str | None) -> None:
    """Raise unless the provider says this reply finished of its own accord.

    Called on the response before anything reads `message`, at every seam where a
    provider's answer enters this project. It returns nothing: there is no value
    to thread through and no boolean for a call site to test and ignore.
    """
    unfinished = UnfinishedReply.of(finish_reason)
    if unfinished is not None:
        raise ReplyUnfinished(unfinished, model, finish_reason)
