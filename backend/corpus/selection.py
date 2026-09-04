"""Which of the retrieved candidates a person is actually shown, and why not the rest.

Retrieval ranks by nearness to the query, and nearness to the query is exactly the
property every rephrasing of one attack shares. So the twenty nearest candidates for
*indirect prompt injection* are twenty ways of writing "ignore all previous
instructions", and a family grown from them would have twenty cases, an `n` of two
hundred, and the coverage of one. That is the failure this module exists to prevent
and it is a property of the **selection**, not of the corpus: the corpus holds the
variety, and a rank-ordered top-k throws it away.

The floor therefore holds between the *selected* candidates and against every one of
them, which is the only version that works. Against the query alone it rejects
nothing, because every candidate is near the query by construction. Against the first
selection alone it lets through a candidate that is far from the first and adjacent to
the second, which is the shape a cluster arrives in once the second cluster starts.

**Nothing here decides a family.** A candidate carries no family, no verdict and no
trigger, and this module adds none: what comes out is a shorter list of the same
things that went in
([ADR-0045](../../docs/adr/0045-the-corpus-is-a-search-surface-and-never-a-library.md)).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from backend.corpus.documents import CorpusAddress


@dataclass(frozen=True)
class Candidate:
    """One retrieved row, as the store returned it and before anyone has judged it.

    Deliberately has no `family` field, and the omission is the invariant rather than
    an oversight. A retrieved row is a phrasing somebody published; which of the six
    it belongs to is a judgement, and #64 is the ticket that has to make that
    judgement into a validated instrument before it may sit upstream of a scored rate.
    A `Candidate` that could carry a `Family` would let the judgement be skipped by
    whoever wrote the query.

    `embedding` is carried rather than recomputed. The store already has it, the floor
    needs it, and asking the model a second time would make the suppression depend on
    an input the retrieval did not use.

    `address` is the typed `CorpusAddress` and not the string the store keys on, so a
    candidate cannot be reported, stored or compared under an address nothing has
    parsed. The store's ids *are* that string (`index.write`), and reading one back is
    the parse.
    """

    address: CorpusAddress
    text: str
    embedding: tuple[float, ...]
    query_distance: float


@dataclass(frozen=True)
class Selection:
    """What a query yielded once near-duplicates were taken out, and what it cost.

    `suppressed` names both ends of every rejection — the candidate and the selection
    that stood in its way — because a reader who disagrees with a suppression needs to
    see the pair to disagree with it. A count would say only that the list got shorter.
    Addresses rather than whole candidates, because the pair is a citation and the text
    it cites is already in `selected` or was never wanted.

    `short_by` is the number of candidates asked for and not supplied, and it is
    reported rather than hidden by silently retrieving more. A family whose corpus
    cannot yield `k` distinct phrasings is a fact #67 needs before it plans twenty
    cases, and a selection that quietly widened its search until it filled the quota
    would be a floor that stopped meaning anything at the moment it started to bind.
    """

    selected: tuple[Candidate, ...]
    suppressed: tuple[tuple[CorpusAddress, CorpusAddress], ...]
    short_by: int


NEAR_DUPLICATE_FLOOR = 0.25
"""The cosine distance two selected candidates must be apart, at `EMBEDDING_MODEL`.

**Measured, not chosen.** Read on 2026-09-04 over the built index at
`source.EMBEDDING_MODEL`, against the declared queries in `queries.py`. Pairs a reader
called rephrasings of one another sat **below ~0.20** — two copies of one jailbreak
template at 0.020, the same template with an added prefix at 0.107 — and pairs that
were different attacks sat **above ~0.30**. Read over the whole index, 28,214
documents: at `k = 20` this figure selected twenty for each of the three searchable
families and suppressed ten, four and five, with no shortfall.

**The boundary is not clean, and 0.25 errs toward suppressing.** Both readings are in
[docs/validation.md](../../docs/validation.md), including the pair at 0.222 that two
different attacks fall on the wrong side of. Erring this way costs coverage breadth
rather than coverage validity, which is the direction to be wrong in here.

The figure is a property of *this* embedding model and would have to be re-read if
`EMBEDDING_MODEL` changed, which is why it sits on the literal rather than in an ADR
(CLAUDE.md, case 4).

Deliberately not a fraction anybody can tune per family, and deliberately not a command
line argument either (`scripts/retrieve_candidates.py`). One floor over one model is a
declared input a reader can check; a floor per family, or per invocation, is a number
chosen after seeing what it returned.
"""


def _cosine_distance(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    """`1 - cos`, over the vectors the store returned.

    Computed here rather than read off the store, because the store reports distance
    to the *query* and the floor is about distance between two candidates. The store
    is asked for cosine as well (`index.py`), so one metric governs both numbers.
    """
    magnitude = math.sqrt(sum(value * value for value in left)) * math.sqrt(
        sum(value * value for value in right)
    )
    return 1.0 - sum(a * b for a, b in zip(left, right, strict=True)) / magnitude


def select_spread(candidates: Sequence[Candidate], k: int, floor: float) -> Selection:
    """The `k` nearest candidates that are all at least `floor` apart from each other.

    Greedy in the retrieval order, which is nearest-to-the-query first: the closest
    match to what was asked for is always kept, and a later candidate is dropped by
    the earlier one it duplicates rather than the other way round. That makes the
    answer a function of the query and the floor alone, so two people running the same
    query at the same revision are shown the same twenty rows.

    Refuses a candidate with no embedding rather than skipping the check on it.
    """
    selected: list[Candidate] = []
    suppressed: list[tuple[CorpusAddress, CorpusAddress]] = []
    for candidate in candidates:
        if len(selected) == k:
            break
        if not any(value for value in candidate.embedding):
            raise ValueError(
                f"candidate {candidate.address.stated()} came back with no "
                "embedding, so it "
                "cannot be checked against the near-duplicate floor. Admitting it "
                "unchecked is the one thing this selection may not do"
            )
        blocker = next(
            (
                held.address
                for held in selected
                if _cosine_distance(held.embedding, candidate.embedding) < floor
            ),
            None,
        )
        if blocker is None:
            selected.append(candidate)
        else:
            suppressed.append((candidate.address, blocker))
    return Selection(
        selected=tuple(selected),
        suppressed=tuple(suppressed),
        short_by=max(0, k - len(selected)),
    )
