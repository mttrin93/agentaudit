"""Prints what the family-assignment instrument says about retrieved candidates.

    uv run python -m scripts.assign_candidates --family data_leakage --k 20
    uv run python -m scripts.assign_candidates --whole-corpus

`scripts/retrieve_candidates.py` prints candidates for a person to read. This prints
the same selection with a **proposal** beside each row, and a tally underneath — so a
person deciding which of the six a phrasing belongs to starts from a shortlist rather
than from twenty rows.

**Every line says whether the instrument is fit to propose, and today it is not.** The
sentence is `assignment.stated_fitness()` and the figures behind it are on
`assignment.MEASURED_AGREEMENT` and `assignment.AGREEMENT_FLOOR`
([ADR-0046](../docs/adr/0046-a-family-assignment-is-proposed-here-and-decided-by-a-person.md),
[docs/validation.md](../docs/validation.md)). So this script is a reading aid whose
own reading says to read the candidate, and nothing it prints is a record: the record
is an `assignment.Assignment`, which takes its family from the person and refuses an
unattributed one.

`--whole-corpus` walks every document in the store instead of running a query, which
is the measurement that says what the corpus can supply *at all* rather than what one
declared query's top `k` happens to hold. It embeds nothing, so it is minutes rather
than hours.

**It reads the store and writes nothing.** Needs `uv sync --extra corpus` and an index
built by `scripts.index_corpus`.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from backend.corpus import index
from backend.corpus.assignment import (
    NOT_PROPOSABLE,
    PROPOSABLE,
    FamilyProposal,
    propose,
    stated_fitness,
)
from backend.corpus.documents import CorpusAddress
from backend.corpus.queries import family_named, query_for, searchable
from backend.corpus.selection import NEAR_DUPLICATE_FLOOR, select_spread

OVERSAMPLE = 6
"""How many candidates are retrieved per candidate wanted.

`retrieve_candidates.OVERSAMPLE`'s number and its reasoning, repeated rather than
imported because the two scripts are two entry points and a shared constant between
them would make changing one change the other's declared behaviour.
"""

PAGE = 2000
"""Documents read per `get` on a whole-corpus walk. The store's own comfortable page."""


def _answer(proposed: FamilyProposal) -> str:
    """The tally key for one proposal: the family it named, or why it named none.

    One function because both walks below count the same thing, and two copies of
    this expression would let a per-query tally and a whole-corpus tally disagree
    about what a refusal is called.
    """
    if proposed.family is not None:
        return proposed.family.value
    return str(proposed.undecidable)


def _tally(counted: Counter[str], over: int) -> None:
    """The proposals by answer, which is the figure a reader of a run wants."""
    print(f"\nover {over} candidates:")
    for answer, count in counted.most_common():
        print(f"  {answer:<28} {count:>6}  {100 * count / over:5.2f}%")
    print(
        f"\nfamilies this instrument may not propose, whatever the text says: "
        f"{', '.join(sorted(family.value for family in NOT_PROPOSABLE))}"
    )


def _one_query(family_name: str, k: int, store: Path) -> None:
    """One declared query's selection, each row with what the instrument says."""
    family = family_named(family_name)
    query = query_for(family)
    print(f"query ({family_name}): {query}")
    print(f"floor: {NEAR_DUPLICATE_FLOOR} cosine, between selected candidates")
    if family not in PROPOSABLE:
        print(
            f"\nnote: `{family_name}` has a declared query and is a family this "
            f"instrument may not propose. {NOT_PROPOSABLE[family]}"
        )

    with index.opened(store) as collection:
        candidates = index.search(collection, query, k * OVERSAMPLE)
    chosen = select_spread(candidates, k=k, floor=NEAR_DUPLICATE_FLOOR)

    counted: Counter[str] = Counter()
    for position, candidate in enumerate(chosen.selected, start=1):
        proposed = propose(candidate.address, candidate.text)
        counted[_answer(proposed)] += 1
        print(f"\n{position:>3}. {proposed.stated()}")
        print(f"     d={candidate.query_distance:.3f}  {candidate.text.strip()[:300]}")
    if chosen.short_by:
        print(f"\nshort by {chosen.short_by}: the corpus did not supply {k}")
    _tally(counted, len(chosen.selected))


def _whole_corpus(store: Path) -> None:
    """What the corpus can supply at all, which is not what one query's top k holds."""
    counted: Counter[str] = Counter()
    read = 0
    with index.opened(store) as collection:
        total = collection.count()
        print(f"walking {total} documents; no query, no embedding")
        while read < total:
            page = collection.get(limit=PAGE, offset=read, include=["documents"])
            for address, text in zip(page["ids"], page["documents"], strict=True):
                counted[_answer(propose(CorpusAddress.parse(address), text))] += 1
                read += 1
    _tally(counted, read)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", choices=searchable())
    parser.add_argument("--k", type=int, default=20)
    parser.add_argument("--whole-corpus", action="store_true")
    parser.add_argument("--store", type=Path, default=index.CORPUS_STORE)
    parsed = parser.parse_args(argv)
    if bool(parsed.family) == parsed.whole_corpus:
        parser.error("one of --family or --whole-corpus, and not both")

    print(f"instrument: {stated_fitness()}")
    if parsed.whole_corpus:
        _whole_corpus(parsed.store)
    else:
        _one_query(parsed.family, parsed.k, parsed.store)
    return 0


if __name__ == "__main__":
    sys.exit(main())
