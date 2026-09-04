"""Prints candidate phrasings from the corpus, for a person to read and judge.

    uv run python -m scripts.retrieve_candidates --family direct_prompt_injection --k 70

**One family is searchable and `k` is about seventy.** #64 hand-read the corpus and
measured what is in it: the one family it holds at volume is
`direct_prompt_injection`, on the elective tier, and yield *falls* as `k` rises — 40%
at `k = 20`, 30% at 60, 22.5% at 120 — so twenty usable candidates need `k ≈ 70`, or
roughly 420 rows at `OVERSAMPLE`. The other queries were dropped rather than re-keyed
([docs/validation.md](../docs/validation.md), `corpus/queries.py`).

**What comes back is candidates and never cases.** Each line is a published row, its
address, its distance from the declared query, and the publisher's own content-safety
label — which is not one of the six and cannot be turned into one by this script
(`corpus/queries.py`). Which family a phrasing belongs to is a judgement, and #64 tried
to make that judgement into an instrument and **measured it unfit**: κ = 0.16 against a
declared floor of 0.40, so `assignment.propose` proposes and a person decides, and the
person's name travels onto the record
([ADR-0045](../docs/adr/0045-the-corpus-is-a-search-surface-and-never-a-library.md),
[ADR-0046](../docs/adr/0046-a-family-assignment-is-proposed-here-and-decided-by-a-person.md)).

**The suppressed rows are printed too, with what suppressed them.** A selection is
only reviewable if the rejections are visible: twenty rows that all say *ignore all
previous instructions* is the failure this group is guarding against, and the way to
see that the guard worked is to read what it threw away and agree.

**And this floor cannot see the failure it is named for.** It reads distances *within
one selection*, so a template repeating across the corpus survives it — #64 read
twenty-one of twenty-five candidates as one prompt-marketplace phrasing. That is why
the population has a second floor a loader enforces, on a technique a person names
([ADR-0048](../docs/adr/0048-a-retrieved-family-grows-by-technique-and-not-by-count.md)).

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
        help="the family whose declared query to search with. The families absent "
        "from this list are absent for reasons corpus/queries.py states, and they "
        "are not one reason: two are judged, one cannot be attacked by a sent prompt "
        "at all, one is decided by the target's tool list, two were hand-read at a "
        "yield of zero, and one was never searched.",
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
