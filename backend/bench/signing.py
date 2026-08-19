"""The signature: Ed25519 over the canonical bytes, detached, and never over less.

`payload.py` makes the bytes and `rendering.py` binds the document a human reads into
them by digest. This module is the last step before an artefact leaves the building:
one Ed25519 signature over the whole canonical payload — the adaptive section
included, because a security report with an unprotected region would be a worse
artefact for a strictly worse reason (ADR-0017 point 1). `verification.py` is the
recipient's side of the same contract.

**Detached, and the payload file stays byte-for-byte what was signed.** The signature
is written beside the payload as `report.sig` rather than wrapped around it, which is
PLAN §11's own wording — *Ed25519 detached signature over the canonical payload* — and
it buys one specific property: a verifier's first act is reading the file, not
re-serialising a parsed copy of it and trusting the copy to be identical. An envelope
would make every verification depend on the recipient's JSON library agreeing with
ours about key order and separators, which is exactly the assumption canonical bytes
exist to remove.

**`key_id` is inside the signature and the signature file names no key.** The
fingerprint of the signing key travels in the payload, where the signature covers it,
so *this document claims key A* is itself a signed claim. A signature file carrying
its own key id would be re-attributable by editing the file beside the payload, and a
recipient pinning one public key would have no way to tell a document signed by
another key from one whose label somebody changed. There is therefore exactly one
statement anywhere of which key signed a report, and altering it invalidates the
signature.

**Nothing here can sign with one key while claiming another.** `bind_key` is the only
thing that sets `key_id`, and it sets it from the key rather than from an argument;
`sign` then refuses any payload whose `key_id` is not the fingerprint of the key in
its hand. The failure that sequence exists to prevent is a report signed by a
throwaway key and labelled with the published one.

**An unbound payload cannot be signed at all.** `rendered_sha256` is `None` until
`rendering.bind` has run, and a signature over a payload holding `None` there would be
a valid signature with no rendering attached to it — which is the doctored-document
substitution the binding exists to prevent, arrived at by omission. `sign` raises.

**The private key is read from the environment and is never written anywhere.** The
public half is committed, in PEM, with its fingerprint published in the README, so a
recipient checking a signature trusts a key published where they can read its history
rather than one that arrived with the document. Publishing this repository therefore
does not publish the ability to forge its reports.

**The key's lifecycle is here too, and deliberately.** `generate`, `encoded_private`
and `public_pem` are called by `scripts.keygen` and never by a run, which reads as a
second concern in one module — and separating them would put the base64 the environment
holds in one file and the code that reads it back in another. A generator and a reader
that disagree about a format is a key that cannot be loaded, discovered at the moment
somebody needs to sign, so both formats are decided in the module that also decides
what a fingerprint is.
"""

import base64
import binascii
import os
from collections.abc import Mapping
from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_pem_public_key,
)

from backend.bench.payload import TargetPayload, canonical_bytes
from backend.bench.rendering import Published, publish

ALGORITHM = "ed25519"
"""The one algorithm, named in the document rather than assumed by the verifier.

Ed25519 and nothing else: a signature format that negotiates its algorithm is a
signature format with a downgrade in it, and this artefact has one producer.
"""

SIGNATURE_FILE = "report.sig"
"""The detached signature, beside `report.json` and `report.md` under a fixed name.

A third fixed name in the same directory, for the reason the first two are fixed: a
recipient handed a directory has to know which file the signature covers without
being told.
"""

SIGNING_KEY_VARIABLE = "AGENTAUDIT_SIGNING_KEY"
"""Where the private key is read from, and the only place it is read from.

Base64 of the 32 raw private bytes, on one line, because an environment variable is
where this value lives and PEM's newlines do not survive a `.env` file. The public
half is PEM, which is the format a recipient's tooling already reads.
"""

KEYS_DIRECTORY = Path(__file__).resolve().parents[2] / "keys"
"""Where the committed public half lives, at the top of the repository.

Its own directory rather than beside the code, because what is in it is published
material a recipient goes looking for — and because a directory holding only public
keys is one whose contents can be read at a glance.
"""

PUBLIC_KEY_PATH = KEYS_DIRECTORY / "agentaudit-signing.pub"
"""The committed public key `verify.py` pins by default.

Committed rather than distributed with the report: a key that arrives beside the
document it verifies proves that whoever sent the document also sent the key.
"""

FINGERPRINT_PREFIX = "sha256:"
"""What a fingerprint is over, written into the fingerprint.

A bare hex string says nothing about what was hashed or with which digest, and a
recipient comparing one against the README has to be told. Written down, a later
algorithm produces a visibly different value rather than an indistinguishable one.
"""


class NoSigningKey(RuntimeError):
    """The private key is not in the environment, so nothing can be signed.

    A refusal and never a fallback. A bench that generated a key when it could not
    find one would sign reports with a key no recipient has ever seen published,
    which is a valid signature over unknown provenance — the exact reading ADR-0017
    point 4 and the README's published fingerprint exist to prevent.
    """


class NotSignable(ValueError):
    """This payload may not be signed in the state it is in.

    Two states reach it, and both are the same mistake in different clothes: a
    payload whose rendering nobody bound, and a payload whose `key_id` names a key
    other than the one signing it.
    """


def fingerprint(public: Ed25519PublicKey) -> str:
    """The key's identity as a report states it: `sha256:` over its raw bytes.

    One representation, used as `key_id` in the payload, as the value the README
    publishes and as what `verify.py` compares against the key it was pinned to. Two
    representations of one key would be two things a recipient has to be told are the
    same, and the whole point of a published fingerprint is that they compare it by
    eye.
    """
    raw = public.public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)
    return FINGERPRINT_PREFIX + sha256(raw).hexdigest()


def signing_key(environment: Mapping[str, str] | None = None) -> Ed25519PrivateKey:
    """The private key from the environment, or a refusal that says what is missing.

    Read here and nowhere else, so there is one line in this repository that could
    ever have written a private key to disk and it does not exist.
    """
    values = os.environ if environment is None else environment
    encoded = values.get(SIGNING_KEY_VARIABLE, "").strip()
    if not encoded:
        raise NoSigningKey(
            f"no signing key in {SIGNING_KEY_VARIABLE}. The private key is read from "
            "the environment and is never committed and never generated on demand: a "
            "report signed by a key nobody has published is a valid signature over "
            "unknown provenance (ADR-0017). Generate a pair with "
            "`uv run python -m scripts.keygen` and export the private half"
        )
    try:
        raw = base64.b64decode(encoded, validate=True)
    except binascii.Error as unusable:
        raise NoSigningKey(
            f"the value of {SIGNING_KEY_VARIABLE} is not base64: {unusable}. It is "
            "the 32 raw private bytes, base64-encoded on one line, as "
            "`scripts.keygen` prints them"
        ) from unusable
    try:
        return Ed25519PrivateKey.from_private_bytes(raw)
    except ValueError as unusable:
        raise NoSigningKey(
            f"the value of {SIGNING_KEY_VARIABLE} is not an Ed25519 private key: "
            f"{unusable}"
        ) from unusable


def public_key(path: Path = PUBLIC_KEY_PATH) -> Ed25519PublicKey:
    """The public key a recipient pins, read from PEM.

    Refuses a key of another kind rather than reporting a failed signature over it: a
    verifier handed an RSA key would otherwise tell its reader the document did not
    verify, when what happened is that they pinned the wrong file.
    """
    loaded = load_pem_public_key(path.read_bytes())
    if not isinstance(loaded, Ed25519PublicKey):
        raise ValueError(
            f"{path} holds a {type(loaded).__name__} and not an Ed25519 public key. "
            f"This artefact is signed with {ALGORITHM} and nothing else"
        )
    return loaded


def bind_key(payload: TargetPayload, key: Ed25519PrivateKey) -> TargetPayload:
    """That payload with the fingerprint of this key inside it, before it is signed.

    The one place `key_id` is set, and it is derived from the key rather than passed
    in — the same discipline `rendering.bind` follows with the digest, and for the
    same reason: a caller who could supply the value could supply the wrong one, and
    the wrong one here is a forgery wearing the published key's name.
    """
    return replace(payload, key_id=fingerprint(key.public_key()))


def sign(payload: TargetPayload, key: Ed25519PrivateKey) -> bytes:
    """The detached signature over this payload's canonical bytes.

    Raises rather than signing a payload that is not ready to be signed. Both
    refusals are about what the signature would *not* cover: an unbound payload has
    no rendering joined to it, and a payload whose `key_id` names another key would
    carry a signed claim about its own provenance that is false.
    """
    if payload.rendered_sha256 is None:
        raise NotSignable(
            "this payload's rendering is unbound, so there is no document joined to "
            "the bytes being signed. `rendering.bind` sets `rendered_sha256` and the "
            "signature has to cover it, or a doctored rendering travels beside a "
            "valid signature (ADR-0017)"
        )
    named = fingerprint(key.public_key())
    if payload.key_id != named:
        raise NotSignable(
            f"this payload names {payload.key_id} as its signing key and the key in "
            f"hand is {named}. Nothing signs bytes that claim another key: use "
            "`bind_key` to set `key_id` from the key that will sign"
        )
    return key.sign(canonical_bytes(payload))


def encoded(signature: bytes) -> str:
    """The signature as the file holds it: lowercase hex, one line.

    Hex rather than raw bytes so the artefact is three text files a recipient can
    read, diff and paste, and so a transport that mangles binary is a visible failure
    rather than an invalid signature nobody can explain.
    """
    return signature.hex() + "\n"


def decoded(text: str) -> bytes:
    """The signature back out of the file. Raises on anything that is not one."""
    return bytes.fromhex(text.strip())


def verify_bytes(signed: bytes, signature: bytes, public: Ed25519PublicKey) -> bool:
    """Whether this signature is this key's over exactly these bytes.

    The library raises and this returns a boolean, because at the call site the
    question is one of three named outcomes rather than an error: a document that does
    not verify is a fact to report to its reader, not an exception to propagate.
    """
    try:
        public.verify(signature, signed)
    except InvalidSignature:
        return False
    return True


@dataclass(frozen=True)
class SignedReport:
    """What one signed run left on disk: three files that cannot disagree.

    The payload here is the bound, keyed one that was actually signed — not the
    payload a caller passed in, which is missing both of the fields the signature
    covers.
    """

    payload: TargetPayload
    signature: bytes
    payload_path: Path
    rendering_path: Path
    signature_path: Path


def publish_signed(
    payload: TargetPayload, directory: Path, key: Ed25519PrivateKey
) -> SignedReport:
    """Write the rendering, the payload and the signature, in that order.

    The order is the dependency order and there is no other available: the key's
    fingerprint goes in first, then the rendering's digest, then the bytes are
    serialised with both inside them, and only then is there something to sign. The
    signature is written last on purpose — an interrupted publication leaves an
    unsigned artefact, which fails verification as *unsigned*, rather than a
    signature over a payload that never reached the disk.
    """
    published: Published = publish(bind_key(payload, key), directory)
    signature = sign(published.payload, key)
    signature_path = directory / SIGNATURE_FILE
    signature_path.write_text(encoded(signature), encoding="utf-8")
    return SignedReport(
        payload=published.payload,
        signature=signature,
        payload_path=published.payload_path,
        rendering_path=published.rendering_path,
        signature_path=signature_path,
    )


def generate() -> Ed25519PrivateKey:
    """A fresh key pair. Called by `scripts.keygen` and by tests, never by a run."""
    return Ed25519PrivateKey.generate()


def encoded_private(key: Ed25519PrivateKey) -> str:
    """The private half as the environment variable holds it: base64, one line.

    Returned rather than written. Nothing in this repository puts a private key on
    disk, which is why `scripts.keygen` prints it and tells the operator where to put
    it.
    """
    raw = key.private_bytes(
        encoding=Encoding.Raw,
        format=PrivateFormat.Raw,
        encryption_algorithm=NoEncryption(),
    )
    return base64.b64encode(raw).decode("ascii")


def public_pem(public: Ed25519PublicKey) -> bytes:
    """The public half as the committed file holds it: PEM, which is what tools read."""
    return public.public_bytes(
        encoding=Encoding.PEM, format=PublicFormat.SubjectPublicKeyInfo
    )
