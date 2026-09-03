"""The stored copies of the published lists this repository cites, and the lookup.

Two lists carry the identifiers this bench prints — OWASP's agentic list and OWASP's
GenAI LLM list — and until #44 one of them was stored. `published.py` held the
agentic copy and derived the coverage subtraction from it; the `LLM0x:2026`
identifiers on the case records had nothing to be looked up in, so a claim the bench
prints about an external standard rested on whatever the author remembered when they
typed it. Three of the identifiers #42 selected disagreed with the ones PLAN §4
carries, and nothing in the repository could say which was right.

**Why the copies live here and not in `published.py`.** A stored copy is only worth
storing if the things that claim its identifiers are checked against it, and the
thing that claims them is a **case record** — so `library.py` has to be able to read
the copy. `published.py` imports `Family` from `library.py`, so it cannot be what
`library.py` imports. This module therefore holds the *copies* and the *lookup* and
nothing else: no judgement about which family claims what, and no subtraction. Those
are `published.py`'s, and it reads its copy from here
([ADR-0036](../../docs/adr/0036-a-published-identifier-resolves-to-a-stored-copy.md)).

**A copy is not the source, and each one says where it came from.** The per-copy
docstrings below carry the provenance of that copy and they are not the same
strength: the LLM 2026 copy was read from the publishing project's own repository,
and the agentic copy is two agreeing secondary readings and says so. Titles are
carried verbatim in both, with no rewording to fit this repository's voice, so a
stale copy is visible as a mismatch rather than hidden as a paraphrase.

**Attribution.** Both lists are published by the OWASP GenAI Security Project under
the Creative Commons Attribution-ShareAlike 4.0 International licence, and what is
stored is each entry's identifier and title and nothing else — no descriptive text and
no mitigations. Why that is the right amount to store is ADR-0036's Attribution note.

**How the three defences against a stale copy divide up.** ADR-0036 §4–6 argues them;
what they are here is the edition tag `resolves` checks, the superseded copy `CURRENT`
excludes, and the renumbering `renumbering` derives. Each is documented on the thing
that carries it rather than restated as a list.

**What is deliberately not here.** No subtraction over the LLM copy: the negative
coverage claim for that list needs a reason beside every unclaimed entry and a
per-family reading of both lists, which is the label record (#45) and the identifier
claims (#47), and each of those *widens a coverage claim* — the one direction nobody
checks (`published.py`). Storing the copy is what makes those two tickets a lookup
instead of an argument, and it makes no coverage claim of its own.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class PublishedCategory:
    """One entry of a published list: its identifier and its title, and no more.

    Deliberately holds no judgement about this bench. A record that carried *why we
    do not test this* beside the published fact would be a copy nobody could check
    against the source without first separating the two, and the whole value of a
    stored copy is that it can be checked.
    """

    identifier: str
    title: str


@dataclass(frozen=True)
class StoredCopy:
    """A committed transcription of one edition of one published list.

    The **edition** and not a fetch date, because the fetch date of a reading says
    nothing about which edition was read. A second edition makes every subtraction
    over a copy stale, and the only defence against a stale subtraction that still
    looks current is naming the edition wherever the copy is used.

    The **tag** is the edition as it appears inside an identifier: the `2026` of
    `LLM01:2026`. It is a field rather than a slice of `edition` because the two are
    not the same string and a parser that derived one from the other would be reading
    a title for a number.
    """

    edition: str
    tag: str
    entries: tuple[PublishedCategory, ...]
    superseded_by: StoredCopy | None = None
    """The copy that replaced this one, or `None` for a current copy.

    Set on a copy that is stored for diagnosis only. `CURRENT` filters on it, so a
    superseded entry can never be what an identifier resolves to — the whole reason
    an old copy is safe to keep in the tree.

    The copy itself and not its edition's name: a name would have to be resolved back
    to a record by scanning, with a raise for the case where it named nothing, and a
    superseded copy whose successor cannot be found is a diagnosis that answers with
    silence. A reference cannot dangle.
    """

    def entry(self, identifier: str) -> PublishedCategory | None:
        """The entry this copy carries under `identifier`, matched exactly.

        Exact equality and never containment. `direct_prompt_injection` is a
        substring of `indirect_prompt_injection` and `LLM01` of `LLM010`; a lookup
        that matched by containment would answer questions nobody asked it.
        """
        for entry in self.entries:
            if entry.identifier == identifier:
                return entry
        return None


AGENTIC_TOP_10_2026 = StoredCopy(
    edition="OWASP Top 10 for Agentic Applications 2026",
    tag="2026",
    entries=(
        PublishedCategory("ASI01", "Agent Goal Hijack"),
        PublishedCategory("ASI02", "Tool Misuse & Exploitation"),
        PublishedCategory("ASI03", "Identity & Privilege Abuse"),
        PublishedCategory("ASI04", "Agentic Supply Chain Vulnerabilities"),
        PublishedCategory("ASI05", "Unexpected Code Execution (RCE)"),
        PublishedCategory("ASI06", "Memory & Context Poisoning"),
        PublishedCategory("ASI07", "Insecure Inter-Agent Communication"),
        PublishedCategory("ASI08", "Cascading Failures"),
        PublishedCategory("ASI09", "Human-Agent Trust Exploitation"),
        PublishedCategory("ASI10", "Rogue Agents"),
    ),
)
"""OWASP Top 10 for Agentic Applications 2026, transcribed 2026-08-20.

Ten entries, `ASI01` through `ASI10` in the published order. The order is part of the
copy: a list whose entries are sorted or grouped by this repository's convenience is
no longer the published list.

**Provenance, and it is the weaker of the two here.** The identifiers and titles were
transcribed from two independent secondary readings of the list, which agreed on all
ten of both; the OWASP resource page refuses automated retrieval, so no reading here
is the primary document. That is weaker provenance than a signed artefact deserves
and it is stated rather than smoothed over: what the subtraction in `published.py`
can claim is *agreement between two readings*, and a reader who needs the
authoritative wording goes to OWASP.
"""

LLM_TOP_10_2026 = StoredCopy(
    edition="OWASP GenAI LLM Top 10 2026",
    tag="2026",
    entries=(
        PublishedCategory("LLM01", "Prompt Injection"),
        PublishedCategory("LLM02", "Sensitive Information Disclosure"),
        PublishedCategory("LLM03", "Excessive Agency"),
        PublishedCategory("LLM04", "Supply Chain"),
        PublishedCategory("LLM05", "Data and Model Poisoning"),
        PublishedCategory("LLM06", "Unbounded Consumption"),
        PublishedCategory("LLM07", "Misinformation"),
        PublishedCategory("LLM08", "Hidden Context Exposure"),
        PublishedCategory("LLM09", "Vector and Embedding Weaknesses"),
        PublishedCategory("LLM10", "Improper Output Handling"),
    ),
)
"""OWASP GenAI LLM Top 10 2026, read 2026-09-03. The copy #44 was opened for.

Ten entries, `LLM01` through `LLM10` in the published order, and the `:2026` suffix
the case records carry is this edition's own tag rather than a convention of ours —
which was not knowable here until this copy existed.

**The publisher uses two names and this is the narrower one.** The project is *OWASP
Top 10 for Large Language Model Applications*, which is the H1 of the repository the
copy was read from and covers every edition; the heading over the ten entries of this
edition, and the title of the resource page that publishes it, is *OWASP GenAI LLM
Top 10 2026*. The edition-specific name is stored because `edition` is what a stale
subtraction is caught by and what the report prints — an umbrella project name
identifies no edition and would go on looking current for ever.

**Provenance, and it is the stronger of the two.** Read from the README of the
publishing project's own repository, `GenAI-Security-Project/GenAI-LLM-Top10`, which
names `2026/final/` as the canonical source, and independently corroborated by three
secondary readings that agreed with it on all ten identifiers and titles. Two further
readings disagreed with it and with each other below `LLM03`; both are content-farm
summaries, neither matches the publisher, and they are recorded here because *the
readings did not all agree* is the fact that makes a stored copy worth having.

Still not a byte-for-byte fetch: the README was read through a page-to-text
conversion, so what this copy claims is a faithful reading of the primary document
rather than the document. The distinction is the same one the agentic copy above
makes and it is kept for the same reason — a reader who needs the authoritative
wording goes to OWASP.
"""

LLM_TOP_10_2025 = StoredCopy(
    edition="OWASP Top 10 for LLM Applications 2025",
    tag="2025",
    entries=(
        PublishedCategory("LLM01", "Prompt Injection"),
        PublishedCategory("LLM02", "Sensitive Information Disclosure"),
        PublishedCategory("LLM03", "Supply Chain"),
        PublishedCategory("LLM04", "Data and Model Poisoning"),
        PublishedCategory("LLM05", "Improper Output Handling"),
        PublishedCategory("LLM06", "Excessive Agency"),
        PublishedCategory("LLM07", "System Prompt Leakage"),
        PublishedCategory("LLM08", "Vector and Embedding Weaknesses"),
        PublishedCategory("LLM09", "Misinformation"),
        PublishedCategory("LLM10", "Unbounded Consumption"),
    ),
    superseded_by=LLM_TOP_10_2026,
)
"""OWASP Top 10 for LLM Applications 2025, read 2026-09-03. Superseded, and stored.

**Why a superseded edition is in the tree at all.** Because #42 and PLAN §4 disagree
on three identifiers, and this copy is what turns that disagreement into a lookup.
#42 selected a number on two of those three rows, and **both are this edition's
number for the entry PLAN §4 names in the 2026 numbering** — which `renumbering`
derives rather than asserts. (The third row selected no identifier at all, so there
is no number to renumber; ADR-0036 says what the copy can and cannot settle there.)
Without the old copy, the sentence *the selection was numbering against a different
edition* would be exactly the kind of claim about an external standard with nothing
behind it that #44 exists to remove.

It licenses nothing. `CURRENT` excludes it, so no identifier resolves here, no
coverage claim can be made against it, and a case record naming `:2025` fails to load
with this copy quoted at it rather than accepted by it.

**Provenance.** Read from the publishing project's own archive page for the edition,
`genai.owasp.org/llm-top-10/`, and corroborated by two independent secondary readings
that agreed on all ten. Two further readings carry `Supply Chain Vulnerabilities` for
`LLM03` where the publisher's own page carries `Supply Chain`; the publisher's wording
is what is stored, and the disagreement is noted because a title read off a
third-party summary is how a paraphrase enters a copy that claims to be verbatim.
"""

STORED_COPIES: tuple[StoredCopy, ...] = (
    AGENTIC_TOP_10_2026,
    LLM_TOP_10_2026,
    LLM_TOP_10_2025,
)
"""Every copy in the tree, current and superseded, in no significant order."""

CURRENT: tuple[StoredCopy, ...] = tuple(
    copy for copy in STORED_COPIES if copy.superseded_by is None
)
"""The copies an identifier may resolve to: one edition of each published list.

Derived from `superseded_by` rather than listed, so retiring an edition is one field
on one record instead of a field and a list that can disagree about which editions
this repository stands behind.
"""

ORIGINATED_HERE = "none — originated here"
"""What a case record carries where it claims no published identifier of its own.

The one identifier that resolves to no stored copy and is still a valid claim, and it
is a declared constant rather than a shape the loader recognises: halt defeat and
disclosure denial originated in this project (ADR-0002, PLAN §4), and *this case
claims no published identifier* has to be a sentence a reader can find in the
repository rather than a blank a typo could imitate.

**It says nothing about the family's label, and since #47 those are two different
claims.** Halt defeat's and disclosure denial's families claim `ASI10` and `ASI09` as
secondary labels in `published.FAMILY_CATEGORY`, and every one of their case records
still carries this constant: a family's label is a reading of a published category,
a case's identifier is what *this payload* tests one case within, and the six records
that used to give *the published lists carry no equivalent entry* as the reason now
name the Article they were written from instead
([ADR-0037](../../docs/adr/0037-a-claimed-category-is-claimed-in-part.md)).
"""


def not_a_claim(identifier: str) -> str | None:
    """Why a case record may not carry this identifier, or `None` where it may.

    The whole of what `ExternalId` refuses, held here so that one module knows what a
    published claim is. Three answers and only the first is a pass: the declared
    no-claim form, an identifier naming its edition and resolving there, or a reason
    the reader is given
    ([ADR-0036](../../docs/adr/0036-a-published-identifier-resolves-to-a-stored-copy.md)).

    **A record's identifier has to name its edition, and that is stricter than
    `resolves`.** An untagged `LLM06` resolves — one current copy per list carries it,
    so the lookup has an unambiguous answer — but as a *claim* it is a wildcard: it
    means Excessive Agency under the numbering #42's table was written in and
    Unbounded Consumption under the copy stored today, and it would go on quietly
    meaning whatever the current copy last said. The edition tag is the defence
    ADR-0036 §4 is about, and it defends nothing if a claim is allowed to omit it.
    """
    if identifier == ORIGINATED_HERE:
        return None
    number, colon, tag = identifier.partition(":")
    if not colon or not tag:
        return (
            f"{identifier} names no edition. A case record's identifier is written "
            f"{number}:<edition>, because the same number is different entries in "
            "different editions of one list and an untagged claim would go on "
            "meaning whatever the stored copy last said. The declared form for a "
            f"case that claims no published identifier is {ORIGINATED_HERE!r}"
        )
    return refusal(identifier)


def resolves(identifier: str) -> PublishedCategory | None:
    """The stored entry this identifier names, or `None` where none does.

    An identifier is `LLM07` or `LLM07:2026`: an entry's identifier, optionally
    followed by the edition tag it is claimed under. A stated tag must be the tag of
    the copy that carries the entry, which is what stops an identifier written under
    a superseded numbering from resolving to whatever now sits at that number.

    **The tag is optional here and required of a case record's claim.** A caller
    holding a copy and asking *what is `ASI06`* is asking a question with one answer,
    and `published.FAMILY_CATEGORY` asks exactly that with bare identifiers. A claim
    stored on a record is a different thing and goes through `not_a_claim`.

    Reads `CURRENT` and never `STORED_COPIES`, so a superseded copy answers nothing.
    """
    number, _, tag = identifier.partition(":")
    for copy in CURRENT:
        entry = copy.entry(number)
        if entry is not None and tag in ("", copy.tag):
            return entry
    return None


def refusal(identifier: str) -> str | None:
    """Why `identifier` resolves to no stored copy, in the words the raise carries.

    `None` where it resolves, so a caller reads this as *the reason there is a
    problem* and gets the empty answer when there is not. Two shapes of wrongness get
    two different sentences, because they need different fixes: a number that a
    **superseded edition** carried is a renumbering and the reader needs the current
    number, while a number **no edition** carries is a typo and the reader needs to
    know that nothing was subtracted for it.
    """
    if resolves(identifier) is not None:
        return None
    number, _, tag = identifier.partition(":")
    for copy in STORED_COPIES:
        if copy.superseded_by is None:
            continue
        entry = copy.entry(number)
        if entry is None or (tag not in ("", copy.tag)):
            continue
        moved = renumbering(copy)[f"{entry.identifier}:{copy.tag}"]
        return (
            f"{identifier} is the {copy.edition} numbering, where that number is "
            f"{entry.title}. That edition is superseded by "
            f"{copy.superseded_by.edition}, which carries the same entry as {moved}. "
            "An identifier written under a superseded numbering is the drift a "
            "stored copy exists to catch: it names a real published entry, and it "
            "names the wrong one"
        )
    editions = ", ".join(copy.edition for copy in CURRENT)
    return (
        f"{identifier} is in none of the editions this repository stores "
        f"({editions}), and it is not {ORIGINATED_HERE!r}. An identifier no stored "
        "copy carries cannot be checked against anything, and a coverage claim "
        "nothing can check is the failure #44 was opened for"
    )


def renumbering(superseded: StoredCopy = LLM_TOP_10_2025) -> Mapping[str, str]:
    """Where each entry of a superseded copy sits in the edition that replaced it.

    **Derived from the two copies by title**, so the mapping cannot say something
    neither copy says. An entry whose title appears in neither the current copy nor
    `RETITLED` is a raise: a copy that has been half-updated, or garbled by a reading
    that paraphrased a title, arrives in exactly that shape and it must not arrive as
    a silently shorter mapping.

    Titles are matched by equality and never by containment — the 2026 edition's
    `Supply Chain` is a substring of a title two secondary readings gave the 2025
    entry, and a containment match would have paired them while the publisher's own
    wording says nothing of the kind.
    """
    current = superseded.superseded_by
    if current is None:
        raise ValueError(
            f"{superseded.edition} is a current copy, so there is no edition to "
            "renumber it into. Only a superseded copy has a successor, and asking "
            "the current one for its renumbering is asking where the entries a "
            "report cites today have moved to"
        )
    by_title = {entry.title: entry.identifier for entry in current.entries}
    if len(by_title) != len(current.entries):
        raise ValueError(
            f"{current.edition} carries two entries under one title, so a mapping "
            "read off the titles would pair a superseded entry with whichever of "
            "them came last. A copy in that shape has been garbled and no "
            "renumbering derived from it can be trusted"
        )
    moved: dict[str, str] = {}
    for entry in superseded.entries:
        claimed = f"{entry.identifier}:{superseded.tag}"
        retitled = RETITLED.get(claimed)
        if retitled is not None:
            moved[claimed] = retitled
            continue
        if entry.title not in by_title:
            raise ValueError(
                f"{entry.identifier} {entry.title} of {superseded.edition} is in "
                f"neither {current.edition} nor RETITLED. An entry that was renamed "
                "rather than dropped has to be declared, because a claim written "
                "under its old number would otherwise read as a typo rather than as "
                "the renumbering it is"
            )
        moved[claimed] = f"{by_title[entry.title]}:{current.tag}"
    return moved


RETITLED: Mapping[str, str] = {
    "LLM07:2025": "LLM08:2026",
}
"""Entries a new edition renamed, which no title match can pair.

Declared, and each one is a published fact rather than a judgement: `LLM07:2025
System Prompt Leakage` is `LLM08:2026 Hidden Context Exposure`, which the 2026
edition's own material states is the renamed entry rather than a new one. Every other
entry of the 2025 list kept its exact title, so this is the only pair `renumbering`
cannot derive — and it is one line rather than a second mapping of ten, because a
declared mapping that duplicates a derivable one is a mapping that can disagree with
the copies.
"""
