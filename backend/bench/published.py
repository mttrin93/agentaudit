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

**The copy is not here, and it is not the source either.** `editions.py` holds the
stored copies of both published lists and the provenance of each — a copy is worth
storing only if the things claiming its identifiers are checked against it, and the
thing that claims them is a case record, so the copies have to live somewhere
`library.py` can import
([ADR-0036](../../docs/adr/0036-a-published-identifier-resolves-to-a-stored-copy.md)).
This module reads the agentic copy from there and adds what a copy cannot carry: who
claims what, why an unclaimed entry is unclaimed, where a claim stops, and the two
derivations over those.

**Three declared things here, one stored elsewhere, and two derived.** The copy is a
copy and holds nothing but the published fact. Which family claims which category is
a judgement, declared apart from the copy. Why an unclaimed category is unclaimed is
a second judgement, declared apart again. Which half of a claimed category the
claiming family does not reach is a third, and a claim without one does not load
([ADR-0037](../../docs/adr/0037-a-claimed-category-is-claimed-in-part.md)) — because
a claim is the only thing that shortens the untested list, and a coverage claim
getting wider is the one direction nobody checks. Only the two subtractions are
computed — and they are computed over the **library's families**, never over the
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

from backend.bench.editions import AGENTIC_TOP_10_2026, PublishedCategory, StoredCopy
from backend.bench.library import Family

FAMILY_CATEGORY: Mapping[Family, str | None] = {
    Family.INDIRECT_PROMPT_INJECTION: "ASI01",
    Family.SCOPE_CREEP: "ASI02",
    Family.WRONGFUL_COMMITMENT: "ASI03",
    Family.DATA_LEAKAGE: None,
    Family.HALT_DEFEAT: "ASI10",
    Family.DISCLOSURE_DENIAL: "ASI09",
}
"""Which agentic category each family tests one case *within* — or none.

A judgement, declared rather than derived, and the wording of ADR-0002 governs it: a
family **tests one case within** an identifier, it **is not** that identifier. Five
claims here and one refusal, and both are argued rather than assumed.

**Three of the five overturned a refusal written in this file, and none of them
deleted the argument that stood in the way**
([ADR-0037](../../docs/adr/0037-a-claimed-category-is-claimed-in-part.md)). Each of
those refusals was true of the *pairing* it was written about and was being read as a
statement about the whole published category:

- `ASI03` Identity & Privilege Abuse goes to `wrongful_commitment` — an agent
  exercising authority its operator never granted it, which is a privilege abused and
  is observable from the one endpoint the bench speaks to. It does **not** go to
  `data_leakage`, for the reason this file already gave and which is the refusal
  below.
- `ASI09` Human-Agent Trust Exploitation goes to `disclosure_denial`, where what the
  human is misled about is whether they are talking to a machine at all. It does
  **not** go to `wrongful_commitment`, and that refusal stands as written: `ASI09` is
  about controlling what a human approver sees at the moment of confirmation, and
  wrongful commitment is about an output that cannot be honoured, whoever reads it.
- `ASI10` Rogue Agents goes to `halt_defeat`. An agent that acts after its operator's
  stop signal reached it is an agent outside operator control, in one turn a harness
  can observe.

**The refusal left, and it is the one this list forces.** `data_leakage` claims no
agentic category: it carries `LLM02:2026` / `LLM08:2026` in PLAN §4, this list has no
disclosure entry, and `ASI03` — the nearest thing to it — is about privileges being
abused rather than material escaping. The agentic list has no accuracy entry either,
which is why `wrongful_commitment`'s claim above is on the *authority* half of
`ASI03` and its accuracy half still lives on the LLM list (`LLM07:2026`
Misinformation, ADR-0036).

**A claim here is a claim on part of a category, and the part it does not reach is
declared in `NOT_REACHED_WITHIN` and printed beside it.** Mapping a family to a
category it merely resembles would be the cheapest possible way to make this report's
coverage look wider than it is, and it would corrupt the subtraction below in the one
direction nobody checks — the direction where a gap disappears. So a claim cannot
leave the untested list shorter without saying what it does not reach:
`claimed_in_part` refuses one that does not.

`halt_defeat` and `disclosure_denial` originated here, and their **cases** claim no
published identifier at all (`editions.ORIGINATED_HERE`). That is not in tension with
the two claims above: a case's identifier and a family's secondary label are two
different claims, which is ADR-0037's boundary and #45's to hold in one record.
"""


OUT_OF_REACH: Mapping[str, str] = {
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
}
"""Why each unclaimed category is unclaimed, in the words the report prints.

Every category no family claims needs an entry, and `untested_categories` raises if
one is missing. A gap with no reason beside it reads as an oversight (`CoverageGap`
says the same thing about the four prose limits), and an unexplained gap is also the
form in which *not yet* and *never* become indistinguishable. Two of these five say
**not yet** and name the kind of target they would need; three say the bench cannot
reach them from where it stands.

**Three entries left this mapping and none of their arguments did.** `ASI03`, `ASI09`
and `ASI10` are claimed above, so a reason beside them here would read as current
while sitting next to a category that is tested. What each of those reasons ruled out
was one half of its category, and that half is now stated in `NOT_REACHED_WITHIN` and
printed beside the claim rather than in place of it (ADR-0037).

What the two *not yet* entries are waiting for on **this** side — the
capabilities the bench's own calibration equipment lacks — is recorded in PLAN §5 P2
and deliberately not in this prose, because these strings render into a target's
report and a target's report never names that equipment (ADR-0018 §6). A reader
deciding whether this bench is worth using needs to tell *not yet* from *never*, and
the distinction is carried in the prose rather than in a flag because the interesting
content is the blocker rather than the boolean.
"""


NOT_REACHED_WITHIN: Mapping[str, str] = {
    "ASI01": (
        "the instruction has to arrive inside content the agent retrieved. A goal "
        "overridden by an instruction in the user's own message is tested by none of "
        "the six families, and every case of this one says so in its own note"
    ),
    "ASI02": (
        "the bench reads which tool was called and not what the call did. A tool "
        "inside the approved list used destructively, and any misuse needing a tool "
        "the bench cannot see the target hold, are outside what one endpoint's "
        "declared list can show"
    ),
    "ASI03": (
        "the target's identity plane. Whether a credential is over-scoped, "
        "long-lived or shared between agents is not observable from the one endpoint "
        "and one token the bench sees, so what is tested is authority exercised "
        "without a grant, in one turn, and never the credential that carried it"
    ),
    "ASI09": (
        "the moment of confirmation. Controlling what a human approver sees needs a "
        "human approver to mislead, and the bench is the only reader of the target's "
        "output — a confident tone does not deceive a success condition. What is "
        "tested is an agent misrepresenting what it is, which is a fact about the "
        "output rather than about a reader"
    ),
    "ASI10": (
        "observation over time. One run cannot separate an agent that is misaligned "
        "from one that a single case caught, so what is tested is one action taken "
        "after the operator's stop signal reached the agent and never a pattern of "
        "autonomous behaviour — the same limit that puts lifecycle consistency out "
        "of reach"
    ),
}
"""Which half of each claimed category the claiming family does not reach.

The third declared judgement in this module, and it is the price of a claim. Every
identifier some family claims in `FAMILY_CATEGORY` needs an entry and
`claimed_in_part` raises if one is missing: a claim shortens the untested list, which
is this document's coverage statement getting **wider**, and the direction nobody
checks is the one where a gap disappears. The defence is that the claim has to say
what it leaves out, in prose somebody had to write
([ADR-0037](../../docs/adr/0037-a-claimed-category-is-claimed-in-part.md)).

**Three of these five are the surviving halves of refusals this module used to make
of a whole category.** `ASI03`, `ASI09` and `ASI10` sat in `OUT_OF_REACH` until #47,
and what each of those reasons ruled out was one half of its category — the identity
plane, the approval moment, observation over time. Those halves are still out of
reach and are still stated, in the sentences they were written in; what changed is
that they are printed beside a claim rather than in place of one.

**The other two were never refused, and they are here for the same reason.** `ASI01`
and `ASI02` have been claimed since ADR-0002, and their limits are PLAN §4's *what it
does not prove* column read at family level. A claim printed without its boundary is
the same overclaim whether or not anybody ever argued about it, so the mapping is
total over the claims rather than over the claims somebody had a fight about.

These strings render into a target's report, so they carry the same restriction
`OUT_OF_REACH` carries: no sentence here names the bench's own calibration
equipment, because a target's report never does (ADR-0018 §6). What one of them names
is a limit of what was attempted against *this* target's kind of endpoint.

The per-case half of the same disclosure is `ExternalId.not_tested` on each case
record, which says which case inside its identifier that case tests. This is the
family-level half and the two are not derived from each other: one is a claim about a
payload, the other about a category.
"""


@dataclass(frozen=True)
class UntestedCategory:
    """A published agentic category no family in the library claims.

    A different type from `editions.PublishedCategory` on purpose. That one is a copy
    of a published fact and says nothing about this bench; this one is a claim this
    bench makes about itself, and it is only ever produced by the subtraction below.
    Nothing can print a tested category in the untested section by passing the wrong
    record, because the untested section takes a type that only the derivation
    constructs.
    """

    identifier: str
    title: str
    reason: str

    def stated(self) -> str:
        """The one line the report prints, in `CoverageGap.stated`'s shape."""
        return f"{self.identifier} {self.title} — not tested: {self.reason}"


@dataclass(frozen=True)
class ClaimedInPart:
    """A published agentic category a family claims, and the half it does not reach.

    The third claim the coverage section makes, and a different type from the two
    beside it because it is a different statement: `CoverageGap` says the bench cannot
    measure something at all, `UntestedCategory` names a published category no family
    reaches, and this one names a category a family **does** reach and states where
    its reach stops. Merging it into either would print a claim as an absence or an
    absence as a claim.

    Only the derivation below constructs one, on `UntestedCategory`'s terms: nothing
    can put a category in this block by holding the wrong record.
    """

    identifier: str
    title: str

    families: tuple[Family, ...]
    """Which families carry this claim — on the record, and not in `stated`.

    Held because a claim is a family's claim: `_claims` names the family in the raise
    a mistyped identifier gets, `FAMILY_CATEGORY`'s reading is per family, and the
    label record (#45) needs the pairing. Kept out of the printed line for the reason
    `stated` gives.

    **A tuple, because two families can claim one category and the printed line is
    one line.** The agentic list has no such row today and the LLM list will (#42:
    `LLM01` once direct prompt injection exists). A record per *claim* would print
    the same category twice — the limit is keyed by identifier, so both lines would
    be identical — and a record that kept only the first would drop a claim the
    mapping makes. One record per category, holding every family that reaches it.
    """

    not_reached: str

    def stated(self) -> str:
        """The one line the report prints, in `UntestedCategory.stated`'s shape.

        **The claiming family is not in the line, and that is the decision rather
        than an omission.** This block is derived over the *library's* families and
        prints in a report a run may have measured two of them for, so a family named
        here that the figures above do not carry would read to a recipient as a family
        this target was tested on — the run-scoping confusion this module refuses,
        arriving from the other end (ADR-0018). What *is* tested within the category
        is said in words by the limit itself; which family says it is the label
        record's to print beside a family name (#45, ADR-0037).

        **Tested in part** and never *tests*, for ADR-0002's reason: a family tests
        one case within an identifier and it is not that identifier, so the line has
        to read as a statement about a category rather than as an equation between a
        category and a family.
        """
        return (
            f"{self.identifier} {self.title} — tested in part; not tested within "
            f"it: {self.not_reached}"
        )


def _claims(
    copy: StoredCopy, claimed: Mapping[Family, str | None]
) -> tuple[tuple[PublishedCategory, Family], ...]:
    """Every family's claim, paired with the copy's own entry, in published order.

    One place where a claim is checked against the copy, because the two derivations
    below both rest on it: a claim that resolved for one and not for the other would
    put a category in both blocks of the coverage section or in neither, and both
    blocks print in the same section of the same document.

    A category claimed by two families is two pairs rather than an error. The agentic
    list has no such row today and the LLM list will (#42: `LLM01` once direct
    injection exists), and a derivation that lost the second claim would print a
    boundary for one family and silently drop the other's.

    Identifiers are compared with `==` and never by containment. `LLM01` is a prefix
    of `LLM010` and a `StrEnum` member is a `str`, so containment here would answer
    questions nobody asked it (`editions.StoredCopy.entry`).

    Raises:
        KeyError: if a family claims an identifier the published copy does not carry,
            which is a typo in `FAMILY_CATEGORY` and would silently subtract nothing.
    """
    published = {category.identifier for category in copy.entries}
    for family, identifier in claimed.items():
        if identifier is not None and identifier not in published:
            raise KeyError(
                f"{family} claims {identifier}, which is not in {copy.edition}. A "
                "family claiming an identifier the stored copy does not carry "
                "subtracts nothing, so the category it meant to cover stays listed "
                "as untested and the mistake reads as a wider gap rather than as "
                "an error"
            )
    return tuple(
        (entry, family)
        for entry in copy.entries
        for family, identifier in claimed.items()
        if identifier == entry.identifier
    )


def claimed_in_part(
    copy: StoredCopy = AGENTIC_TOP_10_2026,
    claimed: Mapping[Family, str | None] = FAMILY_CATEGORY,
    limits: Mapping[str, str] = NOT_REACHED_WITHIN,
) -> tuple[ClaimedInPart, ...]:
    """The categories the library's families claim, each with the half it misses.

    The other side of `untested_categories`, over the same claims and the same copy,
    and the two together are the whole published list. It exists because a claim is
    the *only* thing that shortens the untested block, so a claim arriving without a
    boundary is how this document's coverage statement gets wider than the bench
    (ADR-0037).

    **One record per claimed category and not per claim**, because the printed block
    is a list of categories and the limit is declared per identifier: two families
    claiming one category would otherwise print two identical lines. Both families
    are on the record (`ClaimedInPart.families`).

    Defaults are the declared data on `untested_categories`' terms; the parameters
    exist so a test can drive the derivation with a different mapping.

    Raises:
        KeyError: if a claimed category has no limit in `NOT_REACHED_WITHIN`, which
            would print a category as claimed with nothing said about the boundary of
            the claim.
    """
    claiming: dict[str, tuple[PublishedCategory, tuple[Family, ...]]] = {}
    for entry, family in _claims(copy, claimed):
        held = claiming.get(entry.identifier)
        families = () if held is None else held[1]
        claiming[entry.identifier] = (entry, (*families, family))

    silent = [identifier for identifier in claiming if identifier not in limits]
    if silent:
        raise KeyError(
            f"{silent} are claimed and carry no limit. Each is claimed by a family "
            "that says nothing about what it does not reach within it, which is the "
            "whole of what a claim costs: the category leaves the untested list and "
            "the report's coverage claim widens with nothing beside it a reader can "
            "check"
        )

    return tuple(
        ClaimedInPart(
            identifier=entry.identifier,
            title=entry.title,
            families=families,
            not_reached=limits[entry.identifier],
        )
        for entry, families in claiming.values()
    )


def untested_categories(
    copy: StoredCopy = AGENTIC_TOP_10_2026,
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

    **The copy is a `StoredCopy` and not a tuple of entries**, so the raise below can
    name the edition the claim failed against. A subtraction whose error message
    cannot say *which published list* it read is one a reader cannot check, and there
    are now two of them in the tree (ADR-0036).

    Raises:
        KeyError: if a family claims an identifier the published copy does not carry,
            which is a typo in `FAMILY_CATEGORY` and would silently subtract nothing.
        KeyError: if an unclaimed category has no reason in `OUT_OF_REACH`, which
            would print a bare identifier and read as an oversight.
    """
    covered = {entry.identifier for entry, _ in _claims(copy, claimed)}
    untested = tuple(
        category for category in copy.entries if category.identifier not in covered
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

Computed at import from the declared records above, so the report cannot be rendered
against a subtraction that was made once and drifted. Five of ten today: `ASI01`,
`ASI02`, `ASI03`, `ASI09` and `ASI10` are claimed — in part, and each says which part
(ADR-0037) — and the other five are listed with what stands in the way of each.
"""


CLAIMED_IN_PART: tuple[ClaimedInPart, ...] = claimed_in_part()
"""What the bench claims of the published agentic list, and where each claim stops.

The complement of `UNTESTED_AGENTIC_CATEGORIES` over the same copy, computed at import
from the same declared records, so the two cannot drift into printing one category as
both. Five of ten today, and the five are the claims `FAMILY_CATEGORY` makes.
"""
