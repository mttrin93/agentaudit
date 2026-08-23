"""The bench's own model call, and the wait it is allowed.

No model is called here. What is asserted is the one thing about this client that
cannot be seen from a reply: how long a run will sit still for an answer that is
not coming. The SDK's default is ten minutes, and a suite holding at the attempt it
was scoring for ten minutes is a run nobody is told has stalled.
"""

from collections.abc import Iterator

import pytest

from backend.bench import completion
from backend.bench.completion import MODEL_TIMEOUT_SECONDS


@pytest.fixture(autouse=True)
def _no_client_kept() -> Iterator[None]:
    """The client is cached for the process, so a test that builds one clears it.

    Before and after: a client built here under a stand-in key must not be handed to
    anything else, and one built earlier must not be what this test measures.
    """
    completion._client.cache_clear()
    yield
    completion._client.cache_clear()


def test_a_call_to_an_instrument_waits_the_declared_time_and_no_longer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "not-a-key")

    client = completion._client()

    # Read off the built client rather than off the constant, because the constant
    # being right is not the thing that was wrong: the default was in force because
    # nothing passed it.
    assert client.timeout == MODEL_TIMEOUT_SECONDS
