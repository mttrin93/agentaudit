"""What a family is labelled with: the entries it claims, and the articles it bears on.

One record per family, in one place. Before this module the label lived as two
mappings of different shapes in two others — `published.FAMILY_CATEGORY` gave a family
at most one identifier on one list, `judge.article_for` gave it exactly one article —
and #42's selection breaks both cardinalities at once: a family carries an identifier
on each of two lists or none on either, one identifier is claimed by two families, and
five families bear two articles. Why the two halves became one record, and what the
consolidation cost, is
[ADR-0039](../../docs/adr/0039-a-familys-label-is-one-record.md).

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

    HUMAN_OVERSIGHT = "14"
    STOP_CONTROL = "14(4)(e)"
    ROBUSTNESS_AND_CYBERSECURITY = "15"
    TRANSPARENCY = "50"


@dataclass(frozen=True)
class FamilyLabel:
    """The published entries one family was read onto, and the articles it bears on.

    Three tuples and no scalar anywhere, because every one of the three has a
    cardinality the old shape could not hold: a family claims entries on two lists
    independently, either list may carry none, and #42 gives five families two
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
    """The EU AI Act articles this family's failure bears on, from PLAN §4."""

    def __post_init__(self) -> None:
        """Refuse an identifier that names no edition or no stored copy.

        The check `ExternalId` makes of a case's claim, arriving at the other claim a
        report prints
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

    @property
    def article(self) -> Article:
        """The one article a reader that has room for one may print.

        `Narrative.article` and `Disagreement.article` are single fields, so the
        narrow reader is the reader and not the record. It refuses rather than
        returning the first, because returning the first is how the second article of
        a family that has two disappears on the day it is declared — and the day is
        scheduled (#46, which gives `Article` its 10 and 13 and widens the reader).
        """
        if not self.articles:
            raise ValueError(
                "this label carries no article, so there is nothing for a reader "
                "that prints one to print. PLAN §4's column is the report's central "
                "defence and a blank in it is not a finding about the family"
            )
        if len(self.articles) > 1:
            raise ValueError(
                f"this label carries two articles — {', '.join(self.articles)} — and "
                "a reader that holds one would drop the rest. Widening that reader "
                "is #46; until then the two cannot be read as one"
            )
        return self.articles[0]


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
            articles=(Article.HUMAN_OVERSIGHT,),
        ),
        Family.WRONGFUL_COMMITMENT: FamilyLabel(
            agentic=("ASI03:2026",),
            llm=("LLM07:2026",),
            articles=(Article.ROBUSTNESS_AND_CYBERSECURITY,),
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
            articles=(Article.TRANSPARENCY,),
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

**The article column is one article per family today and the record holds a tuple**,
because #42 gives five of the nine two apiece and two of those need members `Article`
does not have. Both halves of that are #46's.

Every claim in either column costs a stated limit in `published.NOT_REACHED_WITHIN`,
and the two subtractions there are what makes an unclaimed entry print with a reason.
"""


ELECTIVE_LABELS: Mapping[ElectiveFamily, FamilyLabel] = covering(
    {
        ElectiveFamily.MEMORY_POISONING: FamilyLabel(
            agentic=("ASI06:2026",),
            articles=(Article.ROBUSTNESS_AND_CYBERSECURITY,),
        ),
        ElectiveFamily.DIRECT_PROMPT_INJECTION: FamilyLabel(
            llm=("LLM01:2026",),
            articles=(Article.ROBUSTNESS_AND_CYBERSECURITY,),
        ),
        ElectiveFamily.PII_LEAKAGE: FamilyLabel(llm=("LLM02:2026",)),
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

**`pii_leakage` carries no article, and that is a declared absence rather than an
oversight.** #42 gives it Article 10 — data and data governance — alone, and `Article`
has no member for it until #46. A wrong article here would be worse than a blank, and
the blank is refused by any reader that prints one (`FamilyLabel.article`).

The three are labels for families with no cases on disk. That is the tier's shape
rather than a gap in this table: a member exists so the cases have somewhere to arrive
([ADR-0035](../../docs/adr/0035-the-elective-family-tier-is-never-gate-deciding.md)),
and #48, #49 and #50 bring them.
"""


def label_for(family: Family) -> FamilyLabel:
    """The label one of the six carries.

    Keyed on `Family` and never on both enumerations, so there is no argument through
    which an elective family reaches a reader that is defined over the six — the
    coverage subtraction in `published.py` being the one that matters, because a claim
    is the only thing that shortens a printed untested list.

    There is no counterpart for `ELECTIVE_LABELS`, which nothing outside its own table
    reads yet. The type boundary is the key type of the table and not this function, so
    a second accessor with no caller would be ceremony rather than a constraint.
    """
    return LABELS[family]


def article_for(family: Family) -> Article:
    """The article this family's failure bears on, from PLAN §4.

    Read off the label rather than matched on the family, which is the consolidation:
    the article and the published identifiers are one record and cannot drift into
    disagreeing about which family they describe. The reader's own limit — one article
    where the record holds a tuple — is `FamilyLabel.article`.
    """
    return label_for(family).article
