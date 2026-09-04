"""Near-duplicate suppression, which is a property of the selection and not the corpus.

Twenty retrieved candidates for indirect injection are twenty rephrasings of "ignore
all previous instructions" unless something stops them being. A floor between the
query and each candidate does not stop it — every rephrasing is near the query, which
is why it was retrieved. The floor has to hold between the *selected* candidates, and
against **all** of them rather than the first, which is what the fixture here
separates: `SIDEWAYS` is far enough from the nearest selection and too near the
second, so an implementation that compared only against the first would take it.

The distances are hand-computable on purpose. Unit vectors in two dimensions, cosine
distance `1 - cos`, so the expected answers come off the geometry rather than off a
second run of the code under test.
"""

import pytest

from backend.corpus.documents import CorpusAddress
from backend.corpus.selection import Candidate, select_spread


def _at(row: str) -> CorpusAddress:
    """An address for a fixture candidate, so the fixtures read as candidates do."""
    return CorpusAddress(identifier="corpus", revision="r1", row=row)


NEAR = Candidate(
    address=_at("near"),
    text="ignore all previous instructions",
    embedding=(1.0, 0.0),
    query_distance=0.01,
)
SAME = Candidate(
    address=_at("same"),
    text="Ignore all previous instructions.",
    embedding=(1.0, 0.0),
    query_distance=0.02,
)
APART = Candidate(
    address=_at("apart"),
    text="what is the capital of Peru",
    embedding=(0.0, 1.0),
    query_distance=0.50,
)
# cos with NEAR is 0.6 (distance 0.40); cos with APART is 0.8 (distance 0.20).
SIDEWAYS = Candidate(
    address=_at("sideways"),
    text="a third thing",
    embedding=(0.6, 0.8),
    query_distance=0.60,
)


def test_the_floor_holds_against_every_selection_and_not_only_the_first() -> None:
    chosen = select_spread([NEAR, SAME, APART, SIDEWAYS], k=4, floor=0.3)

    assert [held.address.row for held in chosen.selected] == ["near", "apart"]
    assert chosen.suppressed == (
        (_at("same"), _at("near")),
        (_at("sideways"), _at("apart")),
    )
    assert chosen.short_by == 2


def test_the_selection_stops_at_k() -> None:
    chosen = select_spread([NEAR, APART, SIDEWAYS], k=1, floor=0.0)
    assert [held.address.row for held in chosen.selected] == ["near"]
    assert chosen.short_by == 0


def test_a_candidate_with_no_embedding_cannot_be_checked_and_is_refused() -> None:
    # The floor is computed from the embeddings the store returned. A candidate
    # fetched without them would be admitted unchecked, which is the failure this
    # module exists to prevent, so it is a raise rather than a pass-through.
    with pytest.raises(ValueError):
        select_spread(
            [
                Candidate(
                    address=_at("blind"), text="x", embedding=(), query_distance=0.0
                )
            ],
            k=1,
            floor=0.3,
        )
