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
from backend.bench.editions import ORIGINATED_HERE, resolves
from backend.bench.labels import (
    ELECTIVE_LABELS,
    LABELS,
    Article,
    FamilyLabel,
    article_for,
    articles_stated,
    bears_stated,
    claims_stated,
    covering,
    elective_label_for,
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
        ElectiveFamily.PII_LEAKAGE: FamilyLabel(  # type: ignore[dict-item]
            articles=(Article.DATA_GOVERNANCE,)
        ),
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


def test_every_article_is_one_a_family_bears_or_the_one_that_applies_to_all() -> None:
    # The roster, checked from both ends at once. #46 adds 10 and 13 because #42's
    # selection names them, and an `Article` member no label carries is a duty this
    # project has written into a closed enumeration and claims about nobody — the
    # Rule of Two's Article 14 being the row that would arrive that way (ADR-0038's
    # *not decided here*, and ADR-0039 §10 from the other end).
    assert Article.DATA_GOVERNANCE.value == "10"
    assert Article.TRANSPARENCY_TO_DEPLOYERS.value == "13"

    borne = {
        article
        for label in (*LABELS.values(), *ELECTIVE_LABELS.values())
        for article in label.articles
    }
    # Article 12 is the one exception and it is stated rather than skipped: PLAN §4
    # says it applies to every row, so it sits on no family's tuple and on
    # `Disagreement` instead.
    assert borne | {Article.RECORD_KEEPING} == set(Article)
    assert Article.RECORD_KEEPING not in borne


def test_the_articles_a_family_bears_are_read_off_its_label() -> None:
    # PLAN §4's central column with #42's second articles added to it, and a tuple
    # per family rather than one article: four of the nine bear two, so the answer a
    # reader gets is *the articles* and never *the article*.
    assert {family: article_for(family) for family in Family} == {
        Family.INDIRECT_PROMPT_INJECTION: (Article.ROBUSTNESS_AND_CYBERSECURITY,),
        Family.DATA_LEAKAGE: (Article.ROBUSTNESS_AND_CYBERSECURITY,),
        Family.WRONGFUL_COMMITMENT: (
            Article.ROBUSTNESS_AND_CYBERSECURITY,
            Article.HUMAN_OVERSIGHT,
        ),
        Family.SCOPE_CREEP: (
            Article.HUMAN_OVERSIGHT,
            Article.ROBUSTNESS_AND_CYBERSECURITY,
        ),
        Family.HALT_DEFEAT: (Article.STOP_CONTROL,),
        Family.DISCLOSURE_DENIAL: (
            Article.TRANSPARENCY,
            Article.TRANSPARENCY_TO_DEPLOYERS,
        ),
    }

    # The elective tier is the other half of #42's selection and `pii_leakage` is the
    # row #45 had to leave blank: 10 is the article it bears alone, and `Article` had
    # no member for it until this change.
    assert ELECTIVE_LABELS[ElectiveFamily.MEMORY_POISONING].articles == (
        Article.ROBUSTNESS_AND_CYBERSECURITY,
        Article.DATA_GOVERNANCE,
    )
    assert ELECTIVE_LABELS[ElectiveFamily.DIRECT_PROMPT_INJECTION].articles == (
        Article.ROBUSTNESS_AND_CYBERSECURITY,
    )
    assert ELECTIVE_LABELS[ElectiveFamily.PII_LEAKAGE].articles == (
        Article.DATA_GOVERNANCE,
    )


def test_the_order_inside_the_tuple_is_declared_and_could_not_be_derived() -> None:
    # Order is the primary claim first — PLAN §4's column, written before any code —
    # and #42's second article after it, so a reader with room for one prints what
    # the family's failure principally bears on rather than whichever member sorted
    # lower. Asserted by a pair no derivation could produce rather than by restating
    # the literals above: scope creep and wrongful commitment bear the *same two*
    # articles in *opposite* orders, so nothing that sorts a set, or reads the order
    # off `Article`'s own member order, can give both these answers.
    creep = LABELS[Family.SCOPE_CREEP].articles
    commitment = LABELS[Family.WRONGFUL_COMMITMENT].articles
    assert set(creep) == set(commitment)
    assert creep != commitment
    assert creep[0] is Article.HUMAN_OVERSIGHT
    assert commitment[0] is Article.ROBUSTNESS_AND_CYBERSECURITY

    # And descending, on the one family where the primary article has the higher
    # number: 50 is the duty disclosure denial defeats and 13 is the one it defeats
    # second, so a tuple sorted either way would be wrong here.
    assert LABELS[Family.DISCLOSURE_DENIAL].articles == (
        Article.TRANSPARENCY,
        Article.TRANSPARENCY_TO_DEPLOYERS,
    )


def test_a_label_that_bears_no_article_is_refused_where_it_is_written() -> None:
    # The refusal `FamilyLabel.article` used to make on the way out, moved to the way
    # in. #45 left `pii_leakage` blank because `Article` had no member for 10 and a
    # wrong article is worse than a blank; 10 exists now, the last blank is filled,
    # and a blank column is refused rather than guarded against per reader. Empty
    # stays a real answer on the two identifier tuples and is not one here: a family
    # claims nothing on a published list often, and bears no legal duty never.
    with pytest.raises(ValueError, match="bears no article"):
        FamilyLabel(llm=("LLM02:2026",))

    with pytest.raises(ValueError, match="bears no article"):
        FamilyLabel()

    # And every label in the tree carries one, which is the same refusal read as a
    # roster rather than as a raise.
    for label in (*LABELS.values(), *ELECTIVE_LABELS.values()):
        assert label.articles


# --- What a reader prints --------------------------------------------------


def test_the_articles_render_as_one_sentence_that_is_true_of_one_and_of_two() -> None:
    # The sentence every reader of a label prints, in one place so the console, the
    # report and #52's screen cannot word it three ways. *article 15* was true before
    # #46 and stays true; *articles 50 and 13* is what replaces it where a family
    # bears two, and neither says *the* article of a family that has more than one.
    assert articles_stated((Article.ROBUSTNESS_AND_CYBERSECURITY,)) == "article 15"
    assert (
        articles_stated((Article.TRANSPARENCY, Article.TRANSPARENCY_TO_DEPLOYERS))
        == "articles 50 and 13"
    )
    # No family bears three today and the rendering is written for the tuple rather
    # than for its current length, because #42's selection is not the last one.
    assert (
        articles_stated(
            (
                Article.HUMAN_OVERSIGHT,
                Article.ROBUSTNESS_AND_CYBERSECURITY,
                Article.DATA_GOVERNANCE,
            )
        )
        == "articles 14, 15 and 10"
    )

    # Every label in the tree renders, so no family is a blank in the column.
    for label in (*LABELS.values(), *ELECTIVE_LABELS.values()):
        assert articles_stated(label.articles)

    with pytest.raises(ValueError, match="bears no article"):
        articles_stated(())


def test_the_rendering_follows_the_declared_order_and_not_the_number() -> None:
    # What makes the printed line stable, which is what a golden digest is measured
    # against: the same two articles borne by two families print in two different
    # orders, so the rendering reads the tuple and sorts nothing.
    assert articles_stated(LABELS[Family.SCOPE_CREEP].articles) == "articles 14 and 15"
    assert (
        articles_stated(LABELS[Family.WRONGFUL_COMMITMENT].articles)
        == "articles 15 and 14"
    )


def test_the_published_entries_render_as_one_sentence_naming_both_lists() -> None:
    # The other half of a label, and the half a report had no sentence for. Both
    # lists are named in every answer, because *claims nothing here* and *this list
    # was not consulted* are two readings and a line that dropped the empty side
    # would leave a reader unable to tell them apart (ADR-0002, ADR-0039).
    assert claims_stated(LABELS[Family.INDIRECT_PROMPT_INJECTION]) == (
        "claims ASI01:2026 Agent Goal Hijack on the OWASP agentic list and "
        "LLM01:2026 Prompt Injection on the OWASP GenAI LLM list"
    )

    # An empty tuple is an answer rather than a blank, on either side.
    assert claims_stated(LABELS[Family.HALT_DEFEAT]) == (
        "claims ASI10:2026 Rogue Agents on the OWASP agentic list and nothing on "
        "the OWASP GenAI LLM list"
    )
    assert claims_stated(LABELS[Family.DATA_LEAKAGE]) == (
        "claims nothing on the OWASP agentic list and LLM02:2026 Sensitive "
        "Information Disclosure and LLM08:2026 Hidden Context Exposure on the "
        "OWASP GenAI LLM list"
    )

    # No family claims nothing on both lists today and the sentence is written for
    # the record rather than for the table: `FamilyLabel` permits it, so a reader
    # that printed *nothing and nothing* would be the shape this answers instead.
    assert (
        claims_stated(FamilyLabel(articles=(Article.RECORD_KEEPING,)))
        == "claims nothing on either published list"
    )


def test_every_claimed_entry_prints_with_the_title_its_stored_copy_carries() -> None:
    """The published wording, transcribed, rather than this repository's paraphrase.

    A number alone leaves a reader with something to look up, and a paraphrase hides
    a stale copy as a wording choice where a transcription shows it as a mismatch
    against the source
    ([ADR-0036](../../docs/adr/0036-a-published-identifier-resolves-to-a-stored-copy.md),
    ADR-0002). Read off `editions.resolves` at print time, so the title in a report is
    the title in the copy this repository committed and cannot drift from it.
    """
    for label in (*LABELS.values(), *ELECTIVE_LABELS.values()):
        printed = claims_stated(label)
        assert printed.startswith("claims ")
        for identifier in (*label.agentic, *label.llm):
            stored = resolves(identifier)
            assert stored is not None
            # The pair and not the two halves separately: an identifier printed
            # anywhere and a title printed anywhere would pass a containment check
            # over a sentence that had paired them wrongly.
            assert f"{identifier} {stored.title}" in printed
        # And nothing else claimed: exactly one entry named per claim, so a sentence
        # that had picked up a neighbouring entry's title would be caught.
        assert printed.count(":2026") == len(label.agentic) + len(label.llm)


def test_the_article_half_prints_as_a_whole_sentence_naming_the_act() -> None:
    # One rendering and not a fragment each reader appends the Act's name to: the
    # report prints this in three places and the screen in three more, and *of the
    # EU AI Act* written out six times is six chances to say something else
    # (ADR-0040 decision 7).
    assert (
        bears_stated((Article.ROBUSTNESS_AND_CYBERSECURITY,))
        == "bears article 15 of the EU AI Act"
    )
    assert (
        bears_stated(LABELS[Family.DISCLOSURE_DENIAL].articles)
        == "bears articles 50 and 13 of the EU AI Act"
    )
    # Built over `articles_stated`, so the declared order survives into it and the
    # two families bearing the same pair still read differently.
    assert bears_stated(LABELS[Family.SCOPE_CREEP].articles) != bears_stated(
        LABELS[Family.WRONGFUL_COMMITMENT].articles
    )

    with pytest.raises(ValueError, match="bears no article"):
        bears_stated(())


def test_an_elective_family_has_an_accessor_of_its_own_and_the_two_do_not_cross() -> (
    None
):
    # The bench page prints nine rows of labels since the console stopped drawing the
    # tier in a section of its own, so `ELECTIVE_LABELS` has a reader outside its own
    # table for the first time and `label_for`'s docstring no longer holds.
    #
    # A second accessor rather than one widened to `AnyFamily`: the key type of each
    # table is the boundary (ADR-0035), and a single function over both would be the
    # one argument through which an elective family reaches a caller written for the
    # six — `published.py`'s coverage subtraction being the one that matters.
    assert elective_label_for(ElectiveFamily.MEMORY_POISONING).agentic == (
        "ASI06:2026",
    )
    assert elective_label_for(ElectiveFamily.PII_LEAKAGE).llm == ("LLM02:2026",)
    assert elective_label_for(ElectiveFamily.DIRECT_PROMPT_INJECTION).articles == (
        Article.ROBUSTNESS_AND_CYBERSECURITY,
    )

    # Neither accessor answers the other's enumeration, which is the property the two
    # tables' key types carry and this asserts of the functions over them.
    with pytest.raises(KeyError):
        elective_label_for(Family.DATA_LEAKAGE)  # type: ignore[arg-type]
    with pytest.raises(KeyError):
        label_for(ElectiveFamily.PII_LEAKAGE)  # type: ignore[arg-type]
