"""Generates the report signing key pair. Run once, by hand, when a key is needed.

    uv run python -m scripts.keygen
    uv run python -m scripts.keygen --public keys/agentaudit-signing.pub

**It writes the public half and prints the private half.** The public key is committed
so a recipient trusts a key published where they can read its history, and its
fingerprint goes in the README beside it. The private half is printed once, to be put
in the environment as `AGENTAUDIT_SIGNING_KEY` and nowhere else: no line in this
repository writes a private key to disk, and this script is the one place that could
have.

**It refuses to overwrite an existing public key.** A key pair that quietly replaced
the published one would invalidate every signature ever issued under it while leaving
the README's fingerprint saying otherwise — and a recipient comparing the two would
find a mismatch with no way to tell rotation from forgery. Rotation is a deliberate
act: move the old file aside, generate, and update the README's fingerprint in the
same commit.
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from backend.bench.signing import (
    PUBLIC_KEY_PATH,
    SIGNING_KEY_VARIABLE,
    encoded_private,
    fingerprint,
    generate,
    public_pem,
)

EXIT_REFUSED = 2
"""Exit code when a public key is already committed at that path."""


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--public",
        default=str(PUBLIC_KEY_PATH),
        help=(
            "where the public half is written, in PEM. The committed default is the "
            "key `scripts.verify` pins, so writing elsewhere produces a key no "
            "recipient has been told to trust"
        ),
    )
    args = parser.parse_args(argv)

    path = Path(args.public)
    if path.exists():
        print(
            f"{path} already holds a public key, and this script will not replace "
            "it. Every signature ever issued under that key verifies against that "
            "file, and the README publishes its fingerprint: move it aside "
            "deliberately, and update the README in the same commit."
        )
        return EXIT_REFUSED

    key = generate()
    public = key.public_key()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(public_pem(public))

    print(f"public key written to {path} — commit it")
    print(
        f"fingerprint (the payload's key_id, and the README's): {fingerprint(public)}"
    )
    print()
    print("the private half, printed once and written nowhere. Put it in your")
    print(f"environment as {SIGNING_KEY_VARIABLE} and nowhere a repository can see:")
    print()
    print(f"{SIGNING_KEY_VARIABLE}={encoded_private(key)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
