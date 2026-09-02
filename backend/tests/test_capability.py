"""The declared capability table: what each model accepts, and what unknown means.

No model is reached here and none has to be. The whole point of #4 is that the
question *does this model take a temperature* is answered from a declared table
before a request is composed, rather than by composing one and reading the
provider's error — which costs a call, and arrives after the operator has attested
and confirmed a spend.

Two things are asserted that a passing bench cannot otherwise show: that the answer
for a model with no line is a *stated* presumption rather than a silent one, and
that resolving a declared default never turns into a dropped parameter.
"""

from backend.bench.capability import (
    CAPABILITIES,
    accepts_temperature,
    capabilities_of,
    temperature_for,
)

A_BASELINE = "openrouter:openai/gpt-4.1-mini"
"""The model every earlier reading in this repository was taken with."""

A_REASONING_MODEL = "openrouter:openai/gpt-5-mini"
"""On the console's own list of attackers, and the case in hand: it accepts the
provider's default temperature and errors on an explicit one."""


def test_a_reasoning_model_accepts_no_temperature_and_the_answer_is_declared() -> None:
    """The fault #4 was filed for, read off the table instead of off a failed call.

    `declared` is asserted beside it because the two answers are not the same fact:
    a line in the table is knowledge, and the presumption below it is an absence of
    knowledge that happens to compose the same request.
    """
    reading = capabilities_of(A_REASONING_MODEL)

    assert reading.accepts_temperature is False
    assert reading.declared is True


def test_the_exception_is_matched_before_the_family_it_is_an_exception_to() -> None:
    """`gpt-5-chat` is the non-reasoning member of the line and takes a temperature.

    Ordered rather than a mapping for exactly this: a plain prefix match on
    `openai/gpt-5` would withhold a parameter this model accepts, and a withheld
    parameter is a provenance block stating a capability nobody checked.
    """
    assert accepts_temperature("openrouter:openai/gpt-5-chat") is True
    assert accepts_temperature("openrouter:openai/gpt-5") is False


def test_a_model_with_no_line_is_presumed_to_take_the_standard_set_and_says_so() -> (
    None
):
    """Unknown is a presumption that states itself, not a denylist's silence.

    The direction is deliberate and the module says why: sending a parameter a model
    refuses is the provider's loud error before any figure exists, and withholding
    one a model accepts is a false sentence inside a signed document (ADR-0004).
    """
    reading = capabilities_of("openrouter:a/model-nobody-added-a-line-for")

    assert reading.accepts_temperature is True
    assert reading.declared is False
    assert "presumed" in reading.stated()


def test_a_declared_default_is_resolved_against_the_table_and_not_sent_regardless() -> (
    None
):
    """A default meets a model that will not take it and becomes a stated absence.

    `None` back, which the caller records — the resolution is the seam that lets a
    deployment's own `DEFAULT_ATTACKER_TEMPERATURE` coexist with a GPT-5 attacker
    without either the boot failing or the record lying about what was sent.
    """
    assert temperature_for(A_BASELINE, 0.0) == 0.0
    assert temperature_for(A_REASONING_MODEL, 0.0) is None
    # Nothing declared stays nothing declared, whichever model it is: resolving is
    # not a place a temperature can be invented.
    assert temperature_for(A_BASELINE, None) is None
    assert temperature_for(A_REASONING_MODEL, None) is None


def test_a_configuration_string_and_a_bare_model_name_are_one_answer() -> None:
    """Both are held in this project, and two answers about one model is the bug.

    `completion` has parsed the provider off by the time it composes a request;
    `app` holds the whole string a provenance block will print. One function for
    both, so a table consulted from two places cannot disagree with itself.
    """
    assert capabilities_of("openai/gpt-5-mini") == capabilities_of(A_REASONING_MODEL)
    assert capabilities_of("openai/gpt-4.1-mini") == capabilities_of(A_BASELINE)


def test_every_row_is_matched_against_the_name_and_not_the_provider() -> None:
    """A row that carried a provider prefix would never match anything.

    Structural rather than example-based, because the failure is silent: a table
    whose keys did not match would read as a bench where every model accepts
    everything, which is exactly the arrangement #4 replaced.
    """
    for prefix, _ in CAPABILITIES:
        assert ":" not in prefix
        assert capabilities_of(f"openrouter:{prefix}") == capabilities_of(prefix)
