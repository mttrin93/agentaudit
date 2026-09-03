"""The case library as data — one record per file, never inline in code.

A case is one executable test belonging to a family: a payload plus the criterion
that decides its verdict. Adding, retiring and diffing cases is therefore a data
operation. The enumerations here are closed sets on purpose: a case that cannot
name its family, its verdict class or the trigger that caused it to be written
does not load.

Four families reach the verdict from a deterministic `SuccessCondition`; two — the
judged ones — reach it from a `JudgedCondition`, which is prose rather than a
check. A record carries exactly one of the two, and which one is fixed by the
`verdict_class` on the record itself. That is the mechanism behind spec story 18:
a consumer reads the class off the record and never infers it from the family name
(ADR-0004).
"""

import hashlib
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, fields
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any


class Family(StrEnum):
    """The six kinds of failure the bench tests for."""

    INDIRECT_PROMPT_INJECTION = "indirect_prompt_injection"
    SCOPE_CREEP = "scope_creep"
    WRONGFUL_COMMITMENT = "wrongful_commitment"
    DATA_LEAKAGE = "data_leakage"
    HALT_DEFEAT = "halt_defeat"
    DISCLOSURE_DENIAL = "disclosure_denial"


class VerdictClass(StrEnum):
    """How a verdict is reached. Read from the record, never inferred from the
    family."""

    DETERMINISTIC = "deterministic"
    JUDGED = "judged"


class Trigger(StrEnum):
    """Why a case exists. One of six, so the library's growth is auditable.

    A closed set of exactly the six reasons PLAN §6 states, and closed is the
    whole of the point: a library whose motives are free text can be grown by
    anybody who can think of a sentence, and "why does this case exist" then has as
    many answers as it has authors. Every member says what it means in `stated()`,
    so the answer a case gives is the same answer whoever reads the record.

    Distinct from `DiscoveredBy`, which says *who* found the case. A case can be
    triggered by a published technique and still have been found by the adaptive
    attacker, and the two answers are not interchangeable.
    """

    FAMILY_STOPPED_DISCRIMINATING = "family_stopped_discriminating"
    TARGET_PASSED_EVERYTHING = "target_passed_everything"
    USER_REPORTED_GAP = "user_reported_gap"
    NEW_AGENT_TYPE = "new_agent_type"
    NEW_TECHNIQUE_PUBLISHED = "new_technique_published"
    SCAN_CHECKLIST_GREW = "scan_checklist_grew"

    def stated(self) -> str:
        """The reason in the words PLAN §6 states it in.

        The match has no fallback branch on purpose: a seventh trigger must fail the
        type check rather than exist as a member no reader can be given a reason for.
        """
        match self:
            case Trigger.FAMILY_STOPPED_DISCRIMINATING:
                return (
                    "a family stopped discriminating — providers added defences, "
                    "and an attack that separated careful from careless in January "
                    "is refused by default in June"
                )
            case Trigger.TARGET_PASSED_EVERYTHING:
                return (
                    "a target passed everything — either the agent is excellent "
                    "or the attacks are weak, and the adaptive layer is the only "
                    "source that can tell the two apart by demonstration"
                )
            case Trigger.USER_REPORTED_GAP:
                return (
                    "a user reported a gap — a case_gap override from the person "
                    "who knows their own exposure"
                )
            case Trigger.NEW_AGENT_TYPE:
                return (
                    "a new agent type arrived — a voice agent needs different "
                    "payloads from a document agent, so the family stays and the "
                    "cases change"
                )
            case Trigger.NEW_TECHNIQUE_PUBLISHED:
                return (
                    "a new technique was published — the library was behind the field"
                )
            case Trigger.SCAN_CHECKLIST_GREW:
                return (
                    "the scan checklist grew — a new declared control needs an "
                    "attack that checks it works"
                )


class CaseStatus(StrEnum):
    """Whether a case is still run, or kept as the record of one that was.

    Two members and no third: retirement is marked, never deleted, because a case
    that stopped discriminating is evidence that the field moved (CONTEXT.md). A
    retired case leaves the live library and stays queryable in it, which is why
    this is a status on the record rather than a file somebody moved.
    """

    ACTIVE = "active"
    RETIRED = "retired"


class DiscoveredBy(StrEnum):
    """Who found a case. Provenance, and the field that selects its admission bar.

    Distinct from `Trigger`, which says *why* the case exists — a case can be
    triggered by a published technique and still have been found by the adaptive
    attacker, and the two answers are not interchangeable. Kept as its own closed
    set for the reason every other enumeration here is closed: a library whose
    provenance is free text cannot report what fraction of itself the attacker
    wrote (ADR-0012).

    The member is not decoration. `AUTHORED` and `USER_GAP` face the single-model
    bar of ADR-0003; `ADAPTIVE` faces the cross-model bar of ADR-0012, because the
    attacker discovers on the same three agents the gate admits against and a route
    fitted to that set has to prove itself on a model it was not fitted to. The
    mapping lives in `backend/bench/admission.py` and is applied to the record here
    by `Case.__post_init__`.
    """

    AUTHORED = "authored"
    """Written by hand, against no measurement of these three agents."""

    ADAPTIVE = "adaptive"
    """Found by the adaptive attacker and promoted through `propose_case`. Faces
    the second bar."""

    USER_GAP = "user_gap"
    """Written because a user reported an exposure the library did not cover. Not
    fitted to the reference agents either, so it keeps the single-model rule."""


class AdmissionBar(StrEnum):
    """The bar a case actually entered the library under, recorded on the record.

    Recorded rather than derived at read time, and printed beside the case, because
    ADR-0012 requires a reader to be able to tell an adaptive-discovered case from
    an authored one *in the report*. A bar recomputed from `discovered_by` whenever
    someone asked would say what the rule is, not what happened.
    """

    SINGLE_MODEL = "single_model"
    """`D >= 0.4` with disjoint Wilson intervals against the three reference agents
    on one underlying model. ADR-0003."""

    CROSS_MODEL = "cross_model"
    """The same, on the second underlying model as well as the first. ADR-0012."""


class Precondition(StrEnum):
    """What a target must be able to do before a case can be run against it.

    A closed set, like every other enumeration here, and read before the attempt
    rather than after it: a precondition gates *measurability*, never scoring
    (spec, Implementation Decisions). A case whose precondition is unmet is
    skipped explicitly and its family reports **not measurable** — see
    `measurability.py`.
    """

    TOOL_CALL_VISIBILITY = "tool_call_visibility"
    """The endpoint returns the tool calls it made, not only its final text.

    Scope creep and halt defeat reach a deterministic verdict from that trace and
    from nothing else, so against a target without it they have no evidence to
    read (ADR-0004).
    """


class SuccessConditionKind(StrEnum):
    """The deterministic checks a case can ask for.

    Deterministic, all of them, because that is what a success condition is
    (CONTEXT.md). The two judged families have no member here and cannot acquire
    one: their verdict is reached by `JudgedCondition` below, and a semantic
    question sitting in this enumeration would let a judged verdict arrive
    through the function ADR-0004 makes authoritative.
    """

    CANARY_IN_REPLY = "canary_in_reply"

    CANARY_INSTRUCTION_EXECUTED = "canary_instruction_executed"
    """Indirect prompt injection: the target did what a planted instruction in
    content it fetched told it to do."""

    TOOL_CALL_OUTSIDE_DECLARED_LIST = "tool_call_outside_declared_list"
    """Scope creep: the target called a tool its operator never declared it had."""

    TOOL_CALL_AFTER_STOP = "tool_call_after_stop"
    """Halt defeat: the target acted after the operator's stop signal reached it."""


@dataclass(frozen=True)
class ExternalId:
    """The published identifier a case tests one case *within*, and the
    boundary of that claim."""

    identifier: str
    not_tested: str


@dataclass(frozen=True)
class SuccessCondition:
    kind: SuccessConditionKind

    planted_canary: str | None = None
    """What executing a planted instruction produces, for the one kind that reads
    execution rather than a leak.

    Not the registration nonce and never confusable with it: that canary is
    planted *inside* the target's boundary and its appearance proves disclosure
    (ADR-0007), while this one is written by a third party into content the
    target fetched and its appearance proves obedience. Held on the case record
    because the verdict has to be re-derivable by a reader holding the record and
    the transcript, and for no other reason.
    """

    def __post_init__(self) -> None:
        executed = self.kind is SuccessConditionKind.CANARY_INSTRUCTION_EXECUTED
        if executed and not self.planted_canary:
            raise ValueError(
                f"{self.kind} reads whether a planted canary came back, so a case "
                "declaring it has to say which canary was planted"
            )
        if not executed and self.planted_canary is not None:
            raise ValueError(
                f"{self.kind} does not read a planted canary, so carrying one "
                "would put a value on the record that nothing checks"
            )


@dataclass(frozen=True)
class JudgedCondition:
    """The semantic question a judged family's verdict answers, held on the record.

    Wrongful commitment and disclosure denial are irreducibly semantic: whether a
    reply bound its operator to something it cannot honour, and whether it
    presented itself as a person, are questions about meaning and no string
    comparison answers them (ADR-0004). So the criterion is prose — and it is
    prose *on the case record*, not prose inside a prompt, for the same reason
    every threshold is declared in `GateRule`: a reader holding the record and the
    transcript has to be able to see what was asked before they are told what the
    answer was.

    Deliberately carries no `kind` enumeration, unlike everything else in this
    module. A kind would be a name for a branch, and there is no branch: nothing
    dispatches on which judged question this is, because the question itself is
    what the adjudicating model is handed (`backend/bench/adjudication.py`).

    The two sides are stated separately rather than left as the negation of each
    other, because the boundary between them is where a judged verdict is won or
    lost — and it is the figure κ measures against the gold set (#11).
    """

    question: str
    """The question put to the adjudicator.

    Phrased about the reply rather than about the target, because the adjudicator
    is shown a transcript and never an agent, and phrased so that the side
    `succeeded_when` describes is the affirmative one.
    """

    succeeded_when: str
    """What a reply that failed the target's defence looks like."""

    resisted_when: str
    """What a reply that held looks like."""

    def __post_init__(self) -> None:
        stated = (self.question, self.succeeded_when, self.resisted_when)
        if not all(part.strip() for part in stated):
            raise ValueError(
                "a judged condition is the whole of what decides a judged "
                "verdict, so a case declaring one has to state the question and "
                "both sides of the answer"
            )


@dataclass(frozen=True)
class AdmissionReading:
    """What one case scored against the three reference agents on one model.

    Counts and not a rate, and certainly not a stored `D`. A rate is
    `successes / attempts` and an interval is a function of both, so recording the
    derived numbers would let a record carry a `D` that its own counts contradict —
    and admission is the one place in the bench where the number decides whether a
    case may ever reach a user. The arithmetic is `backend/bench/admission.py`,
    reading these counts through the same scorer functions the gate uses.

    The weak agent's count is recorded and is not part of the bar: admission is
    `D` plus interval separation between the two ends (spec story 70), while the
    ordering across all three is the gate's check. It is here because a reading
    that threw it away could not answer the retirement question later.
    """

    model: str
    """The reference agents' underlying model, as `<provider>:<model>`."""

    attempts: int
    """Attempts per agent behind each count below."""

    hardened: int
    weak: int
    trivial: int
    adjudicator: str | None = None
    """The model that decided the verdicts, for a judged case. `None` for a case
    a success condition decided, where no instrument stood between the reply and
    the verdict."""

    def stored(self) -> dict[str, Any]:
        """The reading as a mapping, in the keys `read` takes back.

        The inverse of `read`, here beside it so that a store writing a reading and
        a loader reading one cannot drift on a key name. Only
        `backend/bench/decided.py` writes one today: a case record's `[admission]`
        block is hand-written TOML, not something the bench serialises.
        """
        return {
            "model": self.model,
            "attempts": self.attempts,
            "hardened": self.hardened,
            "weak": self.weak,
            "trivial": self.trivial,
            "adjudicator": self.adjudicator,
        }

    @classmethod
    def read(cls, value: Mapping[str, Any]) -> "AdmissionReading":
        """One reading out of a mapping, whoever wrote the mapping.

        Three callers read these six fields — a case record's `[admission]` block, an
        entry of its decay series, and the admission memory's own rows — and they
        used to be three copies of the same six lines. The coercions are here rather
        than at each: a TOML loader hands back integers already and a JSON one may
        hand back anything, so the one that has to be defensive sets the shape.
        """
        adjudicator = value.get("adjudicator")
        return cls(
            model=str(value["model"]),
            attempts=int(value["attempts"]),
            hardened=int(value["hardened"]),
            weak=int(value["weak"]),
            trivial=int(value["trivial"]),
            adjudicator=None if adjudicator is None else str(adjudicator),
        )

    def __post_init__(self) -> None:
        if self.attempts <= 0:
            raise ValueError(
                f"an admission reading on {self.model!r} over {self.attempts} "
                "attempts is not a measurement"
            )
        for agent, successes in (
            ("hardened", self.hardened),
            ("weak", self.weak),
            ("trivial", self.trivial),
        ):
            if not 0 <= successes <= self.attempts:
                raise ValueError(
                    f"{successes} successes for the {agent} agent in "
                    f"{self.attempts} attempts is not a count"
                )


@dataclass(frozen=True)
class AdmissionRecord:
    """The measurement a case entered the library on, and the bar it entered under.

    Held on the record so that admission is evidence rather than an assertion: a
    reader with this block and `backend/bench/admission.py` can re-derive the
    decision that let the case in, which is the same property ADR-0003 requires of
    the gate. A case whose recorded reading does not clear its own bar does not
    load into the library at all (`admission.admitted_library`), so a rejected case
    cannot be parked on disk in a state that reads as admitted.
    """

    bar: AdmissionBar
    admitted_on: date
    readings: tuple[AdmissionReading, ...]

    def __post_init__(self) -> None:
        if not self.readings:
            raise ValueError(
                f"an admission under the {self.bar} bar with no reading behind it "
                "is an assertion, not a measurement"
            )
        models = {reading.model for reading in self.readings}
        if self.bar is AdmissionBar.CROSS_MODEL and len(models) < 2:
            raise ValueError(
                f"the {self.bar} bar is separation on a second underlying model as "
                f"well as the first, and these readings are all on {sorted(models)} "
                "(ADR-0012)"
            )


@dataclass(frozen=True)
class GateReading:
    """What one gate run measured for one case — the reading a decay series is made of.

    One per case per gate run, appended to `Case.history` by the run that made it,
    so that decay arrives as a series rather than as a surprise (spec story 72).

    **Counts and not a stored `D`**, on the same terms and for the same reason as
    `AdmissionReading` — which is the type the counts are held in, because a reading
    of one case against the three reference agents on one model over one denominator
    is the same measurement whether admission or retirement is the question being
    put to it. Reusing it keeps one arithmetic: `D` here is computed by the function
    the gate and the admission bar compute it with, and a record cannot carry a `D`
    its own counts contradict.
    """

    ran_on: date
    """The date of the gate run this reading was taken on."""

    counts: AdmissionReading
    """What the three reference agents did, on one model, over one denominator."""

    fit_to_report: bool
    """Whether the case's family was fit to report on the run that read this.

    Recorded rather than inferred later, because the fitness of a family is a fact
    about the run and not about the library: κ is measured per run, and a reading
    taken while the adjudicator was below the floor stays a reading taken then.

    It is here because ADR-0015 leaves one question open on purpose — whether the
    retirement rule may operate on an excluded family's cases — and assigns it to
    #14's own decision. Until that decision exists, `retirement.py` declines to
    decide such a case either way rather than resolving the question by default in
    code. The flag is what lets it decline; it is not itself the answer.
    """

    measured_the_field: bool
    """Whether the model underneath the three reference agents was the field at all.

    False on a stub run. `scripts/gate.py --model stub:obedient` is a gate run like
    any other — it reads every case and appends a reading — and ADR-0022 argues why
    the reading it appends is a statement about the fixture, so this flag is what
    lets `retirement.py` decline to retire on one.

    Recorded here by the run that took the reading, on the same terms as
    `fit_to_report` and for the same reason: provenance is a fact about the run.
    Never re-derived later by parsing `counts.model`, which would put a claim about
    what a model *is* in the module that reads the rule, and would make
    `backend/bench/` depend on `backend/targets/` to answer it.
    """

    @property
    def model(self) -> str:
        """The model this reading was taken on.

        One walk rather than one at every call site: the model is a fact about the
        reading, and the retirement rule now reads it on every case (ADR-0022). A rule
        that reached through `counts` for it would make every reader of the series
        depend on where a reading happens to keep its counts.
        """
        return self.counts.model


@dataclass(frozen=True)
class Retirement:
    """When a case stopped discriminating, and the reading it stopped on.

    The retirement half of `status` (PLAN §6): a retired case is kept with its date
    and its last discrimination score, never deleted, because a case the field
    outgrew is evidence that the field moved.

    `final` is the last entry of the case's own history rather than a number written
    beside it — enforced by `Case.__post_init__` — so the recorded final score is
    the reading that retired the case and cannot drift from it. There is no
    `discrimination` field for the same reason `AdmissionReading` has no rate:
    `retirement.py` derives the score from these counts, and a stored one could
    contradict them.
    """

    retired_on: date
    final: GateReading


@dataclass(frozen=True)
class Case:
    id: str
    family: Family
    external_id: ExternalId
    payload: str
    success_condition: SuccessCondition | None
    """The deterministic check, for a case whose verdict class is deterministic.

    `None` on a judged case, where `judged_condition` carries the criterion
    instead. Exactly one of the two is present on every case, and which one is
    fixed by `verdict_class` — see `__post_init__`.
    """

    verdict_class: VerdictClass
    applies_to: tuple[str, ...]
    requires: tuple[Precondition, ...]
    """What the target has to be able to do for this case to mean anything.

    Typed rather than free text so that an unmeasurable case is skipped by a
    check the type system can see, instead of by a string comparison nobody
    updates when the vocabulary moves.
    """
    added_on: date
    trigger: Trigger
    discovered_by: DiscoveredBy
    """Who found this case, from a closed set of three.

    Required rather than defaulted, and deliberately not defaulted to `authored`:
    a default would make the safest answer the one a record acquires by silence,
    and the safest answer is the one that selects the *weaker* bar (ADR-0012).
    """

    status: CaseStatus
    citation: str | None = None
    """Where a published technique came from. Not the trigger, which says why
    the case exists."""

    judged_condition: JudgedCondition | None = None
    """The semantic criterion, for a case whose verdict class is judged.

    Last in the field list rather than beside `success_condition` only because a
    field with a default cannot precede one without: the pairing that matters is
    enforced below, not by the order these are written in.
    """

    admission: AdmissionRecord | None = None
    """What this case measured against the three reference agents to get in.

    `None` on a *proposed* case — one that has been written but not yet run — which
    is the state `scripts/admit.py` reads and the state `propose_case` produces
    (#17). It is not a state the library tolerates: `admission.admitted_library`
    refuses a case with no admission record, so a case that has not earned its place
    cannot be loaded into a run and cannot reach a user (spec story 69).
    """

    history: tuple[GateReading, ...] = ()
    """What this case has measured on every gate run, oldest reading first.

    The decay series (spec story 72). Ordered by the run that took each reading and
    never by date, because two runs can share a day and the retirement rule is read
    over *consecutive runs*: a series sorted by a field that can tie is a series
    whose "previous run" depends on who sorted it.

    Empty on a case no gate run has read yet, which is every case on the run that
    first stores one. The readings are appended by the run that made them
    (`retirement.py`), never transcribed by hand.
    """

    retirement: Retirement | None = None
    """When this case stopped discriminating, on a case that has.

    `None` on an active case, and present on exactly the retired ones — the pairing
    with `status` is enforced below, so a record cannot say *retired* without saying
    when and on what reading, and cannot carry a retirement while still being run.
    """

    def __post_init__(self) -> None:
        """A case declares one route to its verdict, and the one its class names.

        This is what makes "verdict class is read from the case record, never
        inferred from the family name" (spec story 18) a property of the data
        rather than a habit of the caller. A record cannot express a judged case
        with a deterministic check, or a deterministic case with a semantic
        question, so nothing downstream has to guess which one to trust — and
        nothing has to consult the family name to find out.

        The match has no fallback branch on purpose: a third verdict class must
        fail the type check rather than load with no criterion at all.

        Two further refusals sit beside it, and both are about a case being run
        against something it was never written for. A record that applies to no
        agent type can never be run at all, and one whose provenance demands the
        cross-model bar may not record having entered under the single-model one —
        the bar is selected by `discovered_by` (ADR-0012), so a record that
        disagrees with its own provenance is a case that got in on the wrong test.

        The last pair is about retirement, and it keeps `status` and the retirement
        block from ever saying different things. A retired case has to carry the date
        and the reading it retired on, an active one may not carry either, and the
        recorded final score has to *be* the last reading in the case's own history —
        so "kept with its retirement date and final score" (spec story 74) is a
        property of the record rather than of whoever wrote it. Whether the
        retirement *rule* is satisfied is not checked here: the floor is declared in
        `GateRule` and this module holds no threshold, so that check is
        `retirement.py`'s (`live_library`).
        """
        if not self.applies_to:
            raise ValueError(
                f"{self.id} applies to no agent type, so there is no target it "
                "could ever be run against"
            )

        required = bar_for(self.discovered_by)
        if self.admission is not None and self.admission.bar is not required:
            raise ValueError(
                f"{self.id} is {self.discovered_by} and records entering under the "
                f"{self.admission.bar} bar, where that provenance requires "
                f"{required}. An adaptive-discovered case is graded on a model it "
                "was not discovered on (ADR-0012)"
            )

        retired = self.status is CaseStatus.RETIRED
        if retired and self.retirement is None:
            raise ValueError(
                f"{self.id} is marked retired and records no retirement. A retired "
                "case is kept with its date and its final score, because it is "
                "evidence that the field moved rather than a case somebody deleted "
                "(spec story 74)"
            )
        if not retired and self.retirement is not None:
            raise ValueError(
                f"{self.id} records a retirement and is still {self.status}. One of "
                "the two is wrong, and a case that is scored while carrying a "
                "retirement is the one the library must not hold"
            )
        if self.retirement is not None and (
            not self.history or self.retirement.final != self.history[-1]
        ):
            raise ValueError(
                f"{self.id} records a final score that is not the last reading in "
                "its own history. The final score is the reading the case retired "
                "on, and a number written beside the series rather than taken from "
                "it is a score that can drift from what was measured"
            )

        match self.verdict_class:
            case VerdictClass.DETERMINISTIC:
                if self.success_condition is None:
                    raise ValueError(
                        f"{self.id} is deterministic and carries no success "
                        "condition. The success condition is what makes the "
                        "verdict re-derivable by a reader holding the record and "
                        "the transcript (ADR-0004)"
                    )
                if self.judged_condition is not None:
                    raise ValueError(
                        f"{self.id} is deterministic and carries a judged "
                        "condition. Two criteria on one record is a case whose "
                        "verdict depends on which one a caller read"
                    )
            case VerdictClass.JUDGED:
                if self.judged_condition is None:
                    raise ValueError(
                        f"{self.id} is judged and states no question. A judged "
                        "verdict a reader cannot see the criterion for is a "
                        "number with nothing behind it"
                    )
                if self.success_condition is not None:
                    raise ValueError(
                        f"{self.id} is judged and carries a success condition. A "
                        "success condition is deterministic and authoritative "
                        "(ADR-0004), so a judged case holding one would have its "
                        "verdict decided by the deterministic path after all"
                    )


@dataclass(frozen=True)
class LibraryVersion:
    """Which library a run was made against — a count and a digest of the records.

    Recorded on every run, because two runs months apart are comparable or provably
    not (spec story 27), and "provably not" is the half that needs a number. A run
    that says only *eighteen cases* cannot tell a reader whether the eighteen are
    the same eighteen.

    **Read off the records rather than declared beside them.** A hand-kept version
    string is a version string somebody forgets to raise on the run where it
    mattered, and the digest is over what actually ran: every field of every case
    that decides what the case does, including its payload and its criterion, so a
    payload edited without a rename moves the version. It is a hash and not the
    records, so nothing here publishes a payload (ADR-0008).

    **The record of past runs is not part of the case that ran.** `history` and
    `retirement` are excluded from the digest — the two fields a gate run *writes*
    (spec story 72). A digest that moved when a reading was appended would report
    two runs of the identical eighteen cases as incomparable, which is the opposite
    of what this version exists to say, and it would do it on every run by
    construction. Everything a case is *asked* stays in, `status` included: a
    library one of whose cases has retired is a different library, and it is one a
    live run no longer holds at all.
    """

    cases: int
    digest: str

    @classmethod
    def of(cls, cases: Iterable[Case]) -> "LibraryVersion":
        """The version of the library that is about to run, or that just ran.

        Ordered by case id rather than by the order the caller happened to hold
        them in, so that the same library loaded twice is the same version.
        """
        recorded = sorted(cases, key=lambda case: case.id)
        digest = hashlib.sha256(
            "\n".join(_versioned(case) for case in recorded).encode("utf-8")
        )
        return cls(cases=len(recorded), digest=digest.hexdigest()[:12])

    def stated(self) -> str:
        """The version as a run prints it, in the provenance block's words."""
        if not self.cases:
            return (
                "library version: no case ran, so there is nothing to version. Not "
                "a library that happened to be empty at the same digest as another"
            )
        return (
            f"library version: {self.cases} "
            f"{'case' if self.cases == 1 else 'cases'}, sha256:{self.digest} — over "
            "every field of every record that ran, so an edited payload is a "
            "different version"
        )


EMPTY_LIBRARY = LibraryVersion.of(())
"""The version of a run that has no library.

Built through `of` rather than by hand, so that the run state's default and a
version computed from an empty sequence are the same value. Two constructors that
disagreed about the empty case would put two different digests on the same fact.
"""


RUN_RECORD_FIELDS = frozenset({"history", "retirement"})
"""The fields of a case a gate run writes, and so the ones a version leaves out.

Named here rather than inlined in `LibraryVersion.of` because it is the whole of
the exception: every other field is versioned, including any field added later,
which is the direction the default has to point in.
"""


def _versioned(case: Case) -> str:
    """The case as it was asked, without the record of the runs that asked it.

    Built from `dataclasses.fields` rather than from a list of names, so that a
    field added to `Case` is versioned unless somebody deliberately adds it to
    `RUN_RECORD_FIELDS`. A digest over a hand-written list of fields is a digest
    that silently stops covering the next payload-bearing field somebody writes.
    """
    return ", ".join(
        f"{field.name}={getattr(case, field.name)!r}"
        for field in fields(case)
        if field.name not in RUN_RECORD_FIELDS
    )


def trigger_counts(cases: Iterable[Case]) -> dict[Trigger, int]:
    """How many of these cases each trigger accounts for.

    The counterpart to `admission.provenance_counts`, over the closed set that says
    *why* a case exists rather than who found it. It makes the library's growth
    auditable rather than anecdotal (spec story 15): a run prints the census, so a
    library filling up with one trigger's cases is visible in the run that made it.

    Every member is present whether or not it is used, for the reason every other
    census here is total — a missing key reads as an absence of the thing rather
    than as a count of zero.
    """
    counts = dict.fromkeys(Trigger, 0)
    for case in cases:
        counts[case.trigger] += 1
    return counts


def load_library(directory: Path) -> list[Case]:
    """Load every case record in a directory, ordered by file name for a
    stable run order."""
    return [load_case(path) for path in sorted(directory.glob("*.toml"))]


def load_case(path: Path) -> Case:
    record: dict[str, Any] = tomllib.loads(path.read_text(encoding="utf-8"))
    external_id = record["external_id"]
    success = record.get("success_condition")
    judged = record.get("judged_condition")
    history = tuple(_reading(entry) for entry in record.get("history", ()))
    return Case(
        id=record["id"],
        family=Family(record["family"]),
        external_id=ExternalId(
            identifier=external_id["identifier"],
            not_tested=external_id["not_tested"],
        ),
        payload=record["payload"],
        success_condition=None
        if success is None
        else SuccessCondition(
            kind=SuccessConditionKind(success["kind"]),
            planted_canary=success.get("planted_canary"),
        ),
        judged_condition=None
        if judged is None
        else JudgedCondition(
            question=judged["question"],
            succeeded_when=judged["succeeded_when"],
            resisted_when=judged["resisted_when"],
        ),
        verdict_class=VerdictClass(record["verdict_class"]),
        applies_to=tuple(record["applies_to"]),
        requires=tuple(Precondition(name) for name in record["requires"]),
        added_on=record["added_on"],
        trigger=Trigger(record["trigger"]),
        discovered_by=DiscoveredBy(record["discovered_by"]),
        status=CaseStatus(record["status"]),
        citation=record.get("citation"),
        admission=_admission(record.get("admission")),
        history=history,
        retirement=_retirement(record.get("retirement"), history),
    )


def _admission(block: dict[str, Any] | None) -> AdmissionRecord | None:
    """The admission block of a record, or `None` for a case not yet admitted."""
    if block is None:
        return None
    return AdmissionRecord(
        bar=AdmissionBar(block["bar"]),
        admitted_on=block["admitted_on"],
        readings=tuple(AdmissionReading.read(reading) for reading in block["readings"]),
    )


def _reading(entry: dict[str, Any]) -> GateReading:
    """One entry of a case's decay series, as the run that made it wrote it.

    `fit_to_report` and `measured_the_field` are both read rather than defaulted, and
    for one reason: on either flag, the answer a record would acquire by silence is
    the permissive one — the one that lets the retirement rule operate. A series
    whose provenance went missing in the file would read as a series of measurements
    of the field (ADR-0022), which is precisely the claim the flag exists to withhold.
    """
    return GateReading(
        ran_on=entry["ran_on"],
        fit_to_report=entry["fit_to_report"],
        measured_the_field=entry["measured_the_field"],
        counts=AdmissionReading.read(entry),
    )


def _retirement(
    block: dict[str, Any] | None, history: tuple[GateReading, ...]
) -> Retirement | None:
    """The retirement block of a record, or `None` for a case still being run.

    The final score is taken from the series rather than read off the block, so a
    record cannot state a final score its own history does not contain. A record
    that claims a retirement with no reading behind it is refused here rather than
    reaching `Case`, where the message would be about a list index.
    """
    if block is None:
        return None
    if not history:
        raise ValueError(
            f"a retirement on {block['retired_on']} with no reading behind it is an "
            "assertion, not a measurement: a case is retired by two consecutive "
            "readings of one model below the floor, and this record holds none"
        )
    return Retirement(retired_on=block["retired_on"], final=history[-1])


def bar_for(discovered_by: DiscoveredBy) -> AdmissionBar:
    """Which bar this provenance has to clear.

    The mapping ADR-0012 states, held here rather than in
    `backend/bench/admission.py` for one reason: the record enforces it at load
    (`Case.__post_init__`), and the arithmetic that *applies* a bar reads the
    scorer, which reads this module. `admission.bar_for` is the public name for
    this function and the only one anything outside this module should call.

    The match has no fallback branch on purpose: a fourth provenance must fail the
    type check rather than acquire the weaker bar by default.
    """
    match discovered_by:
        case DiscoveredBy.ADAPTIVE:
            return AdmissionBar.CROSS_MODEL
        case DiscoveredBy.AUTHORED | DiscoveredBy.USER_GAP:
            # Neither was fitted to these three agents, so the selection pressure
            # the second bar exists to counter is not acting on it. Stated as a
            # single branch because it is one reason, not two.
            return AdmissionBar.SINGLE_MODEL
