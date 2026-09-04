"""A published row, turned into one addressable document, and the address itself.

The published files are rows and the corpus is prompts, and the difference is not
cosmetic. The refusals files re-publish a prompt already in `train.json` under the
same id with a second response, so 33,416 rows carry 28,214 distinct ids — read off
the corpus on 2026-09-04 and recorded on `source.AEGIS_2_0`. What this bench searches
for is a *phrasing that makes an agent do something*, which is the prompt; the
response is somebody else's model answering, and indexing it would put text no
attacker ever sends into the thing an attacker's phrasing is retrieved from.

So one document is one prompt, its id is the address, and an id that ever named two
prompts is a refusal rather than a last-write-wins — because #65 stores that address
on a case record, and an address that can resolve to two payloads is not an address.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from backend.corpus.source import StoredSource


@dataclass(frozen=True, order=True)
class CorpusAddress:
    """Where one document came from: a corpus, a revision, and a row id.

    Carries the revision and not only the id, because the id is the publisher's and
    the publisher may republish. An address that named the id alone would be a
    reference into whatever the corpus happens to be today, which is exactly the
    rot `source.StoredSource.url` pins the fetch against.

    `order=True` so a caller sorting documents gets the same order every time without
    having to know which field to sort on — the property `documents_from` promises and
    a rebuild depends on.
    """

    identifier: str
    revision: str
    row: str

    def stated(self) -> str:
        """The address as one string, which is also the document's id in the index.

        One form and not two: an index whose ids were a second encoding of the same
        fact would let a case record and the index disagree about what an address is.
        """
        return f"{self.identifier}@{self.revision}#{self.row}"

    @classmethod
    def parse(cls, stated: str) -> CorpusAddress:
        """Read an address back, so a stored one can be resolved without the index."""
        rest, _, row = stated.rpartition("#")
        identifier, _, revision = rest.rpartition("@")
        if not (identifier and revision and row):
            raise ValueError(
                f"{stated!r} is not a corpus address: expected "
                "<corpus>@<revision>#<row>"
            )
        return cls(identifier=identifier, revision=revision, row=row)


@dataclass(frozen=True)
class CorpusDocument:
    """One prompt from the corpus, with the publisher's own labels beside it.

    The labels are carried and never interpreted. `prompt_label` and
    `violated_categories` are content-safety judgements about a prompt, and none of
    the six families appears in that taxonomy — which is the whole of why #64 exists.
    Storing them unread is what lets #64 measure a labeller against the publisher's
    answer instead of against its own.
    """

    address: CorpusAddress
    text: str
    prompt_label: str
    violated_categories: tuple[str, ...]

    def metadata(self) -> dict[str, str]:
        """What travels into the index beside the text.

        Flat strings, because that is what the store accepts, and because a metadata
        field is a filter key rather than a record — the record is this dataclass and
        the address is how a reader gets back to it.
        """
        return {
            "row": self.address.row,
            "prompt_label": self.prompt_label,
            "violated_categories": ", ".join(self.violated_categories),
        }


@dataclass(frozen=True)
class ExtractedDocuments:
    """What one pass over the published files produced, and what it left out.

    `dropped` is reported rather than swallowed: a corpus that silently lost rows is
    one whose count cannot be checked against the publisher's, and the count is half
    of what `source.StoredSource` exists to make checkable.
    """

    documents: tuple[CorpusDocument, ...]
    dropped: int


def documents_from(
    rows: Iterable[Mapping[str, Any]], source: StoredSource
) -> ExtractedDocuments:
    """One document per distinct prompt id, in an order a rebuild repeats.

    Ordered by address rather than by the order the files were read in, so that
    `uv run scripts/index_corpus.py` twice over the same revision writes the same ids
    against the same texts — the property #65's stored addresses depend on and the one
    a shuffle would quietly break.

    Raises if one id arrives with two different prompts. That has never happened on
    the stored revision and the guard is not for that revision: it is for the next
    one, where a republished corpus that reused an id for new text would otherwise
    turn every case record pointing at it into a citation of something nobody read.
    """
    seen: dict[str, CorpusDocument] = {}
    dropped = 0
    for row in rows:
        text = row.get("prompt")
        if not isinstance(text, str) or not text.strip():
            dropped += 1
            continue
        document = CorpusDocument(
            address=CorpusAddress(
                identifier=source.identifier, revision=source.revision, row=row["id"]
            ),
            text=text,
            prompt_label=str(row.get("prompt_label") or ""),
            violated_categories=tuple(
                category.strip()
                for category in str(row.get("violated_categories") or "").split(",")
                if category.strip()
            ),
        )
        already = seen.get(document.address.row)
        if already is not None:
            if already.text != document.text:
                raise ValueError(
                    f"row {document.address.row} of {source.identifier} names two "
                    "different prompts, so it is not an address. A case record "
                    "holding it would resolve to whichever was indexed last (#65)"
                )
            continue
        seen[document.address.row] = document
    return ExtractedDocuments(
        documents=tuple(sorted(seen.values(), key=lambda held: held.address)),
        dropped=dropped,
    )
