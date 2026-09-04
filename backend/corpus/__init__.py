"""The corpus: a search surface the library is grown *from*, and never a library.

`backend/cases/` holds **case** records — executable tests, each with a payload and
the criterion that decides its verdict, and the thing a **library version** is a
digest of (CONTEXT.md, `bench.library`). This package holds something else entirely:
a published safety corpus of 33,416 rows, indexed so that a human building a case can
*find* the handful of phrasings worth writing a case around. Nothing here is
executable, nothing here has a verdict, and nothing here is counted.

**The one-sentence test of whether this package has gone wrong.** If a **candidate**
produced in here can be read by anything under `backend/bench/`, it has. The scored
side takes its input from `load_library`, and the adaptive layer reaches it through
`propose_case` and nowhere else
([ADR-0010](../../docs/adr/0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md));
a candidate that reached either would be a second edge into a scored rate that no
declared threshold stands in front of. So the dependency runs one way — this
package imports `Family` from the bench to key its declared queries, and the bench
imports nothing from here — and a test asserts it
([ADR-0045](../../docs/adr/0045-the-corpus-is-a-search-surface-and-never-a-library.md)).

**It is a build-time instrument.** A person runs `scripts/index_corpus.py` once and
`scripts/retrieve_candidates.py` while they are writing cases. No run, no gate run and
no test opens the index; `chromadb` is an optional extra for that reason and CI does
not install it (`pyproject.toml`).
"""
