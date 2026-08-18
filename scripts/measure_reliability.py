"""Measures the adjudicator against the gold set. One entry point, no web layer.

    uv run python -m scripts.measure_reliability
    uv run python -m scripts.measure_reliability --family disclosure_denial
    uv run python -m scripts.measure_reliability \\
        --adjudicator-model openrouter:openai/gpt-4o-mini

Thirty hand-labelled replies — fifteen per judged family — are put to the
adjudicating model as the briefs a run would build, DeepEval scores each verdict
against its label, and Cohen's κ is computed per family from those per-case results
(ADR-0009). What prints is the figure ADR-0004 requires beside every judged rate,
and the automatic consequence: **κ below 0.6 means the family is not fit to
report.**

**No target is attacked and nothing is registered.** This run reaches the bench's
own model and no endpoint of anyone's, so there is no attestation and no approval
interrupt — the two exist because an attack damages what it measures (ADR-0007), and
nothing here attacks anything. What it does spend is inference on the operator's own
key, so the call count and the model are printed before the first call.

The figure is about the *instrument*, not about any target: it says how far the
thing that decides a judged verdict agrees with the person who labelled the gold
set, and it says nothing about how often any agent fails. It is recorded in
`docs/validation.md` beside the run that produced it, because a κ whose model nobody
wrote down is not a reliability figure about anything.
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv

from backend.bench.completion import DEFAULT_ADJUDICATOR_MODEL, completion_for
from backend.bench.goldset import (
    GoldSet,
    load_gold_sets,
    reliability_from,
    run_gold_set,
)
from backend.bench.library import Family, load_library
from backend.bench.rule import DECLARED_RULE
from scripts.console import EXIT_WITHHELD

CASES_DIR = Path(__file__).resolve().parents[1] / "backend" / "cases"
GOLDSET_DIR = Path(__file__).resolve().parents[1] / "backend" / "goldset"

EXIT_UNFIT = 5
"""Exit code when a judged family came out below the κ floor.

Non-zero, because the outcome is that a family cannot be reported — the same
discipline as a failing gate stopping the build (#13). It is not an error: the
measurement worked and the answer was no.
"""


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--adjudicator-model",
        default=DEFAULT_ADJUDICATOR_MODEL,
        help=(
            "the model whose reliability is being measured, as "
            "'<provider>:<model>'. The instrument, never a reference agent's model"
        ),
    )
    parser.add_argument(
        "--family",
        nargs="+",
        default=None,
        help="which judged families to measure. Both, by default",
    )
    args = parser.parse_args(argv)

    library = load_library(CASES_DIR)
    try:
        sets = _requested(load_gold_sets(GOLDSET_DIR, library), args.family)
    except ValueError as unknown:
        print(f"Not a judged family with a gold set: {unknown}")
        return EXIT_WITHHELD

    calls = sum(len(gold.transcripts) for gold in sets)
    print(
        f"Measuring {args.adjudicator_model} against "
        f"{len(sets)} gold set(s), {calls} labelled transcripts, "
        f"{calls} model calls on your key."
    )
    print(
        f"The declared floor is κ = {DECLARED_RULE.kappa_floor:.2f}; a family below "
        "it is not fit to report (ADR-0004).\n"
    )

    try:
        complete = completion_for(args.adjudicator_model)
    except (KeyError, ValueError) as unusable:
        print(f"No usable adjudicating model: {unusable}")
        return EXIT_WITHHELD

    unfit: list[Family] = []
    for gold in sets:
        reliability = reliability_from(gold.family, run_gold_set(gold, complete))
        print(f"{gold.family}: {reliability.stated()}")
        print(f"  labelled by {gold.labelled_by} on {gold.labelled_on}")
        if not reliability.fit_to_report:
            unfit.append(gold.family)

    if unfit:
        print(
            f"\n{sorted(str(family) for family in unfit)} cannot be reported. Record "
            "the figure and the model in docs/validation.md; the rate stays "
            "unpublished until the instrument or the criterion changes."
        )
        return EXIT_UNFIT

    print(
        "\nEvery family measured reaches the floor. Record the figures and the "
        "model in docs/validation.md — a κ whose model nobody wrote down is not a "
        "reliability figure about anything."
    )
    return 0


def _requested(
    sets: Sequence[GoldSet], families: Sequence[str] | None
) -> tuple[GoldSet, ...]:
    """The gold sets named, or all of them.

    Named by family rather than by file, so a set moved between files is still asked
    for by the thing its figure is about.
    """
    if families is None:
        return tuple(sets)
    wanted = {Family(name) for name in families}
    found = tuple(gold for gold in sets if gold.family in wanted)
    missing = wanted - {gold.family for gold in found}
    if missing:
        raise ValueError(sorted(str(family) for family in missing))
    return found


if __name__ == "__main__":
    sys.exit(main())
