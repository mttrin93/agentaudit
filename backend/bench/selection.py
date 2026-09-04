"""`AttackSelection` — which layers a run runs, and which constructions inside them.

**Named `AttackSelection` and not `Selection`, and the qualifier is load-bearing.**
`backend/corpus/selection.py` already holds a `Selection` — the corpus rows a person
was shown, which is what CONTEXT.md's **technique** entry means by the word — and
`elective.ElectiveSelection` is qualified for the same reason. Three records that
could each be called *the selection* is three readers reading one another's sentence
wrongly, so this one says which selection it is: the layers and constructions an
**attack** is made of. The concept word in prose and in the artefact stays
*selection*, because that is the word `VARIANTS_STATED` already published.

The declared input that **moves the scored denominator**, and the second setting in
the class ADR-0025 put `attempts_per_case` in alone
([ADR-0058](../../docs/adr/0058-the-console-selects-layers-and-constructions.md)).
Every other thing the console sets bounds a layer that is scored on nothing
(ADR-0010) or is a scalar the report prints beside every figure; this one decides
which of the library's records a run sends at all.

**Here rather than in `api/run_config.py`, because the artefact carries it.**
`Provenance` names the selection beside the library version, so the type has to be
importable by `payload.py` — and `backend/bench/` never imports `backend/api/`. The
console's copy of it is `api/app.py`'s and the record it lands on is
`BenchConfig.selection`.

**Not measured and measured at zero are two facts, and nothing here returns a
count.** `runs` answers *was this construction sent*; what a family does when the
selection leaves it nothing is `plan_for`'s answer and it is
`DeclaredGap.TRANSFORMS_SWITCHED_OFF`, which says *not run*. The complement is
`scorer.VariantCounts`, which refuses an entry at zero attempts for the same reason
from the other end: a transform that was never sent is absent from a breakdown rather
than present at zero (ADR-0055).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import assert_never

from backend.bench.library import Transform


class AttackLayer(StrEnum):
    """The three layers an operator switches, in the order a run spends them.

    **A third enumeration, and deliberately not `budget.Layer`.** That one is a pair
    of budget counters — a call on the wire is billed to the scored side or the
    adaptive side and there is no third answer — and both layers here that carry a
    construction bill the same counter. Folding them into it would mean an operator
    could not switch the ladders off without switching the encodings off with them,
    and splitting `Layer` in two would put a third counter under ADR-0007's consent
    figures that nothing enforces. So: two vocabularies, one about spending and one
    about selection, and `layer_of` below is the only join between them.

    **The adaptive layer is a member and carries no `Transform`.** What it would carry
    are the two loops ADR-0051 §3 refuses the enum, so the operator's question about
    it is *does the agent run at all* — `AttackSelection.adaptive`, a boolean, and
    nowhere for an adaptive construction to be named as a thing a scored record could
    claim (ADR-0010).
    """

    SINGLE_TURN = "single_turn"
    """One message in one session: the payload as committed, and the five respellings
    of it."""

    FIXED_MULTI_TURN = "fixed_multi_turn"
    """A fixed script of turns in one session — one attempt, more than one turn
    (ADR-0053, ADR-0054)."""

    ADAPTIVE = "adaptive"
    """The layer scored on nothing, whose episodes reach the scored side through
    `propose_case` and the admission gate alone (ADR-0010)."""

    def stated(self) -> str:
        """What this layer sends, in the words the console and the artefact share.

        The match has no fallback branch, on `Transform.stated`'s terms: a fourth
        layer must fail the type check rather than exist as a member no reader can be
        told what a run of it does.
        """
        match self:
            case AttackLayer.SINGLE_TURN:
                return (
                    "one message in one session — the payload as the record commits "
                    "it and each respelling of it, each scored on its own attempts"
                )
            case AttackLayer.FIXED_MULTI_TURN:
                return (
                    "a fixed script of turns in one session — one attempt reaching "
                    "one verdict, and more than one call on the endpoint"
                )
            case AttackLayer.ADAPTIVE:
                return (
                    "the model-driven attacker, which is scored on nothing: its "
                    "episodes are counted beside a family's rate and are never a "
                    "summand of one"
                )
            case _ as unreached:
                assert_never(unreached)


def layer_of(transform: Transform) -> AttackLayer:
    """The layer that schedules this construction. Total, and the only join.

    A function rather than a property on `Transform`, because it is the one place the
    selection vocabulary touches the library's: `library.py` knows what a construction
    does to a payload and nothing about who may switch it off, and a field on the enum
    would make every reader of a record load the console's vocabulary to read it.

    Exhaustive with no fallback, which is the property a layer switch rests on: a
    transform no layer claimed would be one that ran whatever an operator selected.
    """
    match transform:
        case (
            Transform.PLAIN
            | Transform.BASE64
            | Transform.ROT13
            | Transform.LEETSPEAK
            | Transform.PROMPT_INJECTION_WRAPPER
            | Transform.ROLEPLAY
        ):
            return AttackLayer.SINGLE_TURN
        case Transform.SCRIPTED_CRESCENDO:
            return AttackLayer.FIXED_MULTI_TURN
        case _ as unreached:
            assert_never(unreached)


@dataclass(frozen=True)
class AttackSelection:
    """Which layers the next run runs, and which constructions inside them.

    Two frozen sets and no per-family grain. A six-by-eight grid of switches produces
    runs nobody can compare, and the operator's real question — *do I want the
    encodings, the ladders, or the agent?* — is answered by the layers
    (ADR-0058 §3). A per-family need is a ticket with a reason, not a default.

    **Fewer constructions is a cheaper run and a narrower reading**, which is the
    sentence `families` already earns: `plan_for` drops the cases whose transform is
    not selected and prices what remains, and a family left with nothing is reported
    as *not run* rather than measured on a thinner library.
    """

    layers: frozenset[AttackLayer]
    transforms: frozenset[Transform]

    def __post_init__(self) -> None:
        """Refuse a selection under which no scored construction runs.

        The refusal `app.set_the_families_the_next_run_covers` already makes one level
        up, in the type rather than at the route because every caller that can
        construct one of these can start a run: a suite whose every family reports
        *not run* measures nothing about the target and still spends a registration
        probe per target, which is a bill for a reading nobody receives.

        It is not a refusal of an adaptive-only run in disguise, and there is no such
        run to refuse: an episode needs a deterministic case for its family
        (`adaptive/layer.objectives_for`), so a selection that dropped every case
        would open no episode either. Saying *scores nothing* is saying the whole of
        what such a run would do.
        """
        if not self.scored:
            raise ValueError(
                "this selection scores nothing: no construction it names runs in a "
                "layer it names, so every family would be reported as not run and "
                "the run would still spend a registration probe per target. Leave at "
                "least one construction on in a layer that is on"
            )

    def runs(self, transform: Transform) -> bool:
        """Whether a case attacking by this construction is sent at all.

        Both switches, and both have to be on. The layer switch is the one an operator
        reaches for and the transform list is the finer grain inside it, so a
        construction stays selected while its layer is off — narrowing a run by layer
        and widening it again leaves the constructions where the operator put them.
        """
        return transform in self.transforms and layer_of(transform) in self.layers

    @property
    def scored(self) -> frozenset[Transform]:
        """Every construction this selection actually sends, in no order.

        A set and not a count: what a run measured is the attempts it made, and a
        number here would be the first thing something averaged over.
        """
        return frozenset(transform for transform in Transform if self.runs(transform))

    @property
    def adaptive(self) -> bool:
        """Whether the adaptive layer runs against this run's targets.

        A boolean because the layer names no construction, and read by the estimate
        as well as by the run: a layer switched off puts nothing on the wire, so the
        figure an operator confirms drops to nothing for it (ADR-0007).
        """
        return AttackLayer.ADAPTIVE in self.layers

    def stated(self) -> str:
        """What this run sent, and what it therefore did not measure.

        The **second half of the comparability claim** `payload.VARIANTS_STATED`
        makes. That sentence says two runs are comparable only at equal library
        version and equal selection, and until this record the artefact carried the
        library version and not the selection — so a reader holding two documents
        could check one half of the condition and had to take the other on trust.
        Neither sentence asserts comparability alone: that one says what the
        condition is, this one says what this run's half of it was.

        Written here rather than in the console that produced it, for the reason
        `rule.NOT_A_GATE_RESULT` is written once: a second copy would only have to
        disagree once for a document to claim a denominator it does not carry.
        """
        if self.scored == frozenset(Transform) and self.adaptive:
            return (
                "This run sent every construction the library holds, in every layer: "
                "the payload as each record commits it, each respelling of it, each "
                "fixed script, and the adaptive attacker beside them. Nothing was "
                "switched off, so a reading absent from this document is absent "
                "because the library holds no case for it and never because this run "
                "declined to send one."
            )
        sent = ", ".join(sorted(str(transform) for transform in self.scored))
        layers = ", ".join(sorted(str(layer) for layer in self.layers))
        return (
            f"This run sent these constructions and no others: {sent} — in these "
            f"layers: {layers}. Every other construction the library holds was "
            "switched off for this run and is **not measured** here, which is not the "
            "same fact as measured at zero: no attempt was made by it, so nothing on "
            "this page is a reading about it. Two runs are comparable only at equal "
            "library version and equal selection, and this is this run's half of that "
            "condition."
        )


EVERY_CONSTRUCTION = AttackSelection(
    layers=frozenset(AttackLayer), transforms=frozenset(Transform)
)
"""Every layer and every construction: the selection a run that narrowed nothing made.

The default on `BenchConfig.selection` and the value every caller that makes no
selection gets, so that a bench nobody has narrowed sends the whole library — the
direction `families` defaults in, and the only one in which a forgotten field
over-measures rather than silently reporting a thinner reading as a full one.
"""
