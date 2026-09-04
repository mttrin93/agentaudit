"""The stored record of the corpus this bench searches, and what it refuses.

The corpus is 33,416 published rows and none of them is in this repository
(ADR-0008). What *is* in the repository is the record of where they came from —
identifier, revision, licence, attribution, and one SHA-256 per published file — so
that a build which fetched something else says so instead of indexing it.

That is the inverse of the digest ADR-0036 rejected for the stored OWASP copies. A
digest of a copy this project transcribed proves only that we did not edit our own
file; a digest of the *publisher's* file is the fidelity claim itself, and it is the
only one available for material that may not be committed.
"""

from backend.corpus.source import AEGIS_2_0, EMBEDDING_MODEL, RETRIEVAL


def test_the_record_refuses_a_file_whose_digest_is_not_the_one_it_stored() -> None:
    published = {file.name: file.sha256 for file in AEGIS_2_0.files}
    assert AEGIS_2_0.drift(published) is None

    drifted = dict(published) | {"test.json": "0" * 64}
    refusal = AEGIS_2_0.drift(drifted)
    assert refusal is not None
    assert "test.json" in refusal


def test_the_three_ways_to_disagree_are_told_apart() -> None:
    # A missing file, a changed one and an unexpected one need different fixes: an
    # incomplete fetch, a publisher that moved, and a record gone stale against a
    # corpus that grew a split. One refusal that said only "does not match" would
    # send a reader to the wrong one of the three.
    published = {file.name: file.sha256 for file in AEGIS_2_0.files}

    missing = dict(published)
    del missing["validation.json"]
    assert "validation.json is missing" in (AEGIS_2_0.drift(missing) or "")

    changed = dict(published) | {"validation.json": "1" * 64}
    changed_said = AEGIS_2_0.drift(changed) or ""
    assert "validation.json is sha256:111111111111" in changed_said
    assert "is missing" not in changed_said

    extra = dict(published) | {"holdout.json": "2" * 64}
    extra_said = AEGIS_2_0.drift(extra) or ""
    assert "holdout.json is not a file this repository read" in extra_said
    assert "validation.json" not in extra_said


def test_the_record_carries_the_licence_the_corpus_is_used_under() -> None:
    # A corpus used without its attribution is a licence breach whatever the code
    # does, and the notice has to be reachable by the thing that uses it rather than
    # only by a reader of this file.
    assert AEGIS_2_0.licence == "CC-BY-4.0"
    assert "CC BY 4.0" in AEGIS_2_0.attribution
    assert "NVIDIA" in AEGIS_2_0.attribution
    assert AEGIS_2_0.rows == 33416
    assert len(AEGIS_2_0.files) == 5
    for file in AEGIS_2_0.files:
        assert len(file.sha256) == 64
        assert AEGIS_2_0.revision in AEGIS_2_0.url(file.name)


def test_the_two_declared_inputs_are_reachable_from_a_stored_address() -> None:
    # #63 asks that the embedding model and the corpus version be recorded where a
    # reader of a case record can reach them. The revision travels inside the address
    # #65 stores; the model cannot, because it is not a property of a row. So the walk
    # is address -> these inputs -> the model, and `resolves` is the step that says
    # whether this record is the one that address was written under.
    address = f"{AEGIS_2_0.identifier}@{AEGIS_2_0.revision}#{'a' * 32}"
    assert RETRIEVAL.resolves(address)
    assert RETRIEVAL.source is AEGIS_2_0
    assert RETRIEVAL.embedding_model == EMBEDDING_MODEL

    superseded = f"{AEGIS_2_0.identifier}@0000000000000000#{'a' * 32}"
    assert not RETRIEVAL.resolves(superseded)
    assert not RETRIEVAL.resolves(f"{AEGIS_2_0.identifier}@{AEGIS_2_0.revision}#")

    said = RETRIEVAL.stated()
    assert EMBEDDING_MODEL in said
    assert AEGIS_2_0.revision[:12] in said
    assert AEGIS_2_0.licence in said
