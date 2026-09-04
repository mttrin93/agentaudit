"""Prints candidate phrasings from the corpus, for a person to read and judge.

    uv run python -m scripts.retrieve_candidates --family data_leakage --k 20
    uv run python -m scripts.retrieve_candidates --family scope_creep --k 20

**What comes back is candidates and never cases.** Each line is a published row, its
address, its distance from the declared query, and the publisher's own content-safety
label — which is not one of the six and cannot be turned into one by this script
(`corpus/queries.py`). Which family a phrasing belongs to is a judgement, and #64 is
the ticket that has to make that judgement into an instrument before it may sit
upstream of a scored rate
([ADR-0045](../docs/adr/0045-the-corpus-is-a-search-surface-and-never-a-library.md)).

**The suppressed rows are printed too, with what suppressed them.** A selection is
only reviewable if the rejections are visible: twenty rows that all say *ignore all
previous instructions* is the failure this group is guarding against, and the way to
see that the guard worked is to read what it threw away and agree.

**The near-duplicate floor is not an argument, and that is deliberate.** It is a
declared input with a measurement behind it (`selection.NEAR_DUPLICATE_FLOOR`), and a
flag would have made it a per-invocation choice — which is a per-family floor with
extra steps, and the one thing that literal's own docstring rules out. Trying a
different floor means editing the literal and re-reading the measurement, which is the
cost that keeps the figure meaningful.

**It reads the store and writes nothing.** No case record, no precedent, no run state.
Needs `uv sync --extra corpus` and an index built by `scripts.index_corpus`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from backend.corpus import index
from backend.corpus.queries import family_named, query_for, searchable
from backend.corpus.selection import NEAR_DUPLICATE_FLOOR, select_spread

OVERSAMPLE = 6
"""How many candidates are retrieved per candidate wanted.

The floor rejects, so asking the store for exactly `k` and then suppressing leaves
fewer than `k`. Six is not measured and does not need to be: it is a request size, the
answer is unchanged by making it larger, and `Selection.short_by` reports the case
where even this was not enough rather than letting the shortfall pass unremarked.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--family",
        required=True,
        choices=searchable(),
        help="the family whose declared query to search with. The three families "
        "absent from this list are absent for reasons corpus/queries.py states.",
    )
    parser.add_argument("--k", type=int, default=20)
    parser.add_argument(
        "--store",
        type=Path,
        default=index.CORPUS_STORE,
        help="the index to read, for a store built somewhere other than ./corpus",
    )
    parsed = parser.parse_args(argv)

    query = query_for(family_named(parsed.family))
    print(f"query ({parsed.family}): {query}")
    print(f"floor: {NEAR_DUPLICATE_FLOOR} cosine, between selected candidates")

    with index.opened(parsed.store) as collection:
        candidates = index.search(collection, query, parsed.k * OVERSAMPLE)

    chosen = select_spread(candidates, k=parsed.k, floor=NEAR_DUPLICATE_FLOOR)
    for position, candidate in enumerate(chosen.selected, start=1):
        print(
            f"\n{position:>3}. {candidate.address.stated()}  "
            f"d={candidate.query_distance:.3f}"
        )
        print(f"     {candidate.text.strip()[:400]}")
    print(f"\nsuppressed as near-duplicates: {len(chosen.suppressed)}")
    for suppressed, blocker in chosen.suppressed:
        print(f"  {suppressed.stated()}\n    too near {blocker.stated()}")
    if chosen.short_by:
        print(
            f"\nshort by {chosen.short_by}: the corpus did not supply {parsed.k} "
            f"phrasings at least {NEAR_DUPLICATE_FLOOR} apart for this query"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
