"""The selection an operator makes: which layers run, and which constructions inside.

`AttackSelection` is the second setting in the class ADR-0025 put `attempts_per_case` in
alone — a declared input that **moves the scored denominator**
([ADR-0058](../../docs/adr/0058-the-console-selects-layers-and-constructions.md)).
What is asserted here is the type's own arithmetic: which transform runs under which
selection, that a member the enum does not hold cannot be selected, and that a
selection under which nothing scored could run is refused rather than served as an
expensive registration probe.

**A construction switched off is not a rate of zero**, and this file holds the half of
that the type carries: `runs` answers *was this sent*, and nothing here returns a
count. The consequence for a family — dropped cases and
`DeclaredGap.TRANSFORMS_SWITCHED_OFF` — is `test_api_settings.py`'s, and the
consequence for the artefact is `test_payload.py`'s.
"""

import pytest

from backend.bench.library import Transform
from backend.bench.selection import (
    EVERY_CONSTRUCTION,
    AttackLayer,
    AttackSelection,
    layer_of,
)


def test_every_transform_belongs_to_exactly_one_attack_layer() -> None:
    # The mapping is total, which is what lets a layer switch move a denominator: a
    # transform no layer claims would be one that ran whatever the operator selected.
    # Read over the closed enum, so an eighth member has to be placed here on the day
    # it exists rather than default into the single-turn layer.
    placed = {transform: layer_of(transform) for transform in Transform}
    assert set(placed) == set(Transform)
    assert placed[Transform.PLAIN] is AttackLayer.SINGLE_TURN
    assert placed[Transform.BASE64] is AttackLayer.SINGLE_TURN
    assert placed[Transform.SCRIPTED_CRESCENDO] is AttackLayer.FIXED_MULTI_TURN
    # And the adaptive layer claims none of them, which is ADR-0051 §3 read from the
    # other end: the two adaptive loops are not members, so nothing a `Case` can name
    # is scheduled by the layer that is scored on nothing (ADR-0010).
    assert AttackLayer.ADAPTIVE not in set(placed.values())


def test_a_transform_runs_when_both_it_and_its_layer_are_selected() -> None:
    # Two switches over one construction, and both have to be on. The layer switch is
    # the one the operator reaches for — *do I want the encodings, the ladders or the
    # agent* — and the per-transform list is the finer grain inside it.
    everything = EVERY_CONSTRUCTION
    assert everything.runs(Transform.PLAIN)
    assert everything.runs(Transform.SCRIPTED_CRESCENDO)

    no_ladders = AttackSelection(
        layers=frozenset({AttackLayer.SINGLE_TURN, AttackLayer.ADAPTIVE}),
        transforms=frozenset(Transform),
    )
    assert no_ladders.runs(Transform.PLAIN)
    assert not no_ladders.runs(Transform.SCRIPTED_CRESCENDO)

    no_base64 = AttackSelection(
        layers=frozenset(AttackLayer),
        transforms=frozenset(Transform) - {Transform.BASE64},
    )
    assert no_base64.runs(Transform.PLAIN)
    assert not no_base64.runs(Transform.BASE64)


def test_the_adaptive_layer_is_selected_on_its_own_and_holds_no_construction() -> None:
    # The third layer, switched with the other two and carrying no transform list of
    # its own: what it would list are the two loops `Transform` deliberately does not
    # hold. So this is a boolean, and the type has nowhere to put a construction the
    # adaptive layer performs (ADR-0010, ADR-0051 §3).
    assert EVERY_CONSTRUCTION.adaptive
    scored_only = AttackSelection(
        layers=frozenset({AttackLayer.SINGLE_TURN, AttackLayer.FIXED_MULTI_TURN}),
        transforms=frozenset(Transform),
    )
    assert not scored_only.adaptive
    # Still every scored construction: switching the adaptive layer off moves no
    # scored denominator, which is the whole of why it is the cheap switch.
    assert scored_only.scored == EVERY_CONSTRUCTION.scored


def test_a_selection_that_would_score_nothing_is_refused() -> None:
    # The refusal `families` already makes one level up: a run that scores nothing
    # attacks nothing and still spends a registration probe per target. Refused in the
    # type rather than at the route, because every caller that constructs one — the
    # route, a script, a test — is a caller that could otherwise start a run whose
    # every family reports *not run*.
    with pytest.raises(ValueError, match="scores nothing"):
        AttackSelection(
            layers=frozenset({AttackLayer.ADAPTIVE}), transforms=frozenset()
        )
    with pytest.raises(ValueError, match="scores nothing"):
        AttackSelection(layers=frozenset(AttackLayer), transforms=frozenset())
    with pytest.raises(ValueError, match="scores nothing"):
        AttackSelection(
            layers=frozenset({AttackLayer.FIXED_MULTI_TURN}),
            transforms=frozenset({Transform.PLAIN}),
        )


def test_the_selection_states_the_second_half_of_the_comparability_claim() -> None:
    # `payload.VARIANTS_STATED` is the first half — *comparable only at equal library
    # version and equal selection* — and it names a selection the artefact did not
    # carry. This is the sentence that carries it, and it says which constructions
    # were sent rather than asserting comparability on its own.
    stated = EVERY_CONSTRUCTION.stated()
    assert "every construction" in stated
    narrowed = AttackSelection(
        layers=frozenset({AttackLayer.SINGLE_TURN}),
        transforms=frozenset({Transform.PLAIN}),
    ).stated()
    assert str(Transform.PLAIN) in narrowed
    assert str(Transform.BASE64) not in narrowed
    # Not measured is not measured at zero, and the sentence says so in the document
    # rather than leaving a reader to infer it from an absent count.
    assert "not measured" in narrowed
    assert narrowed != stated
