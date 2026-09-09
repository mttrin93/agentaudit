"""The one code path to the cross-model bar, and the walls that keep it the only one.

`backend/tests/test_multi_model.py` is where the bar's *behaviour* is driven — the
memory consulted before anything is sent, one route measured once per run, a run that
proposed nothing, an admission run that did not happen. Those tests were written
against `scripts/swap.py` and are unchanged by the move, which is the regression check
[ADR-0105](../../docs/adr/0105-deciding-a-pending-route-is-its-own-surface-and-not-a-gate-runs-second-job.md)
§5 asks for.

What is asserted here is the *structural* half, which no behaviour test can see: that
the bar lives in the backend with the swap as a caller rather than the owner, that it
reaches nothing under `scripts/`, and that nothing in it can name which bar applies.
Each of those is a claim about a name being absent, and an absent name is only guarded
by a test that looks for it.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from backend.bench.admitting import cross_model_bar
from backend.tests.conftest import imports_of, reachable_from

ADMITTING_SOURCE = Path(__file__).resolve().parents[1] / "bench" / "admitting.py"
SWAP_SOURCE = Path(__file__).resolve().parents[2] / "scripts" / "swap.py"


def test_the_swap_is_a_caller_of_the_bar_and_not_its_owner() -> None:
    """One code path to a reference agent, and `scripts/swap.py` is not where it is.

    A second surface decides pending routes against the same three agents, and a
    copy of this function would be a second code path to them — measured on an
    arithmetic that nothing would notice drifting from this one.
    """
    defined = {
        node.name
        for node in ast.walk(ast.parse(SWAP_SOURCE.read_text(encoding="utf-8")))
        if isinstance(node, ast.FunctionDef)
    }

    assert "cross_model_bar" not in defined, (
        "scripts/swap.py defines the cross-model bar again. The bar is one function "
        "both entry points call (ADR-0105 §5)"
    )
    assert "backend.bench.admitting.cross_model_bar" in set(imports_of(SWAP_SOURCE))


def test_the_bar_reaches_nothing_under_scripts() -> None:
    """The direction of the dependency, asserted as reachability and not as a line.

    A command-line script may call into the bench; the bench may not call back out.
    Transitive, because a module that imports a module that imports `scripts` has
    reached it — and the second surface for this function is an API route, which
    cannot depend on a terminal's entry point.
    """
    reached = sorted(
        name for name in reachable_from(ADMITTING_SOURCE) if name.startswith("scripts")
    )

    assert not reached, (
        f"{reached} is reachable from the cross-model bar. The bar is in the backend "
        "so that a surface which is not a terminal can call it"
    )


def test_nothing_in_the_bar_can_name_which_bar_applies() -> None:
    """`promote` decides it off the proposal's own `discovered_by`, and only there.

    Two ends. This module names neither the enum nor the function that chooses a bar,
    so a caller cannot be handed one by a line inside it; and the signature has no
    parameter a caller could pass one through, so it cannot be handed one from
    outside either. The second is the one that survives a refactor.
    """
    named = sorted(
        name
        for name in imports_of(ADMITTING_SOURCE)
        if "AdmissionBar" in name or "bar_for" in name or "MODELS_REQUIRED" in name
    )
    assert not named, (
        f"{named} is named in the cross-model bar. Which bar applies is decided "
        "nowhere but `promote`, off the proposal's own `discovered_by` (ADR-0012)"
    )

    parameters = inspect.signature(cross_model_bar).parameters
    assert "bar" not in parameters
    assert not [
        name for name, parameter in parameters.items() if "Bar" in str(parameter)
    ]
