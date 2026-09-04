"""The published category lists the bench reads its own coverage against.

ADR-0002 promises two disclosures and only one of them existed. The per-family half
— which case inside an identifier a case does *not* test — sits on every case record
and prints in section 4. The per-report half — which published categories the bench
does not test at all — was four hand-written prose limits in `assembler.py`, and that
module said so in its own docstring: "a stated list, not a derived one", because "this
repository holds no such copy" of the published lists.

Two things were wrong with that, and neither was the prose. A coverage claim
assembled by hand shortens quietly when a family is added, and it was already wrong
by omission: not one of the four entries is an OWASP category, so the section that
promised to name the untested categories named none of them. This module holds the
subtraction the copies make possible.

**The copies are not here, and they are not the source either.** `editions.py` holds
the stored copies of both published lists and the provenance of each — a copy is worth
storing only if the things claiming its identifiers are checked against it, and the
thing that claims them is a case record, so the copies have to live somewhere
`library.py` can import
([ADR-0036](../../docs/adr/0036-a-published-identifier-resolves-to-a-stored-copy.md)).

**Which family claims what is not here either, and since #45 that is one record.** A
family's label — its agentic identifiers, its LLM identifiers and its articles — is
`labels.LABELS`
([ADR-0039](../../docs/adr/0039-a-familys-label-is-one-record.md)). What this module
adds is what neither a copy nor a label can carry: why an unclaimed entry is
unclaimed, where a claim stops, and the derivations over those.

**Two declared things here, two stored elsewhere, one labelled elsewhere, and two
derived — over each of two lists.** Why an unclaimed category is unclaimed is a
judgement, declared apart from the copy that carries the category and apart from the
label that failed to claim it. Which half of a claimed category the claiming family
does not reach is a second, and a claim without one does not load
([ADR-0037](../../docs/adr/0037-a-claimed-category-is-claimed-in-part.md)) — because a
claim is the only thing that shortens the untested list, and a coverage claim getting
wider is the one direction nobody checks.

**The derivations read the six and never the tier.** `LABELS` is keyed on `Family`;
`labels.ELECTIVE_LABELS` is a second table keyed on `ElectiveFamily` and nothing here
reads it. An elective family's label is a true statement about which published entry
that family was selected from, and it is not a statement that the bench tests the
entry.

**Since #48 one of the tier's families has cases, and the rule did not change.**
Memory poisoning holds three, and `ASI06` is still printed as untested — because the
tier is **requested**, and a report is about one target (ADR-0018). A subtraction that
read `ELECTIVE_LABELS` would print a category as covered in every report, including
the runs that were never asked for the family; what a run *was* asked for is a fact
about that run and is stated in the block `elective.ElectiveSelection` writes. So the
reason beside `ASI06` moved and the entry did not, which is the direction this module
errs in on purpose (ADR-0035, ADR-0039).

Only the subtractions are computed — and they are computed over the **library's
families**, never over the families one run happened to measure. That boundary is
load-bearing: `payload.py` asserts that dropping a family from a result leaves every
other byte of the document unchanged, and a coverage list keyed on this run's measured
families would move under exactly that test. It would also answer the wrong question.
"What does this bench not test" is a statement about the bench and its library; a
family this target could not answer is `NotMeasurable`, which is a statement about the
target and already has its own home in the payload. Folding one into the other would
put a run-shaped absence in a section titled *at all*.

**The limit this leaves, stated.** The subtraction reads the six families the bench
has, not the cases currently live under them. A family whose every case retired still
claims its categories here, and the derived list would not notice. Reading the live
library instead would make a statement about the bench depend on which records happen
to be on disk at render time, which is the run-scoping this module just refused; the
honest fix, if it is ever needed, is a family with no live cases being a fact the
library refuses to load rather than one the coverage section discovers.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from backend.bench.editions import (
    AGENTIC_TOP_10_2026,
    LLM_TOP_10_2026,
    PublishedCategory,
    StoredCopy,
)
from backend.bench.labels import LABELS
from backend.bench.library import Family

AGENTIC_CLAIMS: Mapping[Family, tuple[str, ...]] = {
    family: label.agentic for family, label in LABELS.items()
}
"""Which entries of the agentic list each family claims, read off its label.

A view of `labels.LABELS` and not a second declaration of it: this module's business
is the subtraction, and the claim it subtracts is one half of a record that also holds
the LLM claim and the article (ADR-0039). Editing a claim means editing the label.

Five claims and one refusal, and the readings behind all six are stated on `LABELS`
itself, where ADR-0037 §1 requires them to be — a claim whose reading lives one file
away is a claim the next editor of the table does not know they are inheriting.
"""

LLM_CLAIMS: Mapping[Family, tuple[str, ...]] = {
    family: label.llm for family, label in LABELS.items()
}
"""Which entries of the GenAI LLM list each family claims, read off its label.

PLAN §4's external column, and the half of ADR-0002's promise that had no copy to be
checked against until #44 and no subtraction until #45. `data_leakage` claims two
entries here and no agentic one, which is the mirror of `halt_defeat` and
`disclosure_denial` claiming an agentic entry and nothing here.
"""


OUT_OF_REACH: Mapping[str, str] = {
    "ASI04:2026": (
        "it needs the frameworks, connectors and servers the target is assembled "
        "from, which the bench never sees — the same limit that puts data poisoning "
        "out of reach"
    ),
    "ASI05:2026": (
        "no family claims it yet, and unlike the categories beside it this one is "
        "reachable in principle — against a target that can execute code — so a "
        "family for it is planned rather than ruled out"
    ),
    "ASI06:2026": (
        "a family for it now exists and it is not one this report's figures are "
        "keyed on: memory poisoning is an elective family, run only when a run asks "
        "for it and against a target that carries one turn of a session into the "
        "next. So the entry stays listed here rather than counted as covered, and "
        "which elective families this run was asked for is stated in its own block"
    ),
    "ASI07:2026": (
        "it needs a second agent. Registration takes one endpoint and the bench "
        "speaks to that endpoint alone"
    ),
    "ASI08:2026": (
        "it needs the workflow the target sits inside. One endpoint's replies cannot "
        "show an error propagating through systems the bench cannot reach"
    ),
    "LLM04:2026": (
        "it needs the components the target was assembled from — the models, the "
        "packages and the provenance of each. The bench is given one endpoint and a "
        "token, which is the same limit that puts the agentic supply-chain entry out "
        "of reach"
    ),
    "LLM05:2026": (
        "it needs the training set and the pre-trained components. Both are "
        "permanent limits of this bench rather than gaps in its library: an attacker "
        "that speaks to a running agent cannot reach what that agent was trained on"
    ),
    "LLM06:2026": (
        "it is a question about cost and capacity under load, and every attempt here "
        "is one exchange against a declared budget. What would measure it is driving "
        "a target until something gave way, which is a denial-of-service test "
        "against somebody else's system and not something this bench does to a "
        "target that invited it"
    ),
    "LLM09:2026": (
        "it needs the store the target retrieves from. The bench can put content in "
        "front of an agent as a tool reply, and it cannot write to a corpus it is "
        "never shown"
    ),
    "LLM10:2026": (
        "it needs whatever is downstream of the target — the browser, the shell or "
        "the database an unescaped reply reaches. The bench reads the reply and "
        "there is nothing behind it to be injured, so what could be shown is that a "
        "payload came back and never that anything acted on it"
    ),
}
"""Why each unclaimed category is unclaimed, in the words the report prints.

Every category no family claims needs an entry, on either list, and
`untested_categories` raises if one is missing. A gap with no reason beside it reads
as an oversight (`CoverageGap` says the same thing about the four prose limits), and
an unexplained gap is also the form in which *not yet* and *never* become
indistinguishable. Two of these ten say **not yet** and name the kind of target they
would need; eight say the bench cannot reach them from where it stands.

**One mapping over two lists, keyed as a claim is written.** Every key names its
edition, so a reason is bound to the entry it was written about and not to a number:
the day either list is renumbered, the reason for `LLM06:2026` Unbounded Consumption
stops matching whatever `LLM06` becomes and the guard below raises rather than printing
the old sentence beside the new entry. That is ADR-0036 §4 applied to this module's own
declared prose, and it is why one mapping over two lists is safe where a bare-number
keyspace would have rested on the two lists happening to use different prefixes.

**Three entries left this mapping and none of their arguments did.** `ASI03`, `ASI09`
and `ASI10` are claimed, so a reason beside them here would read as current while
sitting next to a category that is tested. What each of those reasons ruled out was
one half of its category, and that half is now stated in `NOT_REACHED_WITHIN` and
printed beside the claim rather than in place of it (ADR-0037).

What the two *not yet* entries are waiting for on **this** side — the capabilities the
bench's own calibration equipment lacks — is recorded in PLAN §5 P2 and deliberately
not in this prose, because these strings render into a target's report and a target's
report never names that equipment (ADR-0018 §6). A reader deciding whether this bench
is worth using needs to tell *not yet* from *never*, and the distinction is carried in
the prose rather than in a flag because the interesting content is the blocker rather
than the boolean.
"""


NOT_REACHED_WITHIN: Mapping[str, str] = {
    "ASI01:2026": (
        "the instruction has to arrive inside content the agent retrieved. A goal "
        "overridden by an instruction in the user's own message is tested by none of "
        "the six families, and every case of this one says so in its own note"
    ),
    "ASI02:2026": (
        "the bench reads which tool was called and not what the call did. A tool "
        "inside the approved list used destructively, and any misuse needing a tool "
        "the bench cannot see the target hold, are outside what one endpoint's "
        "declared list can show"
    ),
    "ASI03:2026": (
        "the target's identity plane. Whether a credential is over-scoped, "
        "long-lived or shared between agents is not observable from the one endpoint "
        "and one token the bench sees, so what is tested is authority exercised "
        "without a grant, in one turn, and never the credential that carried it"
    ),
    "ASI09:2026": (
        "the moment of confirmation. Controlling what a human approver sees needs a "
        "human approver to mislead, and the bench is the only reader of the target's "
        "output — a confident tone does not deceive a success condition. What is "
        "tested is an agent misrepresenting what it is, which is a fact about the "
        "output rather than about a reader"
    ),
    "ASI10:2026": (
        "observation over time. One run cannot separate an agent that is misaligned "
        "from one that a single case caught, so what is tested is one action taken "
        "after the operator's stop signal reached the agent and never a pattern of "
        "autonomous behaviour — the same limit that puts lifecycle consistency out "
        "of reach"
    ),
    "LLM01:2026": (
        "the same instruction arriving in the user's own message. The published "
        "category covers a direct override and an indirect one; what is tested is "
        "the indirect half, where the instruction is inside content the agent "
        "retrieved, and the direct half is tested by none of the six families"
    ),
    "LLM02:2026": (
        "personal data belonging to somebody else. What is tested is material the "
        "operator placed inside the target's own boundary — a system prompt, a "
        "configured credential — leaving it, and never a third party's data the "
        "agent holds, which is a different success condition and would need a corpus "
        "this bench does not put in front of a target"
    ),
    "LLM03:2026": (
        "excessive permission and excessive autonomy. What is read is which tool was "
        "called against the list the operator declared; whether the target's own "
        "credentials are broader than its task needs, and whether a human should "
        "have been asked before any of it, are properties of the deployment rather "
        "than of one endpoint's reply"
    ),
    "LLM07:2026": (
        "everything the category covers that is not a commitment. A statement that "
        "is merely wrong, a fabricated citation, a confident summary of a subject "
        "the bench has no ground truth for — what is tested is an undertaking the "
        "operator cannot honour, which can be read off one reply, and never whether "
        "the target's answers are true"
    ),
    "LLM08:2026": (
        "context the bench was never told about. What is tested is the system prompt "
        "this bench configured leaving the boundary; instructions, tools or history "
        "hidden from it cannot be shown to have escaped, because nothing here would "
        "recognise them if they did"
    ),
}
"""Which half of each claimed category the claiming family does not reach.

The second declared judgement in this module, and it is the price of a claim. Every
identifier some family claims in `labels.LABELS` needs an entry, keyed as the claim is
written, and `claimed_in_part` raises if one is missing: a claim shortens the untested
list, which is this document's coverage statement getting **wider**, and the direction
nobody checks is the one where a gap disappears. The defence is that the claim has to
say what it leaves out, in prose somebody had to write (ADR-0037).

**Three of the agentic five are the surviving halves of refusals this module used to
make of a whole category.** `ASI03`, `ASI09` and `ASI10` sat in `OUT_OF_REACH` until
#47, and what each of those reasons ruled out was one half of its category — the
identity plane, the approval moment, observation over time. Those halves are still out
of reach and are still stated, in the sentences they were written in; what changed is
that they are printed beside a claim rather than in place of one.

**The other two were never refused, and they are here for the same reason.** `ASI01`
and `ASI02` have been claimed since ADR-0002, and their limits are PLAN §4's *what it
does not prove* column read at family level. A claim printed without its boundary is
the same overclaim whether or not anybody ever argued about it, so the mapping is
total over the claims rather than over the claims somebody had a fight about.

**The five LLM limits are new prose and two of them are boundaries between families
this bench has and families it has selected.** `LLM01`'s limit is the direct override
every indirect-injection case already excludes in its own note, and `LLM02`'s is a
third party's personal data — which is exactly the elective family #42 selected for
that entry. Stating the boundary is what stops the claim from quietly covering the
selection: an elective family's label says which entry it was read onto and it is not
a claim that the entry is tested (ADR-0039).

These strings render into a target's report, so they carry the same restriction
`OUT_OF_REACH` carries: no sentence here names the bench's own calibration equipment,
because a target's report never does (ADR-0018 §6). What one of them names is a limit
of what was attempted against *this* target's kind of endpoint.

The per-case half of the same disclosure is `ExternalId.not_tested` on each case
record, which says which case inside its identifier that case tests. This is the
family-level half and the two are not derived from each other: one is a claim about a
payload, the other about a category.
"""


@dataclass(frozen=True)
class UntestedCategory:
    """A published category no family in the library claims.

    A different type from `editions.PublishedCategory` on purpose. That one is a copy
    of a published fact and says nothing about this bench; this one is a claim this
    bench makes about itself, and it is only ever produced by the subtraction below.
    Nothing can print a tested category in the untested section by passing the wrong
    record, because the untested section takes a type that only the derivation
    constructs.
    """

    identifier: str
    """The entry, naming its edition — `ASI04:2026`.

    Tagged rather than bare since #45, because this block now carries entries from two
    published lists and the same number is different entries in different editions of
    one of them. It is the form every other published claim in the tree is written in
    (`editions.not_a_claim`) and the form a recipient can look up.
    """

    title: str
    edition: str
    """Which published list this entry is from, in full.

    The tag inside the identifier says which edition and the prefix says which list;
    this says both in the words the publisher uses, so a consumer of the payload never
    has to know that `LLM` means the GenAI list to render the block correctly.
    """

    reason: str

    def stated(self) -> str:
        """The one line the report prints, in `CoverageGap.stated`'s shape."""
        return f"{self.identifier} {self.title} — not tested: {self.reason}"


@dataclass(frozen=True)
class ClaimedInPart:
    """A published category a family claims, and the half it does not reach.

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
    edition: str

    families: tuple[Family, ...]
    """Which families carry this claim — on the record, and not in `stated`.

    Held because a claim is a family's claim: `_claims` names the family in the raise
    a mistyped identifier gets, the label record's reading is per family, and #52 has
    to print the pairing beside a family name. Kept out of the printed line for the
    reason `stated` gives.

    **A tuple, because two families can claim one category and the printed line is
    one line.** A record per *claim* would print the same category twice — the limit
    is keyed by identifier, so both lines would be identical — and a record that kept
    only the first would drop a claim the label table makes. One record per category,
    holding every family that reaches it.
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
        is said in words by the limit itself; which family says it is printed beside a
        family name instead, where the run's own figures are (#52, ADR-0039).

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
    copy: StoredCopy, claimed: Mapping[Family, tuple[str, ...]]
) -> tuple[tuple[PublishedCategory, Family], ...]:
    """Every family's claim on this copy, paired with the copy's own entry.

    One place where a claim is checked against the copy, because the two derivations
    below both rest on it: a claim that resolved for one and not for the other would
    put a category in both blocks of the coverage section or in neither, and both
    blocks print in the same section of the same document.

    In published order, and a category claimed by two families is two pairs rather
    than an error — a derivation that lost the second claim would print a boundary for
    one family and silently drop the other's.

    **The claim names its edition and the copy's entry does not**, so the two are
    compared as a number against the entry and a tag against the copy. A claim written
    under another edition's numbering fails here rather than matching whatever now
    sits at that number, which is the drift `editions.py` exists to catch, and a claim
    on the *other* published list fails here too — its number is in no entry of this
    copy.

    Numbers are compared with `==` and never by containment. `LLM01` is a prefix of
    `LLM010` and a `StrEnum` member is a `str`, so containment here would answer
    questions nobody asked it (`editions.StoredCopy.entry`).

    Raises:
        KeyError: if a family claims an identifier this published copy does not carry,
            which is a mistake in the label table and would silently subtract nothing.
    """
    claiming: dict[str, list[Family]] = {}
    for family, identifiers in claimed.items():
        for identifier in identifiers:
            number, _, tag = identifier.partition(":")
            if copy.entry(number) is None or tag != copy.tag:
                raise KeyError(
                    f"{family} claims {identifier}, which is not in {copy.edition}. A "
                    "family claiming an identifier the stored copy does not carry "
                    "subtracts nothing, so the category it meant to cover stays "
                    "listed as untested and the mistake reads as a wider gap rather "
                    "than as an error"
                )
            claiming.setdefault(number, []).append(family)
    return tuple(
        (entry, family)
        for entry in copy.entries
        for family in claiming.get(entry.identifier, ())
    )


def _tagged(entry: PublishedCategory, copy: StoredCopy) -> str:
    """The copy's entry as a claim is written: the number, then the edition tag."""
    return f"{entry.identifier}:{copy.tag}"


def claimed_in_part(
    copy: StoredCopy = AGENTIC_TOP_10_2026,
    claimed: Mapping[Family, tuple[str, ...]] = AGENTIC_CLAIMS,
    limits: Mapping[str, str] = NOT_REACHED_WITHIN,
) -> tuple[ClaimedInPart, ...]:
    """The categories the families claim on one copy, each with the half it misses.

    The other side of `untested_categories`, over the same claims and the same copy,
    and the two together are the whole published list. It exists because a claim is
    the *only* thing that shortens the untested block, so a claim arriving without a
    boundary is how this document's coverage statement gets wider than the bench
    (ADR-0037).

    **One record per claimed category and not per claim**, because the printed block
    is a list of categories and the limit is declared per identifier: two families
    claiming one category would otherwise print two identical lines. Both families
    are on the record (`ClaimedInPart.families`).

    **One copy per call, because a claim is a claim on a named list.** The two
    subtractions are made separately and concatenated below, so a claim can never be
    checked against the wrong copy — see `_claims`.

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

    silent = [
        _tagged(entry, copy)
        for entry, _ in claiming.values()
        if _tagged(entry, copy) not in limits
    ]
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
            identifier=_tagged(entry, copy),
            title=entry.title,
            edition=copy.edition,
            families=families,
            not_reached=limits[_tagged(entry, copy)],
        )
        for entry, families in claiming.values()
    )


def untested_categories(
    copy: StoredCopy = AGENTIC_TOP_10_2026,
    claimed: Mapping[Family, tuple[str, ...]] = AGENTIC_CLAIMS,
    reasons: Mapping[str, str] = OUT_OF_REACH,
) -> tuple[UntestedCategory, ...]:
    """One published list, minus the categories the library's families claim on it.

    The derivation ADR-0002 promised and `assembler.py` could not make. Adding a
    family that claims a category removes it from this list without anyone editing
    prose, which is the whole point: the previous list could only be shortened by
    hand, and a coverage statement that has to be shortened by hand is one that stays
    long after it stopped being true.

    Every argument has a default and the defaults are the declared data, so a caller
    that wants the bench's answer for the agentic list passes nothing. The parameters
    exist so the derivation can be driven with a different mapping in a test — proving
    the list moves when the library does, which is the property a hand-written list
    cannot have and the only reason this function exists rather than a constant — and
    so that the same derivation makes both subtractions rather than a second one being
    written for the second list.

    **The copy is a `StoredCopy` and not a tuple of entries**, so the raise below can
    name the edition the claim failed against. A subtraction whose error message
    cannot say *which published list* it read is one a reader cannot check, and there
    are two of them here (ADR-0036).

    Raises:
        KeyError: if a family claims an identifier the published copy does not carry,
            which is a mistake in the label table and would silently subtract nothing.
        KeyError: if an unclaimed category has no reason in `OUT_OF_REACH`, which
            would print a bare identifier and read as an oversight.
    """
    covered = {entry.identifier for entry, _ in _claims(copy, claimed)}
    untested = tuple(
        category for category in copy.entries if category.identifier not in covered
    )

    missing = [
        _tagged(category, copy)
        for category in untested
        if _tagged(category, copy) not in reasons
    ]
    if missing:
        raise KeyError(
            f"{missing} are untested and carry no reason. A gap with no reason beside "
            "it reads as an oversight, and an unexplained gap is where *not yet* and "
            "*never* stop being distinguishable"
        )

    return tuple(
        UntestedCategory(
            identifier=_tagged(category, copy),
            title=category.title,
            edition=copy.edition,
            reason=reasons[_tagged(category, copy)],
        )
        for category in untested
    )


SUBTRACTED: tuple[tuple[StoredCopy, Mapping[Family, tuple[str, ...]]], ...] = (
    (AGENTIC_TOP_10_2026, AGENTIC_CLAIMS),
    (LLM_TOP_10_2026, LLM_CLAIMS),
)
"""Each stored copy beside the claims made on it, in the order the report prints them.

Declared once and read by both derivations below, because a copy and the claims on it
travel together everywhere in this module and pairing them twice is pairing them twice
*wrongly* once. The agentic copy against the LLM claims would raise rather than
mislead — `_claims` refuses a claim the copy does not carry — but it would raise from
one of the two blocks of the coverage section and not the other, and both print in the
same section of the same document.

Agentic first, because that is the order the two copies entered the tree and the order
the section's own prose introduces them.
"""


UNTESTED_CATEGORIES: tuple[UntestedCategory, ...] = tuple(
    category
    for copy, claims in SUBTRACTED
    for category in untested_categories(copy, claims)
)
"""What the bench does not test at all, of either published list.

Computed at import from the declared records above, so the report cannot be rendered
against a subtraction that was made once and drifted. Ten of twenty today: five of the
agentic list and five of the GenAI LLM list.

**Two subtractions concatenated and never one over a merged list.** A claim is a claim
on a named edition of a named list, and the two copies have different provenance —
`editions.py` says so about each. Merging them would produce one list with two
provenances and no way for the derivation's raise to say which one a claim failed
against.
"""


CLAIMED_IN_PART: tuple[ClaimedInPart, ...] = tuple(
    claim for copy, claims in SUBTRACTED for claim in claimed_in_part(copy, claims)
)
"""What the bench claims of the published lists, and where each claim stops.

The complement of `UNTESTED_CATEGORIES` over the same two copies, computed at import
from the same declared records, so the two cannot drift into printing one category as
both. Ten of twenty, and the ten are the claims `labels.LABELS` makes.
"""
