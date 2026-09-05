"""The configuration scan: what a target says it defends, and what it does not claim.

The scan reads declarations and sends nothing. That is not an optimisation — it is
the boundary the whole declared-and-defeated finding rests on. A scan that probed
an endpoint would be a measurement wearing a declaration's name, and the report's
headline would compare two measurements instead of comparing a claim against a
measurement. So this module imports no transport, takes a `TargetConfig` and
returns a record, and a test asserts the first of those at import level rather
than trusting the second.

**Nothing here reaches a rate.** ADR-0005 killed a composite score whose second
defect was that it added measured behaviour to untested self-report, and whose
worst property was that a target raised its number by *declaring more controls*.
The consequence is structural rather than remembered: a `Scan` carries no number,
the checklist is a closed set of names, and the only edge from this module to the
scored side is the join in `assembler.py`, which crosses declarations with
**verdicts** and never with rates (ADR-0006's table, the configuration-scan row).

**The checklist is the hardened reference agent's own architecture.** Four
controls — input check, scope limit, output filter, stop control — are what PLAN §3
builds that agent from and what `backend/targets/reference/controls.py` implements
as removable pieces. Each claims exactly one of the four deterministic families, so
a declared control is defeated by a verdict a reader can re-derive from the case
record and the transcript (ADR-0004). The two judged families have no control in
the checklist, which is why the spec can say the join is computed against the
attacker's *deterministic* findings and mean it literally.

An absent control is listed and nothing else happens to it. The rejected composite
score subtracted points for absence; here the absence of a claim is not a finding,
because the bench has not tested for the presence of a control — it has tested
whether the family that control claims can be broken, and that result stands on its
own line whether or not anything was declared.
"""

from dataclasses import dataclass
from enum import StrEnum

from backend.bench.contract import AgentCapability, DeclaredControl, TargetConfig
from backend.bench.library import AnyFamily, Family

CONTROL_CHECKLIST: tuple[DeclaredControl, ...] = tuple(DeclaredControl)
"""The controls the scan asks about, in the order a report prints them.

Read off the enumeration rather than typed again, for the reason `AdaptiveBudget`
reads its family count off `Family`: a checklist that could drift from the set of
controls the bench has attacks for is a checklist that can silently stop asking
about one.
"""


def family_claimed_by(control: DeclaredControl) -> Family:
    """The family a declared control claims to defend.

    The whole of the join's semantics, in one closed mapping. Every arm names a
    deterministic family, so a defeat is always a re-derivable verdict; the match
    has no fallback branch on purpose, so a fifth control fails the type check
    rather than joining against nothing and reporting `untested` for ever.
    """
    match control:
        case DeclaredControl.INPUT_CHECK:
            return Family.INDIRECT_PROMPT_INJECTION
        case DeclaredControl.SCOPE_LIMIT:
            return Family.SCOPE_CREEP
        case DeclaredControl.OUTPUT_FILTER:
            return Family.DATA_LEAKAGE
        case DeclaredControl.STOP_CONTROL:
            return Family.HALT_DEFEAT


def control_claiming(family: AnyFamily) -> DeclaredControl | None:
    """The control that claims this family, or `None` where no control claims it.

    `family_claimed_by` above read the other way, and **derived from it** by walking
    the checklist rather than written out as a second table: the drift between two
    tables would be silent, and a fifth control claims its family in both directions
    the moment the mapping above gains an arm.

    **`None` is a real answer and not a lookup miss** — it is what the two judged
    families and the three elective ones get, because the checklist holds four
    controls and each claims a deterministic family. Why that answer needs a name of
    its own rather than being read as *the operator declared none*, and where the
    name lives, is
    [ADR-0068](../../docs/adr/0068-an-attributed-cause-is-derived-from-the-case-record-and-the-scan.md)
    §3.
    """
    for control in CONTROL_CHECKLIST:
        if family_claimed_by(control) is family:
            return control
    return None


class Supervision(StrEnum):
    """What the operator said about a human confirming what their agent does.

    Three members and not a `bool`, for the reason `NotMeasurable` is not a `None`:
    *nobody said* is a third answer, and the one it must never be read as is
    *unsupervised*. An agent holding all three capabilities under human confirmation
    is not the shape the Rule of Two warns about, so silence here decides the reading
    and has to be legible in it.
    """

    CONFIRMED = "human_confirms"
    """A human confirms the agent's actions inside the session."""

    UNSUPERVISED = "unsupervised"
    """The agent acts inside the session without human confirmation."""

    NOT_STATED = "supervision_not_stated"
    """The operator said nothing either way. Not `unsupervised`."""

    @classmethod
    def declared(cls, stated: bool | None) -> "Supervision":
        """The declaration as a name, `None` becoming *nobody said*."""
        if stated is None:
            return cls.NOT_STATED
        return cls.CONFIRMED if stated else cls.UNSUPERVISED

    def stated(self) -> str:
        """This declaration in the words the report prints it in."""
        match self:
            case Supervision.CONFIRMED:
                return "a human confirms what it does inside the session"
            case Supervision.UNSUPERVISED:
                return "no human confirms what it does inside the session"
            case Supervision.NOT_STATED:
                return "nobody said whether a human confirms what it does"


class RuleOfTwoStanding(StrEnum):
    """The shape one target declared, read against the Agents Rule of Two.

    **A name, and never a figure**
    ([ADR-0038](../../docs/adr/0038-the-rule-of-two-is-a-declared-property.md),
    decision 4). Each member says what the operator declared rather than how well:
    there is no *pass*, no *fail* and no ordering, so nothing here can be ranked or
    added — the property `Band` has for the same reason (ADR-0005, and `scorer.py`
    says it there).

    Five of them, and the first two below are two different absences rather than one
    word for both: a target that said nothing at all is not a target that answered
    some of the four, and the reading a reader can do with each is different.
    """

    NOT_DECLARED = "not_declared"
    """None of the four was stated, so the rule was never read.

    The same kind of absence as a control the checklist asks about and the operator
    did not claim, and **not a sixth kind of nothing** beside `payload.py`'s five
    (ADR-0038, decision 6).
    """

    PARTLY_DECLARED = "partly_declared"
    """Some of it was stated, and not enough of it to read the rule.

    Reached two ways and both are real: a capability left unstated, or all three
    stated and held with the supervision declaration missing. The record names which,
    because the two are a reader's next question.
    """

    AT_MOST_TWO = "at_most_two"
    """Two of the three at most, which is the shape the rule permits."""

    THREE_UNDER_SUPERVISION = "three_under_supervision"
    """All three, with a human confirming. Not the shape the rule warns about, and
    printed as itself rather than folded into `at_most_two`: an agent that holds all
    three is a different fact from one that holds two, and what keeps the two apart
    here is a declaration a reader can see."""

    THREE_UNSUPERVISED = "three_unsupervised"
    """All three, unsupervised — the shape the published rule warns about.

    **Still a declaration**, and the arm that most needs `NOT_A_MEASUREMENT` printed
    beside it: it is the one a reader coming from the join above will read as a
    finding, and there is no verdict behind it and no case id to point at.
    """


@dataclass(frozen=True)
class RuleOfTwo:
    """What one target declared it can do, and what the published rule says of it.

    Three names, a supervision declaration and one derived standing. **No number of
    any kind**, and that is the shape rather than a habit: there is no field here a
    rate, an interval, a band or a `D` could arrive in, no count of held capabilities
    for two targets to be compared on, and no `Family` anywhere — the three
    capabilities are near-neighbours of three families the bench measures, and a
    mapping to one would make this a view over verdicts rather than a reading of a
    declaration
    ([ADR-0038](../../docs/adr/0038-the-rule-of-two-is-a-declared-property.md)).

    Three tuples that partition `AgentCapability`, on the reasoning `Scan` keeps
    `declared` and `absent` apart: the held side is what the rule is read over, the
    unstated side is the reason it sometimes cannot be, and a capability in two of
    them would be a claim and an absence at once.

    There is therefore **no empty reading**: the three defaults name none of the
    rule's properties, so `RuleOfTwo()` is refused by the partition below and the
    reading of a registration that said nothing is `NOTHING_DECLARED`, where the
    three sit under `unstated`. The defaults exist so that a side with nothing in it
    can be left out, not so that a reading can be made without one.
    """

    held: tuple[AgentCapability, ...] = ()
    """The capabilities the operator declared their agent has, in enumeration
    order — so two targets' blocks are read down the same column."""

    not_held: tuple[AgentCapability, ...] = ()
    """The capabilities the operator declared it does not have. Stated, not assumed:
    this is the side that separates a declaration from a silence."""

    unstated: tuple[AgentCapability, ...] = ()
    """The capabilities nobody said anything about. Never read as `not_held`."""

    supervision: Supervision = Supervision.NOT_STATED

    def __post_init__(self) -> None:
        named = (*self.held, *self.not_held, *self.unstated)
        if len(set(named)) != len(named) or set(named) != set(AgentCapability):
            raise ValueError(
                f"{[str(one) for one in named]} does not name each of the rule's "
                "three properties exactly once. The three sides partition the rule, "
                "and a property held and unstated at once, or missing from all "
                "three, would be a standing read over a rule with a different "
                "number of properties in it"
            )

    @property
    def standing(self) -> RuleOfTwoStanding:
        """This declaration read against the rule. Derived, and never set.

        In the discipline `Scan.absent` and `MeasuredSection.unfit_to_report` follow:
        a standing a caller supplied would be a standing a caller could supply
        wrongly, and the whole content of this one is that it is a function of the
        registration and of nothing else.

        Not one comparison in it is arithmetic — the arms test tuples for emptiness
        rather than counting what is in them, so there is no count here for anything
        downstream to reach.

        **`not_held` is read before `unstated`**, and that order is the rule rather
        than a preference: one property the operator declared their agent does *not*
        have means it cannot hold three, whatever it left unsaid, so the reading is
        settled and *partly declared* would print a sentence that is false. What stays
        undecidable is a declaration with something unsaid and nothing declared
        absent, where the shape could still be either.
        """
        said_nothing = not self.held and not self.not_held
        if said_nothing and self.supervision is Supervision.NOT_STATED:
            return RuleOfTwoStanding.NOT_DECLARED
        if self.not_held:
            return RuleOfTwoStanding.AT_MOST_TWO
        if self.unstated:
            return RuleOfTwoStanding.PARTLY_DECLARED
        match self.supervision:
            case Supervision.CONFIRMED:
                return RuleOfTwoStanding.THREE_UNDER_SUPERVISION
            case Supervision.UNSUPERVISED:
                return RuleOfTwoStanding.THREE_UNSUPERVISED
            case Supervision.NOT_STATED:
                return RuleOfTwoStanding.PARTLY_DECLARED

    def stated(self) -> str:
        """The block a report prints for this target's declared shape.

        Three parts, in one order on every arm: what the operator declared, what the
        published rule makes of it, and that none of it was measured. The last is not
        a disclaimer somebody remembered — this block sits beside a join whose rows
        point at verdicts, and a reader arriving here has just been shown findings.

        The declaration is printed in full rather than only the half each reading
        turns on. All three sides and the supervision answer, every time: a sentence
        that named only what was held would leave a reader unable to tell a property
        declared absent from one nobody was asked about, which is the distinction the
        record exists to keep.
        """
        return f"{self._declaration()} — {self._reading()}. {NOT_A_MEASUREMENT}"

    def _declaration(self) -> str:
        """What the operator said, all four answers, in one clause."""
        return (
            "the Agents Rule of Two — declared: "
            f"{_named(self.held)}; declared absent: {_named(self.not_held)}; "
            f"not stated: {_named(self.unstated)}; supervision: "
            f"{self.supervision.stated()}"
        )

    def _reading(self) -> str:
        """What the published rule makes of that declaration, on one arm."""
        match self.standing:
            case RuleOfTwoStanding.NOT_DECLARED:
                return (
                    "not declared, so the rule was not read. An absence on the "
                    "operator's side of the boundary, and nothing was attempted "
                    "against it"
                )
            case RuleOfTwoStanding.PARTLY_DECLARED:
                return (
                    "partly declared: nothing here is declared absent and something "
                    "is unsaid, so what this target holds could still be two of the "
                    "three or all three, and the scan does not say which shape this "
                    "is. Declared, never inferred — the bench does not guess a "
                    "capability from a tool name"
                )
            case RuleOfTwoStanding.AT_MOST_TWO:
                return (
                    "at most two of the three, which is the shape the rule permits: "
                    "a property the operator declares this agent does not have is "
                    "one it cannot hold, whatever else went unsaid. The rule warns "
                    "about an agent holding all three unsupervised"
                )
            case RuleOfTwoStanding.THREE_UNDER_SUPERVISION:
                return (
                    "all three, under human supervision. The rule warns about an "
                    "agent holding all three *unsupervised*, so what is declared "
                    "here is not that shape"
                )
            case RuleOfTwoStanding.THREE_UNSUPERVISED:
                return (
                    "**all three, unsupervised — the shape the published rule warns "
                    "about**"
                )


NOT_A_MEASUREMENT = (
    "Nothing was sent to establish any of this: it is what the operator declared "
    "about their own agent, read against a published rule. No attempt was made "
    "against it, no verdict lies behind it, and it is not a finding"
)
"""What every reading above says about itself, in one wording rather than five.

Appended once by `stated()` instead of hand-written on each arm, on the discipline
`contract.NOT_A_SECURITY_RESULT` follows: a sentence this load-bearing, written five
times, only has to drift once for one standing to be presented as something the bench
established. The arm that most needs it is the one that reads most like a finding.
"""


def _named(capabilities: tuple[AgentCapability, ...]) -> str:
    """The capabilities as prose, or the word for none of them."""
    if not capabilities:
        return "none"
    return ", ".join(str(one) for one in capabilities)


def read_rule_of_two(target: TargetConfig) -> RuleOfTwo:
    """Read one target's four Rule-of-Two declarations. Sends nothing, like the scan.

    The one place the four fields on `TargetConfig` are read together, which is what
    makes the partition above a property rather than something four call sites agree
    about.
    """
    stated = {
        AgentCapability.PROCESSES_UNTRUSTED_INPUT: target.processes_untrusted_input,
        AgentCapability.REACHES_PRIVATE_DATA: target.reaches_private_data,
        AgentCapability.CHANGES_STATE_OR_COMMUNICATES: (
            target.changes_state_or_communicates
        ),
    }
    return RuleOfTwo(
        held=tuple(one for one in AgentCapability if stated[one] is True),
        not_held=tuple(one for one in AgentCapability if stated[one] is False),
        unstated=tuple(one for one in AgentCapability if stated[one] is None),
        supervision=Supervision.declared(target.under_human_supervision),
    )


NOTHING_DECLARED = RuleOfTwo(unstated=tuple(AgentCapability))
"""A target that stated none of the four. The default of every registration.

Not an absent reading: a target whose operator said nothing about its shape is one
the rule was not read over, and the block says that rather than leaving a reader to
infer it from a heading with nothing under it — the discipline
`elective.NOTHING_REQUESTED` follows.
"""


@dataclass(frozen=True)
class Scan:
    """What one target declared, and what it left unclaimed.

    One tuple and one property over a closed checklist, and deliberately not a
    mapping of control to boolean: the declared side is joined against verdicts and
    the absent side is only ever listed, so keeping them apart is what stops a
    caller looping over both and treating an absence as a status.
    """

    declared: tuple[DeclaredControl, ...]
    """The controls the operator claimed, in checklist order.

    Checklist order rather than declaration order, so two targets' sections are
    read down the same column and a report's row order cannot be rearranged by the
    order a registration form was filled in. `scan()` puts them in it.
    """

    rule_of_two: RuleOfTwo = NOTHING_DECLARED
    """What this target declared about its own shape, read against the published rule.

    On the scan rather than beside it, because it is the same kind of thing the
    checklist is — a declaration read at registration, with nothing sent to establish
    it — and because a second reader of `TargetConfig` would be a second place the
    boundary this module states has to hold. What it is *not* is a fifth control: it
    claims no family, joins against no verdict, and there is no `family_claimed_by`
    for a declared capability
    ([ADR-0038](../../docs/adr/0038-the-rule-of-two-is-a-declared-property.md)).
    """

    def __post_init__(self) -> None:
        if len(set(self.declared)) != len(self.declared):
            raise ValueError(
                f"{self.declared} declares a control twice, which would give one "
                "claim two rows in the section and two chances to be defeated"
            )

    @property
    def absent(self) -> tuple[DeclaredControl, ...]:
        """The controls the operator did not claim. Listed, never counted.

        Derived rather than stored, so the two sides cannot disagree about the
        checklist. A control the target never declared is not a defect and carries
        no penalty — the family it would have claimed is measured either way and its
        rate stands on its own line. ADR-0005's rejected score deducted points
        here, which is what made declaring more controls profitable.
        """
        return tuple(
            control for control in CONTROL_CHECKLIST if control not in self.declared
        )


def scan(target: TargetConfig) -> Scan:
    """Read one target's declared controls. Sends no message and spends nothing.

    A pure function of the registration, which is why it can run before the
    approval interrupt without asking anyone for anything: there is no call to
    estimate and no budget to charge it against.
    """
    return Scan(
        declared=tuple(
            control
            for control in CONTROL_CHECKLIST
            if control in target.declared_controls
        ),
        rule_of_two=read_rule_of_two(target),
    )
