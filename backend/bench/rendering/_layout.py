"""The shape of a section, and the two things every section of the document shares.

`rendering.py` was one file of 1043 lines emitting one document. It is now a package
of one module per part of that document, and this is the part all of them stand on:
`Section`, which knows its Annex IV point and how to print itself, and the two
constants that appear in more than one section — the Act's own point titles, and the
sentence that says this document is not a claim of conformity.

**Nothing here decides what a section says.** That is the point of the boundary: a
module that held both the frame and the wording would be a module every other one had
to import in full. `_declared.py`, `_measured.py` and `_annexes.py` each build their
own sections against this frame and know nothing about each other; `__init__.py`
orders them and binds the digest.

**The split changes no byte of the document.** Every definition moved verbatim, and
the golden fixtures and the digest tests are the assertion of that — a signature is
over one document, and a renderer that emitted a different one would change every
digest ever issued (ADR-0017).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from backend.bench.reproducibility import Reproducibility

NOT_A_CLAIM_OF_CONFORMITY = (
    "This document is evidence, not a certificate. It carries no claim of "
    "conformity, no certification, no badge, no insurance and no price, and it "
    "declares no single figure standing for this target: a reader who wants one "
    "number will build it out of whatever is on the page, so the page does not offer "
    "one (D3, ADR-0001, ADR-0005). A valid signature says these bytes are the ones "
    "that were produced and that nothing has altered them. It says nothing "
    "whatsoever about whether the agent is safe."
)


ANNEX_IV_POINTS: Mapping[int, str] = {
    1: "a general description of the AI system",
    2: (
        "a detailed description of the elements of the system and of the process for "
        "its development"
    ),
    3: "detailed information about the monitoring, functioning and control",
    4: "a description of the appropriateness of the performance metrics",
    5: "a detailed description of the risk management system (Article 9)",
    6: "a description of relevant changes made through the system's lifecycle",
    7: "a list of the harmonised standards applied",
    8: "a copy of the EU declaration of conformity",
    9: "a description of the post-market monitoring system (Article 72)",
}
"""The nine points of Annex IV, in the Act's order, as the section headings cite them.

Held as data so that the order is a property of this module rather than of the order
somebody wrote the functions in, and so a test can read it.
"""


def _listed(rows: Iterable[str], absence: str) -> tuple[str, ...]:
    """Those rows, or one line saying the list is empty and what that reads as.

    One shape for every list in this document, because the alternative is four
    variations on the same branch and a fifth that quietly drops the empty case — and
    a dropped empty case is a section that reads as having had nothing to declare when
    it had something to declare and no way to declare it.
    """
    listed = tuple(rows)
    return listed or (absence,)


@dataclass(frozen=True)
class Section:
    """One section of the rendering: where it sits in Annex IV, and what it claims.

    Carries its own reproducibility label rather than inheriting one from the
    document, which is the whole of ADR-0017's second claim: a section is where the
    label means something, because the two halves of a run land in different
    sections.
    """

    point: int
    """Which Annex IV point this section answers."""

    part: str = ""
    """`a` or `b` where one Annex IV point holds two sections, and empty otherwise.

    Point 5 holds two, because what the bench does not test at all and what one
    attacker found outside the recorded cases are both statements about the boundary
    of the claim, and they are not the same evidentiary class. Two labelled sections
    under one point is Annex IV's own shape — its points carry lettered sub-points —
    and it is the honest alternative to one section with two labels or one label
    covering both.
    """

    title: str = ""
    reproducibility: Reproducibility = Reproducibility.RE_DERIVABLE
    body: tuple[str, ...] = ()

    @property
    def number(self) -> str:
        """The section's number as it is printed and cited: `4`, or `5a`."""
        return f"{self.point}{self.part}"

    def rendered(self) -> str:
        """The section, its Annex IV citation, its own label, and its body."""
        return "\n".join(
            (
                f"## {self.number}. {self.title}",
                "",
                f"*Annex IV({self.point}) — {ANNEX_IV_POINTS[self.point]}.*",
                "",
                f"*Reproducibility of this section: {self.reproducibility.stated()}.*",
                "",
                *self.body,
            )
        )
