"""The narrative pass, driven through the calibration entry point.

Before this, `assess_finding`, `Finding.of`, `suggest_remediation` and
`disagreements` had callers in this directory and nowhere else: a run produced
**attempts** and never **findings** (CONTEXT.md keeps those apart, and the
difference is a narrative). The assertions here are about the seam that closed
that gap, and they are all reachable from `run_calibration` because that is where
the spec puts them (spec, Testing Decisions, seam one: "the judge's narrative
fields").

**No model is reached.** The reference agents run on the deterministic stub model
and the two narrative instruments are stubs that answer with the lines they were
handed, on `test_judge.py`'s own reasoning: what the judge would *say* about a
transcript is not under test — κ against the gold set is the evaluation of that
(ADR-0009) — and what is under test is what the run around it can and cannot do
with the answer.
"""

import ast
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import cast, get_type_hints

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.runs import BenchConfig, BenchRuns, RunStatus
from backend.bench.adaptive.budget import AdaptiveBudget
from backend.bench.adaptive.episode import AdaptiveEpisode, EpisodeOutcome
from backend.bench.adaptive.precedent import NO_PRECEDENT
from backend.bench.calibration import CalibrationResult, run_calibration
from backend.bench.evaluator import Verdict
from backend.bench.judge import (
    Exposure,
    JudgeBrief,
    JudgeFailed,
    NotAScoredAttempt,
    Reading,
    assess_finding,
)
from backend.bench.labels import Article, article_for
from backend.bench.library import Case, Family
from backend.bench.narration import (
    Narration,
    Narrator,
    narrate,
    narrate_successes,
)
from backend.bench.unfinished import (
    NOT_AN_ANSWER,
    ReplyUnfinished,
    UnfinishedReply,
)
from backend.graph.approval import Approval
from backend.graph.runstate import Attempt
from backend.tests.conftest import (
    ADJUDICATING,
    BENCH_ATTESTATION,
    CONFIRMING,
    a_target,
    reference_target,
)
from backend.tests.test_api_runs import (
    a_request,
    registered,
    settled,
    watched_reference,
)
from scripts.console import findings_section

JUDGED = {
    "reads_as": "reads_as_succeeded",
    "exposure": "confidential_material",
    "confidence": "0.8",
    "reason": "The reply carried material the agent was told to keep inside.",
    "remediation": "Filter the configured secret out of every outbound reply.",
}
"""The five lines the judge is asked for, as a well-behaved model answers them."""

FIX = "Add an output filter that redacts the configured secret before replying."
"""The one line `suggest_remediation` is asked for."""

NARRATION_SOURCE = Path(__file__).resolve().parents[1] / "bench" / "narration.py"


@dataclass
class Recording:
    """A stub instrument that answers with fixed lines and keeps what it was shown.

    What it kept is the evidence for the blinding assertions: the brief is built on
    the harness side of the call (`JudgeBrief.about`), so the only way to ask
    whether a target's identity reached the judge is to look at what the model was
    actually handed.
    """

    lines: dict[str, str]
    shown: list[str] = field(default_factory=list)
    prompts: list[str] = field(default_factory=list)

    def __call__(self, system_prompt: str, message: str) -> str:
        self.prompts.append(system_prompt)
        self.shown.append(message)
        return "\n".join(f"{key}: {value}" for key, value in self.lines.items())


def judging(**overrides: str) -> Recording:
    """A judge that answers the five lines, with any of them replaced."""
    return Recording(lines={**JUDGED, **overrides})


def remediating(fix: str = FIX) -> Recording:
    return Recording(lines={"fix": fix})


@dataclass(frozen=True)
class Narrated:
    """One run made with narrative instruments, and the two stubs it used."""

    result: CalibrationResult
    judge: Recording
    remediation: Recording

    @property
    def attempts(self) -> tuple[Attempt, ...]:
        [target_run] = self.result.target_runs
        return target_run.attempts

    @property
    def succeeded(self) -> list[Attempt]:
        return [a for a in self.attempts if a.verdict is Verdict.SUCCEEDED]


def narrated(
    case: Case,
    name: str = "trivial",
    judge: Recording | None = None,
    remediation: Recording | None = None,
) -> Narrated:
    """One case against one served reference agent, with the judge wired in."""
    assess = judge if judge is not None else judging()
    remediate = remediation if remediation is not None else remediating()
    with reference_target(name=name) as reference:
        result = run_calibration(
            cases=[case],
            targets=[reference.target],
            attestation=BENCH_ATTESTATION,
            plant_nonce=reference.plant_nonce,
            approve=CONFIRMING,
            adjudicator=ADJUDICATING,
            narrator=Narrator(assess=assess, remediate=remediate),
        )
    return Narrated(result=result, judge=assess, remediation=remediate)


@pytest.fixture
def leaking(leakage_case: Case) -> Iterator[Narrated]:
    """A run against the agent that hands over its configuration, narrated."""
    yield narrated(leakage_case)


@pytest.fixture
def leaked_brief(leaking: Narrated, leakage_case: Case) -> JudgeBrief:
    """One recorded succeeded attempt, blinded the way a run blinds it."""
    return JudgeBrief.about(leaking.succeeded[0], leakage_case)


# --- One finding per succeeded attempt ---------------------------------------


def test_a_scored_run_produces_a_finding_for_every_succeeded_attempt(
    leaking: Narrated,
) -> None:
    """The ticket in one assertion: attempts *and* findings, not attempts alone.

    A finding is a verdict plus its narrative (CONTEXT.md), so the count that has
    to match is the count of succeeded attempts — the population
    `RunState.succeeded_attempts` has always been able to name and never been able
    to explain.
    """
    assert leaking.succeeded, (
        "this run recorded no succeeded attempt, so there was nothing for the "
        "judge to explain and the assertion below would pass over an empty list"
    )

    [target_run] = leaking.result.target_runs
    narrations = target_run.narrations
    assert narrations is not None
    assert len(narrations) == len(leaking.succeeded)
    assert sorted(n.finding.case_id for n in narrations) == sorted(
        attempt.case_id for attempt in leaking.succeeded
    )
    # Every finding is about a success. A narrative written about a transcript the
    # success condition read as resisted would be a finding with no failure in it.
    assert all(n.finding.verdict is Verdict.SUCCEEDED for n in narrations)


def test_a_finding_carries_the_judges_narrative_and_the_tools_fix(
    leaking: Narrated, leakage_case: Case
) -> None:
    """Both instruments ran, and what each produced is on the record.

    The articles and the external identifier are asserted because they are the two
    fields the judge is *not* trusted with: the articles come from `article_for`
    and the identifier off the case record, so a run cannot widen a case's
    coverage claim by asking a model (`judge.py`, PLAN §11).
    """
    [target_run] = leaking.result.target_runs
    assert target_run.narrations is not None
    narration = target_run.narrations[0]

    assert narration.finding.narrative.reason == JUDGED["reason"]
    assert narration.finding.narrative.remediation == JUDGED["remediation"]
    assert narration.finding.narrative.exposure is Exposure.CONFIDENTIAL_MATERIAL
    assert narration.finding.narrative.reads_as is Reading.READS_AS_SUCCEEDED
    assert narration.finding.narrative.articles == (
        Article.ROBUSTNESS_AND_CYBERSECURITY,
    )
    assert narration.finding.narrative.external_id == leakage_case.external_id
    assert narration.remediation.fix == FIX
    # Nothing was recorded against this family, so the fix was written against no
    # precedent — which is a truthful answer on run one (ADR-0019).
    assert narration.remediation.informed_by == ()


# --- Blinded, at the run rather than at the call -----------------------------


def test_the_judge_is_shown_no_target_identity_and_no_verdict(
    leaking: Narrated,
) -> None:
    """Blinding survives being wired into a run, which is where it could be lost.

    `test_judge.py` asserts the fields a `JudgeBrief` has; this asserts what the
    model was actually handed by a run that knows the target's name and its url
    and had both in scope at the call site. A judge that can tell the hardened
    agent from the trivial one can infer the expected answer and manufacture
    discrimination (ADR-0004, ADR-0003).
    """
    target = leaking.result.target_runs[0].target
    assert leaking.judge.shown, "the judge was never called"

    for brief in leaking.judge.shown:
        assert target.name not in brief
        assert target.url not in brief
        # And no verdict, so it cannot agree with one it has already been told.
        for verdict in Verdict:
            assert str(verdict) not in brief


def test_a_finding_names_its_target_and_neither_instruments_brief_does(
    leaking: Narrated,
) -> None:
    """The asymmetry ADR-0004 draws, visible in one run's records and its briefs.

    A `Finding` names its target because the reader of one is the engineer who
    owns the agent and already knows which it is (judge.py). Blinding is a
    property of what the two *instruments* were shown, both of which had returned
    before the record existed — so the name on the finding is not a leak, and the
    absence of it from both briefs is what makes that true.
    """
    [target_run] = leaking.result.target_runs
    assert leaking.remediation.shown, "the remediation tool was never called"

    for brief in [*leaking.judge.shown, *leaking.remediation.shown]:
        assert target_run.target.name not in brief

    findings = target_run.findings
    assert findings, "a run with no finding cannot say whose failure it was"
    assert all(finding.target_name == target_run.target.name for finding in findings)


# --- A run with no narrative instrument says so ------------------------------


def test_a_run_made_with_no_narrative_instrument_explains_nothing_and_says_so(
    leakage_case: Case,
) -> None:
    """The absent judge is a stated absence and never an empty result.

    Every caller that hands in no narrator gets `None` here, which is the reading
    a gate run and this suite's other tests are: the run measured what it measured
    and explained none of it. A `()` would say the target succeeded at nothing,
    which the succeeded attempts beside it contradict.
    """
    with reference_target(name="trivial") as reference:
        result = run_calibration(
            cases=[leakage_case],
            targets=[reference.target],
            attestation=BENCH_ATTESTATION,
            plant_nonce=reference.plant_nonce,
            approve=CONFIRMING,
            adjudicator=ADJUDICATING,
        )

    [target_run] = result.target_runs
    assert target_run.narrations is None
    assert target_run.findings is None
    assert target_run.disagreements is None
    # And the difference matters, because this run did have successes to explain.
    assert result.run_state.succeeded_attempts


def test_a_target_that_succeeded_at_nothing_is_an_empty_queue_and_not_an_absent_one(
    leakage_case: Case,
) -> None:
    """The other side of the distinction: instruments that ran and found nothing.

    The hardened agent holds the leakage case, so there is no succeeded attempt to
    explain — and a bench that looked and found nothing is a measurement, where a
    bench that did not look is not.
    """
    held = narrated(leakage_case, name="hardened")

    [target_run] = held.result.target_runs
    assert not held.succeeded
    assert target_run.narrations == ()
    assert target_run.findings == ()
    assert target_run.disagreements == ()
    assert held.judge.shown == []


# --- Disagreements are logged and nothing resolves them ----------------------


def test_a_disagreement_is_logged_under_article_12_and_moves_no_verdict(
    leakage_case: Case,
) -> None:
    """Spec story 32, and PLAN §3's weaker human-in-the-loop instance.

    The judge reads a transcript the success condition read as succeeded as having
    been resisted. That is the two instruments disagreeing, which is information
    about the instruments — so it is recorded, handed to a human, and averaged away
    nowhere: the verdict stands and the run finishes (ADR-0004).
    """
    contradicting = narrated(leakage_case, judge=judging(reads_as="reads_as_resisted"))

    [target_run] = contradicting.result.target_runs
    queue = target_run.disagreements
    assert queue, (
        "the two instruments read this transcript differently, so a run that "
        "logged nothing has resolved the disagreement by dropping it"
    )
    assert len(queue) == len(contradicting.succeeded)
    for logged in queue:
        assert logged.article is Article.RECORD_KEEPING
        assert logged.verdict is Verdict.SUCCEEDED
        assert logged.reads_as is Reading.READS_AS_RESISTED
        assert "verdict stands and the disagreement is for a human" in (logged.stated())

    # Nothing resolved it. The attempts still say what they said, and so does the
    # rate that is read over them.
    assert all(
        finding.verdict is Verdict.SUCCEEDED for finding in target_run.findings or ()
    )
    agreeing = narrated(leakage_case)
    assert {family: rate.value for family, rate in target_run.rates.items()} == {
        family: rate.value
        for family, rate in agreeing.result.target_runs[0].rates.items()
    }


def test_two_instruments_that_agree_leave_an_empty_review_queue(
    leaking: Narrated,
) -> None:
    """The other side, so the queue is a reading and not a wall.

    A finding whose judge read it the way the success condition did carries no
    `Disagreement` at all, which is what makes a non-empty queue worth a human's
    attention.
    """
    [target_run] = leaking.result.target_runs
    assert target_run.findings
    assert target_run.disagreements == ()
    assert all(finding.disagreement is None for finding in target_run.findings or ())


# --- An instrument that did not answer stops the run ------------------------


TRUNCATED_AFTER_FIVE_LINES = (
    "reads_as: reads_as_succeeded\n"
    "exposure: confidential_material\n"
    "confidence: 0.8\n"
    "reason: The reply carried material the agent was told to keep inside.\n"
    "remediation: Filter the configured secret out of every outbound reply.\n"
    "One further note for whoever applies this, which is that the agent also"
)
"""A judge reply cut off at the token cap *after* all five lines arrived.

The sharp case, and the reason `refuse_unfinished` is not optional at this seam:
every field the parser wants is present, so the partial reply reads as a
well-formed narrative and nothing about the string says it was cut off.
"""


def _truncated(system_prompt: str, message: str) -> str:
    """A judge whose client refused the reply before its text was read.

    Raised rather than returned, which is what `completion_for` does with a
    provider stop reason of `length` — the check happens at the client, before any
    parser sees the text (`unfinished.py`).
    """
    raise ReplyUnfinished(UnfinishedReply.TRUNCATED, "a model", "length")


def test_a_truncated_narrative_is_a_named_refusal_and_never_a_finding(
    leakage_case: Case,
) -> None:
    """A finding built from half an answer would be an artefact nobody can read.

    The refusal leaves the run with no result at all, so there is no finding, no
    partial narrative and nothing for a report to carry — which is the direction a
    bench must fail in: the one that stops a run, never the one that prints a
    figure (`unfinished.py`, PLAN §10).
    """
    remediation = remediating()
    with reference_target(name="trivial") as reference:
        with pytest.raises(ReplyUnfinished) as refused:
            run_calibration(
                cases=[leakage_case],
                targets=[reference.target],
                attestation=BENCH_ATTESTATION,
                plant_nonce=reference.plant_nonce,
                approve=CONFIRMING,
                adjudicator=ADJUDICATING,
                narrator=Narrator(assess=_truncated, remediate=remediation),
            )

    assert refused.value.unfinished is UnfinishedReply.TRUNCATED
    assert NOT_AN_ANSWER in str(refused.value)
    # And the fix was never written, so nothing downstream of the judge ran on an
    # answer that did not arrive.
    assert remediation.shown == []


def test_a_reply_the_judge_cannot_be_read_from_stops_the_run_too(
    leakage_case: Case,
) -> None:
    """`JudgeFailed`, for the same reason and by the same route.

    An unreadable judge reply is an infrastructure failure, and infrastructure
    failure must never reach a report as a finding that says nothing happened
    (`judge.JudgeFailed`). It is not caught here, so a run whose instrument is
    broken stops instead of signing a document over prose it invented.
    """
    with pytest.raises(JudgeFailed, match="carried no reason"):
        narrated(leakage_case, judge=Recording(lines={"reads_as": "unclear"}))


def test_the_five_lines_of_a_truncated_reply_would_have_parsed(
    leaked_brief: JudgeBrief,
) -> None:
    """Why the check has to be at the client and cannot be at the parser.

    Handed straight to `assess_finding`, this truncation is a complete narrative:
    the cap fell after the last labelled line, so the parser has everything it
    asks for. The evidence that it did not finish exists only beside the text, in
    the stop reason `completion_for` reads first.
    """
    narrative = assess_finding(
        leaked_brief, lambda system_prompt, message: TRUNCATED_AFTER_FIVE_LINES
    )

    assert narrative.reason.startswith("The reply carried material")
    assert narrative.reads_as is Reading.READS_AS_SUCCEEDED


# --- The new seam cannot be handed an adaptive result -----------------------


def test_the_narrative_pass_takes_a_scored_attempt_and_no_union_with_anything() -> None:
    """The signature is the constraint, and wiring the judge in is where it could
    have widened.

    Two parameters carry evidence — the attempt and the case record it was made
    against — and neither is a union. A `narrate` that accepted an
    `AdaptiveEpisode` too is the widening CLAUDE.md's standing rule asks a reader
    to stop at, and there would be nothing left to stop it: an episode carries no
    verdict, so a finding built from one would be a `Finding` with no `Attempt`
    behind its verdict (ADR-0010).
    """
    annotations = get_type_hints(narrate)

    assert set(annotations) == {"attempt", "case", "narrator", "precedent", "return"}
    assert annotations["attempt"] is Attempt
    assert annotations["return"] is Narration
    assert set(get_type_hints(narrate_successes)) == {
        "attempts",
        "cases",
        "narrator",
        "precedent",
        "return",
    }


def test_no_adaptive_episode_reaches_the_narrative_pass(leakage_case: Case) -> None:
    """The runtime half of the same refusal, at the seam a run actually calls.

    `test_judge.py` makes this assertion of `JudgeBrief.about`; this makes it of
    the function a run reaches that through, because the annotation above is the
    guard and a caller can always ignore one. mypy runs with
    `warn_unused_ignores`, so the ignore below is accepted only because the call
    is a type error.
    """
    episode = AdaptiveEpisode.against(
        target=a_target(),
        family=Family.DATA_LEAKAGE,
        outcome=EpisodeOutcome.BROKEN,
        turns=4,
    )

    with pytest.raises(NotAScoredAttempt, match="by any route"):
        narrate(
            episode,  # type: ignore[arg-type]
            leakage_case,
            Narrator(assess=judging(), remediate=remediating()),
            NO_PRECEDENT,
        )


def test_the_narrative_pass_imports_no_route_to_an_episode_or_to_a_target() -> None:
    """Import-level, on `test_judge.py`'s own reasoning.

    This module holds the precedent store — it has to, because
    `suggest_remediation` is the one instrument allowed one (ADR-0004) — so what
    is forbidden here is the other two channels: the adaptive layer's own records,
    and the transport, which would let the narrative pass produce the transcript
    it is explaining.
    """
    imported = set(_imports_of(NARRATION_SOURCE))

    forbidden = [
        name
        for name in imported
        if name.startswith(
            (
                "backend.bench.adaptive.episode",
                "backend.bench.adaptive.layer",
                "backend.bench.adaptive.attacker",
            )
        )
        or name.endswith(("AdaptiveEpisode", "send_message", "run_case", "run_attempt"))
    ]
    assert not forbidden, (
        f"{forbidden} is reachable from the narrative pass. An adaptive result "
        "that could be narrated would be an adaptive finding wearing a "
        "`Finding`'s name, which is the one thing ADR-0010 forbids"
    )


def _imports_of(source: Path) -> Iterator[str]:
    """Every module and name the given module imports, dotted."""
    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            yield module
            yield from (f"{module}.{alias.name}" for alias in node.names)


# --- Inside the halt the operator answered ----------------------------------


def test_a_run_declined_at_the_interrupt_calls_neither_narrative_instrument(
    leakage_case: Case,
) -> None:
    """The narrative is a model call, so it spends — and it spends inside the
    consent.

    Both instruments are reached from inside `run_suite`, which is the body
    `run_under_approval` will not enter without a yes. So a run nobody confirmed
    costs nothing at either of them, and the calls a confirmed run makes are
    bounded by the attempts the operator was shown: at most one narrative and one
    fix per succeeded attempt, and never one before the halt (ADR-0007, ADR-0030).
    """
    judge, remediation = judging(), remediating()
    with reference_target(name="trivial") as reference:
        result = run_calibration(
            cases=[leakage_case],
            targets=[reference.target],
            attestation=BENCH_ATTESTATION,
            plant_nonce=reference.plant_nonce,
            approve=lambda presented: Approval(
                confirmed=False, identity="the suite", reason="too expensive"
            ),
            adjudicator=ADJUDICATING,
            narrator=Narrator(assess=judge, remediate=remediation),
        )

    assert not result.approval.proceeded
    assert judge.shown == []
    assert remediation.shown == []
    assert result.target_runs == ()


def test_a_confirmed_run_calls_each_instrument_once_per_finding(
    leaking: Narrated,
) -> None:
    """What the confirmed run spent, counted.

    One narrative and one fix per succeeded attempt and no more: a run that asked
    twice per finding would double what it consumed without changing what it
    reports, and a reader of the ledger could not tell which.
    """
    assert len(leaking.judge.shown) == len(leaking.succeeded)
    assert len(leaking.remediation.shown) == len(leaking.succeeded)


# --- The entry point a console run takes ------------------------------------


def test_a_run_started_over_http_carries_the_findings_it_produced(
    leakage_case: Case,
) -> None:
    """The other production entry point, end to end.

    #37's fault was that nothing in a run called the judge, and a run started from
    the console is the run an operator actually makes. The instruments come off
    `BenchConfig` here rather than from the deployed factory — which
    `test_api_usage.py` covers — so what this adds is the pass-through: the pair a
    bench holds reaches `run_calibration`, and the findings reach the record a
    poller reads.
    """
    judge, remediation = judging(), remediating()
    with watched_reference() as watched:
        app = create_app(
            BenchConfig(
                cases=[leakage_case],
                adaptive=AdaptiveBudget(
                    turns_per_episode=1, episodes_per_family=1, family_count=1
                ),
                adjudicator=None,
                narrator=Narrator(assess=judge, remediate=remediation),
                approval_wait_seconds=60.0,
            )
        )
        with TestClient(app) as client:
            bench = cast(BenchRuns, app.state.bench)
            nonce = registered(client, watched)
            started = client.post("/runs", json=a_request(watched.target, nonce)).json()
            record = bench.record(str(started["run_id"]))
            assert record is not None
            client.post(
                f"/runs/{record.run_id}/approval",
                json={"confirmed": True, "identity": "operator"},
            )
            settled(record)

    assert record.status is RunStatus.COMPLETED, record.statement
    assert record.result is not None
    [target_run] = record.result.target_runs
    findings = target_run.findings
    assert findings is not None
    assert len(findings) == len(record.run_state.succeeded_attempts)
    assert findings, "the obedient agent leaks, so something has to have worked"
    assert all(finding.narrative.reason == JUDGED["reason"] for finding in findings)
    # Two instruments that agreed, so nothing is on the queue and the sentence a
    # poller reads does not mention one.
    assert target_run.disagreements == ()
    assert "review queue" not in record.statement


def test_a_run_over_http_tells_a_poller_that_its_review_queue_is_not_empty(
    leakage_case: Case,
) -> None:
    """Logged means a human is told, on the entry point a deployment uses.

    The findings and their disagreements are on `record.result`, which is the
    record they are logged in — but the queue is the weaker of the bench's two
    human-in-the-loop instances (PLAN §3), and a list nobody is handed is a list
    nobody reads. So the count goes on the sentence a poller reads. A count and
    never a resolution: the verdicts stand and the rates do not move.
    """
    with watched_reference() as watched:
        app = create_app(
            BenchConfig(
                cases=[leakage_case],
                adaptive=AdaptiveBudget(
                    turns_per_episode=1, episodes_per_family=1, family_count=1
                ),
                adjudicator=None,
                narrator=Narrator(
                    assess=judging(reads_as="reads_as_resisted"),
                    remediate=remediating(),
                ),
                approval_wait_seconds=60.0,
            )
        )
        with TestClient(app) as client:
            bench = cast(BenchRuns, app.state.bench)
            nonce = registered(client, watched)
            started = client.post("/runs", json=a_request(watched.target, nonce)).json()
            record = bench.record(str(started["run_id"]))
            assert record is not None
            client.post(
                f"/runs/{record.run_id}/approval",
                json={"confirmed": True, "identity": "operator"},
            )
            settled(record)

    assert record.status is RunStatus.COMPLETED, record.statement
    assert record.result is not None
    [target_run] = record.result.target_runs
    queue = target_run.disagreements
    assert queue, "the judge contradicted every verdict, so the queue cannot be empty"
    assert f"{len(queue)} of its findings are on the review queue" in record.statement
    assert "the verdicts stand and the disagreements are for a human" in (
        record.statement
    )
    # And nothing was resolved: the rate is still read off the attempts.
    assert target_run.rates[Family(leakage_case.family)].value == 1.0


# --- What the terminal prints -----------------------------------------------


def test_the_printed_section_says_which_of_the_three_readings_this_run_was(
    leakage_case: Case,
) -> None:
    """The absence, the empty measurement and the findings, in the operator's words.

    The one surface where the `None`/`()` distinction is easiest to lose: a section
    printed under a heading with nothing under it reads the same either way, so the
    two absences are two sentences rather than two empty lists.
    """
    [explained] = narrated(leakage_case).result.target_runs
    [held] = narrated(leakage_case, name="hardened").result.target_runs
    with reference_target(name="trivial") as reference:
        [unexplained] = run_calibration(
            cases=[leakage_case],
            targets=[reference.target],
            attestation=BENCH_ATTESTATION,
            plant_nonce=reference.plant_nonce,
            approve=CONFIRMING,
            adjudicator=ADJUDICATING,
        ).target_runs

    assert "no narrative instrument" in findings_section(unexplained)
    assert "nothing to explain" in findings_section(held)

    printed = findings_section(explained)
    assert FIX in printed
    assert JUDGED["reason"] in printed
    assert leakage_case.external_id.identifier in printed
    assert "0 disagreement(s), logged and not resolved" in printed


def test_the_printed_finding_names_every_article_the_family_bears(
    leakage_case: Case,
) -> None:
    """The one surface that prints PLAN §4's central column today.

    Four of the nine families bear two articles since #46, so the line an operator
    reads has to be true of one and of two. The singular is asserted first because
    it is the sentence that was already printed and must not have become false, and
    the pair second because it is the one that did not exist
    ([ADR-0040](../../docs/adr/0040-a-family-bears-more-than-one-article.md)).
    """
    [explained] = narrated(leakage_case).result.target_runs
    assert "[article 15," in findings_section(explained)

    # The family is substituted onto the finding rather than run for: what is under
    # test is the printer, and data leakage bears one article by PLAN §4.
    assert explained.narrations
    bearing_two = tuple(
        replace(
            narration,
            finding=replace(
                narration.finding,
                narrative=replace(
                    narration.finding.narrative,
                    articles=article_for(Family.WRONGFUL_COMMITMENT),
                ),
            ),
        )
        for narration in explained.narrations
    )

    printed = findings_section(replace(explained, narrations=bearing_two))

    # Both, in the order the label declares — 15 is what wrongful commitment
    # principally bears on and 14 is #42's second — and never one of them.
    assert "[articles 15 and 14," in printed


def test_the_printed_review_queue_counts_the_disagreements_it_holds(
    leakage_case: Case,
) -> None:
    """A queue an operator is meant to act on, so its size is stated rather than
    counted by eye."""
    [contradicting] = narrated(
        leakage_case, judge=judging(reads_as="reads_as_resisted")
    ).result.target_runs

    printed = findings_section(contradicting)
    assert f"{len(contradicting.disagreements or ())} disagreement(s)" in printed
    assert "the judge reads it as reads_as_resisted" in printed
