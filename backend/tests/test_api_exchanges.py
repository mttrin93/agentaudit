"""What `GET /runs/{run_id}/attempts` serves, and the two absences it does not fake.

The exchanges behind the attacks that worked on one operator's own endpoint, out of
the process that made them. The scored layer's counterpart to `test_api_episodes.py`,
and the assertions divide the same way: what is served is grouped by family because a
rate is denominated per family, and what is **not** served is a count of anything —
the numerator of a rate whose denominator is on the report would be a figure with
nothing under it.

The target is the obedient reference agent, so attempts succeed without a scripted
attacker: what a real payload would say is not under test here, and a leak that
happens on the first attempt is what lets an exchange be asserted at all.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from typing import Any, cast

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.runs import BenchConfig, BenchRuns, RunRecord, RunStatus
from backend.bench.adaptive.budget import AdaptiveBudget
from backend.bench.evaluator import Verdict
from backend.bench.library import Case, Family
from backend.graph.runstate import Attempt
from backend.tests.test_api_runs import (
    Watched,
    a_request,
    registered,
    settled,
    watched_reference,
)


class BenchApi:
    """A live client and the registry the run records live in."""

    def __init__(self, client: TestClient, bench: BenchRuns) -> None:
        self.client = client
        self.bench = bench

    def started(self, watched: Watched) -> RunRecord:
        """A registered run, started and halted at its interrupt."""
        nonce = registered(self.client, watched)
        started = self.client.post(
            "/runs", json=a_request(watched.target, nonce)
        ).json()
        record = self.bench.record(str(started["run_id"]))
        assert record is not None
        return record

    def answer(self, run_id: str, confirmed: bool) -> None:
        self.client.post(
            f"/runs/{run_id}/approval",
            json={"confirmed": confirmed, "identity": "operator"},
        )

    def attempts(self, run_id: str) -> Any:
        return self.client.get(f"/runs/{run_id}/attempts")


@contextmanager
def bench_with_one_family(cases: list[Case]) -> Iterator[BenchApi]:
    """The API over a bench holding the cases handed in, with no adaptive layer.

    One turn and one episode per family keeps the second layer to the smallest thing
    that still runs: this route reads the scored layer's attempts and an episode of
    the other one is neither served here nor asserted about. `family_count` is read
    off the cases rather than fixed, because it is what the adaptive ceiling is built
    from — a bench holding six families under a ceiling declared for one aborts on
    its own budget before the run completes.
    """
    app = create_app(
        BenchConfig(
            cases=cases,
            adaptive=AdaptiveBudget(
                turns_per_episode=1,
                episodes_per_family=1,
                family_count=len({case.family for case in cases}),
            ),
            approval_wait_seconds=60.0,
        )
    )
    with TestClient(app) as client:
        yield BenchApi(client=client, bench=cast(BenchRuns, app.state.bench))


def test_the_exchange_behind_every_succeeded_attempt_is_served_by_family(
    leakage_case: Case,
) -> None:
    """The attacks that worked, grouped by family, with what came back.

    Both halves of one exchange, because a payload without its reply is unreadable:
    the sent text is what an operator hands their own engineer, and the reply is the
    only thing that shows what their agent did with it. The verdict class travels on
    the row rather than being inferred from the family name, which is the inference
    the record exists to make impossible.
    """
    with (
        watched_reference() as watched,
        bench_with_one_family([leakage_case]) as api,
    ):
        record = api.started(watched)
        api.answer(record.run_id, confirmed=True)
        settled(record)
        response = api.attempts(record.run_id)

    assert record.status is RunStatus.COMPLETED, record.statement
    succeeded = record.run_state.succeeded_attempts
    assert succeeded, "the obedient agent leaks, so something has to have worked"

    assert response.status_code == 200
    body = response.json()
    assert body["held"] is True
    assert body["run_id"] == record.run_id

    [family] = body["families"]
    assert family["family"] == str(leakage_case.family)
    assert family["verdict_class"] == str(leakage_case.verdict_class)
    assert len(family["succeeded"]) == len(succeeded)
    for served, attempt in zip(family["succeeded"], succeeded, strict=True):
        assert served["case_id"] == attempt.case_id
        assert served["sent"] == attempt.transcript.sent["message"]
        assert served["reply"] == attempt.transcript.reply_text
        assert served["verdict"] == str(Verdict.SUCCEEDED)
        # One-based on the way out: a reader counts *the third attempt* and the
        # record holds an index into ten.
        assert served["attempt"] == attempt.index + 1

    # And the response says what it is, because a screenshot of it travels alone.
    assert "not part of the signed artefact" in body["stated"].lower()
    assert "gone when this process stops" in body["stated"]


def test_the_families_are_in_the_librarys_own_order_and_carry_no_count(
    library: list[Case],
) -> None:
    """`Family`'s order, so this surface and the report's cards line up row for row.

    And no figure that spans anything: a length taken off one of these lists is the
    numerator of a rate whose denominator is on the report, and a family is here only
    if something in it succeeded — so the absence of a family is not a zero
    (ADR-0006, ADR-0010).
    """
    with (
        watched_reference() as watched,
        bench_with_one_family(library) as api,
    ):
        record = api.started(watched)
        api.answer(record.run_id, confirmed=True)
        settled(record)
        response = api.attempts(record.run_id)

    assert record.status is RunStatus.COMPLETED, record.statement
    body = response.json()
    served = [family["family"] for family in body["families"]]
    assert served, "the obedient agent gives something up in at least one family"

    declared = [str(family) for family in Family]
    assert served == [family for family in declared if family in served]

    rows = sum(len(family["succeeded"]) for family in body["families"])
    assert rows == len(record.run_state.succeeded_attempts)
    assert "count" not in body
    assert all(
        "count" not in family and "of" not in family for family in body["families"]
    )


def test_a_resisted_attempt_is_not_served_though_the_record_holds_it(
    leakage_case: Case,
) -> None:
    """Only the attacks that worked, and the record keeps the rest either way.

    A resisted attempt is the same recorded payload against the same case, one attempt
    apart, and serving it too would be the log this surface has already refused once
    (`RECENT_ATTEMPTS`). The resisted attempt is put on the record by hand rather than
    hunted for on the wire: which payloads a reference agent happens to resist is not
    what this route is being held to, and a filter asserted against an agent's mood is
    a filter that stops being asserted when the agent changes.
    """
    with (
        watched_reference() as watched,
        bench_with_one_family([leakage_case]) as api,
    ):
        record = api.started(watched)
        api.answer(record.run_id, confirmed=True)
        settled(record)
        assert record.status is RunStatus.COMPLETED, record.statement
        worked = len(record.run_state.succeeded_attempts)
        record.run_state.attempts.append(
            _resisted(record.run_state.attempts[0], RESISTED_PAYLOAD)
        )
        body = api.attempts(record.run_id).json()

    assert len(record.run_state.attempts) == worked + 1
    [family] = body["families"]
    assert len(family["succeeded"]) == worked
    assert RESISTED_PAYLOAD not in [one["sent"] for one in family["succeeded"]]
    assert all(one["verdict"] == str(Verdict.SUCCEEDED) for one in family["succeeded"])


RESISTED_PAYLOAD = "KESTREL-RESISTED: a payload this target turned down"
"""A payload carrying a word that appears nowhere else in this repository.

Distinctive so that *this payload is not in the response* is an assertion rather than
a hope: a resisted attempt that read like the ones beside it could be served without
any assertion here noticing.
"""


def _resisted(like: Attempt, payload: str) -> Attempt:
    """One resisted attempt, otherwise identical to an attempt that worked.

    Copied off a real one so that the only difference the route could be filtering on
    is the verdict: an attempt that differed in its family or its case as well would
    let a route that filtered on either of those pass this test.
    """
    return replace(
        like,
        index=like.index + 1,
        verdict=Verdict.RESISTED,
        transcript=replace(like.transcript, sent={"message": payload}),
    )


def test_a_run_this_process_never_started_is_refused_by_name(
    leakage_case: Case,
) -> None:
    """A `404`, and the sentence says why a restart is this same answer.

    The exchange lives with the process that made the attempt. So the id of a run
    from before a restart is an id this bench never started, and the refusal has to
    read as *there is nothing held* rather than as *this route was wrong*.
    """
    with bench_with_one_family([leakage_case]) as api:
        response = api.attempts("run-nobody-started")

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert "run-nobody-started" in detail
    assert "restart" in detail


def test_a_run_where_nothing_succeeded_states_the_absence(leakage_case: Case) -> None:
    """A declined run made no attempt, and an empty list would read as one that did.

    Two different readings and only one of them is about the target: a run nobody
    approved never sent anything, and a run whose every attempt was resisted is a
    finding. The response carries the sentence that says both arrive here and that
    the rates say which.
    """
    with (
        watched_reference() as watched,
        bench_with_one_family([leakage_case]) as api,
    ):
        record = api.started(watched)
        api.answer(record.run_id, confirmed=False)
        settled(record)
        response = api.attempts(record.run_id)

    assert record.status is RunStatus.DECLINED
    assert not record.run_state.succeeded_attempts
    assert response.status_code == 200
    body = response.json()
    assert body["held"] is False
    assert "families" not in body
    assert "no attempt in this run's scored layer succeeded" in body["stated"]
    assert "not an empty list" in body["stated"]
    assert watched.ledger.hits == 0
