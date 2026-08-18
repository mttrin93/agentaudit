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

from backend.bench.contract import DeclaredControl, TargetConfig
from backend.bench.library import Family

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
        )
    )
