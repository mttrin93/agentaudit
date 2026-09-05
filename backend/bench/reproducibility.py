"""Whether a figure can be re-derived by its reader, or only read.

One type, shared by the gate and by the report, because the scoping ADR-0010 asks
for is a claim about *both* halves of a run and a claim stated on one side only is
a caveat rather than a distinction. The gate decision is re-derivable from its
recorded inputs; the adaptive layer is a stochastic search, recorded rather than
re-derivable; and a run prints both sentences beside each other.

**`NOT_REPRODUCIBLE` had one subject and now has two.** Its sentence used to name the
adaptive attacker and its route, because the adaptive section was the only section
that carried the label; since
[ADR-0070](../../docs/adr/0070-a-signed-document-may-carry-a-remediation.md) the
findings section carries it too, and there is no attacker and no route in that one. So
the wording here says what the label means for any stochastic instrument, and each
section says in its own body which instrument it means — a shared label whose sentence
described one of its two subjects would be a signed document making a false statement
about the other.

It lives in its own module rather than in `assembler.py` so that the gate can say
the same thing in the same words without importing a report — and, more to the
point, without importing anything that can see an episode.
"""

from enum import StrEnum


class Reproducibility(StrEnum):
    """Whether a section can be re-derived by its reader, or only read.

    Printed on every section rather than in a footnote about one, because the
    distinction only means something if it is stated on both sides: a reader who
    sees "not reproducible" once and nothing anywhere else cannot tell whether the
    label is a property of that section or a caveat the author felt like adding.

    Scoping reproducibility rather than claiming it whole is ADR-0010's own
    consequence — the gate decision is re-derivable from recorded inputs, the
    adaptive search is recorded and not re-derivable, and printing the difference is
    the same discipline as printing κ beside a judged family.
    """

    RE_DERIVABLE = "re_derivable"
    NOT_REPRODUCIBLE = "not_reproducible"

    def stated(self) -> str:
        """The label in the words the section header prints."""
        match self:
            case Reproducibility.RE_DERIVABLE:
                return (
                    "re-derivable — every figure here follows from the recorded "
                    "attempts, the case records and the stated rule, so a reader "
                    "holding those can recompute it without this bench"
                )
            case Reproducibility.NOT_REPRODUCIBLE:
                return (
                    "not reproducible — a stochastic instrument produced this "
                    "section, so running it again would not produce it again. What "
                    "is recorded here is evidence that it happened; what is absent "
                    "from it is evidence of nothing"
                )
