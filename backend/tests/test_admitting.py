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

    Every way the name could be bound again, and not only `def`: a coroutine and a
    module-level alias are both a second path under the old name, and a wall that one
    of the three ways through it walks past is not a wall.
    """
    tree = ast.parse(SWAP_SOURCE.read_text(encoding="utf-8"))
    bound = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
    } | {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }

    assert "cross_model_bar" not in bound, (
        "scripts/swap.py defines the cross-model bar again. The bar is one function "
        "both entry points call (ADR-0105 §5)"
    )
    assert "backend.bench.admitting.cross_model_bar" in set(imports_of(SWAP_SOURCE)), (
        "scripts/swap.py does not import the bar from the backend, so whatever it is "
        "calling is not the function the other surface calls"
    )


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
    assert "bar" not in parameters, (
        "the cross-model bar takes a `bar` argument. Which bar applies is a property "
        "of the proposal, so a caller that could pass one could pass the wrong one"
    )
    named_in_a_signature = [
        name for name, parameter in parameters.items() if "Bar" in str(parameter)
    ]
    assert not named_in_a_signature, (
        f"{named_in_a_signature} could carry a bar into the function. `promote` reads "
        "it off `discovered_by`, and this signature is the other end of that claim"
    )


def test_the_memory_is_written_by_selection_and_never_by_a_caught_refusal() -> None:
    """ADR-0031 point 3: the choice is made before the call, not by the exception.

    `DecidedRoutes.remember` refuses a decision that says nothing about its route,
    and a path that reached the store and caught `NotAboutTheRoute` would look
    identical from the outside — the same records written, the same records not.
    It is not identical: the store's refusal is a wall, and a caller that used it
    as a branch would have no way to say *why* it chose not to remember, and would
    swallow a genuine store failure with it. So `worth_remembering` selects, and
    this asserts the shape rather than the outcome, because the outcome cannot tell
    the two apart.
    """
    tree = ast.parse(ADMITTING_SOURCE.read_text(encoding="utf-8"))
    guarded: list[ast.If] = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.If) and "worth_remembering" in ast.unparse(node.test)
    ]
    assert len(guarded) == 1, (
        "the write into the admission memory is not selected by "
        "`worth_remembering`. A decision that says nothing about a route is not "
        "remembered, and the selection is what says so (ADR-0031 point 3)"
    )
    remembering = [
        node
        for node in ast.walk(guarded[0])
        if isinstance(node, ast.Call) and ast.unparse(node.func).endswith(".remember")
    ]
    assert len(remembering) == 1, "the guarded branch does not remember anything"

    caught = [
        ast.unparse(handler)
        for node in ast.walk(tree)
        if isinstance(node, ast.Try)
        for handler in node.handlers
        if any(
            isinstance(inner, ast.Call)
            and ast.unparse(inner.func).endswith(".remember")
            for inner in ast.walk(node)
        )
    ]
    assert not caught, (
        f"{caught} wraps the write into the admission memory. The store's refusal is "
        "a wall and not a branch: a caller that used it as one would have no way to "
        "say why it chose not to remember, and would swallow a genuine store failure "
        "with it"
    )
    assert "NotAboutTheRoute" not in set(imports_of(ADMITTING_SOURCE)), (
        "the bar names the store's refusal. It has no reason to: the selection is "
        "made before the call and the refusal is never reached (ADR-0031 point 3)"
    )
