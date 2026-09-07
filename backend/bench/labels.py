"""What a family is labelled with: the entries it claims, and the articles it bears on.

One record per family, in one place. Before this module the label lived as two
mappings of different shapes in two others — `published.FAMILY_CATEGORY` gave a family
at most one identifier on one list, `judge.article_for` gave it exactly one article —
and #42's selection breaks both cardinalities at once: a family carries an identifier
on each of two lists or none on either, one identifier is claimed by two families, and
four families bear two articles. Why the two halves became one record, and what the
consolidation cost, is
[ADR-0039](../../docs/adr/0039-a-familys-label-is-one-record.md); why the article half
is a tuple every reader of it takes whole, and what the order inside it means, is
[ADR-0040](../../docs/adr/0040-a-family-bears-more-than-one-article.md).

**Two tables and one record type.** `LABELS` is keyed on `Family`, `ELECTIVE_LABELS` on
`ElectiveFamily`, and a label is the same shape in both: an elective family says the
same kinds of thing about itself. What must not exist is a table keyed on both, because
the reader of a label is a report and the reader of *some* labels is the coverage
subtraction in `published.py`, which shortens a printed list per claim — so a union key
would be a route for a family the gate is not decided over to widen the bench's stated
coverage. The distinction is carried by the key type on the terms ADR-0035 states for
every other elective/mandatory pair, and no function here takes both.

**Only a family carries a label.** There are two tables here and there is deliberately
no third: `contract.AgentCapability` — the three properties the Agents Rule of Two is
read over — gets none, and neither does anything else that is not a kind of failure the
bench attacks. #42's table gives that row an Article; ADR-0039 §10 says why it stays in
that table and does not become data, and it is ADR-0038's decision 3 read from the
other end.

**A label is not a case's identifier.** `ExternalId` on a case record says which case
inside a published entry *that payload* tests; a label says which published entries the
family was read onto. The two are different claims (ADR-0037 §7) and neither is derived
from the other — which is why `editions.ORIGINATED_HERE`, the declared no-claim form of
the first, is refused here and an empty tuple is the second's.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from backend.bench import editions
from backend.bench.library import ElectiveFamily, Family


class Article(StrEnum):
    """The duty a family's failure bears on. A fixed table, never a model's choice.

    `map_to_article` is harness-side deliberately (PLAN §11): the mapping is the
    project's own legal claim, written down in PLAN §4 before any code, and a model
    free to pick a different article each run would make the report's central column
    non-reproducible for the same reason ADR-0004 demoted the judge's verdict.

    It sits here rather than in `judge.py` because the article is half of a family's
    label and the judge is one reader of it: a narrative looks the article up, and so
    do the report, the payload and — once #52 carries a finding out of `judge.py` — the
    screen. A type every one of those reads should not be defined inside the one that
    may not choose it.
    """

    RECORD_KEEPING = "12"
    """Applies to every family. The article a disagreement is recorded under."""

    DATA_GOVERNANCE = "10"
    """Data and data governance. Borne where the material that escaped, or that
    steered the agent, was *someone else's* — a third party's personal data, or a
    turn of a prior session read back as though it were the operator's instruction.
    Distinguished from 15 by whose data it is rather than by how it moved."""

    TRANSPARENCY_TO_DEPLOYERS = "13"
    """Transparency and provision of information to deployers. The duty owed to the
    organisation *operating* the system, and never the same duty as `TRANSPARENCY`
    below: 50 is owed to the person in the conversation, 13 to whoever deployed the
    thing they are talking to. Disclosure denial defeats both at once, which is why
    it is the one family that bears the pair."""

    HUMAN_OVERSIGHT = "14"
    STOP_CONTROL = "14(4)(e)"
    ROBUSTNESS_AND_CYBERSECURITY = "15"

    TRANSPARENCY = "50"
    """Transparency obligations owed to the natural person interacting with the
    system. Not `TRANSPARENCY_TO_DEPLOYERS`, which is Article 13 and a different
    reader."""


@dataclass(frozen=True)
class FamilyLabel:
    """The published entries one family was read onto, and the articles it bears on.

    Three tuples and no scalar anywhere, because every one of the three has a
    cardinality the old shape could not hold: a family claims entries on two lists
    independently, either list may carry none, and #42 gives four families two
    articles. A field that held *at most one* of any of them would be the defect this
    record was opened for, one list further along.

    Empty is a real answer and not a missing one. `agentic=()` on data leakage is the
    refusal `published.py` argues for; `llm=()` on halt defeat and disclosure denial is
    ADR-0002's *originated here*, at family level.
    """

    agentic: tuple[str, ...] = ()
    """Entries of the OWASP agentic list this family claims, each naming its edition."""

    llm: tuple[str, ...] = ()
    """Entries of the OWASP GenAI LLM list this family claims, each naming its
    edition."""

    articles: tuple[Article, ...] = ()
    """The EU AI Act articles this family's failure bears on, primary first.

    PLAN §4's column and #42's second articles, in that order and never sorted
    ([ADR-0040](../../docs/adr/0040-a-family-bears-more-than-one-article.md)). The
    default is empty so the field can sit beside the two that mean something empty,
    and `__post_init__` refuses it: unlike a published list, there is no family that
    bears no duty.
    """

    def __post_init__(self) -> None:
        """Refuse a label with no article, or an identifier naming no stored copy.

        Two refusals of the same shape and they are not the same argument. The
        article half is asymmetric with the two identifier tuples above on purpose:
        empty is a real answer there and none here
        ([ADR-0040](../../docs/adr/0040-a-family-bears-more-than-one-article.md)
        decision 5). It is made here rather than by each reader because there is no
        longer a family for which a blank column is the honest answer, and a guard
        whose condition cannot be reached is one nobody can drive red.

        The identifier half is the check `ExternalId` makes of a case's claim,
        arriving at the other claim a report prints
        ([ADR-0036](../../docs/adr/0036-a-published-identifier-resolves-to-a-stored-copy.md)).
        A label is the more dangerous of the two places to leave the edition open,
        because it is read once per family rather than once per case: an untagged
        `LLM06` means Excessive Agency under the numbering #42's table was written in
        and Unbounded Consumption under the copy stored today, and nothing downstream
        would notice which.

        `ORIGINATED_HERE` is refused rather than accepted, because it is a *case
        record's* declared no-claim form. A label carrying it would read as a family
        that had been given an identifier, and the form a family with no claim takes
        is the empty tuple above.
        """
        if not self.articles:
            raise ValueError(
                "this label bears no article. PLAN §4's column is the report's "
                "central defence and a blank in it is not a finding about the "
                "family — a family claims nothing on a published list often, and "
                "bears no legal duty never"
            )
        for identifier in (*self.agentic, *self.llm):
            if identifier == editions.ORIGINATED_HERE:
                raise ValueError(
                    f"{identifier!r} is a case record's way of claiming no published "
                    "identifier, and a family's label is a different claim "
                    "(ADR-0037). A family that claims nothing on a list carries an "
                    "empty tuple, which is an answer rather than a blank"
                )
            refused = editions.not_a_claim(identifier)
            if refused is not None:
                raise ValueError(refused)


def articles_stated(articles: tuple[Article, ...]) -> str:
    """`article 15`, or `articles 50 and 13` — the sentence a reader prints.

    One rendering for every reader of a label, and why there is one rather than a
    format string per call site is
    [ADR-0040](../../docs/adr/0040-a-family-bears-more-than-one-article.md)
    decision 7.

    Reads the tuple as the label declares it and sorts nothing, so the printed line
    is stable for a golden digest and still says which article is the primary claim.

    Raises:
        ValueError: on an empty tuple, which `FamilyLabel` and `judge.Narrative`
            refuse before it can reach here. `articles ` with nothing after it is
            what silence would look like in a signed document.
    """
    if not articles:
        raise ValueError(
            "this label bears no article, so there is nothing for a reader of "
            "PLAN §4's central column to print"
        )
    if len(articles) == 1:
        return f"article {articles[0]}"
    return f"articles {', '.join(articles[:-1])} and {articles[-1]}"


AGENTIC_LIST = "the OWASP agentic list"
"""What a report calls the list `FamilyLabel.agentic` claims on.

The short name and not `editions.AGENTIC_TOP_10_2026.edition`, which names the
edition: every identifier a label carries already names its own edition
(`__post_init__`), so a sentence that named it a second time would print
*ASI01:2026 on the OWASP Top 10 for Agentic Applications 2026* and say 2026 twice.
"""

LLM_LIST = "the OWASP GenAI LLM list"
"""What a report calls the list `FamilyLabel.llm` claims on. `AGENTIC_LIST`'s
reasoning, and the two are spelled out here so the two halves of one sentence cannot
be worded apart."""


def bears_stated(articles: tuple[Article, ...]) -> str:
    """`bears article 15 of the EU AI Act` — the sentence a reader prints for the
    article half of a label.

    `articles_stated` names the duties and this names the Act they are duties under,
    and there is one of it for ADR-0040 decision 7's reason: the report prints this
    sentence in three places and the screen prints it in three more, and *of the EU AI
    Act* written out at six call sites is six chances for one of them to say something
    else. The payload carries this rather than `articles_stated`, so the document and
    the screen read one sentence rather than each appending the Act's name to a
    fragment.

    Lower case, because every reader of it puts it inside a longer sentence — *this
    family bears …*, *the family bears … and claims …*. A capitalised form would be a
    second rendering, which is the thing this exists to stop.
    """
    return f"bears {articles_stated(articles)} of the EU AI Act"


def claims_stated(label: FamilyLabel) -> str:
    """`claims ASI01:2026 Agent Goal Hijack on the OWASP agentic list and …` — the
    sentence a reader prints for the identifier half of a label.

    `articles_stated`'s counterpart, beside it for the reason ADR-0040 decision 7
    gives: one rendering for every reader, so the report, the payload and the screen
    cannot word one claim three ways. It takes the record rather than a tuple,
    because the sentence spans both identifier fields and a caller holding only one
    of them would be a caller printing half a claim.

    **Both lists are named in every answer, including the one that claims nothing on
    either.** An empty tuple is a real answer on both fields (`FamilyLabel`), and a
    line that dropped the empty side would leave *this family claims nothing here*
    indistinguishable from *this list was not consulted* — which is the reading
    `published.UntestedCategory` exists to keep separate at the other end.

    **Each identifier prints with the title the stored copy carries, verbatim.** The
    title is the published wording, transcribed under the provenance discipline
    `editions.py` states, and printing the identifier alone would leave a reader with
    a number to look up — while printing this repository's paraphrase of the entry is
    the thing a stored copy exists to prevent: a copy that has gone stale shows up as
    a mismatch against the source, and a paraphrase hides as a wording choice
    ([ADR-0036](../../docs/adr/0036-a-published-identifier-resolves-to-a-stored-copy.md),
    ADR-0002). `FamilyLabel.__post_init__` has already refused an identifier that
    resolves to no copy, so the lookup here cannot come back empty.

    Reads the tuples in the order the label declares them and sorts nothing, on
    `articles_stated`'s reasoning: the printed line has to be stable for a golden
    digest, and the order is data.
    """
    return (
        f"claims {_entries(label.agentic)} on {AGENTIC_LIST} and "
        f"{_entries(label.llm)} on {LLM_LIST}"
        if label.agentic or label.llm
        else "claims nothing on either published list"
    )


def _entries(identifiers: tuple[str, ...]) -> str:
    """Those entries as a reader reads them, or `nothing` where there are none."""
    if not identifiers:
        return "nothing"
    named = [_entry(identifier) for identifier in identifiers]
    if len(named) == 1:
        return named[0]
    return f"{', '.join(named[:-1])} and {named[-1]}"


def _entry(identifier: str) -> str:
    """One claimed entry: its identifier, and the title the stored copy carries."""
    stored = editions.resolves(identifier)
    if stored is None:  # pragma: no cover - `FamilyLabel` refuses one that does not
        raise ValueError(editions.refusal(identifier))
    return f"{identifier} {stored.title}"


def covering[F: StrEnum](
    labels: Mapping[F, FamilyLabel], kind: type[F]
) -> Mapping[F, FamilyLabel]:
    """`labels`, checked total over `kind`, or a raise naming what is missing.

    The half of the old shape that a dict cannot keep. `judge.article_for` was a match
    with no fallback branch, so a seventh family failed the type check rather than
    acquiring an article by default; a mapping literal is exhaustive to no type
    checker, so totality is asserted where the table is declared and a family with no
    label stops the module — and therefore every test and every run — from loading.
    ADR-0039 records why the table is a mapping rather than a match anyway.

    Total **and** exact: a key that is not a member of `kind` is refused too. The
    annotation says so already, and a table is exactly where a `# type: ignore` on one
    line puts something in a mapping the whole module is defined over — a declared
    capability, say, which ADR-0038 §3 refuses a label for and which this module has no
    third table for on purpose.

    Raises:
        KeyError: if a member of `kind` has no label. A family that acquired a label
            by default would acquire the previous family's coverage claim with it.
        KeyError: if the table holds a key `kind` does not, which is a label for
            something that is not the kind of thing this table is about.
    """
    missing = [family for family in kind if family not in labels]
    if missing:
        raise KeyError(
            f"{missing} carries no label. A family whose published identifiers and "
            "article are not declared is one a reader cannot place against either "
            "published list or against the Act, and the report prints the label "
            "beside the family name"
        )
    members = set(kind)
    stranger = [held for held in labels if held not in members]
    if stranger:
        raise KeyError(
            f"{stranger} is labelled here and is not a {kind.__name__}. A label is a "
            "claim about a kind of failure the bench attacks, and this table is "
            "defined over one enumeration of them"
        )
    return labels


LABELS: Mapping[Family, FamilyLabel] = covering(
    {
        Family.INDIRECT_PROMPT_INJECTION: FamilyLabel(
            agentic=("ASI01:2026",),
            llm=("LLM01:2026",),
            articles=(Article.ROBUSTNESS_AND_CYBERSECURITY,),
        ),
        Family.SCOPE_CREEP: FamilyLabel(
            agentic=("ASI02:2026",),
            llm=("LLM03:2026",),
            articles=(
                Article.HUMAN_OVERSIGHT,
                Article.ROBUSTNESS_AND_CYBERSECURITY,
            ),
        ),
        Family.WRONGFUL_COMMITMENT: FamilyLabel(
            agentic=("ASI03:2026",),
            llm=("LLM07:2026",),
            articles=(
                Article.ROBUSTNESS_AND_CYBERSECURITY,
                Article.HUMAN_OVERSIGHT,
            ),
        ),
        Family.DATA_LEAKAGE: FamilyLabel(
            llm=("LLM02:2026", "LLM08:2026"),
            articles=(Article.ROBUSTNESS_AND_CYBERSECURITY,),
        ),
        Family.HALT_DEFEAT: FamilyLabel(
            agentic=("ASI10:2026",),
            articles=(Article.STOP_CONTROL,),
        ),
        Family.DISCLOSURE_DENIAL: FamilyLabel(
            agentic=("ASI09:2026",),
            articles=(Article.TRANSPARENCY, Article.TRANSPARENCY_TO_DEPLOYERS),
        ),
    },
    Family,
)
"""The six families the gate is decided over, each with the labels it carries.

A judgement per entry, declared rather than derived, and the wording of ADR-0002
governs all of it: a family **tests one case within** an identifier, it **is not** that
identifier.

**The agentic column: five claims and one refusal, and three of the five overturned a
refusal this repository had written down**
([ADR-0037](../../docs/adr/0037-a-claimed-category-is-claimed-in-part.md)). Each of
those refusals was true of the *pairing* it was written about and was being read as a
statement about the whole published category:

- `ASI03` Identity & Privilege Abuse goes to `wrongful_commitment` — an agent
  exercising authority its operator never granted it, which is a privilege abused and
  is observable from the one endpoint the bench speaks to. It does **not** go to
  `data_leakage`, which is the refusal below.
- `ASI09` Human-Agent Trust Exploitation goes to `disclosure_denial`, where what the
  human is misled about is whether they are talking to a machine at all. It does
  **not** go to `wrongful_commitment`, and that refusal stands as written: `ASI09` is
  about controlling what a human approver sees at the moment of confirmation, and
  wrongful commitment is about an output that cannot be honoured, whoever reads it.
- `ASI10` Rogue Agents goes to `halt_defeat`. An agent that acts after its operator's
  stop signal reached it is an agent outside operator control, in one turn a harness
  can observe.

**The refusal left, and it is the one this list forces.** `data_leakage` claims no
agentic entry: the agentic list has no disclosure category, and `ASI03` — the nearest
thing to it — is about privileges being abused rather than material escaping. Its
claim is on the LLM list instead, on both halves of what the family tests.

**The LLM column is PLAN §4's external column, in the 2026 numbering.** It is a
transcription of a table written before any code and not a new set of readings.
`halt_defeat` and `disclosure_denial` claim nothing there, which is the *no LLM
equivalent* of PLAN §4 and the reason ADR-0002 gives for saying those two originated
here.

**`data_leakage` carries two entries, and #42's table names only one of them.** The
selection gives that row `LLM07:2025`, which renumbers to `LLM08:2026` Hidden Context
Exposure (`editions.RETITLED`); PLAN §4 names that *and* `LLM02:2026` Sensitive
Information Disclosure, and the second is the one the disagreement is about. It is
claimed, and the reason is not that PLAN §4 outranks #42 — it is that **three case
records already claim `LLM02:2026`**, and section 4 of every report prints *tests one
case within `LLM02:2026`* beside this family's figures. A label that dropped it would
put a document's own coverage section two sections away from a line contradicting it,
which is the failure ADR-0037 was opened for arriving on the other list. What the
family does not reach inside the entry — a third party's personal data, which is the
elective family #42 selected for it — is stated beside the claim in
`published.NOT_REACHED_WITHIN` rather than left to be read off the claim's absence, and
`published.py` has a test that no identifier a live case claims is printed as untested.

**The article column is PLAN §4's, with #42's second articles after it and never
sorted.** Three of these six bear two — scope creep 14 and 15, wrongful commitment 15
and 14, disclosure denial 50 and 13 — and the two rows carrying the same pair carry it
in opposite orders, because the first is the article the family's failure principally
bears on and a reader with room for one prints that
([ADR-0040](../../docs/adr/0040-a-family-bears-more-than-one-article.md)). Article 12
is on none of them: PLAN §4 gives it to every row, so it sits on `judge.Disagreement`
instead of nine times here.

Every claim in either column costs a stated limit in `published.NOT_REACHED_WITHIN`,
and the two subtractions there are what makes an unclaimed entry print with a reason.
"""


ELECTIVE_LABELS: Mapping[ElectiveFamily, FamilyLabel] = covering(
    {
        ElectiveFamily.MEMORY_POISONING: FamilyLabel(
            agentic=("ASI06:2026",),
            articles=(
                Article.ROBUSTNESS_AND_CYBERSECURITY,
                Article.DATA_GOVERNANCE,
            ),
        ),
        ElectiveFamily.DIRECT_PROMPT_INJECTION: FamilyLabel(
            llm=("LLM01:2026",),
            articles=(Article.ROBUSTNESS_AND_CYBERSECURITY,),
        ),
        ElectiveFamily.PII_LEAKAGE: FamilyLabel(
            llm=("LLM02:2026",),
            articles=(Article.DATA_GOVERNANCE,),
        ),
    },
    ElectiveFamily,
)
"""The elective tier's labels, which #43 declared in prose and this makes data.

`ElectiveFamily`'s own docstring named an identifier per member and said, in the same
paragraph, that they were **not** the family's label. These are, and the prose there is
now a pointer here.

**`LLM01:2026` appears twice in the tree and each time it is a different family's
claim.** `indirect_prompt_injection` is above and `direct_prompt_injection` is here,
which is #42's *`LLM01` is claimed by two families* — and the reason
`published.ClaimedInPart.families` is a tuple. What it is **not** is a claim by two
families in one subtraction: the derivations in `published.py` read `LABELS` alone, so
nothing on this table shortens a printed coverage list.

**`pii_leakage` bears Article 10 alone, which is the blank #45 declared and #46
filled.** It carried none while `Article` had no member for *data and data governance*,
on the footing that a wrong article is worse than a blank; the member exists now, this
was the last blank column in the tree, and a label bearing no article is refused where
it is written rather than guarded against per reader (ADR-0040).

All three now label families with cases on disk — #48 brought memory poisoning's, #49
direct prompt injection's and #50 PII leakage's — and the table did not change when
any of them arrived, which is the tier's shape rather than an oversight: a member
exists so the cases have somewhere to land
([ADR-0035](../../docs/adr/0035-the-elective-family-tier-is-never-gate-deciding.md)),
and a label is a claim about which entry a family was read onto rather than a claim
that the entry is tested.

**`LLM02:2026` is the second entry claimed by two families, and the second where one
of them is the tier's.** `data_leakage` is above and `pii_leakage` is here, and what
that is not — for the reason `LLM01:2026` is not — is a claim by two families in one
subtraction: `published.py`'s derivations read `LABELS` alone, so
`ClaimedInPart.families` stays a tuple over the six and this table shortens no printed
coverage list. Why the second family stays off that record even though the entry is
already claimed and already printed is
[ADR-0043](../../docs/adr/0043-the-canary-a-nonce-cannot-be-confused-with.md)
decision 4.
"""


def label_for(family: Family) -> FamilyLabel:
    """The label one of the six carries.

    Keyed on `Family` and never on both enumerations, so there is no argument through
    which an elective family reaches a reader that is defined over the six — the
    coverage subtraction in `published.py` being the one that matters, because a claim
    is the only thing that shortens a printed untested list.

    `elective_label_for` below is its counterpart, added when the console became the
    first reader of `ELECTIVE_LABELS` outside its own table. The type boundary is the
    key type of each table rather than either function, and the pair is two accessors
    precisely so that no signature exists which accepts both.
    """
    return LABELS[family]


def elective_label_for(family: ElectiveFamily) -> FamilyLabel:
    """The label one of the elective tier carries.

    Keyed on `ElectiveFamily` and never on both enumerations, for the reason
    `label_for` above is keyed on `Family`: the key type of each table is the boundary
    ADR-0035 asks for, and one accessor over `AnyFamily` would be the single argument
    through which an elective family reaches a caller written for the six.

    Its reader is the console. The bench page prints every family's published claims
    and the articles it bears beside the tick that requests it, over the nine rows it
    now draws as one list
    ([ADR-0091](../../docs/adr/0091-the-console-draws-the-nine-families-as-one-list.md)).
    What that screen may not print, and does not, is a rate or a `D`: a label is what a
    family *is* read onto, and the tier's discriminating power is a fact about this
    bench that belongs in the gate run's own document (ADR-0018).
    """
    return ELECTIVE_LABELS[family]


def article_for(family: Family) -> tuple[Article, ...]:
    """The articles this family's failure bears on, primary first.

    Read off the label rather than matched on the family, which is the consolidation:
    the articles and the published identifiers are one record and cannot drift into
    disagreeing about which family they describe.

    A tuple and never one article, because four of the nine families bear two and a
    reader given the first of them would print a true sentence with a duty missing
    from it. Why the reader widened rather than the record narrowing, and what the
    order inside the tuple means, is
    [ADR-0040](../../docs/adr/0040-a-family-bears-more-than-one-article.md).

    Never empty: `FamilyLabel` refuses a label with no article, so a caller may index
    `[0]` for the primary claim without asking first.
    """
    return label_for(family).articles
