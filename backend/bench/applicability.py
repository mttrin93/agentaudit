"""Whether a case was written for this target at all — asked before it is run.

A case declares the agent types it applies to (spec story 16). The reason is a
payload: the library's cases talk about supplier notes, August invoices, a shared
inbox and settling a balance, and against a voice agent taking restaurant bookings
those words find no referent. Such a case does not measure a voice agent's
defences; it measures whether the payload landed. Counting its `resisted` verdicts
would report a target as defended against an attack it was never asked to face,
which is the same lie `measurability.py` refuses one level along.

**This is not the *not measurable* outcome, and the two are separate types on
purpose.** Not measurable is a fact about the *target*: it cannot expose its tool
calls, so a family that reads a tool trace has no evidence to read, and the gap is
the operator's to close by exposing them. Inapplicable is a fact about the
*library*: nothing is missing from the target, and the gap is the bench's to close
by writing cases for that agent type — trigger 4, `NEW_AGENT_TYPE`. A reader told
"not measurable" would go looking for a capability to add to their agent, and
would find nothing wrong with it. So they are reported apart, they are reached by
different checks, and neither can be coerced into the other.

**The skip is explicit, and that is the whole decision here.** The alternative —
sending the case anyway and scoring the reply — is the one the spec names and
refuses: a payload written for a document agent must not be "run against a voice
agent and counted as a pass". The alternative to *that* is dropping the case
silently, which moves a denominator with nothing on the page to say it moved. So a
skipped case is recorded, per case, with the agent type it was skipped for and the
types it does apply to, and it appears in the run's own section beside the rates.

CONTEXT.md puts *skipped* and *not applicable* on the avoid-list **for not
measurable**, which is exactly what this module protects: those words mean this
outcome, so they cannot be spent on the other one.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from backend.bench.contract import TargetConfig
from backend.bench.library import Case, Family


class Inapplicable(StrEnum):
    """Why a case was not run against a target.

    A reason rather than a flag, like `NotMeasurable`, and for the same reason: a
    skip with no cause is as unhelpful as a missing number. There is one member
    today because `applies_to` is the one thing on a record that says which targets
    a case was written for.
    """

    AGENT_TYPE_OUTSIDE_APPLIES_TO = "agent_type_outside_applies_to"

    def stated(self) -> str:
        """The reason in the words a report prints."""
        return (
            "not run — this case was not written for this target's agent type, so "
            "no attempt was spent on it and nothing about it is counted"
        )


@dataclass(frozen=True)
class SkippedCase:
    """One case that was not run against one target, and what it was skipped for.

    Per case rather than per family, because `applies_to` is a property of a case:
    a family can have two cases that apply to a target and one that does not, and
    the family's rate is then a rate over the two that ran. A family-level record
    would have to choose between reporting a rate and reporting a skip for the same
    family, and both are true.
    """

    case_id: str
    family: Family
    agent_type: str
    """The type the target is registered as — the operator's own word for it."""

    applies_to: tuple[str, ...]
    reason: Inapplicable = Inapplicable.AGENT_TYPE_OUTSIDE_APPLIES_TO

    def stated(self) -> str:
        """The line a report prints for one skipped case."""
        return (
            f"{self.case_id} ({self.family}): {self.reason.stated()} — registered "
            f"as {self.agent_type!r}, the case applies to "
            f"{', '.join(repr(kind) for kind in self.applies_to)}"
        )


def applies(case: Case, target: TargetConfig) -> bool:
    """Whether this case was written for this target's agent type.

    Compared case-folded and stripped, because a target's agent type is free text
    the operator wrote at registration and `'Document'` is not a different kind of
    agent from `'document'`.

    Deliberately a string comparison against no closed set, unlike every other
    vocabulary in the bench. The agent type is the *operator's* description of
    their own agent, and a closed set here would refuse to register a target whose
    kind the bench had not thought of yet — while the honest answer to an agent type
    the library has no cases for is the skip below, not a refused registration.
    """
    kind = _normalised(target.agent_type)
    return any(kind == _normalised(applicable) for applicable in case.applies_to)


def applicable(cases: Sequence[Case], target: TargetConfig) -> list[Case]:
    """The cases of this library that were written for this target."""
    return [case for case in cases if applies(case, target)]


def skipped_cases(
    cases: Iterable[Case], target: TargetConfig
) -> tuple[SkippedCase, ...]:
    """The cases this target will not be sent, in library order.

    Every one of them, rather than a count: a run that reported "three cases
    skipped" would leave a reader unable to tell which family lost coverage.
    """
    return tuple(
        SkippedCase(
            case_id=case.id,
            family=case.family,
            agent_type=target.agent_type,
            applies_to=case.applies_to,
        )
        for case in cases
        if not applies(case, target)
    )


def _normalised(agent_type: str) -> str:
    return agent_type.strip().casefold()
