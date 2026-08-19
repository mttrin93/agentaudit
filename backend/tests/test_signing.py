"""The producing side of the signature, tested by what it refuses.

A test that signs a payload and verifies it proves that `cryptography` works. What is
worth asserting is the four things this module will not do: sign bytes that do not
include the adaptive section, sign a payload with no rendering bound to it, sign with
one key while the payload claims another, and read a private key from anywhere but the
environment. Each of those is a way a signature could exist and mean less than a
recipient would read into it.

The keys here are generated per test rather than read from the repository. The
committed public key's private half is not in this repository by design, so a suite
that needed it could not run — and a suite that generated one on demand inside the
library would be asserting the fallback ADR-0017 forbids.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from backend.bench.assembler import AdaptiveSection
from backend.bench.payload import canonical_bytes, canonical_json
from backend.bench.rendering import (
    REPORT_MARKDOWN,
    REPORT_PAYLOAD,
    bind,
    digest,
    render,
)
from backend.bench.signing import (
    PUBLIC_KEY_PATH,
    SIGNATURE_FILE,
    SIGNING_KEY_VARIABLE,
    NoSigningKey,
    NotSignable,
    bind_key,
    decoded,
    encoded_private,
    fingerprint,
    generate,
    public_key,
    publish_signed,
    sign,
    signing_key,
    verify_bytes,
)
from backend.tests.test_payload import a_payload, an_episode

README = Path(__file__).resolve().parents[2] / "README.md"
ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"
"""Where the signing key's fingerprint is published for a recipient to compare."""


def test_the_signature_covers_the_whole_payload_including_the_adaptive_section() -> (
    None
):
    # ADR-0017 point 1: one artefact, one signature, no unprotected region. The
    # adaptive section is the one with something worth deleting — it describes the
    # routes an attacker found against the reader's own agent — so it is the section
    # this test alters.
    key = generate()
    payload = bind(bind_key(a_payload(), key))
    signature = sign(payload, key)

    assert verify_bytes(canonical_bytes(payload), signature, key.public_key())

    altered = replace(
        payload,
        result=replace(
            payload.result,
            adaptive=AdaptiveSection(
                episodes=(replace(an_episode(), description="a route nobody removed"),)
            ),
        ),
    )
    assert canonical_bytes(altered) != canonical_bytes(payload)
    assert not verify_bytes(canonical_bytes(altered), signature, key.public_key()), (
        "The signature verified over a payload whose adaptive section had been "
        "rewritten, so that section travels unprotected (ADR-0017 point 1)."
    )


def test_a_payload_whose_rendering_is_unbound_cannot_be_signed() -> None:
    # A signature over `rendered_sha256: null` would be a valid signature with no
    # document joined to it — the doctored-rendering substitution arrived at by
    # omission rather than by substitution.
    key = generate()
    unbound = bind_key(a_payload(), key)
    assert unbound.rendered_sha256 is None

    with pytest.raises(NotSignable, match="unbound"):
        sign(unbound, key)


def test_key_id_names_the_signing_key_and_the_signature_covers_that_claim() -> None:
    # ADR-0017 point 4: `key_id` is inside the signature rather than beside it, so
    # *this document claims key A* is itself a signed claim and cannot be
    # re-attributed by editing a file.
    key = generate()
    other = generate()
    payload = bind(bind_key(a_payload(), key))

    assert payload.key_id == fingerprint(key.public_key())
    assert payload.key_id is not None and payload.key_id in canonical_json(payload)

    signature = sign(payload, key)
    relabelled = replace(payload, key_id=fingerprint(other.public_key()))
    assert not verify_bytes(canonical_bytes(relabelled), signature, key.public_key()), (
        "The key_id was changed and the signature still verified, so it is outside it."
    )

    with pytest.raises(NotSignable, match="names"):
        sign(payload, other)


def test_the_private_key_is_read_from_the_environment_and_not_from_the_repository() -> (
    None
):
    # Publishing this repository must not publish the ability to forge its reports:
    # the committed half is the public one, and a missing private key is a refusal
    # rather than a key generated on demand.
    with pytest.raises(NoSigningKey, match=SIGNING_KEY_VARIABLE):
        signing_key({})

    key = generate()
    read = signing_key({SIGNING_KEY_VARIABLE: encoded_private(key)})
    assert fingerprint(read.public_key()) == fingerprint(key.public_key())

    committed = PUBLIC_KEY_PATH.read_text(encoding="utf-8")
    assert "PRIVATE" not in committed.upper(), (
        f"{PUBLIC_KEY_PATH} holds private key material, so the repository publishes "
        "the ability to forge its own reports."
    )
    assert fingerprint(public_key()).startswith("sha256:")


def test_the_committed_example_environment_names_the_key_and_carries_no_value() -> None:
    # `.env` is gitignored and `.env.example` is not, which is the whole point of the
    # pair and also the way a private key gets committed by accident: the file exists
    # to be filled in, and a filled-in copy is one `git add` away from publishing the
    # ability to forge this repository's reports (ADR-0017, ADR-0020). The variable is
    # named here so a reader knows what to set; its value is empty here forever.
    example = ENV_EXAMPLE.read_text(encoding="utf-8")

    assert f"{SIGNING_KEY_VARIABLE}=" in example, (
        f"{ENV_EXAMPLE.name} does not name {SIGNING_KEY_VARIABLE}, so the one "
        "variable without which the factory refuses to boot is undiscoverable."
    )
    for line in example.splitlines():
        if line.startswith(f"{SIGNING_KEY_VARIABLE}="):
            assert line == f"{SIGNING_KEY_VARIABLE}=", (
                f"{ENV_EXAMPLE.name} carries a value for {SIGNING_KEY_VARIABLE}. A "
                "committed private key is a forgeable bench, and this file is "
                "committed."
            )
    assert "-----BEGIN" not in example, (
        f"{ENV_EXAMPLE.name} holds a PEM block. Nothing in an environment file is "
        "key material; the private half is base64 on one line and lives outside "
        "every committed path."
    )


def test_the_committed_keys_fingerprint_is_the_one_published_in_the_readme() -> None:
    # A recipient's only defence against a valid signature over an unknown key is a
    # fingerprint published where they can read its history. If the key is rotated and
    # the README is not, that published value silently starts describing a key nobody
    # signs with — and a mismatch a recipient finds cannot be told from a forgery.
    published = README.read_text(encoding="utf-8")
    assert fingerprint(public_key()) in published, (
        f"{PUBLIC_KEY_PATH} does not have its fingerprint published in {README}. "
        "Rotation is a deliberate act and the README is part of it."
    )


def test_publishing_a_signed_run_writes_three_files_and_signs_the_bytes_on_disk(
    tmp_path: Path,
) -> None:
    # The signature has to cover the file a recipient holds, not a payload the
    # producer had in hand a moment earlier: the bound, keyed payload is the artefact
    # and the unbound one a caller passed in is missing both signed fields.
    key = generate()
    report = publish_signed(a_payload(), tmp_path, key)

    assert sorted(path.name for path in tmp_path.iterdir()) == sorted(
        (REPORT_MARKDOWN, REPORT_PAYLOAD, SIGNATURE_FILE)
    )
    written = report.payload_path.read_bytes()
    assert verify_bytes(written, report.signature, key.public_key()), (
        "The signature does not verify over the bytes that were written, so what was "
        "signed is not what a recipient holds."
    )
    assert (
        decoded(report.signature_path.read_text(encoding="utf-8")) == report.signature
    )
    assert report.payload.rendered_sha256 == digest(render(report.payload))
    assert report.payload.key_id == fingerprint(key.public_key())
