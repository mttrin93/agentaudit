"""The four declared model settings, and whether their committed defaults agree.

No model is reached here and no run is made. What is asserted is that the four
settings `.env.example` documents and the constants the entry points fall back to
are the same four strings — because they are written down in five files and a
reader who sets none of them gets the constants rather than the documentation.

The settings are separate on purpose and that argument is elsewhere — the four
constants' own docstrings in `backend/bench/completion.py` and
`backend/targets/reference/model.py`, and the commentary in `.env.example` above each
one. Which model the reference agents run on is
[ADR-0083](../../docs/adr/0083-the-reference-model-must-resolve-its-own-middle.md).
What is local here is the drift: four entry points once held four copies of one
literal, so moving the reference model was four edits, and any three of them was a
bench measuring two models in one run and printing one of them.
"""

import re
from pathlib import Path

from backend.bench.completion import (
    ADJUDICATOR_MODEL_ENV,
    ATTACKER_MODEL_ENV,
    DEFAULT_ADJUDICATOR_MODEL,
    DEFAULT_ATTACKER_MODEL,
    REFERENCE_MODEL_ENV,
    SECOND_REFERENCE_MODEL_ENV,
)
from backend.targets.reference.model import DEFAULT_REFERENCE_MODEL

ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"


def declared_in_example(variable: str) -> str:
    """What `.env.example` sets that variable to, as the file's own text says it.

    A regular expression over the committed bytes rather than `load_dotenv` into the
    process environment: this file is documentation that happens to be parseable, and
    a test that imported it into `os.environ` would leave the rest of the suite
    running under whatever it declared.
    """
    found = re.search(
        rf"^{re.escape(variable)}=(.*)$",
        ENV_EXAMPLE.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert found is not None, (
        f"{ENV_EXAMPLE.name} does not name {variable}, so a setting the bench reads "
        "is undiscoverable to the reader the file exists for."
    )
    return found.group(1).strip()


def test_the_reference_agents_default_to_what_the_example_environment_says() -> None:
    # The two ends of one decision: the constant is what an unset environment gets,
    # and the line in `.env.example` is what a reader copying the file gets. A
    # disagreement is a bench whose documented model and measured model differ, and a
    # rate is not readable without knowing which instrument produced it.
    assert declared_in_example(REFERENCE_MODEL_ENV) == DEFAULT_REFERENCE_MODEL, (
        f"{ENV_EXAMPLE.name} declares "
        f"{REFERENCE_MODEL_ENV}={declared_in_example(REFERENCE_MODEL_ENV)} and the "
        f"reference agents fall back to {DEFAULT_REFERENCE_MODEL}. One of the two "
        "moved without the other."
    )


def test_the_two_instrument_models_default_to_what_the_example_says() -> None:
    # The same drift, on the two settings that decide nothing about the target: the
    # adjudicator's default carries its own κ readings (ADR-0004) and the attacker's
    # is a third setting rather than a reading of either other (ADR-0011). Both are
    # documented in the same file, so both can drift from it.
    assert declared_in_example(ADJUDICATOR_MODEL_ENV) == DEFAULT_ADJUDICATOR_MODEL
    assert declared_in_example(ATTACKER_MODEL_ENV) == DEFAULT_ATTACKER_MODEL


def test_every_entry_point_falls_back_to_the_one_reference_model_constant() -> None:
    # Five commands send the reference agents at a model and four of them used to name
    # it themselves. The failure that shape allows is silent and expensive: three of
    # the four edited leaves one command admitting cases on the model the others
    # stopped measuring on, and a family's pooled rate then spans two instruments —
    # the averaging ADR-0055 keys its breakdown to avoid, arriving through
    # configuration rather than through arithmetic.
    from scripts import admit, attack, calibrate, gate, swap

    # `swap.py` re-exports `gate.DEFAULT_MODEL` rather than holding its own, so it is
    # here to hold that re-export in place: it is the fifth command that resolves
    # `AGENTAUDIT_REFERENCE_MODEL`, and the one whose whole subject is two models.
    for entry in (gate, admit, calibrate, attack, swap):
        assert entry.DEFAULT_MODEL == DEFAULT_REFERENCE_MODEL, (
            f"scripts/{entry.__name__.split('.')[-1]}.py defaults the reference "
            f"agents to {entry.DEFAULT_MODEL}, and the declared default is "
            f"{DEFAULT_REFERENCE_MODEL}."
        )


def test_the_swap_re_runs_on_a_model_the_reference_agents_are_not_on() -> None:
    # `scripts/swap.py` answers #15 by re-running one library with one setting
    # changed, so its second model has to differ from the first — two runs of one
    # model measure run-to-run variation and the script refuses that pairing at
    # runtime. What this asserts is the pairing nobody chose: the committed defaults,
    # which is what an operator who declares neither variable gets. Moving the
    # reference model onto the second model's string would have made the supported
    # zero-configuration swap a refusal.
    from scripts import swap

    assert swap.DEFAULT_SECOND_MODEL != DEFAULT_REFERENCE_MODEL, (
        "the committed defaults put both halves of the swap on "
        f"{DEFAULT_REFERENCE_MODEL}, so `uv run python -m scripts.swap` with nothing "
        "declared is refused rather than run."
    )
    # The variable is declared beside the other model names now that a second
    # surface reads it (`/pending-routes`, ADR-0105); what stays with the script is
    # the default it falls back to, which is what this pairs against the file.
    assert declared_in_example(SECOND_REFERENCE_MODEL_ENV) == swap.DEFAULT_SECOND_MODEL
