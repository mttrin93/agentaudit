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

from dataclasses import dataclass, field
from enum import StrEnum
from typing import assert_never

from backend.bench.adaptive.tree import BranchSchedule
from backend.bench.library import Transform
from backend.bench.transforms import ADAPTIVE_SPELLINGS


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


DECLARED_SCHEDULES: frozenset[BranchSchedule] = frozenset({BranchSchedule.LINEAR})
"""The schedules a selection carries when nobody named any: the line alone.

A constant rather than a literal inside the field's default, because two readers need
it — the field below, and `verification._selection`, which rebuilds a selection from a
document that predates the key and has to rebuild the selection those runs *made*
(ADR-0096, ADR-0097). Two literals could come to disagree about what an older
artefact meant.
"""

DECLARED_ADAPTIVE_CONSTRUCTIONS: frozenset[Transform] = frozenset({Transform.PLAIN})
"""The spelling a selection carries when nobody named one: the attacker's own words.

`DECLARED_SCHEDULES`' constant, over the other of the adaptive layer's two switches
and for the same two readers.
"""


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
    schedules: frozenset[BranchSchedule] = field(
        default_factory=lambda: DECLARED_SCHEDULES
    )
    """Which schedules the adaptive layer attacks under, if it runs at all.

    **The third switch, and the adaptive layer's own.** The layer names no
    construction — what it would name are the two loops ADR-0051 §3 refuses the
    `Transform` enum — so until this field the operator's only question about it was
    *does the agent run*, and the box on the console said so. These are the two names
    the catalogues carry, each standing for a policy the bench declares, and selecting
    both is **two episode sets per family** rather than one wider search: the ceiling
    doubles and the operator confirms the doubled figure
    ([ADR-0096](../../docs/adr/0096-the-adaptive-schedule-is-selected-and-both-schedules-are-two-episodes.md)).

    A set with a default rather than a required field, and the default is the **line
    alone** — where this parts from `transforms`, whose default is everything the
    library holds. A construction switched on measures more of the same library; a
    second schedule is a different attacker, and the reference agents were gated under
    the line (ADR-0023, ADR-0057 §2). So a caller that says nothing gets the schedule
    every reading in this bench was produced under, and a bench nobody has narrowed is
    still on the line.

    It reaches the run through `AdaptiveBudget.under`, which is the only join, and it
    reaches a **target run only**: a gate run is priced and calibrated without a
    selection, so the citation stays a claim about the line whatever this console is
    set to.
    """

    adaptive_constructions: frozenset[Transform] = field(
        default_factory=lambda: DECLARED_ADAPTIVE_CONSTRUCTIONS
    )
    """Which spellings the adaptive layer's probes are composed in.

    **The fourth switch, and the second one that is the adaptive layer's own.** The
    scored layer attacks in seven constructions and the adaptive layer attacked in one
    — the attacker's own words, as composed — so a target that refuses a plain request
    and answers the same request in base64 was a difference this bench could measure
    in its scored layer and could not search for in its adaptive one
    ([ADR-0097](../../docs/adr/0097-the-adaptive-layer-attacks-in-a-spelling-and-it-is-selected.md)).

    **One spelling per episode set, on the schedules' own arithmetic**: `k` episodes
    per family per schedule per spelling, so an episode is composed in one spelling
    throughout and selecting a second one is a second episode set rather than a
    mixture nobody can read. The ceiling multiplies, and the operator confirms it.

    **A subset of `Transform`, and `ADAPTIVE_SPELLINGS` is the whole of it**, refused
    below rather than filtered: the two framing constructions need words this
    repository writes per family and withholds for one of them, and the crescendo is a
    ladder rather than a spelling (`transforms.ADAPTIVE_SPELLINGS`). A selection naming
    one of the three is a `422` naming what is missing, never a run that quietly sent
    plain probes under a construction's name.

    The default is `plain` alone, on `schedules`' terms: it is the layer every reading
    this bench has published was taken under.
    """

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
        if not self.schedules:
            raise ValueError(
                "the adaptive layer has to attack under a schedule: an empty set is "
                "a layer that opens no episode, which is what switching the layer "
                "off already says, and two ways of saying it are two things a "
                "reader has to reconcile. Name linear_jailbreak, tree_jailbreak or "
                "both — the layer switch is how the layer is turned off"
            )
        if not self.adaptive_constructions:
            raise ValueError(
                "the adaptive layer has to compose its probes in some spelling: an "
                "empty set is a layer that opens no episode, which is what switching "
                "the layer off already says. Leave plain on, or name the spellings "
                "you want beside it"
            )
        unspellable = sorted(
            str(one) for one in self.adaptive_constructions - ADAPTIVE_SPELLINGS
        )
        if unspellable:
            raise ValueError(
                f"{', '.join(unspellable)} cannot respell a probe the attacker "
                "composed: a framing is words this repository writes per family and "
                "a crescendo is a ladder computed from a case record, and neither is "
                "a spelling of somebody else's sentence. The adaptive layer attacks "
                f"in {', '.join(sorted(str(one) for one in ADAPTIVE_SPELLINGS))}"
            )
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

    def constructions_stated(self) -> str:
        """Which spellings the adaptive layer composed its probes in, in a sentence.

        Its own sentence for `schedules_stated`'s reason and beside it in the
        artefact: `stated()` is re-derived by the verifier from the layers and
        constructions it names, and a wording that grew a clause would report every
        document issued after ADR-0097 as a disagreement nothing tampered with.

        Said when the layer is off too, and says the same thing that one does: a
        spelling nothing was composed in is a setting rather than a fact about this
        run.
        """
        named = ", ".join(
            str(one) for one in Transform if one in self.adaptive_constructions
        )
        if not self.adaptive:
            return (
                "The adaptive layer was switched off for this run, so no probe was "
                "composed in any spelling."
            )
        if self.adaptive_constructions == frozenset({Transform.PLAIN}):
            return (
                "The adaptive layer composed its probes plainly — the attacker's own "
                "words, as it wrote them — which is the spelling every reading this "
                "bench has published was taken under."
            )
        if len(self.adaptive_constructions) == 1:
            return (
                f"The adaptive layer composed every probe in one spelling, {named}: "
                "the attacker's own words, respelled by the harness as each turn was "
                "sent, and the transcripts carry what went on the wire."
            )
        return (
            f"The adaptive layer attacked in these spellings — {named} — which is one "
            "episode set per spelling per family and never a mixture inside one "
            "episode. An episode is a summand of nothing in any of them, and the "
            "ceiling this run was approved against carries the multiplication."
        )

    def schedules_stated(self) -> str:
        """Which schedules the adaptive layer attacked under, in one sentence.

        **Part of the selection and therefore part of the comparability claim** — and
        its own sentence rather than a clause appended to `stated()` above, which is a
        decision about the *verifier* and not about prose. `stated()` is re-derived by
        `verification._selection` from the members beside it, so a wording that grew a
        schedules clause would make every document a version-2 verifier reads report a
        disagreement it cannot explain: a false tampering claim, where a key added
        beside the others is a key an older verifier skips over a document whose
        figures it still re-derives in full (ADR-0044 §8, ADR-0070, ADR-0096 §8). The
        artefact carries both strings, side by side in section 2.

        Said even when the adaptive layer is off, and says so: *no schedule ran* is
        the fact, and a sentence that went quiet there would leave a reader deciding
        whether the schedules were absent or unrecorded.
        """
        named = ", ".join(str(one) for one in BranchSchedule if one in self.schedules)
        if not self.adaptive:
            return (
                "The adaptive layer was switched off for this run, so no episode was "
                "opened and no schedule ran. What was selected is not named here: a "
                "schedule nothing ran under is a setting rather than a fact about "
                "this run, and naming it would invite a reader to think it did."
            )
        if len(self.schedules) == 1:
            return (
                f"The adaptive layer attacked under one schedule, {named}, so its "
                "episodes are k per family and their turns are that schedule's."
            )
        return (
            f"The adaptive layer attacked under both schedules — {named} — which is "
            "one episode set per schedule per family and twice the episodes of a run "
            "under one of them. An episode is a summand of nothing either way, and "
            "the ceiling this run was approved against carries the doubling."
        )


EVERY_CONSTRUCTION = AttackSelection(
    layers=frozenset(AttackLayer),
    transforms=frozenset(Transform),
    # Every layer and every construction, and **one** schedule. Not both, for the
    # reason the field's own docstring gives: a second schedule is a second attacker
    # and not more of the same library, so the selection nobody narrowed is still the
    # one the reference agents were gated under (ADR-0023, ADR-0096).
    schedules=DECLARED_SCHEDULES,
    # And one spelling, on the schedules' own reasoning: the attacker's own words are
    # what every published reading of this layer was taken under, and a spelling
    # switched on by default would be a second episode set nobody asked for
    # (ADR-0097).
    adaptive_constructions=DECLARED_ADAPTIVE_CONSTRUCTIONS,
)
"""Every layer and every construction: the selection a run that narrowed nothing made.

The default on `BenchConfig.selection` and the value every caller that makes no
selection gets, so that a bench nobody has narrowed sends the whole library — the
direction `families` defaults in, and the only one in which a forgotten field
over-measures rather than silently reporting a thinner reading as a full one.
"""
