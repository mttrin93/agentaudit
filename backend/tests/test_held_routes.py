"""The fifth store: a confirmed break the admission bar refused, kept per target.

What is asserted here is the *shape* of a target library and nothing that fills one.
[ADR-0117](../../docs/adr/0117-a-refused-break-is-held-against-the-target-it-beat-and-is-scored-beside-the-six.md)
§1 and §6 are what these tests are about, and the fence they rest on is a property
of the type rather than of any call site — so the type comes first and the writers
come in later tickets (#239 files, #240 sends).

Three seams:

1. **The sixth provenance** — `DiscoveredBy.TARGET_SPECIFIC`, declared last so the
   census prints in an order two gate runs can be compared in (ADR-0107 §1), and
   refused a bar so that no `Case` can carry it.
2. **The record** — `HeldRoute`, which is not a `Case` and holds its own clean-run
   count rather than having one derived by scanning run records (ADR-0019).
3. **Where it is** — one git-ignored directory with its sidecars, one record per
   route per target, and a read that survives the object and the process that wrote
   it.
"""

from __future__ import annotations

import dataclasses

import pytest

from backend.bench.adaptive.proposal import FOUND_BY_THE_ATTACKER
from backend.bench.admission import (
    NoAdmissionBar,
    bar_for,
    found_by_the_attacker,
    library_provenance,
)
from backend.bench.library import Case, DiscoveredBy


def test_the_sixth_provenance_is_declared_last() -> None:
    """ADR-0117's last stated cost, and ADR-0107 §1's reason for the position.

    The provenance census prints in declaration order, so a member inserted above
    one already counted reorders a line readers of two gate runs compare. Asserted
    as the whole sequence rather than as `list(DiscoveredBy)[-1]`, because what the
    reader of two runs needs is that *none* of the five moved.
    """
    assert list(DiscoveredBy) == [
        DiscoveredBy.AUTHORED,
        DiscoveredBy.ADAPTIVE,
        DiscoveredBy.USER_GAP,
        DiscoveredBy.RETRIEVED,
        DiscoveredBy.ADAPTIVE_ON_TARGET,
        DiscoveredBy.TARGET_SPECIFIC,
    ]


def test_the_provenance_census_prints_six_members_in_declaration_order() -> None:
    """ADR-0107 §1's reason for the position, asked of the line it is about.

    The census is the artefact the ordering claim is *for*: a reader comparing two
    gate runs reads this line, so the assertion is on the printed order and not
    only on the enum's.
    """
    stated = library_provenance([]).stated()
    live = next(
        line for line in stated.splitlines() if line.startswith("provenance of")
    )
    printed = [member for member in DiscoveredBy if f"{member} 0" in live]

    assert printed == list(DiscoveredBy)
    assert live.index("target_specific") > live.index("adaptive_on_target")
    assert "retirement rate, target_specific: none written" in stated


def test_a_case_cannot_carry_the_held_route_provenance(library: list[Case]) -> None:
    """ADR-0117 §1 carried by the type rather than by a rule at a call site.

    A record claiming this provenance would be a held route inside the shared
    instrument — counted on a family's denominator and versioned into the library
    digest — so it is refused where every case record is built, which is
    `Case.__post_init__` calling `bar_for`.
    """
    with pytest.raises(NoAdmissionBar, match="faces no admission bar"):
        dataclasses.replace(
            library[0], discovered_by=DiscoveredBy.TARGET_SPECIFIC, admission=None
        )

    with pytest.raises(NoAdmissionBar):
        bar_for(DiscoveredBy.TARGET_SPECIFIC)


def test_the_held_route_provenance_is_in_neither_half_of_the_adaptive_fraction(
    library: list[Case],
) -> None:
    """`found_by_the_attacker` answers `False` here, and #223 does not return.

    That defect needs a member a `Case` can carry, and the test above is why this
    one cannot: both counts are zero by construction, so the member is in neither
    the numerator nor the denominator of the fraction ADR-0012 §2 asks for.
    """
    provenance = library_provenance(library)

    assert provenance.live[DiscoveredBy.TARGET_SPECIFIC] == 0
    assert provenance.retired[DiscoveredBy.TARGET_SPECIFIC] == 0
    assert provenance.retirement_rate(DiscoveredBy.TARGET_SPECIFIC) is None
    assert found_by_the_attacker(DiscoveredBy.TARGET_SPECIFIC) is False
    assert DiscoveredBy.TARGET_SPECIFIC not in FOUND_BY_THE_ATTACKER
