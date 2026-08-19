"""Checks a report the way its recipient does: offline, with no credential, three
answers.

    uv run python -m scripts.verify path/to/report
    uv run python -m scripts.verify path/to/report --pubkey some-other-key.pub

**This is the script for somebody who does not trust the sender and cannot reach
them.** It reads three files out of one directory — `report.json`, `report.md` and
`report.sig` — and answers three questions about them: is the signature this key's over
exactly these bytes, does the Markdown hash to the digest inside the payload, and does
the arithmetic re-derive from the counts the payload carries.

**All three, every time.** A verifier that printed *signature valid* alone would let its
reader infer re-derivability from integrity, which is the one inference ADR-0017 exists
to prevent — so the three results are printed together and the two claims are printed
under them. The third result is the one that is about the bench rather than about the
transport, and it can fail on a document nobody tampered with.

**It reaches nothing.** No network, no model, no API key, no `.env`: the pinned public
key is a committed file and everything else is arithmetic. That is the whole point of
the artefact — a report has to stay checkable after it leaves the engineer who produced
it, and a check that phoned home would be a check the recipient cannot make when the
sender is gone.

**It pins the committed key by default.** `keys/agentaudit-signing.pub`, whose
fingerprint is published in this repository's README, so a valid signature over an
unknown key is never mistaken for provenance. `--pubkey` overrides it, and a report
signed by a key other than the pinned one is reported under its own outcome rather than
as tampering.

**Nothing here writes.** A disagreement is reported and never corrected: the exit code
and the printed paths are the whole of the output, and the directory is left as it was
found.
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from backend.bench.signing import PUBLIC_KEY_PATH, public_key
from backend.bench.verification import NotThisArtefact, verify

EXIT_UNREADABLE = 2
"""Exit code when there is no artefact of a known kind here, or no usable key.

Distinct from a failed verification, because they are different facts: this one says
the verifier does not know what it is holding, and a script that treated it as
tampering would report a version mismatch as an attack.
"""

EXIT_DID_NOT_VERIFY = 3
"""Exit code when one or more of the three results did not hold.

One code for the three, because all three outcomes are always printed by name and the
shell's answer to *should I trust this document* is the same in each case: no.
"""


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "directory",
        help=(
            "the directory holding report.json, report.md and report.sig — the three "
            "files one run published, under the fixed names a recipient does not have "
            "to be told"
        ),
    )
    parser.add_argument(
        "--pubkey",
        default=str(PUBLIC_KEY_PATH),
        help=(
            "the public key to pin, in PEM. Defaults to the key committed to this "
            "repository, whose fingerprint the README publishes: a key that arrived "
            "beside the document it verifies proves only that one sender sent both"
        ),
    )
    args = parser.parse_args(argv)

    try:
        pinned = public_key(Path(args.pubkey))
    except (OSError, ValueError) as unusable:
        print(f"No usable public key at {args.pubkey}: {unusable}")
        return EXIT_UNREADABLE

    try:
        verification = verify(Path(args.directory), pinned)
    except NotThisArtefact as unknown:
        print(f"Nothing here to verify:\n{unknown}")
        return EXIT_UNREADABLE
    except OSError as unreadable:
        print(f"Cannot read the report in {args.directory}: {unreadable}")
        return EXIT_UNREADABLE

    print(verification.stated())
    print()
    if verification.verified:
        print(
            "All three held. This artefact is the one that was produced, the document "
            "beside it is the one that was signed, and its arithmetic re-derives. "
            "None of that says the agent is safe."
        )
        return 0
    print(
        "This artefact did not verify. The result that failed is named above; nothing "
        "was changed on disk, and no figure here was corrected into agreement."
    )
    return EXIT_DID_NOT_VERIFY


if __name__ == "__main__":
    sys.exit(main())
