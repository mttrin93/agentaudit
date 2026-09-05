"""One run-scoped namespace, dropped wholesale, on every exit path a run has.

The invariant of
[ADR-0063](../../docs/adr/0063-one-run-scoped-namespace-dropped-wholesale.md),
driven at four seams:

* `planting.namespace_for`, `planting.teardown` and `planting.teardown_all` — the
  shape of the namespace, and a drop that never raises.
* `shim.serve_callback` — a callback that can plant and cannot clean up, refused
  before a port is bound.
* `calibration.run_calibration` — the whole of it, and the reason this file exists:
  **the runs that end badly.** A clean finish, a declined checkpoint, a plant that
  raised, a target that outlived its retry policy, a budget breached mid-run, a
  cancellation, and a registration that never completed. Every one of them drops the
  namespace, because the drop is in a `finally` on the run rather than a line at the
  end of the happy path.
* `targets/reference/server.py` — the test equipment, held to the same contract.

**The failure paths are the tests that matter here.** Deleting the `finally` in
`run_calibration` leaves the clean-finish test passing and takes every test under
*the runs that end badly* red with it, which is the shape the issue asked for.
"""

from __future__ import annotations

import uuid
from dataclasses import replace

import pytest

from backend.bench.calibration import CalibrationResult, run_calibration
from backend.bench.contract import (
    RetryPolicy,
    TargetConfig,
    TargetFailure,
    TargetUnreachable,
    send_message,
)
from backend.bench.library import Case
from backend.bench.payload import document
from backend.bench.planting import (
    NAMESPACE_PREFIX,
    NOTHING_WAS_PLANTED,
    PlantingFailed,
    Teardown,
    TeardownFailure,
    anonymous_run_id,
    namespace_for,
    teardown,
    teardown_all,
)
from backend.bench.registration import ECHO_PROBE
from backend.bench.rendering import render
from backend.bench.rule import DECLARED_RULE
from backend.bench.shim import PlantsWithNothingToDropIt, serve_callback
from backend.graph.approval import Approve
from backend.graph.budget import (
    REGISTRATION_PROBES_PER_TARGET,
    BudgetExceeded,
    RunBudget,
)
from backend.observability import TracedRun
from backend.tests.conftest import (
    BENCH_ATTESTATION,
    CONFIRMING,
    served_references,
    unlisted_case,
)
from backend.tests.test_payload import a_payload, a_provenance

RUN_ID = "0123456789abcdef"

IMPATIENT = RetryPolicy(sends=3, backoff_seconds=0.0)
"""Three sends and no backoff: a run that gives up quickly, so a test that is about
the cleanup does not spend its time in a retry loop."""


class Planting:
    """A callback that plants into a namespace and can drop it again.

    Everything it is handed on both calls is kept, in order, so a test can ask the
    one question this file is about: was the value planted into the value dropped,
    and did the drop happen at all.
    """

    def __init__(self, *, teardown_raises: bool = False) -> None:
        self.planted: list[str] = []
        """The namespace each plant was given, one entry per hook call."""

        self.dropped: list[str] = []
        self.canary: str | None = None
        self._teardown_raises = teardown_raises

    def __call__(self, message: str, session_id: str) -> str:
        return self.canary or "nothing to say"

    def plant_config_canary(self, namespace: str, canary: str) -> None:
        self.planted.append(namespace)
        self.canary = canary

    def teardown(self, namespace: str) -> None:
        self.dropped.append(namespace)
        if self._teardown_raises:
            raise RuntimeError("the vector store refused the drop")


class PlantRaises(Planting):
    def plant_config_canary(self, namespace: str, canary: str) -> None:
        raise RuntimeError("the content store was unreachable")


class PlantCancelled(Planting):
    """A plant interrupted rather than failed.

    `KeyboardInterrupt` is a `BaseException`, so it is not the `Exception` `plant`
    turns into a `PlantingFailed` — it leaves `run_calibration` exactly as raised,
    which is what a cancelled run does.
    """

    def plant_config_canary(self, namespace: str, canary: str) -> None:
        raise KeyboardInterrupt


def _calibrate(
    targets: list[TargetConfig],
    cases: list[Case],
    planters: dict[str, object],
    *,
    budget: RunBudget | None = None,
    approve: Approve | None = CONFIRMING,
) -> CalibrationResult:
    """One run against served callbacks, under a run id this file can name.

    The trace is what carries the run id, and the run id is what the namespace is
    derived from — so passing one here is what lets every assertion below be an
    equality against `namespace_for(RUN_ID)` rather than a shape match.
    """
    return run_calibration(
        cases=cases,
        targets=targets,
        attestation=BENCH_ATTESTATION,
        planters=planters,
        approve=approve,
        budget=budget,
        trace=TracedRun(id=RUN_ID),
    )


# --- The shape of the namespace ----------------------------------------------


def test_the_namespace_is_derived_from_the_run_id_and_never_invented() -> None:
    """`run-<id>`, and a run id that could not be one is refused rather than fixed."""
    assert namespace_for(RUN_ID) == f"{NAMESPACE_PREFIX}{RUN_ID}"
    assert namespace_for(anonymous_run_id()).startswith(NAMESPACE_PREFIX)

    # Two anonymous runs are two namespaces. A constant here would give the second
    # run's teardown the first run's plants to drop.
    assert anonymous_run_id() != anonymous_run_id()

    for refused in ("", "run/../etc", "a b", "drop table"):
        with pytest.raises(ValueError, match="run namespace"):
            namespace_for(refused)


def test_the_value_planted_into_is_the_value_dropped(leakage_case: Case) -> None:
    """One namespace, reaching both hooks as an argument and stored on neither.

    The two calls are made by the harness out of one derivation, so there is no
    field on the shim between them for a later run to have overwritten.
    """
    agent = Planting()
    with serve_callback(agent, name="scoped") as target:
        result = _calibrate([target], [leakage_case], {target.name: agent})

    namespace = namespace_for(RUN_ID)
    assert agent.planted == [namespace]
    assert agent.dropped == [namespace]
    assert result.namespace == namespace
    [performed] = result.target_runs[0].plantings
    assert performed.namespace == namespace


def test_a_teardown_of_an_object_that_has_none_is_a_named_outcome() -> None:
    """The seam on its own: `teardown` answers, and never raises.

    `None` for a run holding no planter — nothing planted, so nothing to report
    dropping — and a named record for an object that cannot drop what it was given.
    """
    assert teardown(None, "run-x", target_name="t") is None

    class NoTeardown:
        pass

    assert teardown(NoTeardown(), "run-x", target_name="t") == Teardown(
        namespace="run-x",
        target_name="t",
        failure=TeardownFailure.HOOK_MISSING,
        # No `error`: there was no call, so there are no words of the operator's to
        # report, and the member's own sentence is the whole of it.
        error=None,
    )

    agent = Planting(teardown_raises=True)
    [raised] = teardown_all({"t": agent}, "run-x")
    assert raised.failed
    assert raised.failure is TeardownFailure.HOOK_RAISED
    assert raised.namespace == "run-x"
    # The operator's own words, because this is their cleanup code failing against
    # their own store and the report is written for them.
    assert "the vector store refused the drop" in (raised.error or "")


# --- Refused at construction --------------------------------------------------


def test_a_callback_that_can_plant_and_cannot_clean_up_is_refused() -> None:
    """Before a port is bound, and not withdrawn: this callback *can* be measured.

    Withdrawal is the answer for a shim with no hook at all. This one has hooks and
    no way to take back what they write, which is a bench pointed at somebody's
    store with no way out of it (ADR-0063 §4).
    """

    class PlantsAndCannotClean:
        def __call__(self, message: str, session_id: str) -> str:
            return "hello"

        def plant_config_canary(self, namespace: str, canary: str) -> None:
            pass

    with pytest.raises(PlantsWithNothingToDropIt) as refused:
        with serve_callback(PlantsAndCannotClean(), name="messy"):
            pytest.fail("the shim served a callback it cannot clean up after")

    assert "teardown(namespace)" in str(refused.value)
    assert "config_canary" in str(refused.value)


def test_a_callback_with_no_hooks_at_all_needs_no_teardown() -> None:
    """The refusal is about the pair, not about teardowns.

    A plain function plants nothing and is served exactly as it was before, or the
    check would have turned the ordinary case into an error.
    """

    def plain(message: str, session_id: str) -> str:
        return "hello"

    with serve_callback(plain, name="plain") as target:
        assert target.plants == frozenset()


# --- The runs that end badly --------------------------------------------------


def test_a_clean_finish_drops_the_namespace(leakage_case: Case) -> None:
    """The happy path, stated so the failure paths below have something to differ
    from — and it is the one test deleting the `finally` leaves passing only if the
    drop is written at the end of the happy path instead."""
    agent = Planting()
    with serve_callback(agent, name="clean") as target:
        result = _calibrate([target], [leakage_case], {target.name: agent})

    assert agent.dropped == [namespace_for(RUN_ID)]
    assert [one.failed for one in result.teardowns] == [False]


def test_a_declined_checkpoint_drops_the_namespace(leakage_case: Case) -> None:
    """Nothing was planted, and the drop happens anyway (ADR-0028, ADR-0063 §2).

    A wholesale drop of a namespace nobody created is a shim author's no-op, and the
    alternative — the harness deciding per exit path whether cleanup applies — is a
    branch that goes wrong on the path nobody tests.
    """
    agent = Planting()
    with serve_callback(agent, name="declined") as target:
        result = _calibrate(
            [target], [leakage_case], {target.name: agent}, approve=None
        )

    assert not result.approval.proceeded
    assert agent.planted == []
    assert agent.dropped == [namespace_for(RUN_ID)]


def test_a_plant_that_raised_drops_the_namespace(leakage_case: Case) -> None:
    """A `PlantingFailed` stops the run before the first attempt, and cleans up.

    The half-planted run is the one that most needs this: a plant that raised may
    have written something before it fell over, and the namespace is dropped whether
    or not it did.
    """
    agent = PlantRaises()
    with serve_callback(agent, name="raises") as target:
        with pytest.raises(PlantingFailed):
            _calibrate([target], [leakage_case], {target.name: agent})

    assert agent.dropped == [namespace_for(RUN_ID)]


def test_a_raise_after_a_plant_still_drops_the_namespace(leakage_case: Case) -> None:
    """The issue's own red drive: raise inside the run *after* a plant has landed.

    Two targets, one namespace. The first is planted; the second's hook falls over
    and the run stops. What the first target put in its store is dropped anyway,
    which is only true because the drop is on the run and not on the plant.
    """
    planted = Planting()
    breaks = PlantRaises()
    with serve_callback(planted, name="first") as one:
        with serve_callback(breaks, name="second") as two:
            with pytest.raises(PlantingFailed):
                _calibrate(
                    [one, two],
                    [leakage_case],
                    {one.name: planted, two.name: breaks},
                )

    namespace = namespace_for(RUN_ID)
    assert planted.planted == [namespace]
    assert planted.dropped == [namespace]
    assert breaks.dropped == [namespace]


def test_a_cancellation_after_a_plant_still_drops_the_namespace(
    leakage_case: Case,
) -> None:
    """A `BaseException` is not caught anywhere on the way out, and cleans up anyway.

    `finally` and not `except Exception`, which is the difference between a run
    somebody stopped with a keystroke and a run that tidied up after itself.
    """
    agent = PlantCancelled()
    with serve_callback(agent, name="cancelled") as target:
        with pytest.raises(KeyboardInterrupt):
            _calibrate([target], [leakage_case], {target.name: agent})

    assert agent.dropped == [namespace_for(RUN_ID)]


def test_a_target_that_outlived_its_retry_policy_drops_the_namespace(
    leakage_case: Case,
) -> None:
    """A `TargetUnreachable` propagates and the namespace goes with it.

    The plant landed — it is ahead of the registration probe — so this is a run that
    wrote into somebody's store and then never reached their agent at all.
    """
    agent = Planting()

    class Unreachable(Planting):
        def __call__(self, message: str, session_id: str) -> str:
            raise RuntimeError("the callback fell over")

    agent = Unreachable()
    with serve_callback(agent, name="unreachable", retry=IMPATIENT) as target:
        with pytest.raises(TargetUnreachable) as raised:
            _calibrate([target], [leakage_case], {target.name: agent})

    assert raised.value.failure is TargetFailure.UNAVAILABLE
    assert agent.planted == [namespace_for(RUN_ID)]
    assert agent.dropped == [namespace_for(RUN_ID)]


def test_a_budget_breached_mid_run_drops_the_namespace(leakage_case: Case) -> None:
    """The abort ADR-0007 requires, and the cleanup happens under it.

    A ceiling declared for one case and a suite of two: the run spends every call it
    was given, refuses the next one, and still takes back what it planted.
    """
    agent = Planting()
    with serve_callback(agent, name="over") as served:
        target = replace(served, retry=RetryPolicy(sends=1, backoff_seconds=0.0))
        agreed = RunBudget.declare(cases=[leakage_case], targets=[target])
        assert agreed.scored_ceiling == (
            REGISTRATION_PROBES_PER_TARGET + DECLARED_RULE.attempts_per_case
        )
        with pytest.raises(BudgetExceeded):
            _calibrate(
                [target],
                [leakage_case, unlisted_case("second payload", "case-second")],
                {target.name: agent},
                budget=agreed,
            )

    assert agent.dropped == [namespace_for(RUN_ID)]


def test_a_registration_that_never_completed_drops_the_namespace(
    leakage_case: Case,
) -> None:
    """The run finishes, measures nothing, and still cleans up.

    A target that answers the echo probe with something else never registers, so no
    attempt is made against it — and the plant that preceded the probe is still in
    its store until this drops it.
    """

    class NeverEchoes(Planting):
        def __call__(self, message: str, session_id: str) -> str:
            return "I would rather not say" if message == ECHO_PROBE else "hello"

    agent = NeverEchoes()
    with serve_callback(agent, name="silent") as target:
        result = _calibrate([target], [leakage_case], {target.name: agent})

    [target_run] = result.target_runs
    assert not target_run.registration.complete
    assert target_run.attempts == ()
    assert agent.planted == [namespace_for(RUN_ID)]
    assert agent.dropped == [namespace_for(RUN_ID)]


# --- A teardown that failed is reported and changes no figure -----------------


def test_a_teardown_that_failed_is_on_the_result_and_moves_no_figure(
    leakage_case: Case,
) -> None:
    """The run's numbers stand; the operator is told what is still in their store.

    Every attempt was made and every verdict was reached before anything was
    dropped, so a failed cleanup is a fact about the store and never about the
    measurement (ADR-0063 §3).
    """
    agent = Planting(teardown_raises=True)
    with serve_callback(agent, name="stuck") as target:
        result = _calibrate([target], [leakage_case], {target.name: agent})

    [dropped] = result.teardowns
    assert dropped.failed
    assert dropped.namespace == namespace_for(RUN_ID)
    assert dropped.target_name == "stuck"
    assert namespace_for(RUN_ID) in dropped.stated()
    assert "the vector store refused the drop" in dropped.stated()

    [target_run] = result.target_runs
    assert len(target_run.attempts) == DECLARED_RULE.attempts_per_case


# --- The test equipment, held to the same contract ----------------------------


def test_the_reference_agents_scope_a_planted_nonce_to_the_run_that_planted_it() -> (
    None
):
    """Two runs' plants coexist, and dropping one takes only that one with it.

    The state this replaced was one slot per agent, overwritten by whichever run
    registered last and never removed at all. What makes this the same contract the
    user-facing hooks are held to is the shape: the namespace arrives as an argument
    on the plant, the drop takes the namespace and not the records, and a dropped
    namespace can never answer for a live one (ADR-0063 §5).
    """
    first, second = "run-first", "run-second"
    with served_references() as references:
        [trivial] = [one for one in references.served if one.target.name == "trivial"]

        references.plant_nonce(
            trivial.target, "AGENTAUDIT-CANARY-AAAAAAAAAAAAAAAA", first
        )
        references.plant_nonce(
            trivial.target, "AGENTAUDIT-CANARY-BBBBBBBBBBBBBBBB", second
        )
        assert "BBBBBBBBBBBBBBBB" in _echo(trivial.target)

        # The second run ends. What it planted goes, and the first run's plant — a
        # different namespace — is untouched by the drop.
        references.drop_namespace(second)
        assert "AAAAAAAAAAAAAAAA" in _echo(trivial.target)

        references.drop_namespace(first)
        assert "AAAAAAAAAAAAAAAA" not in _echo(trivial.target)

        # And a drop of a namespace nobody created is a no-op, because a teardown
        # runs on the exit paths that planted nothing too.
        references.drop_namespace("run-never-created")


def _echo(target: TargetConfig) -> str:
    """What this agent answers the registration probe with, right now."""
    return send_message(
        target, ECHO_PROBE, session_id=f"echo-{uuid.uuid4()}"
    ).reply_text


# --- What the artefact says about it ------------------------------------------


def test_a_run_that_planted_nothing_says_so_in_the_document() -> None:
    """Never a missing line: silence is the failure mode this block exists against.

    Every endpoint run is this run — nothing was planted, so no namespace was created
    — and a document that omitted the block would read as an older shape of artefact
    rather than as a run that planted nothing.
    """
    body = document(a_payload(provenance=replace(a_provenance(), teardown=None)))

    assert body["provenance"]["teardown"] == {
        "planted": False,
        "failed": False,
        "stated": NOTHING_WAS_PLANTED,
    }
    assert NOTHING_WAS_PLANTED in render(a_payload())


def test_a_teardown_that_failed_names_the_namespace_and_the_error_in_the_document() -> (
    None
):
    """The one thing an operator can act on, and the only place it can reach them.

    The run's figures are unaffected, so nothing else in the document moves — which
    is exactly why this line has to be here: a reader comparing rates would never
    find out on their own that this bench left content in their store (ADR-0063 §3).
    """
    stuck = Teardown(
        namespace="run-abcdef",
        target_name="agent",
        failure=TeardownFailure.HOOK_RAISED,
        error="RuntimeError: the vector store refused the drop",
    )
    payload = a_payload(provenance=replace(a_provenance(), teardown=stuck))
    block = document(payload)["provenance"]["teardown"]

    assert block["planted"] is True
    assert block["failed"] is True
    assert block["namespace"] == "run-abcdef"
    assert block["failure"] == str(TeardownFailure.HOOK_RAISED)
    assert block["error"] == "RuntimeError: the vector store refused the drop"

    rendered = render(payload)
    assert "run-abcdef" in rendered
    assert "the vector store refused the drop" in rendered


def test_a_teardown_that_worked_keeps_the_namespace_out_of_the_document() -> None:
    """A name a reader has nothing to do with, and one this document does not carry.

    The namespace is derived from the run id, which no artefact holds (ADR-0018), and
    on a run that cleaned up after itself there is nothing to look for. So it travels
    only when it is the thing an operator has to type.
    """
    dropped = Teardown(namespace="run-abcdef", target_name="agent")
    payload = a_payload(provenance=replace(a_provenance(), teardown=dropped))
    block = document(payload)["provenance"]["teardown"]

    assert block["planted"] is True
    assert block["failed"] is False
    assert block["namespace"] is None
    assert "run-abcdef" not in render(payload)
