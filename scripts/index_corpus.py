"""Builds the vector index over the published corpus the LLM-list families grow from.

    uv sync --extra corpus
    uv run python -m scripts.index_corpus
    uv run python -m scripts.index_corpus --from ~/aegis --keep

**A build-time instrument, run by a person, and never by a run or by CI.** It fetches
five published files, checks their digests against `corpus.source.AEGIS_2_0`, turns
them into one document per prompt and upserts them under their addresses. Nothing it
produces reaches a case record, a rate or a gate decision — the step from a retrieved
phrasing to an admitted case is a human judgement (#64) and an admission bar (#65),
and neither is here
([ADR-0045](../docs/adr/0045-the-corpus-is-a-search-surface-and-never-a-library.md)).

**What it costs.** Roughly an hour and three quarters of wall time on four cores for
the whole corpus, almost all of it embedding — measured on 2026-09-04. That is a
per-revision cost paid once by whoever rebuilds, and it is the number to know before
planning a second corpus: `chromadb`'s bundled model runs on the CPU, and there is no
per-query cost afterwards. A query against the built index answers in under a second.

**It reaches the network twice and says so both times.** The five files come from the
publisher at the pinned revision, and the first run of the embedding model downloads a
79.3 MB archive into `~/.cache/chroma`. That is why this is a script and not a test,
why `chromadb` is an optional extra CI does not install, and why the ticket's
expectation of "no network in the build path" is corrected in ADR-0045 rather than
repeated here.

**Idempotent, and demonstrably so.** Documents are keyed by
`CorpusAddress.stated()` and written with `upsert`, and extraction sorts by address,
so a second run over the same revision writes the same ids over the same texts and
reports the same counts. Run it twice and compare the four numbers it prints; that is
the check, and it is a demonstration rather than an assertion because asserting it
would mean a test that embeds 28,214 documents.

**What it does not do.** It does not delete. A revision change writes new addresses
beside the old ones rather than over them, because a case record admitted against the
old revision still cites it and a store that dropped the row would turn that citation
into a dangling one. Removing a superseded revision is a decision with a case-record
consequence, so it is a person's with `rm -rf corpus/`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import httpx

from backend.corpus import index
from backend.corpus.documents import documents_from
from backend.corpus.source import (
    AEGIS_2_0,
    EMBEDDING_MODEL,
    EMBEDDING_MODEL_ARCHIVE,
    StoredSource,
)

MODEL_ARCHIVE = (
    Path.home()
    / ".cache"
    / "chroma"
    / "onnx_models"
    / EMBEDDING_MODEL.rpartition(":")[2]
    / "onnx.tar.gz"
)
"""Where `chromadb` caches the archive `source.EMBEDDING_MODEL` names.

The model's own directory and not whatever archive sorts first under
`onnx_models/`: a machine that has cached a second model would otherwise be told
"as recorded" about an archive this index never used.
"""


def _digest(path: Path) -> str:
    reading = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            reading.update(block)
    return reading.hexdigest()


def _fetched(source: StoredSource, into: Path) -> Path:
    """The five published files on disk, downloaded if they are not there already."""
    into.mkdir(parents=True, exist_ok=True)
    for file in source.files:
        landing = into / file.name
        if landing.exists():
            continue
        print(f"fetching {file.name} from {source.url(file.name)}")
        with httpx.stream(
            "GET", source.url(file.name), follow_redirects=True, timeout=300.0
        ) as response:
            response.raise_for_status()
            with landing.open("wb") as handle:
                for block in response.iter_bytes():
                    handle.write(block)
    return into


def _rows(directory: Path, source: StoredSource) -> list[dict[str, Any]]:
    """Every published row, with the digests checked before a byte is indexed.

    The refusal is the point of storing digests at all. An index built from a file
    this repository cannot vouch for is an index whose addresses point at something
    nobody read, and a case record citing one of those addresses would be a citation
    of an unknown payload.
    """
    present = {
        file.name: _digest(directory / file.name)
        for file in source.files
        if (directory / file.name).exists()
    }
    drifted = source.drift(present)
    if drifted is not None:
        raise SystemExit(drifted)
    rows: list[dict[str, Any]] = []
    for file in source.files:
        held = json.loads((directory / file.name).read_text(encoding="utf-8"))
        if len(held) != file.rows:
            raise SystemExit(
                f"{file.name} holds {len(held)} rows and this repository read "
                f"{file.rows}, at a digest that matches. That is a reader bug here, "
                "not drift there"
            )
        rows.extend(held)
    return rows


def _model_archive_said() -> str:
    """What the embedding model on this machine is, beside what was recorded.

    Reported and never refused on. A model archive republished at a new digest is a
    fact about every answer the index gives, and deciding what to do about it — re-read
    the floor, or re-index — is a person's call rather than a script's.
    """
    if not MODEL_ARCHIVE.is_file():
        return (
            f"embedding model: {EMBEDDING_MODEL} is not yet cached at "
            f"{MODEL_ARCHIVE}; the first index will fetch it"
        )
    found = _digest(MODEL_ARCHIVE)
    agrees = "as recorded" if found == EMBEDDING_MODEL_ARCHIVE else "NOT as recorded"
    return f"embedding model: {EMBEDDING_MODEL} sha256:{found[:12]} — {agrees}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--from",
        dest="source_dir",
        type=Path,
        default=None,
        help="a directory already holding the five published files, so nothing is "
        "fetched. Their digests are checked either way.",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="keep the downloaded files, in ./aegis, instead of discarding them",
    )
    parser.add_argument(
        "--store",
        type=Path,
        default=index.CORPUS_STORE,
        help="the index to write, for a store built somewhere other than ./corpus",
    )
    parsed = parser.parse_args(argv)

    print(AEGIS_2_0.attribution)
    print(f"corpus: {AEGIS_2_0.identifier} at {AEGIS_2_0.revision}")
    print(_model_archive_said())

    with tempfile.TemporaryDirectory() as scratch:
        directory = parsed.source_dir or _fetched(
            AEGIS_2_0, Path(scratch) if not parsed.keep else Path("aegis")
        )
        rows = _rows(directory, AEGIS_2_0)
        extracted = documents_from(rows, AEGIS_2_0)

    with index.opened(parsed.store) as collection:
        held_before = collection.count()
        index.write(collection, extracted.documents)
        report = index.IndexReport(
            documents=len(extracted.documents),
            dropped=extracted.dropped,
            held_before=held_before,
            held_after=collection.count(),
        )

    print(report.stated(rows=len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
