"""The list of runs, and the third figure it must never carry.

`GET /runs` is the console's answer to *which of these did I start, and what did it
cost me* for an operator who did not keep the URL. It is a read over records that
already exist: nothing on it is computed, and the one thing it could compute is the
one thing it must not.

**The blend is the failure this file is mostly about.** A row shows two spends
side by side, which makes a list of runs the single most likely surface in this
application to grow a third column — a total per run, a total per column, a mean
across the rows. Each of those would put an adaptive quantity into a figure a reader
reads beside a scored one, and each of them would hide which half of a run consumed
the operator's budget (ADR-0007, ADR-0010). So the arithmetic is asserted twice
over: once against a real run's own counters, and once over rows whose figures are
chosen so that no sum, no column total and no average could appear by coincidence.

**The absence is structural, not editorial.** The row's and the list's field sets
are asserted exactly, because a total is not absent when nobody printed it — it is
absent when there is no field for it to be printed in.

**A zero is a fact about the wire.** A run nobody answered spent nothing, and the
list says so with a zero and the standing beside it, because an abandoned run and a
cheap run are different facts and a row with nothing in it would read as neither.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from fastapi.testclient import TestClient

from backend.api.app import RUNS_ROUTE, RunList, RunRow, create_app, runs_response
from backend.api.report import ReportConfig
from backend.api.runs import (
    BenchConfig,
    RunRecord,
    RunStatus,
    plan_for,
)
from backend.bench.library import Case, LibraryVersion
from backend.graph.budget import Layer
from backend.graph.runstate import RunState
from backend.tests.conftest import BENCH_ATTESTATION, a_budget, a_target, some_cases
from backend.tests.test_api_runs import (
    a_request,
    api,
    registered,
    settled,
    watched_reference,
)

SPENDS = ((181, 96), (37, 8), (0, 0))
"""Three runs' per-layer spends, chosen so that no blend of them is a figure a row
legitimately carries.

Every quantity a reader could construct out of these — 277, 45 and 0 per run; 218
scored and 104 adaptive down the columns; 322 over everything; and the means 138.5,
22.5 and 0 — is absent from the set of figures the list is allowed to show, which is
`{181, 96, 37, 8, 0}`. The third pair is a run that spent nothing in either layer,
so the fixture exercises the zero branch in the same payload as the arithmetic.
"""


def a_record(scored: int, adaptive: int, name: str) -> RunRecord:
    """A run on the record, having spent that much in each layer.

    Built by hand rather than run, because what is under test is the arithmetic of
    the response and a real run cannot be made to spend 181 calls on demand. The
    figures go through `RunState.record_call`, one layer at a time and never through
    `RunState.calls_spent`, so they are counted the way a real run counts them.
    """
    target = a_target(name=name)
    plan = plan_for(BenchConfig(cases=some_cases(3)), note_planted=True)
    budget = a_budget(cases=18, targets=1)
    state = RunState(budget=budget, library=LibraryVersion.of(plan.cases))
    for layer, calls in ((Layer.SCORED, scored), (Layer.ADAPTIVE, adaptive)):
        if calls:
            state.record_call(layer, calls)
    return RunRecord(
        run_id=f"run-{name}",
        thread_id=f"halt-{name}",
        target=target,
        attestation=BENCH_ATTESTATION,
        nonce="nonce",
        plan=plan,
        budget=budget,
        run_state=state,
        presented=budget.as_payload(),
    )


def test_the_route_lists_each_run_with_calls_spent_per_layer(
    leakage_case: Case,
) -> None:
    """One real run, listed: what it was against, when, where it got to, what it
    spent in each layer.

    The two spends are compared against the run's own counters rather than against
    each other or against a constant, because the claim is that the list reports
    what the run did — and the counters are the same two `GET /runs/{id}` reports,
    read one layer at a time.
    """
    with watched_reference() as watched, api([leakage_case]) as (client, bench):
        nonce = registered(client, watched)
        started = client.post("/runs", json=a_request(watched.target, nonce)).json()
        run_id = str(started["run_id"])
        record = bench.record(run_id)
        assert record is not None
        client.post(
            f"/runs/{run_id}/approval",
            json={"confirmed": True},
        )
        settled(record)
        body = _listed(client)

    assert [row["run_id"] for row in body["runs"]] == [run_id]
    row = body["runs"][0]
    state = record.run_state
    assert row["scored"]["calls_spent"] == state.spent_in(Layer.SCORED) > 0
    assert row["adaptive"]["calls_spent"] == state.spent_in(Layer.ADAPTIVE) > 0
    assert row["status"] == str(RunStatus.COMPLETED) == "completed"
    assert row["statement"] == record.statement

    # The target under its own name, and its endpoint nowhere: a live URL that
    # answers jailbreak payloads does not belong in a list a screenshot is taken of
    # (ADR-0008).
    assert row["target"] == watched.target.name
    assert watched.target.url not in client.get(RUNS_ROUTE).text

    # A wall clock, so that "which of these did I start yesterday" has an answer.
    # `RunState.started_at` is monotonic and has no date in it.
    assert datetime.fromisoformat(row["recorded_at"]).tzinfo is not None

    # And the sum of the two, over a run where both layers spent something, appears
    # nowhere in the document.
    assert _numbers(row) == {
        row["scored"]["calls_spent"],
        row["adaptive"]["calls_spent"],
    }


def test_a_run_nobody_answered_is_listed_with_zero_in_both_layers_and_its_standing(
    leakage_case: Case,
) -> None:
    """An abandoned run stays distinguishable from a cheap one.

    Zero in both layers, the standing named as **unanswered** — not declined, which
    is a human refusing — and the record's own sentence beside it. The zero is a
    fact about the wire and the endpoint's own ledger says so, which is what makes
    it a figure rather than the rate of zero CONTEXT.md forbids.
    """
    with (
        watched_reference() as watched,
        api([leakage_case], approval_wait_seconds=0.2) as (client, bench),
    ):
        nonce = registered(client, watched)
        started = client.post("/runs", json=a_request(watched.target, nonce)).json()
        record = bench.record(str(started["run_id"]))
        assert record is not None
        settled(record)
        body = _listed(client)
        hits = watched.ledger.hits

    row = body["runs"][0]
    assert hits == 0
    assert row["scored"]["calls_spent"] == 0
    assert row["adaptive"]["calls_spent"] == 0
    assert row["status"] == str(RunStatus.UNANSWERED) == "unanswered"
    assert row["status"] != str(RunStatus.DECLINED)
    assert "never answered" in row["statement"]

    # Each layer says its own zero is nothing on the wire, so neither is read as a
    # layer that ran and found nothing.
    for layer in ("scored", "adaptive"):
        assert "no call on the operator's endpoint" in row[layer]["statement"]


def test_nothing_on_this_list_adds_or_averages_the_two_layers() -> None:
    """No total per run, no total per column, no mean, and nowhere to put one.

    Over three runs at once rather than one, because the blend a list invites is
    not only the per-row sum: a column total and an average across the rows are the
    two figures a table grows next. The figures are chosen so that every one of
    those quantities is absent from the set the rows are allowed to show, so a
    total added later fails here rather than in review.
    """
    records = [
        a_record(scored, adaptive, f"target-{index}")
        for index, (scored, adaptive) in enumerate(SPENDS)
    ]
    body = runs_response(records).model_dump(mode="json")

    shown = _numbers(body)
    assert shown == {181, 96, 37, 8, 0}

    per_run = {scored + adaptive for scored, adaptive in SPENDS}
    columns = {sum(spend[0] for spend in SPENDS), sum(spend[1] for spend in SPENDS)}
    everything = {sum(scored + adaptive for scored, adaptive in SPENDS)}
    for blended in (per_run | columns | everything) - {0}:
        assert blended not in shown, f"{blended} is a blend of two layers"

    # The means, which would arrive as text rather than as an integer.
    text = _prose(body)
    for scored, adaptive in SPENDS:
        mean = (scored + adaptive) / 2
        if mean:
            assert f"{mean}" not in text

    # Structural, and this is the assertion that matters: there is no field for a
    # total to be printed in, on the row or on the list.
    assert set(RunRow.model_fields) == {
        "run_id",
        "target",
        "recorded_at",
        "status",
        "statement",
        "scored",
        "adaptive",
    }
    assert set(RunList.model_fields) == {"runs", "statement"}
    assert "no total" in body["statement"]


def test_the_runs_are_listed_most_recently_recorded_first(leakage_case: Case) -> None:
    """A returning operator reads the run they started last, first.

    Three real runs through the bench, so the order under test is the one
    `BenchRuns.records` decided rather than one this test sorted for it. None of
    them is answered, so the target is described and never called — an unanswered
    run puts nothing on the wire, which is what makes three of them cheap.
    """
    target = a_target(name="described-and-never-called")
    with api([leakage_case], approval_wait_seconds=0.2) as (client, bench):
        started = []
        for _ in range(3):
            nonce = str(client.post("/nonces").json()["nonce"])
            run = client.post("/runs", json=a_request(target, nonce)).json()
            started.append(str(run["run_id"]))
        for run_id in started:
            record = bench.record(run_id)
            assert record is not None
            settled(record)
        body = _listed(client)

    assert [row["run_id"] for row in body["runs"]] == started[::-1]
    recorded = [row["recorded_at"] for row in body["runs"]]
    assert recorded == sorted(recorded, reverse=True)


def test_a_bench_that_has_started_no_runs_answers_with_no_rows() -> None:
    """An empty list is a `200` with nothing in it, and never a refusal.

    A fresh deployment has no runs, and an operator opening the console for the
    first time is in exactly that state: a `404` there would be an error where the
    honest answer is *none yet*.
    """
    client = TestClient(create_app(BenchConfig(cases=[], report=ReportConfig())))
    response = client.get(RUNS_ROUTE)

    assert response.status_code == 200
    assert response.json()["runs"] == []


def _listed(client: TestClient) -> dict[str, Any]:
    response = client.get(RUNS_ROUTE)
    assert response.status_code == 200
    return cast(dict[str, Any], response.json())


def _prose(body: Any) -> str:
    """Every string on the list except the timestamps, joined.

    The timestamps are left out because they are digits around a decimal point and
    nothing else: `12:37:22.512345` contains the text `22.5`, so a scan for an
    average that read the clock would fail on the hour it ran rather than on an
    average anybody printed. Nothing else here is numeric prose.
    """
    if isinstance(body, str):
        return body
    if isinstance(body, dict):
        return " ".join(
            _prose(value) for key, value in body.items() if key != "recorded_at"
        )
    if isinstance(body, list):
        return " ".join(_prose(item) for item in body)
    return ""


def _numbers(body: Any) -> set[int]:
    """Every integer anywhere in a response, however deeply nested."""
    if isinstance(body, bool):
        return set()
    if isinstance(body, int):
        return {body}
    if isinstance(body, dict):
        return set().union(*(_numbers(value) for value in body.values()), set())
    if isinstance(body, list):
        return set().union(*(_numbers(value) for value in body), set())
    return set()
