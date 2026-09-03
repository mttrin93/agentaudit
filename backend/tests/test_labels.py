"""One record per family, and the two tables it is held in.

`labels.py` is a consolidation: the agentic identifier lived in a mapping in
`published.py` and the article in a match in `judge.py`, each holding half the answer
and each with the wrong cardinality for what #42 selected. What these tests hold is
the shape rather than the readings — which family claims which category is argued in
[ADR-0037](../../docs/adr/0037-a-claimed-category-is-claimed-in-part.md) and asserted
against the stored copies in `test_published.py`.

Nothing here checks a copy. `test_editions.py` does that.
"""

from collections.abc import Mapping

import pytest

from backend.bench import labels
from backend.bench.contract import AgentCapability
from backend.bench.editions import ORIGINATED_HERE
from backend.bench.labels import (
    ELECTIVE_LABELS,
    LABELS,
    Article,
    FamilyLabel,
    article_for,
    covering,
    label_for,
)
from backend.bench.library import ElectiveFamily, Family

# --- Nine families, one shape ------------------------------------------------


def test_every_family_and_every_elective_family_carries_a_label() -> None:
    # The guard that makes a family impossible to add silently. Before this record
    # existed a new family inherited two different defaults — no agentic claim, and a
    # `match` that failed to typecheck — and the label record has to be at least as
    # unforgiving as the half of it that was.
    assert set(LABELS) == set(Family)
    assert set(ELECTIVE_LABELS) == set(ElectiveFamily)


def test_a_family_with_no_label_is_refused_where_the_table_is_declared() -> None:
    # A dict cannot be checked for exhaustiveness by a type checker the way the
    # `match` in `judge.article_for` could, so totality is checked by the call that
    # wraps each table literal — which runs at module scope, so a family with no label
    # stops the module loading and takes every test and every run with it.
    # Annotated, because mypy narrows the key type of the comprehension to the five
    # literals that survive the guard and `Mapping` is invariant in its key.
    thinner: Mapping[Family, FamilyLabel] = {
        family: label
        for family, label in LABELS.items()
        if family is not Family.SCOPE_CREEP
    }
    with pytest.raises(KeyError, match="scope_creep"):
        covering(thinner, Family)

    with pytest.raises(KeyError, match="carries no label"):
        covering({}, ElectiveFamily)

    # And exact, not only total: the table is defined over one enumeration, and a
    # `# type: ignore` on one line is exactly how something that is not a family
    # arrives in it.
    intruder: Mapping[Family, FamilyLabel] = {
        **LABELS,
        ElectiveFamily.PII_LEAKAGE: FamilyLabel(),  # type: ignore[dict-item]
    }
    with pytest.raises(KeyError, match="is not a Family"):
        covering(intruder, Family)


def test_an_elective_label_is_the_same_record_and_never_in_the_other_table() -> None:
    # Same type and same shape: an elective family's label says the same kinds of
    # thing about it. The distinction is carried by the key type of the table, on the
    # terms ADR-0035 states for every other elective/mandatory pair, so there is no
    # argument anywhere through which one arrives where the other is read.
    assert all(isinstance(label, FamilyLabel) for label in ELECTIVE_LABELS.values())
    # Exact string equality between the two key sets and never containment: a
    # `StrEnum` member is a `str` and these names nest — `direct_prompt_injection` is
    # a substring of `indirect_prompt_injection`, so a containment check here would
    # answer a question nobody asked it.
    assert not {str(family) for family in LABELS} & {
        str(family) for family in ELECTIVE_LABELS
    }

    with pytest.raises(KeyError):
        label_for(ElectiveFamily.MEMORY_POISONING)  # type: ignore[arg-type]
    with pytest.raises(KeyError):
        ELECTIVE_LABELS[Family.DATA_LEAKAGE]  # type: ignore[index]


def test_nothing_that_is_not_a_family_carries_a_label() -> None:
    # The Agents Rule of Two is a property of what a target declares and #42's table
    # gives its row an Article. It gets no label: an article printed beside it would
    # put a legal duty next to a self-declaration in a document whose every other
    # article sits beside a verdict, and a mapping between the two enumerations in
    # either direction is the thing ADR-0038 §3 refuses.
    #
    # Over the value sets and never by containment, for the reason above.
    capabilities = {one.value for one in AgentCapability}

    assert not capabilities & {str(family) for family in LABELS}
    assert not capabilities & {str(family) for family in ELECTIVE_LABELS}

    # And over every table in the module rather than over the two named above, which
    # is the half that guards the *absence*: the two assertions above hold whether or
    # not somebody adds a third table beside them, and a third table keyed on
    # `AgentCapability` is the whole of what ADR-0038 §3 refuses.
    tables = [held for held in vars(labels).values() if isinstance(held, Mapping)]
    assert tables
    assert not [
        table
        for table in tables
        if any(isinstance(key, AgentCapability) for key in table)
    ]


# --- What an identifier on a label has to be ---------------------------------


def test_every_identifier_a_label_carries_names_its_edition() -> None:
    # The discipline ADR-0036 put on a case record's claim, arriving at the other
    # claim a report prints. An untagged `LLM06` means Excessive Agency under the
    # numbering #42's table was written in and Unbounded Consumption under the copy
    # stored today, and a label is the more dangerous of the two places to leave that
    # open because it is read per family rather than per case.
    for label in (*LABELS.values(), *ELECTIVE_LABELS.values()):
        for identifier in (*label.agentic, *label.llm):
            assert identifier.endswith(":2026")

    with pytest.raises(ValueError, match="names no edition"):
        FamilyLabel(agentic=("ASI01",), articles=(Article.TRANSPARENCY,))


def test_an_identifier_no_stored_copy_carries_is_refused_on_the_label() -> None:
    with pytest.raises(ValueError, match="none of the editions"):
        FamilyLabel(llm=("LLM11:2026",), articles=(Article.TRANSPARENCY,))


def test_a_family_that_claims_nothing_on_a_list_carries_an_empty_tuple() -> None:
    # And never `ORIGINATED_HERE`, which is a *case record's* declared no-claim form.
    # A family's label and a case's identifier are two different claims (ADR-0037),
    # and the constant that says *this payload claims no published entry* would read
    # on a label as though the family had been given one.
    assert LABELS[Family.DATA_LEAKAGE].agentic == ()
    assert LABELS[Family.HALT_DEFEAT].llm == ()
    assert LABELS[Family.DISCLOSURE_DENIAL].llm == ()

    with pytest.raises(ValueError, match="originated here"):
        FamilyLabel(agentic=(ORIGINATED_HERE,), articles=(Article.TRANSPARENCY,))


# --- The article, read off the record ----------------------------------------


def test_the_article_a_family_bears_is_read_off_its_label() -> None:
    # PLAN §4's central column, unchanged by the consolidation: the same six answers
    # `judge.article_for` gave from a match of its own.
    assert {family: article_for(family) for family in Family} == {
        Family.INDIRECT_PROMPT_INJECTION: Article.ROBUSTNESS_AND_CYBERSECURITY,
        Family.DATA_LEAKAGE: Article.ROBUSTNESS_AND_CYBERSECURITY,
        Family.WRONGFUL_COMMITMENT: Article.ROBUSTNESS_AND_CYBERSECURITY,
        Family.SCOPE_CREEP: Article.HUMAN_OVERSIGHT,
        Family.HALT_DEFEAT: Article.STOP_CONTROL,
        Family.DISCLOSURE_DENIAL: Article.TRANSPARENCY,
    }


def test_a_label_with_two_articles_has_no_single_article_to_be_read_as() -> None:
    # The cardinality the record already has and its reader does not. #42 gives five
    # families two articles each; the record holds a tuple today and `Narrative.article`
    # is one field, so the reader refuses rather than picking the first — which would
    # drop an article silently on the day the second one lands (#46).
    two = FamilyLabel(
        articles=(Article.HUMAN_OVERSIGHT, Article.ROBUSTNESS_AND_CYBERSECURITY)
    )
    with pytest.raises(ValueError, match="two articles"):
        _ = two.article

    with pytest.raises(ValueError, match="no article"):
        _ = FamilyLabel().article
