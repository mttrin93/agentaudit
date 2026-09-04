"""Where the corpus came from, stored so a build that fetched something else says so.

The material this package indexes is published by somebody else and cannot be
committed: 33,416 rows, most of them harmful prompts, which
[ADR-0008](../../docs/adr/0008-repo-disclosure-posture.md) forbids far more clearly
than it forbids any single case payload. So what is stored is not the corpus but the
*record* of it — identifier, revision, licence, attribution, and one SHA-256 per
published file — on the reasoning
[ADR-0036](../../docs/adr/0036-a-published-identifier-resolves-to-a-stored-copy.md)
gives for the published lists, applied to material that may not be copied
([ADR-0045](../../docs/adr/0045-the-corpus-is-a-search-surface-and-never-a-library.md)).

**Why a digest here when ADR-0036 refused one for the OWASP copies** is ADR-0045
decision 2. The consequence at this call site is that the digests below are of the
*publisher's* files rather than of anything this repository wrote, so `drift` is asked
before a byte is indexed and refuses rather than warns
(`scripts/index_corpus.py`).

**Attribution.** The corpus is published by NVIDIA under the Creative Commons
Attribution 4.0 International licence, ungated. `ATTRIBUTION` below is the notice that
licence requires, and it is what `scripts/index_corpus.py` prints — a licence that asks
for attribution is not satisfied by a URL in a docstring nobody runs.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class SourceFile:
    """One published file of the corpus: its name, its digest, and its row count.

    The row count is stored beside the digest rather than derived, because the two
    fail differently and a reader needs both answers. A digest mismatch says *this is
    not the file we read*; a count mismatch on a matching digest would say *the reader
    of this file has changed*, which is a bug here rather than a drift there.
    """

    name: str
    sha256: str
    rows: int


@dataclass(frozen=True)
class StoredSource:
    """The published corpus this bench searches, recorded rather than copied.

    Every field is a claim a reader can check against the publisher without this
    repository's help, which is the whole design: `identifier` and `revision` address
    the material, `files` pins its bytes, and `licence` and `attribution` say on what
    terms it was used. Nothing here is a judgement about this bench — the same
    separation `editions.py` keeps between a copy and what claims it.
    """

    identifier: str
    also_published_as: str
    revision: str
    licence: str
    attribution: str
    read_on: date
    files: tuple[SourceFile, ...]
    note: str

    @property
    def rows(self) -> int:
        """The published row count, summed from the files rather than declared.

        A total typed by hand beside five counts is a sixth number that can disagree
        with the other five.
        """
        return sum(file.rows for file in self.files)

    def url(self, name: str) -> str:
        """Where one published file is fetched from, pinned to the revision.

        Pinned and not `main`: a corpus address stored on a case record (#65) is only
        an address if the thing it addresses cannot be replaced underneath it.
        """
        return (
            f"https://huggingface.co/datasets/{self.identifier}/resolve/"
            f"{self.revision}/{name}"
        )

    def drift(self, digests: Mapping[str, str]) -> str | None:
        """What a reader is told when the fetched files are not the stored ones.

        `None` when every stored file is present at its stored digest, and otherwise
        one sentence naming every file that disagrees and how. The caller's job is to
        refuse: an index built from a file this record cannot vouch for is an index
        whose addresses point somewhere nobody read.

        Three ways to disagree and all three are named, because they need different
        fixes. A **missing** file is an incomplete fetch. A **changed** digest is the
        publisher having moved, or a truncated download. An **unexpected** file is
        this record having gone stale against a corpus that grew a split — the one
        case where the repository is wrong and the fetch is right.
        """
        stored = {file.name: file.sha256 for file in self.files}
        faults = [
            f"{name} is missing" for name in sorted(stored) if name not in digests
        ]
        faults += [
            f"{name} is sha256:{digests[name][:12]} and this repository read "
            f"sha256:{stored[name][:12]}"
            for name in sorted(stored)
            if name in digests and digests[name] != stored[name]
        ]
        faults += [
            f"{name} is not a file this repository read"
            for name in sorted(digests)
            if name not in stored
        ]
        if not faults:
            return None
        return (
            f"{self.identifier} at revision {self.revision[:12]} is not what this "
            f"repository read on {self.read_on.isoformat()}: " + "; ".join(faults)
        )


ATTRIBUTION = (
    "Nemotron Content Safety Dataset V2 (formerly Aegis AI Content Safety Dataset "
    "2.0) © NVIDIA Corporation, licensed under CC BY 4.0 "
    "(https://creativecommons.org/licenses/by/4.0/). Used unmodified as a retrieval "
    "corpus; no part of it is redistributed by this repository."
)
"""The notice CC BY 4.0 asks for, in the words a reader of a build log sees.

Kept as a constant rather than as prose in this module's docstring because the
licence's condition is that the notice travels with the use, and the use is
`scripts/index_corpus.py`, which prints it.
"""


AEGIS_2_0 = StoredSource(
    identifier="nvidia/Aegis-AI-Content-Safety-Dataset-2.0",
    also_published_as="Nemotron Content Safety Dataset V2",
    revision="d86bb8bedff51d25ac834ab7838f1cc61acb7a2c",
    licence="CC-BY-4.0",
    attribution=ATTRIBUTION,
    read_on=date(2026, 9, 4),
    files=(
        SourceFile(
            name="train.json",
            sha256="154fba82c71d9fa73abd2ca5588a198e693ddc816c83444df180a22f613e02f6",
            rows=25007,
        ),
        SourceFile(
            name="validation.json",
            sha256="a97200e226ad4f6ba6a639982f817f675909bc74513859df3e8fc9a92951dfcd",
            rows=1245,
        ),
        SourceFile(
            name="test.json",
            sha256="b0a6d602260524866053cb34105194f074f2c2906e3691b68d43b9e6e9318f35",
            rows=1964,
        ),
        SourceFile(
            name="refusals_train.json",
            sha256="ff948d3696c9da94cf2523f5d4ae7f16cad7b3c0fd3cb46a331dad0ed717fbe2",
            rows=5000,
        ),
        SourceFile(
            name="refusals_validation.json",
            sha256="aba81546da0108bc931ae7fb7662b687b42b0bb3e734cde34fbddfbe33cadfcf",
            rows=200,
        ),
    ),
    note=(
        "The publisher renamed this dataset after the identifier was chosen: the "
        "card now reads Nemotron Content Safety Dataset V2, and the identifier "
        "resolves unchanged. Recorded because a reader who searches for the new name "
        "and finds no such dataset id has been given two facts that look like a "
        "contradiction. The five files hold 33,416 rows between them and 28,214 "
        "distinct prompts: the refusals files re-use a row id to publish a second "
        "response to a prompt already published, so an id addresses a prompt and "
        "never a row (`documents.py`)."
    ),
)
"""The corpus, read on 2026-09-04 from the publisher's own repository at one revision.

**Read and not transcribed.** The five files were fetched from
`huggingface.co/datasets/nvidia/Aegis-AI-Content-Safety-Dataset-2.0` at the revision
above, which is the commit the dataset's own API named as its head on that date, and
the digests here are of those bytes. That is a stronger provenance than either OWASP
copy in `editions.py` has — nothing was read through a page-to-text conversion and
nothing needed a second reading to corroborate it — and it is available only because
this material is fetched at build time rather than copied into the tree.

**What was checked about the content, beyond the digests.** Row counts per file, the
33,416 total the publisher's card states, 28,214 distinct prompt ids, and two rows
whose prompt is null. Recorded in [docs/validation.md](../../docs/validation.md)
beside what has *not* been checked, which is everything about whether the rows say
what the publisher's labels say they say.
"""


EMBEDDING_MODEL = "chroma:onnx:all-MiniLM-L6-v2"
"""The embedding model the index is built with, declared because it decides the answer.

A corpus indexed with one embedding model returns a different set for the same query
than the same corpus indexed with another, so the model belongs on the record beside
the corpus revision — the argument
[ADR-0025](../../docs/adr/0025-the-console-may-set-a-runs-declared-inputs.md) makes for
the attacker's model, applied to the instrument that decides what a human is shown.

This is `chromadb`'s own default: the quantised ONNX build of
`sentence-transformers/all-MiniLM-L6-v2`, 384 dimensions, cosine distance. Chosen for
having no per-query cost and no key to rotate, and **not** for being offline — the
first use downloads a 79.3 MB archive from `chroma-onnx-models.s3.amazonaws.com` into
`~/.cache/chroma`, measured on 2026-09-04, which is a build-time fetch by a person and
is the reason no test may construct this index.
"""


EMBEDDING_MODEL_ARCHIVE = (
    "913d7300ceae3b2dbc2c50d1de4baacab4be7b9380491c27fab7418616a16ec3"
)
"""SHA-256 of the model archive `EMBEDDING_MODEL` names, read on 2026-09-04.

Stored for the reason the corpus files' digests are: the model is a declared input
fetched from a third party, so *which* model answered a query is a claim, and a claim
this repository prints is one it can be asked to back. `scripts/index_corpus.py`
reports the archive it found beside this value; it does not refuse on a mismatch,
because a model archive republished at a new digest is a fact about the index that a
person has to decide about, not one a script can decide for them.
"""


@dataclass(frozen=True)
class RetrievalInputs:
    """The two declared inputs that decide what a query returns, in one record.

    #63 asks that "the embedding model and corpus version are recorded where a reader
    of a case record can reach them", and the two halves arrive by different routes.
    The **revision** travels inside every address, because `CorpusAddress` carries it
    (`documents.py`); the **model** cannot, since it is not a property of the row. So
    this record is the other end of that walk: #65 stores an address on a case record,
    `resolves` says whether this record is the one that address was written under, and
    `stated()` is the sentence a reader of the record is given.

    A record rather than two loose constants, because the pair is what a reader needs
    together — a revision without the model that indexed it does not say what came
    back, and a model without the revision does not say what it came back *from*.
    """

    source: StoredSource
    embedding_model: str
    archive: str

    def resolves(self, address: str) -> bool:
        """Whether one stored corpus address was written under these inputs.

        A reader holding a case record asks *which model retrieved this*, and gets an
        answer or a `False` that means the record predates a re-index at a new
        revision. Not a raise: an address from a superseded revision is a real thing
        that still names real material, and diagnosing it is `StoredSource`'s job
        rather than a crash here.
        """
        prefix = f"{self.source.identifier}@{self.source.revision}#"
        return address.startswith(prefix) and len(address) > len(prefix)

    def stated(self) -> str:
        """What a reader of a case record is told about how its payload was found."""
        return (
            f"retrieved from {self.source.identifier} "
            f"({self.source.also_published_as}) at revision "
            f"{self.source.revision[:12]}, {self.source.licence}, indexed with "
            f"{self.embedding_model} — both are declared inputs and either changes "
            "what a query returns"
        )


RETRIEVAL = RetrievalInputs(
    source=AEGIS_2_0, embedding_model=EMBEDDING_MODEL, archive=EMBEDDING_MODEL_ARCHIVE
)
"""The inputs every candidate this repository has ever retrieved was retrieved under.

One value and not a constructor call at each site, so that *the corpus this bench
searches* is a single thing a reader can find, and so that #65 has one name to store
against rather than a pair to keep in step.
"""
