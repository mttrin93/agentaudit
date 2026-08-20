"""The published category list the bench reads its own coverage against.

ADR-0002 promises two disclosures and only one of them existed. The per-family half
— which case inside an identifier a case does *not* test — sits on every case record
and prints in section 4. The per-report half — which published **agentic** categories
the bench does not test at all — was four hand-written prose limits in
`assembler.py`, and that module said so in its own docstring: "a stated list, not a
derived one", because "this repository holds no such copy" of the published lists.

Two things were wrong with that, and neither was the prose. A coverage claim
assembled by hand shortens quietly when a family is added, and it was already wrong
by omission: not one of the four entries is an OWASP agentic category, so the section
that promised to name the untested categories named none of them. This module holds
the copy, and the subtraction the copy makes possible.

**A copy is not the source, and this one says where it came from.** The identifiers
and titles below were transcribed on 2026-08-20 from two independent secondary
readings of the list, which agreed on all ten of both; the OWASP resource page itself
refuses automated retrieval, so no reading here is the primary document. That is
weaker provenance than a signed artefact deserves and it is stated rather than
smoothed over: what the derivation below can claim is *agreement between two
readings*, and a reader who needs the authoritative wording goes to OWASP. Titles are
carried verbatim from that agreement, with no rewording to fit this repository's
voice, so that a stale copy is visible as a mismatch rather than hidden as a
paraphrase.

**Three declared things, and one derived one.** The transcription is a
transcription and holds nothing but the published fact. Which family claims which
category is a judgement, declared apart from the copy. Why an unclaimed category is
unclaimed is a second judgement, declared apart again. Only the subtraction is
computed — and it is computed over the **library's families**, never over the
families one run happened to measure. That boundary is load-bearing: `payload.py`
asserts that dropping a family from a result leaves every other byte of the document
unchanged, and a coverage list keyed on this run's measured families would move under
exactly that test. It would also answer the wrong question. "What does this bench not
test" is a statement about the bench and its library; a family this target could not
answer is `NotMeasurable`, which is a statement about the target and already has its
own home in the payload. Folding one into the other would put a run-shaped absence in
a section titled *at all*.

**The limit this leaves, stated.** The subtraction reads the six families the bench
has, not the cases currently live under them. A family whose every case retired still
claims its category here, and the derived list would not notice. Reading the live
library instead would make a statement about the bench depend on which records happen
to be on disk at render time, which is the run-scoping this module just refused; the
honest fix, if it is ever needed, is a family with no live cases being a fact the
library refuses to load rather than one the coverage section discovers.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from backend.bench.library import Family


@dataclass(frozen=True)
class AgenticCategory:
    """One entry of the published list: its identifier and its title, and no more.

    Deliberately holds no judgement about this bench. A record that carried *why we
    do not test this* beside the published fact would be a copy nobody could check
    against the source without first separating the two, and the whole value of a
    stored copy is that it can be checked.
    """

    identifier: str
    title: str


AGENTIC_TOP_10_2026: tuple[AgenticCategory, ...] = (
    AgenticCategory("ASI01", "Agent Goal Hijack"),
    AgenticCategory("ASI02", "Tool Misuse & Exploitation"),
    AgenticCategory("ASI03", "Identity & Privilege Abuse"),
    AgenticCategory("ASI04", "Agentic Supply Chain Vulnerabilities"),
    AgenticCategory("ASI05", "Unexpected Code Execution (RCE)"),
    AgenticCategory("ASI06", "Memory & Context Poisoning"),
    AgenticCategory("ASI07", "Insecure Inter-Agent Communication"),
    AgenticCategory("ASI08", "Cascading Failures"),
    AgenticCategory("ASI09", "Human-Agent Trust Exploitation"),
    AgenticCategory("ASI10", "Rogue Agents"),
)
"""OWASP Top 10 for Agentic Applications 2026, transcribed 2026-08-20.

Ten entries, `ASI01` through `ASI10` in the published order. The order is part of the
copy: a list whose entries are sorted or grouped by this repository's convenience is
no longer the published list.
"""

EDITION = "OWASP Top 10 for Agentic Applications 2026"
"""What the copy above is a copy of, printed beside the derived list.

The edition and not a fetch date, because the fetch date of a secondary reading says
nothing about which edition was read. A second edition of this list makes every
subtraction below stale, and the only defence against a stale subtraction that still
looks current is naming the edition in the report.
"""


FAMILY_CATEGORY: Mapping[Family, str | None] = {
    Family.INDIRECT_PROMPT_INJECTION: "ASI01",
    Family.SCOPE_CREEP: "ASI02",
    Family.WRONGFUL_COMMITMENT: None,
    Family.DATA_LEAKAGE: None,
    Family.HALT_DEFEAT: None,
    Family.DISCLOSURE_DENIAL: None,
}
"""Which agentic category each family tests one case *within* — or none.

A judgement, declared rather than derived, and the wording of ADR-0002 governs it: a
family **tests one case within** an identifier, it **is not** that identifier. Two
claims here and four refusals, and the refusals are the part worth arguing.

`wrongful_commitment` and `data_leakage` both carry `LLM0x:2026` identifiers in
PLAN §4 and neither has an agentic home, because this list has no accuracy entry and
no disclosure entry — the agentic list assumes both are covered by the GenAI LLM list
beside it. `ASI09` is the nearest thing to wrongful commitment and claiming it would
be an overclaim: `ASI09` is about controlling what a human approver sees at the
moment of confirmation, and wrongful commitment is about an output that cannot be
honoured, whoever reads it. `ASI03` is the nearest thing to data leakage and is about
privileges being abused rather than material escaping. `halt_defeat` and
`disclosure_denial` originated here and claim no external identifier at all, on
either list.

Mapping a family to a category it merely resembles would be the cheapest possible way
to make this report's coverage look wider than it is, and it would corrupt the
subtraction below in the one direction nobody checks — the direction where a gap
disappears.
"""


OUT_OF_REACH: Mapping[str, str] = {
    "ASI03": (
        "the bench sees one endpoint and one token. Whether a credential is "
        "over-scoped, long-lived or shared between agents is a property of the "
        "target's identity plane, and a message-level attacker cannot observe it"
    ),
    "ASI04": (
        "it needs the frameworks, connectors and servers the target is assembled "
        "from, which the bench never sees — the same limit that puts data poisoning "
        "out of reach"
    ),
    "ASI05": (
        "no family claims it yet, and unlike the categories beside it this one is "
        "reachable in principle — against a target that can execute code — so a "
        "family for it is planned rather than ruled out"
    ),
    "ASI06": (
        "no family claims it yet, and unlike the categories beside it this one is "
        "reachable in principle — against a target that retains state across a "
        "session — so a family for it is planned rather than ruled out"
    ),
    "ASI07": (
        "it needs a second agent. Registration takes one endpoint and the bench "
        "speaks to that endpoint alone"
    ),
    "ASI08": (
        "it needs the workflow the target sits inside. One endpoint's replies cannot "
        "show an error propagating through systems the bench cannot reach"
    ),
    "ASI09": (
        "it needs a human approver to mislead. The bench is the only reader of the "
        "target's output and a confident tone does not deceive a success condition, "
        "so measuring this needs a human subject rather than a harness"
    ),
    "ASI10": (
        "it needs observation over time. One run cannot separate an agent that is "
        "misaligned from one that a single case caught — the same limit that puts "
        "lifecycle consistency out of reach"
    ),
}
"""Why each unclaimed category is unclaimed, in the words the report prints.

Every category no family claims needs an entry, and `untested_categories` raises if
one is missing. A gap with no reason beside it reads as an oversight (`CoverageGap`
says the same thing about the four prose limits), and an unexplained gap is also the
form in which *not yet* and *never* become indistinguishable. Two of these eight say
**not yet** and name the kind of target they would need; six say the bench cannot
reach them from where it stands. What the two are waiting for on *this* side — the
capabilities the bench's own calibration equipment lacks — is recorded in PLAN §5 P2
and deliberately not in this prose, because these strings render into a target's
report and a target's report never names that equipment (ADR-0018 §6). A reader
deciding whether this bench is worth using needs to tell *not yet* from *never*, and
the distinction is carried in the prose rather than in a flag because the interesting
content is the blocker rather than the boolean.
"""


@dataclass(frozen=True)
class UntestedCategory:
    """A published agentic category no family in the library claims.

    A different type from `AgenticCategory` on purpose. That one is a copy of a
    published fact and says nothing about this bench; this one is a claim this bench
    makes about itself, and it is only ever produced by the subtraction below. Nothing
    can print a tested category in the untested section by passing the wrong record,
    because the untested section takes a type that only the derivation constructs.
    """

    identifier: str
    title: str
    reason: str

    def stated(self) -> str:
        """The one line the report prints, in `CoverageGap.stated`'s shape."""
        return f"{self.identifier} {self.title} — not tested: {self.reason}"


def untested_categories(
    categories: tuple[AgenticCategory, ...] = AGENTIC_TOP_10_2026,
    claimed: Mapping[Family, str | None] = FAMILY_CATEGORY,
    reasons: Mapping[str, str] = OUT_OF_REACH,
) -> tuple[UntestedCategory, ...]:
    """The published list minus the categories the library's families claim.

    The derivation ADR-0002 promised and `assembler.py` could not make. Adding a
    family that claims a category removes it from this list without anyone editing
    prose, which is the whole point: the previous list could only be shortened by
    hand, and a coverage statement that has to be shortened by hand is one that stays
    long after it stopped being true.

    Every argument has a default and the defaults are the declared data, so a caller
    that wants the bench's real answer passes nothing. The parameters exist so the
    derivation can be driven with a different mapping in a test — proving the list
    moves when the library does, which is the property a hand-written list cannot
    have and the only reason this function exists rather than a constant.

    Raises:
        KeyError: if a family claims an identifier the published copy does not carry,
            which is a typo in `FAMILY_CATEGORY` and would silently subtract nothing.
        KeyError: if an unclaimed category has no reason in `OUT_OF_REACH`, which
            would print a bare identifier and read as an oversight.
    """
    published = {category.identifier for category in categories}
    for family, identifier in claimed.items():
        if identifier is not None and identifier not in published:
            raise KeyError(
                f"{family} claims {identifier}, which is not in {EDITION}. A family "
                "claiming an identifier the stored copy does not carry subtracts "
                "nothing, so the category it meant to cover stays listed as untested "
                "and the mistake reads as a wider gap rather than as an error"
            )

    covered = {identifier for identifier in claimed.values() if identifier is not None}
    untested = tuple(
        category for category in categories if category.identifier not in covered
    )

    missing = [
        category.identifier
        for category in untested
        if category.identifier not in reasons
    ]
    if missing:
        raise KeyError(
            f"{missing} are untested and carry no reason. A gap with no reason beside "
            "it reads as an oversight, and an unexplained gap is where *not yet* and "
            "*never* stop being distinguishable"
        )

    return tuple(
        UntestedCategory(
            identifier=category.identifier,
            title=category.title,
            reason=reasons[category.identifier],
        )
        for category in untested
    )


UNTESTED_AGENTIC_CATEGORIES: tuple[UntestedCategory, ...] = untested_categories()
"""What the bench does not test at all, of the published agentic list.

Computed at import from the three declared records above, so the report cannot be
rendered against a subtraction that was made once and drifted. Eight of ten today:
`ASI01` and `ASI02` are claimed by indirect prompt injection and scope creep, and the
other eight are listed with what stands in the way of each.
"""
