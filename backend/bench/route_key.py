"""What one proposed route is filed under. A key, and nothing that holds a file.

Its own module, and the reason is a wall rather than tidiness. `RouteKey` used to
live in `decided.py` beside the admission memory it keys, and `test_decided.py`'s
`test_no_scored_instrument_can_reach_the_admission_memory` holds that nothing
producing a signed number may reach that module by any chain of imports — the memory
is a machine-local git-ignored file, so a rate, an interval, a band, a `D` or a κ
that read it would be a figure that depended on the machine (ADR-0010, ADR-0032).

The target library keys on the same value
([ADR-0117](../../docs/adr/0117-a-refused-break-is-held-against-the-target-it-beat-and-is-scored-beside-the-six.md)
§1), and a run sends held routes, so `calibration.py` — which is in that wall's list
— now reaches `held.py`. With the key still in `decided.py` that made the admission
memory reachable from a run, and the wall was right to fail. So the **key** moved out
from behind the wall and the **memory** did not: nothing here opens a file, holds a
connection or names a namespace, and `decided.py` re-exports this name so that every
caller that was reading a key off the memory's module still reads the same type.

That is deliberately not a widening of what the wall permits. What may now be
reached from a scored instrument is a frozen pair of a family and a digest; what may
not, and still may not, is anything that reads the store.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from backend.bench.library import AnyFamily, Case


@dataclass(frozen=True)
class RouteKey:
    """What one proposed route is filed under: its family, and a digest of its probe.

    **A key and not a route, and the name says so** — CONTEXT.md's **route** is "the
    sequence of probes that worked", and this is neither a sequence nor a route. What
    it identifies is the one probe a `ProposedRoute` carries: `propose_case` drafts a
    case from the probe that actually ran, so the route an episode took reaches
    admission as a single payload, and it is that payload's identity within its
    family that two proposals of one path have in common.

    **Deliberately not the case.** `proposal.py` mints
    `id=f"adaptive-{family}-{uuid.uuid4().hex[:8]}"`, so a case id is a fresh value
    every time the attacker rediscovers the same path — a key nothing could ever hit
    twice, which is the fact that decides this shape.

    The digest is over the probe and is never the probe, for the reason CONTEXT.md
    gives under **route**: a path that beat a target is a working unpublished exploit
    (ADR-0008). It buys the same two things `Precedent.key` is content-addressed for
    — a re-proposal under a fresh case id lands on the same key, and the name the
    store lists derives from no clock and no target.

    The family is in the key and not only beside it. The same words sent under two
    families are two cases with two criteria, and one entry standing for both would
    answer a question about one of them with the other's counts.
    """

    family: AnyFamily
    """Which family the proposed route belongs to, in either tier.

    Widened with the record it is read off, and it is not a container the gate
    counts: the admission memory holds what a measurement was, and admission is
    decided per case (ADR-0032, ADR-0035). No elective family reaches it today —
    the adaptive layer's episodes are over the six — and the type does not have to
    know that to stay out of a denominator.
    """

    probe: str
    """A `sha256` of the probe that actually ran, truncated. Never the probe."""

    @classmethod
    def of(cls, case: Case) -> RouteKey:
        """The key one proposed case is filed under, read off the case record.

        Off `case.script` — the probe the episode actually sent, which
        `proposed_from` copies from the episode's own record rather than from the
        tool's argument — so nothing can be keyed by a payload the target never saw.

        Every turn of it, which for a proposed route is the one turn a probe is: a
        proposal is a single message the attacker composed, so the digest of the
        joined script is the digest of the probe and keys already filed still resolve
        (ADR-0053).
        """
        return cls(family=case.family, probe=_digest(case.script))

    @property
    def filed_under(self) -> str:
        """The key the store files this route under."""
        return f"{self.family}-{self.probe}"

    def stated(self) -> str:
        """The route as a report names it: the family, and the digest of the probe."""
        return f"{self.family}, probe sha256:{self.probe}"


def _digest(text: str) -> str:
    """A truncated `sha256`, on `Precedent.key`'s terms and at its length."""
    return sha256(text.encode("utf-8")).hexdigest()[:16]
