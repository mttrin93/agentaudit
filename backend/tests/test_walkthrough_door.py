"""What the browser walkthrough's harness serves: a bench with no door, or a doored one.

`frontend/e2e/harness.py` is test equipment and it is also the one caller in this
repository that passes `NO_DOOR` (ADR-0121). That makes the question *when* it passes
it a thing worth an assertion of its own: the walkthrough has two paths now — the
issuerless one every clone and every CI run takes, and a doored one an operator opts
into by exporting an issuer's key and a test user — and the difference between them is
one reading of the environment.

**Asserted here rather than in Playwright, because Playwright cannot see it.** The
suite that would cover the doored path is the one that needs an account to run; what
this file covers is the decision taken before either suite starts, which is answerable
with a dict and no servers at all.

The module is loaded by path because `frontend/e2e/` is not a package and is on no
import path: it is a script Playwright runs, and importing it here must not require it
to become anything else.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

HARNESS = Path(__file__).resolve().parents[2] / "frontend" / "e2e" / "harness.py"


@pytest.fixture(scope="module")
def harness() -> ModuleType:
    """The walkthrough's harness, loaded from the path Playwright runs it from."""
    spec = importlib.util.spec_from_file_location("walkthrough_harness", HARNESS)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_walkthrough_declaring_no_issuer_serves_a_bench_with_no_door(
    harness: ModuleType,
) -> None:
    """The path every clone and every CI run takes: nothing exported, no door."""
    assert harness.declared_door({}) is None


def test_a_blank_key_is_no_issuer_and_not_an_empty_one(harness: ModuleType) -> None:
    """Blank is unset, as it is in `identity.declared_issuer` and for its reason: a
    variable cleared by whatever set it has declared nothing."""
    assert harness.declared_door({harness.DOOR_JWT_KEY_VARIABLE: "   "}) is None


def test_an_exported_issuer_key_puts_the_door_up(harness: ModuleType) -> None:
    """The doored path: the operator exported the issuer's public key, so the harness
    serves the deployed reading of the factory and the bench checks every request."""
    door = harness.declared_door({harness.DOOR_JWT_KEY_VARIABLE: "-----BEGIN PEM-----"})
    assert door == {"AGENTAUDIT_ISSUER_JWT_KEY": "-----BEGIN PEM-----"}


def test_the_secret_key_rides_along_when_it_is_exported(harness: ModuleType) -> None:
    """A machine credential is checked at the issuer and needs the secret key beside
    the PEM (ADR-0124), so a walkthrough that means to exercise one may export both."""
    door = harness.declared_door(
        {
            harness.DOOR_JWT_KEY_VARIABLE: "-----BEGIN PEM-----",
            harness.DOOR_SECRET_KEY_VARIABLE: "sk_test_nothing",
        }
    )
    assert door == {
        "AGENTAUDIT_ISSUER_JWT_KEY": "-----BEGIN PEM-----",
        "AGENTAUDIT_ISSUER_SECRET_KEY": "sk_test_nothing",
    }


def test_a_secret_key_alone_is_not_a_door_this_harness_will_serve(
    harness: ModuleType,
) -> None:
    """Offline verification is the point of the PEM (ADR-0116 §4). A walkthrough given
    only the secret key would run against a bench that called the issuer on every poll,
    which is a different bench from the deployed one — so it is refused rather than
    served as though it were the doored path."""
    assert (
        harness.declared_door({harness.DOOR_SECRET_KEY_VARIABLE: "sk_test_nothing"})
        is None
    )
