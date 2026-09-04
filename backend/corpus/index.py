"""The vector index: where it lives, who holds it open, and for how long.

A thin adapter and deliberately thin. Everything worth arguing about — what a
document is, what an address is, which candidates survive the near-duplicate floor —
is in the modules beside this one and is tested without `chromadb` installed. What is
left here is the part that cannot be tested at all, because exercising it downloads a
79.3 MB embedding model over the network
([ADR-0045](../../docs/adr/0045-the-corpus-is-a-search-surface-and-never-a-library.md)).

**Where the store lives.** `/corpus/`, git-ignored, beside `/precedent/`,
`/decisions/`, `/runs/` and `/checkpoints/`. Why it is git-ignored, why it is
deliberately not a `store.DatabaseStore` subclass, and why that is ADR-0029 decision 6
applied rather than skipped are
[ADR-0045](../../docs/adr/0045-the-corpus-is-a-search-surface-and-never-a-library.md)
decision 3.

**Who owns the connection, and what that costs here.** The batch owns it, on ADR-0045
decision 3's reading of ADR-0032's deciding question — no operation in this module
spans a wait. The local consequence is `opened`: a context manager rather than a
module-level client, and `clear_system_cache` on the way out, because `chromadb`
caches a client per path and a second `opened` in one process would otherwise be handed
the first one's system. Without that line the ownership would be a comment.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.corpus.documents import CorpusAddress, CorpusDocument
from backend.corpus.selection import Candidate

CORPUS_STORE = Path(__file__).resolve().parents[2] / "corpus"
"""The git-ignored directory the index is written to.

At the repository root beside the other four derived stores rather than inside
`backend/`, so that the one glob `load_library` runs — `backend/cases/*.toml` — cannot
reach it however the store's internals change.
"""

COLLECTION = "aegis-2-0"
"""The collection name inside the store.

Named after the corpus and not after this bench, because the store holds one
publisher's material and a second corpus (HarmBench, deferred to a later ticket)
would be a second collection rather than more rows in this one. Mixing two
publishers' rows under one name would make an address's corpus half unverifiable
from the index.
"""

METRIC = "cosine"
"""The distance the index ranks by, declared because the default is not this.

`chromadb` defaults to squared L2. `selection.NEAR_DUPLICATE_FLOOR` is a cosine
distance and is measured as one, so the store is asked for cosine and one metric
governs both the ranking and the floor. A store built under the default would rank
plausibly and compare against a floor read on a different scale.
"""

BATCH = 2000
"""Documents written per call.

`chromadb` caps a single `add` well below the corpus size, so ingestion is chunked.
The number is not a tuning knob — anything under the cap is correct — and it is named
rather than inlined only so that a reader of the loop is not left wondering whether it
is arithmetic.
"""


@dataclass(frozen=True)
class IndexReport:
    """What one ingestion wrote, in the terms the next one can be compared against.

    `documents` and `dropped` come from `documents_from`; `held_before` and
    `held_after` are what the store held either side of the write. An ingestion that
    is idempotent writes the same ids over the same texts, so a second run reports the
    same four numbers and `held_before == held_after` — which is the property
    `scripts/index_corpus.py` is asked to demonstrate rather than assert, because
    asserting it would mean a test that embeds 28,214 documents.
    """

    documents: int
    dropped: int
    held_before: int
    held_after: int

    def stated(self, rows: int) -> str:
        """The four numbers in the words the operator reads them in."""
        return (
            f"indexed {self.documents} documents from {rows} rows "
            f"({self.dropped} dropped for an empty prompt); the store held "
            f"{self.held_before} and now holds {self.held_after}"
        )


@contextmanager
def opened(store: Path = CORPUS_STORE) -> Iterator[Any]:
    """The collection, for the length of one batch, and closed after it.

    One client per batch, cleared on the way out, for the reason this module's
    docstring gives.
    """
    import chromadb

    store.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(store))
    try:
        yield client.get_or_create_collection(
            name=COLLECTION, metadata={"hnsw:space": METRIC}
        )
    finally:
        client.clear_system_cache()


def write(collection: Any, documents: Sequence[CorpusDocument]) -> None:
    """Upsert every document under its address, in chunks the store accepts.

    `upsert` and not `add`, which is the whole of what makes a re-index idempotent: an
    address that is already there is written over with the same text rather than
    raising or duplicating. The ids are `CorpusAddress.stated()`, so a re-index at the
    same revision touches the same rows and a re-index at a *new* revision writes new
    ones — which is correct, because a different revision is a different corpus.
    """
    for start in range(0, len(documents), BATCH):
        chunk = documents[start : start + BATCH]
        collection.upsert(
            ids=[document.address.stated() for document in chunk],
            documents=[document.text for document in chunk],
            metadatas=[document.metadata() for document in chunk],
        )


def search(collection: Any, query: str, take: int) -> list[Candidate]:
    """The `take` nearest rows to one declared query, with their embeddings.

    Embeddings are asked for because `selection.select_spread` needs the distances
    *between* candidates and the store reports only distance to the query. Fetching
    them here rather than re-embedding later is what keeps the suppression a function
    of the same vectors the ranking used.

    Each id is parsed back into a `CorpusAddress`, so the boundary where an address
    stops being a string is the same boundary where the store stops being ours. An id
    the store returns that this repository cannot parse is a raise, which is what a
    collection built by something else looks like from here.
    """
    found = collection.query(
        query_texts=[query],
        n_results=take,
        include=["documents", "embeddings", "distances"],
    )
    return [
        Candidate(
            address=CorpusAddress.parse(address),
            text=text,
            embedding=tuple(float(value) for value in embedding),
            query_distance=float(distance),
        )
        for address, text, embedding, distance in zip(
            found["ids"][0],
            found["documents"][0],
            found["embeddings"][0],
            found["distances"][0],
            strict=True,
        )
    ]
