"""The artefact: one target run as canonical JSON, carrying counts and no verdict.

`assembler.py` produces the structured result — three sections, the coverage gaps
and no scalar. This module is the point at which that result stops being an object
in a process and becomes **bytes that travel**: sorted keys, fixed separators, and
byte-identical for an identical result, because a signature covers bytes and a
signature over an unstable serialisation certifies nothing (`rendering.py` binds the
Markdown view into it by digest, #51 signs it).

**Counts, never a rate somebody computed once.** Every measured figure is written
with the counts it came from: `successes` and `attempts` beside the rate, the
interval's confidence beside the interval, the band cuts beside the bands, and
`agreements` of `transcripts` beside κ. That is the idiom `[admission]` and
`[[history]]` already follow on a case record, and it is what makes the verifier of
#51 possible at all — a recipient re-derives the arithmetic instead of trusting it.
A payload holding only computed figures would leave *re-derivable* a sentence in the
document rather than a property of it.

**No gate decision about the target, and no field that could hold one** (ADR-0018).
The gate is a claim about the bench: `D` is trivial minus hardened, monotonicity is
an ordering across three agents, and both thresholds are counts over families of
*contrast* — not one of them has a definition when the subject is a single target,
so there is no arithmetic here that could produce a target gate decision and any
field claiming to hold one could only be filled by copying the bench's own result
across. The bench's gate result appears once, as a `GateCitation` inside
`Provenance`, and the words differ deliberately: the bench *passed its gate*, the
target *has rates, intervals and bands*. Neither sentence is available for the other
subject, and `GateDecision` is not importable from here.

**Nothing totals, averages or ranks across families** (ADR-0005, D12). There is no
key at any depth that reaches across two families, and the structural half of that
claim is testable: drop a family from the result and every other byte of the
document is unchanged, because nothing anywhere is computed from more than one.

**Three kinds of nothing, kept apart.** A family measured at 0 of 30 is a
measurement; a family the target could not answer is `not_measurable` with the
reason that closes it; a judged family below the κ floor is **absent from the
measured figures** and named under `withheld` with the reading that barred it
(ADR-0015). A control the operator declared and nothing tested, and one the
checklist asks about and they did not declare, are two further absences and are
reported as themselves. None of the four is a rate of zero, and a reader can tell
which they are looking at without reading a footnote.

**And a fifth, for a family nobody asked for.** An elective family this run was not
requested to test is `not_requested` under `elective` — the bench holds a tier for
it, nothing was attempted, and nobody could not answer
([ADR-0035](../../docs/adr/0035-the-elective-family-tier-is-never-gate-deciding.md)).
It travels beside the request it is the complement of, and the two together are the
whole of what this document says about the tier: **a name and never a figure.** An
elective family's `D` is a claim about the bench and this artefact is about a target
(ADR-0018), and `MeasuredSection` is keyed on `Family`, so there is no field here one
could arrive in — which is what makes "a family whose discriminating power was never
measured may not print in a signed report" a property of the shape rather than a
check somebody performs.

**No payload text, anywhere** (ADR-0008). Attempts are not serialised, only the
counts over them; episode transcripts and proposals are not serialised at all, only
the prose description the adaptive section already holds. Case **ids** appear where
a control was defeated, because an id is a pointer into the evidence and not a copy
of it.
"""

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any

from backend.bench.assembler import (
    AdaptiveSection,
    CoverageGap,
    DeclaredSection,
    FamilyEntry,
    MeasuredSection,
    ReportedEpisode,
    ScannedControl,
    TargetResult,
)
from backend.bench.capability import (
    NO_REASONING_EFFORT_ACCEPTED,
    NO_TEMPERATURE_ACCEPTED,
    PRESUMED_NO_REASONING_EFFORT,
    ReasoningEffort,
    accepts_reasoning_effort,
    accepts_temperature,
    capabilities_of,
)
from backend.bench.elective import ElectiveSelection
from backend.bench.labels import FamilyLabel, bears_stated, claims_stated, label_for
from backend.bench.library import ExternalId, Family, LibraryVersion
from backend.bench.planting import NOTHING_WAS_PLANTED, Teardown
from backend.bench.published import ClaimedInPart, UntestedCategory
from backend.bench.registration import AttestationRecord
from backend.bench.rule import DECLARED_RULE, GateRule
from backend.bench.scanner import RuleOfTwo
from backend.bench.scorer import GateOutcome, Interval, Reliability, VariantCounts
from backend.bench.selection import EVERY_CONSTRUCTION, AttackSelection
from backend.graph.budget import Layer

ARTEFACT = "agentaudit.target-report"
"""What this document is, written into it.

A reader who meets the file without the sender says what kind of artefact it is by
reading it, and `verify.py` refuses one of a kind it does not know rather than
checking a signature over something else.
"""

ARTEFACT_VERSION = 1
"""The shape of this document, so a later shape is a different shape and says so."""

CANONICAL_SEPARATORS = (",", ":")
"""No insignificant whitespace. Half of what makes the bytes stable; sorted keys
is the other half."""


class WithheldReason(StrEnum):
    """Why a judged family's rate is absent from the measured figures.

    Two members, because they are two different readings. A κ below the floor says
    the instrument that decided the family was measured and found wanting; no κ at
    all says nobody measured it, which is not the same fact and is not a κ of zero
    (ADR-0004, ADR-0013).
    """

    KAPPA_BELOW_FLOOR = "kappa_below_floor"
    NO_KAPPA_MEASURED = "no_kappa_measured"


@dataclass(frozen=True)
class Withheld:
    """One judged family the report may not publish, and the reading that barred it.

    Carries κ with its counts and the floor it faced, and **no rate** — the rate was
    measured and is recorded on the run (ADR-0006 keeps a measured rate measured),
    and what it does not have is a statable evidentiary strength, which is the whole
    of what a report is for (ADR-0015).
    """

    family: str
    reason: WithheldReason
    floor: float
    kappa: float | None = None
    agreements: int | None = None
    transcripts: int | None = None

    @classmethod
    def of(cls, entry: FamilyEntry, rule: GateRule = DECLARED_RULE) -> "Withheld":
        """The withholding one unfit entry produces, read off the entry itself.

        Derived rather than set, in the discipline `MeasuredSection.unfit_to_report`
        already follows: a renderer that had to be *told* which families to withhold
        is one where forgetting to ask publishes the rate.
        """
        reliability = entry.reliability
        if reliability is None:
            return cls(
                family=entry.family.value,
                reason=WithheldReason.NO_KAPPA_MEASURED,
                floor=rule.kappa_floor,
            )
        return cls(
            family=entry.family.value,
            reason=WithheldReason.KAPPA_BELOW_FLOOR,
            floor=reliability.floor,
            kappa=reliability.kappa,
            agreements=reliability.agreements,
            transcripts=reliability.transcripts,
        )

    def stated(self) -> str:
        """The line the report prints in place of the rate it is not printing."""
        if self.kappa is None:
            return (
                f"{self.family}: withheld — no κ was measured against the gold set, "
                "so the strength of the evidence behind this family's rate cannot "
                "be stated and the rate is not published (ADR-0004, ADR-0013)"
            )
        return (
            f"{self.family}: withheld — κ = {self.kappa:.2f} "
            f"({self.agreements} of {self.transcripts} transcripts agreed) is below "
            f"the declared floor of {self.floor:.2f}. The attempts were made and the "
            "rate is recorded; it is not published (ADR-0015)"
        )


@dataclass(frozen=True)
class NotRequested:
    """One elective family this run was not asked to test.

    The **fifth kind of nothing**, and it is none of the other four
    ([ADR-0035](../../docs/adr/0035-the-elective-family-tier-is-never-gate-deciding.md)).
    A `CoverageGap` and an `UntestedCategory` are categories nobody tests at all; a
    `not_measurable` family is one the target could not answer; a `Withheld` family
    is one whose instrument was measured and found wanting. This one is a family the
    bench holds a tier for and this run did not ask for — nothing was attempted, and
    nobody could not answer.

    It carries no figure and there is nothing for it to carry: an elective family's
    `D` is a claim about the bench and a report is about a target (ADR-0018), and
    `MeasuredSection` is keyed on `Family`, so there is no field in this document one
    could arrive in.
    """

    family: str

    @classmethod
    def over(cls, selection: ElectiveSelection) -> tuple["NotRequested", ...]:
        """The absences one selection produces, derived rather than supplied.

        In the discipline `Withheld.of` already follows: a renderer that had to be
        *told* which families to name is one where forgetting to ask prints nothing,
        and this is the one absence whose whole content is that nobody asked.
        """
        return tuple(cls(family=family.value) for family in selection.not_requested)

    def stated(self) -> str:
        """The line the report prints in place of a figure it has none of.

        **The word *gate* does not appear in it**, and that is ADR-0018 rather than
        brevity: this document is about a target, the vocabulary of the gate belongs
        to the bench, and the one line of a target report that may name it is the `D`
        line that says in the same breath what it is. So the sentence says what the
        absence costs the reader — nothing — without borrowing the bench's words for
        it, and where the tier's own figures live is stated in ADR-0035.
        """
        return (
            f"{self.family}: not requested — this run was not asked to test this "
            "elective family, so no attempt was made against it and it has no rate, "
            "no interval and no band. Its absence takes nothing off the figures "
            "above: this bench's discriminating power on an elective family is a "
            "fact about the bench, stated where the bench states its own figures "
            "and never here (ADR-0035, ADR-0018)"
        )


@dataclass(frozen=True)
class LibraryMoved:
    """The library has grown past the version its cited gate run was earned at.

    A **gate citation** is a claim about a library version — *this bench passed its
    own gate at eighteen cases, digest 90a8ebcc* — earned by running that library.
    Since the admission gate writes an admitted route into the library
    ([ADR-0033](../../docs/adr/0033-an-admitted-route-is-written-into-the-library.md))
    the version can move without a gate run, and a citation left standing untouched
    would be a pass recorded against a library that no longer exists.

    **It is not a correction of that gate run and takes nothing off it.** The
    outcome, the date, the version it was earned at and the two addresses its figures
    are recovered through are all still the record's own. This is one more fact
    beside them, about the library rather than about the run — the same shape
    ADR-0023 chose when a failing gate run replaced a passing citation: nothing is
    deleted, and the loss is announced.

    **No figure, on the same terms as the citation itself.** A count and a digest of
    the records now on disk, and the ids that entered. There is no rate here, no `D`
    and no reading of the new cases at all: what a reader is told is that the bench's
    discriminating power was measured at another version, not what it would measure
    at this one. The answer to that is a gate run, which is also what clears this.
    """

    version: LibraryVersion
    """What the library is at now, read off the records rather than declared."""

    by: tuple[str, ...]
    """The cases that entered since the cited gate run, in the order they entered.

    The ids and not a count, because the one question a reader has is *which* cases
    the gate run did not see, and `discovered_by` on each record is how they find
    out who wrote them. Appended to across runs, so a library that has drifted over
    four runs says so rather than reporting the last one.
    """

    def stated(self) -> str:
        """The superseding in the words a report carries."""
        entered = ", ".join(self.by)
        return (
            f"**This library has grown past the version that gate run was decided "
            f"at.** {len(self.by)} "
            f"{'case' if len(self.by) == 1 else 'cases'} entered it since — "
            f"{entered} — so it now stands at {self.version.stated()}. Each entered "
            "by clearing the cross-model admission bar, which is the same declared "
            "floor the gate holds a family to (ADR-0012); none of them was in the "
            "library the outcome above was measured on. Running the gate again is "
            "what earns a citation at this version"
        )


@dataclass(frozen=True)
class GateCitation:
    """The bench's own gate result, cited as provenance and never as a result.

    The instrument's certification, in the part of a document that says *how this
    was made*. It is a fact about the bench — that a stated, falsifiable rule was
    put to three agents of known construction and could have answered "this bench
    measures nothing" — and it is the project's answer to the reader's legitimate
    question about why the figures above should be believed at all (ADR-0018).

    **Typed apart from the target's figures, and that is the whole of the design.**
    This record holds no `Rate`, no `Interval`, no `Band` and no `D`; it is reachable
    only through `Provenance`; and `GateDecision` — the record that carries the
    passing and monotonic counts, the per-family outcomes and the rule — is not
    imported by this module and cannot be put anywhere in this payload. A future
    contributor who wants a gate verdict beside a customer's agent name has to widen
    a type, which is the signal ADR-0010 established for exactly this class of
    mistake.

    **It reaches the figures without carrying them, and that is ADR-0023's line.**
    `record` names the machine-readable **gate run record** of the same gate run, so
    a reader holding this block recovers each reference agent's rate and each
    family's `D` without parsing the dated document — the thing #75 refused to build
    a parser for. What did *not* change is that those figures are not *here*: the
    record names `hardened`, `weak` and `trivial`, and no reference agent is named in
    a user's report (ADR-0018, point 6). A pointer travels; a table beside a
    customer's agent name invites the comparison this project exists to refuse.
    """

    outcome: GateOutcome
    decided_on: date
    library: LibraryVersion
    document: str | None
    """Where the run that decided it is written down in prose, or `None`.

    `None` is a gate run started from the console, which leaves the record below and
    no dated document (ADR-0021, ADR-0023). A missing document is a fact about which
    entry point ran and not a gap in the citation — the figures are reachable either
    way, through `record` — so it is typed as an absence rather than papered over with
    a sentence in a field a reader would follow as a path."""

    record: str
    """Where the same gate run is written down as fields, for the figures above.

    The **gate run record**'s own file name, off the record itself rather than
    composed here (`gate_record.RecordedGateRun.record`), so a reader following it
    arrives at the file the gate run wrote. Named and never opened by anything that
    renders this citation: this is an address, and the arithmetic behind it stays
    where the run put it (ADR-0023).
    """

    moved: LibraryMoved | None = None
    """Whether the library has grown past the version this gate run was decided at.

    `None` on a citation whose library still holds exactly the cases the gate run
    put itself through, which is every citation a gate run writes. Set by the write
    that moved it (`bench/entry.py`), and cleared by the next gate run, because a
    gate run decided at this version supersedes nothing (ADR-0033).

    Last in the field list because it has a default and the four fields above it do
    not. It is the only field on this record a gate run did not measure, which is
    also why it is typed apart rather than folded into `library`: that one is the
    version the outcome was earned at and this one is where the library has got to,
    and a single field holding whichever was later would lose the pair.
    """

    def stated(self) -> str:
        """The citation in the bench's own words, which are not the target's.

        *The bench passed its gate.* There is no sentence available here in which a
        target passes or fails anything, and that absence is deliberate: what
        circulates is a screenshot of one section, so a field whose correctness
        depends on an adjacent caption is a field that will eventually be wrong in
        the flattering direction (ADR-0018).

        **A superseded library is said here and not left to a reader's arithmetic.**
        The version the gate run was earned at and the version the library is at now
        are both on this record, so a reader *could* compare two digests — and a
        figure a reader has to cross-reference to qualify is a figure that will be
        quoted unqualified, which is the reasoning ADR-0032 applied to the admission
        counts one ticket earlier.
        """
        prose = (
            f"recorded in {self.document}, and as fields in {self.record}"
            if self.document is not None
            else f"recorded as fields in {self.record} and in no dated document — "
            "this gate run was started from the console, which leaves the one and "
            "not the other"
        )
        return (
            f"the bench {self.outcome.value} its own gate on "
            f"{self.decided_on.isoformat()}, against its three agents of known "
            f"construction, at {self.library.stated()} — {prose}, where every "
            "per-family figure behind that answer is recoverable without reading a "
            "sentence. A fact about the instrument that produced the figures above, "
            "and not a verdict on this target: this target has rates, intervals and "
            "bands, and passes and fails nothing"
        ) + ("" if self.moved is None else f". {self.moved.stated()}")


UNCITED_GATE = (
    "no gate run is cited — this report was produced by a bench whose own "
    "discriminating power is unstated here. A stated absence, not a blank: an "
    "uncited instrument is a fact about this report (ADR-0018)"
)
"""What provenance says when it cannot name a gate run.

Said rather than omitted. A missing line reads as a document that had nothing to
declare, and this one has something to declare and no way to declare it.
"""


@dataclass(frozen=True)
class DeclaredModels:
    """The three model identifiers a run was made under. Configuration, not results.

    The same three the gate document records, because they are the three settings
    that decide what a run *is*: the model the bench's own calibration equipment ran
    on, the model that adjudicates the two judged families, and the model the
    adaptive attacker runs on. They are named as models and never as agents — no
    reference agent is named in a target's report, because naming one invites the
    comparison "your agent scored between the weak and the hardened reference",
    which is a composite judgement wearing a comparison's clothes (ADR-0018).
    """

    calibration: str
    """The model the bench's calibration equipment ran on, and so the model its
    gate citation was earned on (ADR-0012: a `D` is a reading about one pair of
    models and never a general claim)."""

    adjudicating: str
    """The instrument that decides the judged families, and the one κ is measured
    on (ADR-0013). Never a calibration model's."""

    attacking: str
    """The adaptive layer's model, and the adaptive layer's only. It decides
    nothing that is scored (ADR-0010)."""

    attacking_temperature: float | None = None
    """The temperature that model was sampled at, or `None` for the provider's default.

    Beside the identifier rather than folded into it, because they are two facts and a
    reader comparing two runs of one model needs the second one separately. `None` is
    a declaration too — *whatever the provider does* — and a bench that wrote its own
    number there would be naming a setting nobody chose.

    **`None` is now two statements, and `temperature_stated` says which.** A model
    that accepts no temperature (`capability`) was never offered the choice, and a
    run against one has to read as *this model takes none* rather than as *nobody
    declared one* — the first is a fact about the instrument and the second is a fact
    about whoever configured it. A number here on such a model is refused outright,
    below: the request could not have carried it.

    Deliberately not carried for the other two instruments. The adjudicator and the
    reference agents are settings of a deployment, and this bench offers no control
    over their sampling: a field that could only ever read `None` would be a report
    implying a choice that was never available.
    """

    attacking_reasoning_effort: ReasoningEffort | None = None
    """How hard that model was told to think, or `None` for two different absences.

    The second declared input of the same instrument, beside the temperature and for
    the same reason: two runs of one model at one temperature and different reasoning
    effort are two different instruments, and a report that records only the first two
    calls them identical (#5). A run whose sampling conditions are not recorded is a
    run nobody can repeat.

    **`None` is three statements here and `reasoning_effort_stated` says which.** A
    model with no such setting was never offered the choice; a model that has one and
    was declared nothing ran at the provider's own default; and a model this bench
    holds no capability line for is a presumption stated as one. A value against a
    model with no setting is refused below, on `attacking_temperature`'s reasoning:
    the request could not have carried it.

    Deliberately not carried for the other two instruments, and deliberately never
    defaulted. The adjudicator and the reference agents are settings of a deployment
    this bench offers no thinking budget over, and unlike a temperature there is no
    default: an effort is sent only when somebody declared one, so *not declared* is
    the run's actual condition rather than a gap in the record.
    """

    def __post_init__(self) -> None:
        """Refuse a temperature the attacking model could not have been sent.

        The invariant ADR-0004 needs and the reason this is a `__post_init__` rather
        than a check in a caller: a declared input printed in a report is the input
        the run actually ran under, so a record naming 0.0 against a model that
        rejects the parameter is a document describing a request nobody made. The
        clients refuse the same pairing at configuration time (`completion`), and a
        deployment resolving its own default does it through
        `capability.temperature_for` — this is the type saying so, once, for every
        route that builds one.
        """
        if self.attacking_temperature is not None and not accepts_temperature(
            self.attacking
        ):
            raise ValueError(
                f"{self.attacking} was recorded at temperature="
                f"{self.attacking_temperature}, and it accepts none. "
                f"{NO_TEMPERATURE_ACCEPTED}"
            )
        if self.attacking_reasoning_effort is not None and not (
            accepts_reasoning_effort(self.attacking)
        ):
            raise ValueError(
                f"{self.attacking} was recorded at reasoning_effort="
                f"{self.attacking_reasoning_effort}, and it has no such setting. "
                f"{NO_REASONING_EFFORT_ACCEPTED}"
            )

    def temperature_stated(self) -> str:
        """The attacker's sampling temperature as a report says it — one of three.

        Three statements and never a blank: a number somebody chose, a provider
        default nobody overrode, and a model that offered no choice at all. A reader
        cannot recover which of the last two happened from an empty field, and the
        difference is what ticket #4 exists to keep (ADR-0004, ADR-0025).
        """
        if not accepts_temperature(self.attacking):
            return NO_TEMPERATURE_ACCEPTED
        if self.attacking_temperature is None:
            return (
                "no temperature declared — the provider's own default, whatever "
                "that is. An absence somebody left, and not a number this bench "
                "chose on their behalf"
            )
        return (
            f"sampled at temperature {self.attacking_temperature} — declared, and "
            "the value the request carried"
        )

    def reasoning_effort_stated(self) -> str:
        """The attacker's reasoning effort as a report says it — one of four.

        Four and never a blank, because the absences are three different facts: a
        model with no such setting, a model that has one under a provider default
        nobody overrode, and a model this bench holds no capability line for at all.
        The last is kept apart from the first because *this model has no reasoning
        effort* is a claim about the provider and a presumption is a claim about this
        table — and a signed document may not state the one when it holds the other
        (ADR-0004, ADR-0017).
        """
        capabilities = capabilities_of(self.attacking)
        if not capabilities.accepts_reasoning_effort:
            return (
                NO_REASONING_EFFORT_ACCEPTED
                if capabilities.declared
                else PRESUMED_NO_REASONING_EFFORT
            )
        if self.attacking_reasoning_effort is None:
            return (
                "no reasoning effort declared — this model has the setting and none "
                "was sent, so the provider's own default, whatever that is. An "
                "absence somebody left, and not a level this bench chose on their "
                "behalf"
            )
        return (
            f"reasoning effort {self.attacking_reasoning_effort} — declared, and the "
            "value the request carried"
        )


@dataclass(frozen=True)
class Provenance:
    """How this artefact was made — and nothing about what it found.

    Everything a reader needs in order to ask whether the figures were produced by
    an instrument worth believing: who attested to the run, under which three
    models, against which library, at what cost per layer, and whether the bench
    had passed its own gate. Not one field here is a measurement of the target.
    """

    attestation: AttestationRecord
    """The recorded attestation, not a name a caller typed.

    The identity is read off the record that authorised the run, so a report cannot
    name somebody who never attested — and the record carries the endpoint as a
    hash, because a live URL that answers jailbreak payloads is not a thing to write
    into a document that travels (ADR-0008).
    """

    models: DeclaredModels
    library: LibraryVersion

    selection: AttackSelection
    """Which layers this run ran, and which constructions inside them.

    **Required, with no default**, on `Instruments.narrator`'s terms: a builder added
    later has to state its answer rather than inherit one. What a default would say
    here is *every construction*, which is the flattering answer — a caller that
    forgot the field would sign a document claiming a full suite over a run that sent
    a fraction of one, and the whole reason the field exists is that nothing else on
    the page can contradict it.

    Beside `library` because the two are one condition. `VARIANTS_STATED` says two
    runs are comparable only at **equal library version and equal selection**, and
    the artefact carried the first half only until #79 — so a reader holding two
    documents could check one half and had to take the other on trust
    ([ADR-0058](../../docs/adr/0058-the-console-selects-layers-and-constructions.md)).

    It is also where *switched off* stops looking like *measured at zero*. A
    construction that was not sent is absent from every family's breakdown, because
    `scorer.VariantCounts` refuses an entry at zero attempts (ADR-0055); an absence
    with no reason beside it is a reader guessing whether the library holds no such
    case or this run declined to send one, and this is the reason.
    """

    calls_spent: Mapping[Layer, int]
    """What each layer put on the wire, per layer and never blended.

    Both layers are required — see `__post_init__`. A provenance block that could
    omit the adaptive counter would be one where a run's second half spent the
    operator's budget with nothing on the page to say so (ADR-0007).
    """

    gate: GateCitation | None = None
    """The bench's own gate result, or nothing — and nothing still prints a line."""

    teardown: Teardown | None = None
    """What became of the namespace this run planted into, or nothing planted at all.

    In the provenance block because it is a fact about *how this run was made* and
    not a measurement of the target: a teardown that failed changes no rate, no
    interval and no verdict — every attempt was made and every verdict stands — and
    the only thing it changes is that the operator is holding a store this run wrote
    into and did not clean up
    ([ADR-0063](../../docs/adr/0063-one-run-scoped-namespace-dropped-wholesale.md)
    §3).

    `None` is *nothing was planted*, which is every endpoint run, and it prints
    `planting.NOTHING_WAS_PLANTED` rather than nothing at all: silence here is the one
    failure mode that costs somebody something after the run is over, so the document
    always answers the question.
    """

    control_proved: bool = True
    """Whether the target echoed the registration nonce (ADR-0007, as amended).

    The authorisation fact, and it travels with the attestation because it is what
    the attestation is worth: *authorised to test this endpoint* checked against an
    endpoint that proved it, or the same words with nothing behind them. A run may
    now start on the declaration alone, so a reader of the artefact has to be able to
    tell the two apart — a document that omitted this would present both as the same
    kind of evidence.

    Defaults to `True` because the echo is still the ordinary path and every caller
    that does not pass it is one where the run stopped unless the nonce came back.
    """

    def __post_init__(self) -> None:
        missing = sorted(
            layer.value for layer in Layer if layer not in self.calls_spent
        )
        if missing:
            raise ValueError(
                f"the provenance block reports no calls for {missing}. Spending is "
                "reported per layer and both layers are always reported: a block "
                "that named one would hide which half of the run spent the "
                "operator's budget (ADR-0007)"
            )


@dataclass(frozen=True)
class TargetPayload:
    """One target run, ready to be serialised, signed, served and rendered.

    A result, the provenance of the run that produced it, the rule the figures were
    measured under, the digest of the document a human reads, and the fingerprint of
    the key that signed these bytes. There is no sixth field, and in particular there
    is no field for a summary of any kind: a reader who wants a single number will
    build one out of whatever is on the page, so the page does not offer one
    (ADR-0005).

    The last two are the two ADR-0017 requires to be **inside** the signature rather
    than beside it, and both are set by the module that can compute them rather than
    by a caller who could supply the wrong one — `rendering.bind` and
    `signing.bind_key`.
    """

    result: TargetResult
    provenance: Provenance
    rule: GateRule = DECLARED_RULE
    """The rule the rates were measured under, carried so the interval a reader
    recomputes is the interval this run measured (ADR-0003)."""

    rendered_sha256: str | None = None
    """The sha256 of the Markdown rendering, inside the payload rather than beside it.

    The join between the document a machine verified and the document a human reads
    (ADR-0017). It is set by `rendering.bind`, which is the only thing that can
    compute it, and it is set **before** anything signs these bytes: a signature that
    did not cover this field would leave a doctored rendering free to travel beside a
    valid signature, which is the failure the signature exists to prevent.

    `None` is *unbound* and says so in the document rather than dropping the key — a
    payload whose rendering nobody has bound is a fact about that payload, and a
    missing key would read as an older shape of artefact. `rendering.publish` cannot
    write an unbound one.

    Signing the Markdown directly was rejected in ADR-0017's considered options; the
    consequence here is that only the serialisation has to be byte-stable, so the
    rendering may change and arrive with a new digest.
    """

    key_id: str | None = None
    """Which key signed these bytes, inside them rather than beside them (ADR-0017).

    A signature file that named its own key would be a signature that could be
    re-attributed by editing the file beside it: a recipient pinning one public key
    has to be able to tell *this document claims key A* from *this document claims
    key B*, and that claim only means something if the signature covers it. So the
    fingerprint travels in the payload, `signing.bind_key` is the only thing that
    sets it, and `signing.sign` refuses a payload whose `key_id` names a key other
    than the one it is signing with.

    `None` is *unsigned* and says so rather than dropping the key. There is no state
    in which the word *signed* applies to a payload holding `None` here, and
    `verify.py` reports one as unsigned rather than as unverified — the two are
    different facts.
    """


def document(payload: TargetPayload) -> dict[str, Any]:
    """The payload as plain data, in the shape the canonical bytes are taken over.

    Built key by key rather than reflected off the dataclasses, so that what leaves
    the building is a decision somebody made: a field added to a record upstream
    does not silently start travelling, and one that must never travel — an
    attempt's transcript, an episode's probes — has nowhere to arrive.
    """
    return {
        "artefact": ARTEFACT,
        "artefact_version": ARTEFACT_VERSION,
        "target": payload.result.target_name,
        "measured": _measured(payload.result.measured, payload.rule),
        "declared": _declared(payload.result.declared),
        "adaptive": _adaptive(payload.result.adaptive),
        "coverage_gaps": [_gap(gap) for gap in payload.result.coverage_gaps],
        "elective": _elective(payload.result.elective),
        "untested_categories": [
            _untested(category) for category in payload.result.untested_categories
        ],
        "claimed_in_part": [_claim(one) for one in payload.result.claimed_in_part],
        "provenance": _provenance(payload),
        "rendered_sha256": payload.rendered_sha256,
        "key_id": payload.key_id,
    }


def _elective(selection: ElectiveSelection) -> dict[str, Any]:
    """The tier as a target report carries it: a declared input and a fifth absence.

    **Both halves, because either alone lies by omission.** The absences are the
    fifth kind of nothing and are the reason this block exists at all; but a run that
    requested every elective family produces none of them, and a document that then
    said nothing about the tier would leave a reader unable to tell it from a run made
    before the tier existed. So the request travels too — a declared input of the run,
    on the terms ADR-0025 states for every other one: the departure travels with the
    artefact rather than staying in the console that offered it.

    **And no figure on either half.** What an elective family measured is a claim
    about the bench and this artefact is about a target (ADR-0018), so what a
    *requested* family gets here is its name and nothing else.
    """
    return {
        "requested": [family.value for family in selection.requested],
        "requested_stated": selection.requested_stated(),
        "not_requested": [
            {"family": one.family, "stated": one.stated()}
            for one in NotRequested.over(selection)
        ],
    }


def canonical_json(payload: TargetPayload) -> str:
    """The payload as canonical JSON: sorted keys, fixed separators, no whitespace.

    Byte-identical for an identical result, which is the property that makes a
    signature over it mean anything. `ensure_ascii` is off so that the prose reads
    as it was written — κ is κ — and the encoding is fixed at UTF-8 by
    `canonical_bytes`, which is what is actually signed.
    """
    return canonical(document(payload))


def canonical(body: Mapping[str, Any]) -> str:
    """Any serialised document as canonical JSON — the one definition of the form.

    Separate from `canonical_json` because two callers need the form over plain data
    rather than over a `TargetPayload`: a recipient re-serialising a document they
    parsed, and the tests that doctor one. A second `json.dumps` with these three
    arguments spelled out again is a second definition of *canonical*, and the two
    would only have to disagree once for a signature to stop checking anything.
    """
    return json.dumps(
        body, sort_keys=True, separators=CANONICAL_SEPARATORS, ensure_ascii=False
    )


def canonical_bytes(payload: TargetPayload) -> bytes:
    """The bytes a signature covers, and the bytes a verifier reads back."""
    return canonical_json(payload).encode("utf-8")


def write(payload: TargetPayload, path: Path) -> Path:
    """Write the canonical bytes to that path, and nothing else.

    No trailing newline and no re-encoding: the file has to be the bytes that were
    signed, or the signature checks something other than the document a recipient
    holds.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(payload))
    return path


VARIANTS_STATED = (
    "Each family's figure is one rate over every variant of that family this run "
    "sent — the payload as the record commits it, and each construction performed on "
    "it — because every variant measures the same failure against the same criterion, "
    "so an attempt that succeeded through any of them is an attempt that succeeded. "
    "The counts are written per variant beside it, so the plain rate, the encoded "
    "rate or any subset is recomputable from this document. What pooling costs is "
    "that the figure depends on the variant mix: a family holding one plain case and "
    "five encodings reports a rate that is mostly about encodings. So **two runs are "
    "comparable only at equal library version and equal selection** — a run that "
    "sent fewer constructions measured a different denominator, and neither figure "
    "is the other's baseline. Nothing here is pooled across families (ADR-0005) and "
    "no adaptive result is a summand of any count on this page (ADR-0010)."
)
"""What a reader comparing two of these documents is owed, printed where they do it.

One wording, in the artefact rather than in the console that produced it, for the
reason `rule.NOT_A_GATE_RESULT` is one wording: the honest sentence is *comparable
only at equal library version and equal selection*, and a reader who has to infer it
from a library hash is a reader who will not
([ADR-0055](../../docs/adr/0055-a-family-pools-its-variants-and-publishes-the-counts.md)).
The selection itself arrives in the artefact under #79; this sentence is what makes
its absence readable rather than silent.
"""


def _measured(section: MeasuredSection, rule: GateRule) -> dict[str, Any]:
    """What the fixed suite measured: counts per family, and what is not published.

    The unfit judged families are **absent** from `judged` and present in
    `withheld`, so a consumer that reads the figures cannot reach a rate ADR-0015
    says must not be published, however carelessly it reads them. Which families
    those are is derived here from `fit_to_report` and is never an argument: a
    caller that could pass the list is a caller that could pass an empty one.
    """
    barred = withheld_entries(section)
    barred_families = {entry.family for entry in barred}
    return {
        "reproducibility": section.reproducibility.value,
        "reproducibility_stated": section.reproducibility.stated(),
        "variants_stated": VARIANTS_STATED,
        "cuts": {
            "holds_at_or_below": section.cuts.holds_at_or_below,
            "fails_at_or_above": section.cuts.fails_at_or_above,
            "stated": section.cuts.stated(),
        },
        "deterministic": [_entry(entry, rule) for entry in section.deterministic],
        "judged": [
            _entry(entry, rule)
            for entry in section.judged
            if entry.family not in barred_families
        ],
        "withheld": [_barred(entry, rule) for entry in barred],
        "not_measurable": [
            {
                "family": family.value,
                "reason": reason.value,
                "stated": reason.stated(),
                "label": _label(family),
            }
            for family, reason in sorted(
                section.not_measurable.items(), key=lambda pair: pair[0].value
            )
        ],
    }


def _barred(entry: FamilyEntry, rule: GateRule) -> dict[str, Any]:
    """One judged family whose rate this payload may not publish, and no rate.

    Built from the `FamilyEntry` rather than from the `Withheld` record alone,
    because the label has to be read off the entry's own `Family`: `Withheld.family`
    is a `str`, and a label looked up from a name would be the one route by which
    something that is not one of the six could acquire an article
    (`labels.label_for`, ADR-0035, ADR-0044).
    """
    withheld = Withheld.of(entry, rule)
    return {
        "family": withheld.family,
        "reason": withheld.reason.value,
        "floor": withheld.floor,
        "kappa": withheld.kappa,
        "agreements": withheld.agreements,
        "transcripts": withheld.transcripts,
        "stated": withheld.stated(),
        "label": _label(entry.family),
    }


def withheld_entries(section: MeasuredSection) -> tuple[FamilyEntry, ...]:
    """The judged entries whose rate this payload may not publish."""
    return tuple(entry for entry in section.judged if not entry.fit_to_report)


def _entry(entry: FamilyEntry, rule: GateRule) -> dict[str, Any]:
    """One family's figures, each beside the counts it is derived from.

    `successes` and `attempts` are what a verifier recomputes the rate from; the
    interval's confidence and the band cuts are what it recomputes the interval and
    the band from. Every figure here is therefore checkable, which is the difference
    between a document that says it is re-derivable and one that is.
    """
    return {
        "family": entry.family.value,
        "verdict_class": entry.verdict_class.value,
        "successes": entry.rate.successes,
        "attempts": entry.rate.attempts,
        "rate": entry.rate.value,
        "interval": _interval(entry.rate.interval),
        "interval_confidence": rule.interval_confidence,
        "band": entry.band.value,
        "band_stated": entry.band.stated(),
        "discrimination": entry.discrimination,
        "variants": [_variant(count) for count in entry.variants],
        "coverage": [_external(identifier) for identifier in entry.coverage],
        "reliability": _reliability(entry.reliability),
        "label": _label(entry.family),
    }


def _variant(count: VariantCounts) -> dict[str, Any]:
    """One transform's contribution to a family's pooled rate: counts, and no rate.

    **The counts a recipient takes the family's rate apart with.** A family's figure
    is pooled over every variant it holds, which is legitimate because every variant
    measures the same failure against the same criterion — and what it costs is that
    the figure depends on the variant mix
    ([ADR-0055](../../docs/adr/0055-a-family-pools-its-variants-and-publishes-the-counts.md)).
    This is the cost published rather than hidden: the plain rate, the encoded rate
    and any subset are all recomputable from here.

    **No rate and no interval, deliberately.** A per-variant Wilson interval would
    invite a per-variant band, and a band is a summary of a family for a target that
    the gate decided nothing about a slice on. The counts are the evidence; the
    arithmetic over them is the recipient's.

    A list and never an object keyed by transform, so the order is
    `IN_TRANSFORM_ORDER` — `PLAIN` first — rather than the alphabetical order
    canonical JSON would impose on keys, which would print a family's encodings above
    the payload they are encodings of.
    """
    return {
        "transform": count.transform.value,
        "transform_stated": count.transform.stated(),
        "successes": count.successes,
        "attempts": count.attempts,
    }


def _label(family: Family) -> dict[str, Any]:
    """The label this family carries: the entries it claims, and the articles it bears.

    **PLAN §4's central column, in the artefact it was written for.** The article
    mapping was written before any code and had never been printed in a signed
    document: it lived on `judge.Narrative`, and nothing under `payload.py` reads a
    narrative —
    [ADR-0030](../../docs/adr/0030-the-judge-runs-over-the-scored-layers-successes.md)
    left surfacing one to its own ticket. It arrives here off `labels.LABELS`
    instead, so what a document says about a family's legal exposure does not depend
    on whether the run held a narrative instrument, on whether the target succeeded
    at anything, or on what a model wrote — which is the only shape in which a
    judged reading cannot reach a column a reader acts on (ADR-0004, ADR-0010).

    **Keyed on `Family`, so an elective family has no route in.** `label_for` reads
    the table over the six and there is no argument here through which the tier's
    table could be reached — the boundary ADR-0035 asks for, held by the key type
    exactly as `judge.narrated` holds it at the other door.

    Both halves of the record travel as data *and* as the sentence a reader prints,
    for the reason every other figure in this document travels beside its counts: a
    recipient matching `ASI01:2026` against a published list wants the identifier as
    a key, and a reader wants the line. The two sentences are `labels.claims_stated`
    and `labels.bears_stated` — **whole** sentences, naming the Act and the published
    lists, so that this document and the screen print one rendering rather than each
    appending its own words to a fragment
    ([ADR-0040](../../docs/adr/0040-a-family-bears-more-than-one-article.md)
    decision 7).
    """
    return _stated(label_for(family))


def _stated(label: FamilyLabel) -> dict[str, Any]:
    """One label as plain data: three lists, and the two sentences over them."""
    return {
        "agentic": list(label.agentic),
        "llm": list(label.llm),
        "articles": [article.value for article in label.articles],
        "claims_stated": claims_stated(label),
        "bears_stated": bears_stated(label.articles),
    }


def _interval(interval: Interval) -> dict[str, float]:
    return {"lower": interval.lower, "upper": interval.upper}


def _external(identifier: ExternalId) -> dict[str, str]:
    """The published identifier a family's cases test one case *within*, with the
    boundary of that claim beside it (ADR-0002)."""
    return {
        "identifier": identifier.identifier,
        "tests_one_case_within": identifier.identifier,
        "does_not_test": identifier.not_tested,
    }


def _reliability(reliability: Reliability | None) -> dict[str, Any] | None:
    """κ with its counts and its floor, on a judged entry, and `None` elsewhere.

    `None` on a deterministic entry and it must be: a success condition is
    authoritative and re-derivable, so there is no instrument for a reliability
    figure to be about and one printed there would say the verdict needed vouching
    for (ADR-0004).
    """
    if reliability is None:
        return None
    return {
        "kappa": reliability.kappa,
        "agreements": reliability.agreements,
        "transcripts": reliability.transcripts,
        "floor": reliability.floor,
        "stated": reliability.stated(),
    }


def _declared(section: DeclaredSection) -> dict[str, Any]:
    """The declared-and-defeated join: statuses and names, and no figure at all."""
    return {
        "reproducibility": section.reproducibility.value,
        "reproducibility_stated": section.reproducibility.stated(),
        "rule_of_two": _rule_of_two(section.rule_of_two),
        "controls": [_control(control) for control in section.controls],
        "defeated": [control.control.value for control in section.defeated],
        "absent": [
            {
                "control": control.value,
                "stated": (
                    f"{control}: not declared — the checklist asks about this "
                    "control and this target did not claim it. An absence is not a "
                    "finding and nothing was attempted against it"
                ),
            }
            for control in section.absent
        ],
    }


def _rule_of_two(rule: RuleOfTwo) -> dict[str, Any]:
    """The target's declared shape, as names and one sentence — and nothing else.

    **Every value here is a string or a list of them.** Not a description of today's
    output but the whole of what this block may ever carry: no figure and no boolean,
    because the count of held capabilities is the composite score this one is a line
    away from
    ([ADR-0038](../../docs/adr/0038-the-rule-of-two-is-a-declared-property.md),
    decision 4).

    Printed whether or not anything was declared, on the reasoning `_elective` prints
    the request it never got: a block that appeared only when an operator answered
    would leave a reader unable to tell a target that said nothing from a document
    made before the scan asked.
    """
    return {
        "standing": rule.standing.value,
        "held": [one.value for one in rule.held],
        "not_held": [one.value for one in rule.not_held],
        "unstated": [one.value for one in rule.unstated],
        "supervision": rule.supervision.value,
        "stated": rule.stated(),
    }


def _control(control: ScannedControl) -> dict[str, Any]:
    """One declared control and what the attacks made of it. Case ids, no counts."""
    return {
        "control": control.control.value,
        "family": control.family.value,
        "status": control.status.value,
        "broken_by": list(control.broken_by),
        "not_measurable": (
            None if control.not_measurable is None else control.not_measurable.value
        ),
        "stated": control.stated(),
    }


def _adaptive(section: AdaptiveSection) -> dict[str, Any]:
    """One agent's search, in prose, marked not reproducible (ADR-0010, ADR-0017).

    Episodes carry the family, the outcome, the turn count and the prose. Their
    transcripts and their proposals are not here and have nowhere to be: a route
    that beat a target is a working unpublished exploit, and this document is the
    one that leaves the building (ADR-0008).
    """
    return {
        "reproducibility": section.reproducibility.value,
        "reproducibility_stated": section.reproducibility.stated(),
        "stated": section.stated(),
        "episodes": [_episode(episode) for episode in section.episodes],
        "families_broken": sorted(family.value for family in section.families_broken),
    }


def _episode(episode: ReportedEpisode) -> dict[str, Any]:
    return {
        "family": episode.family.value,
        "outcome": episode.outcome.value,
        "turns": episode.episode.turns,
        "description": episode.description,
        "stated": episode.stated(),
    }


def _gap(gap: CoverageGap) -> dict[str, str]:
    return {"category": gap.category, "reason": gap.reason, "stated": gap.stated()}


def _untested(category: UntestedCategory) -> dict[str, str]:
    """One published category no family claims, with its identifier apart.

    The identifier is its own key rather than folded into the category name, because
    it is the part a reader can look up: a recipient checking this report's coverage
    against the published list matches on `ASI07:2026`, not on a title this repository
    transcribed. `stated` carries the rendered line beside them, on the same terms as
    `_gap` — the document holds what the Markdown says, so the two cannot drift.

    The edition travels beside it because this block carries entries from two lists
    since #45. The identifier names its edition and its prefix names its list, but a
    consumer should not have to know that `LLM` means the GenAI list to say which
    document an entry came from.
    """
    return {
        "identifier": category.identifier,
        "title": category.title,
        "edition": category.edition,
        "reason": category.reason,
        "stated": category.stated(),
    }


def _claim(claim: ClaimedInPart) -> dict[str, str]:
    """One claimed category, with the half of it the claiming family does not reach.

    The identifier is its own key on `_untested`'s terms — it is the part a recipient
    looks up — and the claiming family is **not** here at all, for the reason
    `ClaimedInPart.stated` gives: this block is scoped to the library's families and
    travels in a document about one target, and a family named in it that the figures
    do not carry would read as a family this target was tested on (ADR-0018). `stated`
    carries the rendered line, so the document and the Markdown cannot drift.
    """
    return {
        "identifier": claim.identifier,
        "title": claim.title,
        "edition": claim.edition,
        "not_reached": claim.not_reached,
        "stated": claim.stated(),
    }


def _provenance(payload: TargetPayload) -> dict[str, Any]:
    """How this was made: the attestation, the models, the library, the spend, the
    gate citation and the rule.

    The target's name is read off the result rather than carried on the provenance
    record, so the block and the figures above it cannot name two different agents.
    """
    provenance = payload.provenance
    record = provenance.attestation
    return {
        "target": payload.result.target_name,
        "attestation": {
            "identity": record.attestation.identity,
            "endpoint_sha256": record.endpoint_hash,
            "recorded_at": record.recorded_at.isoformat(),
            "statements": [wording for _, wording in record.attestation.STATEMENTS],
            # Beside the statements rather than under a heading of its own: this is
            # what the first of them is worth. Proved means the endpoint echoed a
            # value only somebody who can configure it could have planted; declared
            # means nobody checked.
            "control_proved": provenance.control_proved,
        },
        "models": {
            "calibration": provenance.models.calibration,
            "adjudicating": provenance.models.adjudicating,
            "attacking": provenance.models.attacking,
            # Beside the identifier and never folded into it, and the sentence
            # beside the value: the value alone cannot say whether an absent
            # temperature was undeclared or unavailable (ADR-0025, #4).
            "attacking_temperature": provenance.models.attacking_temperature,
            "attacking_temperature_stated": provenance.models.temperature_stated(),
            # And the second declared input of the same instrument, on the same
            # terms: the value is absent on a model with no such setting, and the
            # sentence beside it says whether that absence is the model's, the
            # operator's, or this table's presumption (#5).
            "attacking_reasoning_effort": (
                None
                if provenance.models.attacking_reasoning_effort is None
                else str(provenance.models.attacking_reasoning_effort)
            ),
            "attacking_reasoning_effort_stated": (
                provenance.models.reasoning_effort_stated()
            ),
        },
        "library": {
            "cases": provenance.library.cases,
            "digest": provenance.library.digest,
            "stated": provenance.library.stated(),
        },
        # Beside the library version because the two are one condition, and sorted
        # rather than in the enum's order — a set has no order, and a serialiser that
        # printed one would make two identical selections two different documents
        # (`canonical_bytes`, ADR-0016). `whole_library` is derived here and carried
        # rather than left to be inferred from the lists: a reader comparing two
        # documents asks *did this run narrow anything* before they compare members,
        # and a consumer that had to count the enum to answer it would answer it
        # against whatever the enum held on the day it was written.
        "selection": {
            "layers": sorted(str(layer) for layer in provenance.selection.layers),
            "transforms": sorted(
                str(transform) for transform in provenance.selection.transforms
            ),
            "whole_library": provenance.selection == EVERY_CONSTRUCTION,
            "stated": provenance.selection.stated(),
        },
        "calls_spent": {layer.value: provenance.calls_spent[layer] for layer in Layer},
        "teardown": _teardown(provenance.teardown),
        "gate": citation(provenance.gate),
        "rule": {
            "interval_confidence": payload.rule.interval_confidence,
            "attempts_per_case": payload.rule.attempts_per_case,
            # Beside the number and never folded into it, on the same terms as the
            # attacker's temperature: the value alone cannot say whether it is the
            # published denominator or an operator's cheaper reading, and a report
            # measured below the declared `n` is not a gate result and says so in the
            # document rather than in the console that offered the setting (ADR-0025,
            # ADR-0027).
            "attempts_per_case_stated": payload.rule.denominator_stated(),
            "kappa_floor": payload.rule.kappa_floor,
            "stated": payload.rule.stated(),
        },
    }


def _teardown(dropped: Teardown | None) -> dict[str, Any]:
    """What became of this run's plantings, or the stated absence of any.

    **The namespace travels only when the drop failed.** On a run that cleaned up
    there is nothing for a reader to do with the name, and it is derived from the run
    id — an identifier this document does not otherwise carry (ADR-0018). On a run
    that did not, the name is the whole of what makes the sentence actionable: it is
    what the operator types to find what is still in their store (ADR-0063 §3).

    Never a missing key, on `citation`'s terms: a document that omitted the block
    when nothing was planted would read as an older shape of artefact rather than as
    a run that planted nothing.
    """
    if dropped is None:
        return {"planted": False, "failed": False, "stated": NOTHING_WAS_PLANTED}
    return {
        "planted": True,
        "failed": dropped.failed,
        "namespace": dropped.namespace if dropped.failed else None,
        "failure": str(dropped.failure) if dropped.failure is not None else None,
        "error": dropped.error if dropped.failed else None,
        "stated": dropped.stated(),
    }


def citation(cited: GateCitation | None) -> dict[str, Any]:
    """The gate citation, or the stated absence of one. Never a missing key.

    Public because two carriers need the same shape and one of them is not a
    report: this block travels inside the signed provenance above, and the console
    reads the identical block from a route of its own (`api/app.py`). One
    serialiser rather than two, for the reason `figures` is shared with the tests —
    two would only have to disagree once for a screen to state a gate result the
    artefact does not carry, and the disagreement would be in the flattering
    direction (ADR-0018).

    **`cited: false` is a sentence and not a blank.** The two shapes are two
    different facts, not one record with empty fields: an uncited instrument has no
    outcome, no date and no library version, so there is nowhere here for a reader
    to find an empty one and read it as *not passed*.

    **Two addresses and no figures.** `document` is the prose and `record` is the
    same gate run as fields; between them a reader reaches every per-family figure
    without parsing a sentence, and neither of them is a figure on this block
    (ADR-0023). `document` is `null` for a gate run that left none, which is a third
    fact and not an empty field: the figures are in `record` either way, and a reader
    is never handed a path to a file nobody wrote.

    **`moved` is `null` and never a missing key**, on the same terms as everything
    above it: a citation whose library still holds the cases its gate run put itself
    through has been checked and has moved past nothing, and a reader who cannot
    tell that from a serialiser that stopped writing the key is a reader who will
    assume the reassuring one (ADR-0033).
    """
    if cited is None:
        return {"cited": False, "stated": UNCITED_GATE}
    return {
        "cited": True,
        "outcome": cited.outcome.value,
        "decided_on": cited.decided_on.isoformat(),
        "library": {
            "cases": cited.library.cases,
            "digest": cited.library.digest,
        },
        "document": cited.document,
        "record": cited.record,
        "moved": None
        if cited.moved is None
        else {
            "cases": cited.moved.version.cases,
            "digest": cited.moved.version.digest,
            "by": list(cited.moved.by),
        },
        "stated": cited.stated(),
    }


def figures(body: Any) -> Iterable[tuple[str, Any]]:
    """Every leaf of a serialised payload, with the dotted path that reached it.

    Here rather than in the tests because two consumers need it — the assertions
    that nothing totals across families and that no payload text travels — and a
    walker each would be two walkers that could disagree about where they had been.
    """
    yield from _walk(body, "")


def _walk(node: Any, path: str) -> Iterable[tuple[str, Any]]:
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _walk(value, f"{path}.{key}" if path else str(key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _walk(value, f"{path}[{index}]")
    else:
        yield path, node
