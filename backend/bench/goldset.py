"""The gold set, run through DeepEval, and κ read out of its per-case results.

ADR-0004 requires a stated reliability figure beside every judged rate, and
ADR-0013 says which instrument that figure is about: `adjudication.adjudicate`,
because that is what produces the verdict. ADR-0009 says how it is executed —
DeepEval **runs** the evaluation rather than sitting beside it, because the gold set
already has DeepEval's shape:

| DeepEval | Here |
|---|---|
| `Golden.input` | the `AdjudicationBrief` the instrument sees, rendered |
| `Golden.expected_output` | the hand label |
| `LLMTestCase.actual_output` | the `Verdict` `adjudicate` returned |
| a custom `BaseMetric` | verdict against gold label, threshold 1.0 |
| `evaluate()`'s per-case results | **what κ is computed from** |

The last row is the load-bearing one. κ is not computed from a list this module
kept on the side while DeepEval printed a pass rate: `reliability_from` takes
DeepEval's `TestResult` objects and reads both labels off them, and it refuses a
result whose metric disagreed with the labels it carries. Remove DeepEval and this
figure loses its execution harness, which is what ADR-0009 means by load-bearing.

**The blinding has to survive the harness** (ADR-0009's own amendment). A golden
carrying a transcript is the obvious place for a target name to re-enter, because
`input` is a field a labeller fills by hand. So a gold record holds a *reply* and
never a transcript, and the golden's `input` is built by `AdjudicationBrief.about`
— the same function the run uses, on the harness side of the same call. There is no
field on a gold record through which a target's identity could arrive, and the
labeller's own reasoning stays out of the brief for the same reason.

**The gold label is binary, because the verdict is.** Adjudication has no *unclear*
(ADR-0013), so a transcript a labeller could not decide is not a third label — it is
a transcript that does not belong in a set measuring agreement on a binary decision.
Each gold file therefore carries an `excluded` statement saying what was left out
and why, and a file without one does not load.

**No prose is asserted on anywhere.** The narrative judge's quality has this
evaluation and no other (spec: "Deliberately not unit-tested: the judge's narrative
quality"), and what is measured here is the verdict, which is the thing that lands
in a denominator.
"""

import os
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from deepeval.dataset import EvaluationDataset, Golden
from deepeval.evaluate import evaluate
from deepeval.evaluate.configs import (
    AsyncConfig,
    CacheConfig,
    DisplayConfig,
    ErrorConfig,
)
from deepeval.evaluate.types import TestResult
from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

from backend.bench.adjudication import (
    AdjudicationBrief,
    Completion,
    adjudicate,
)
from backend.bench.evaluator import Verdict
from backend.bench.library import Case, Family, VerdictClass
from backend.bench.rule import DECLARED_RULE, GateRule
from backend.bench.scorer import Reliability, cohens_kappa

AGREEMENT_METRIC = "verdict agrees with the gold label"
"""What the custom metric is called in DeepEval's per-case output."""

AGREEMENT_THRESHOLD = 1.0
"""The metric's pass threshold, and the only value it can be.

Agreement on a binary label is 1 or 0, so a threshold anywhere below 1.0 would pass
a case where the instrument said the opposite of the label. It is declared rather
than inlined for the reason every threshold in this bench is, and it is a *per-case*
bar: whether the family may be reported is κ against `GateRule.kappa_floor`, which
is a different question asked of the set as a whole.
"""


class GoldSetUnusable(ValueError):
    """The gold set cannot measure what it is for, so it does not load.

    Raised before any model call. A reliability figure computed over a set that is
    the wrong size, or labelled one way, or pointed at a case no instrument decides,
    is a number with the authority of κ and none of its meaning — and it would be
    printed beside a judged rate as though it had both.
    """


class ReliabilityUnreadable(RuntimeError):
    """DeepEval's per-case results do not carry a κ can be computed from.

    A named failure rather than a κ of 0.0, on the same reasoning as
    `AdjudicationFailed`: a broken harness reported as perfect disagreement would
    mark a working family unfit, and a broken harness reported as anything at all is
    a number nobody can trace to a transcript.
    """


@dataclass(frozen=True)
class GoldTranscript:
    """One hand-labelled reply, and the labeller's reason for the label.

    The reply and not the transcript it came out of: a `Transcript` carries the url
    it was sent to and the url names the agent, which is the channel ADR-0009's
    amendment closes. What the instrument is shown is built from this by
    `AdjudicationBrief.about`, so this record cannot widen it.
    """

    id: str
    label: Verdict
    reply: str
    labelled_because: str
    """Why the labeller decided it that way, for a reader auditing the set.

    Never shown to the instrument — it is not a field on `AdjudicationBrief`, and it
    could not become one without a labeller's reasoning becoming part of the evidence
    κ is measured on. It exists so that a reader can disagree with a label rather
    than only with the figure.
    """

    def __post_init__(self) -> None:
        if not self.reply.strip():
            raise GoldSetUnusable(f"{self.id} carries no reply to label")
        if not self.labelled_because.strip():
            raise GoldSetUnusable(
                f"{self.id} carries a label with no reason. A gold label a reader "
                "cannot argue with is a reference point they have to take on trust"
            )


@dataclass(frozen=True)
class GoldSet:
    """One judged family's labelled transcripts, held against its case record.

    The case comes off the library rather than being restated here, so the question
    and both sides of the answer that the instrument is measured against are the same
    prose a run would put to it. A gold set that carried its own copy of the criterion
    would let the two drift, and κ would then be a figure about a question no attempt
    was ever decided on.
    """

    case: Case
    labelled_by: str
    labelled_on: date
    excluded: str
    """What was written, left out rather than labelled, and why (ADR-0009).

    Required, because the interesting failure of a gold set is invisible: a set that
    quietly dropped every hard transcript would report a κ about the easy ones and
    look identical to one that had no hard transcripts to drop.
    """

    transcripts: tuple[GoldTranscript, ...]
    rule: GateRule = DECLARED_RULE

    def __post_init__(self) -> None:
        if self.case.verdict_class is not VerdictClass.JUDGED:
            raise GoldSetUnusable(
                f"{self.case.id} is {self.case.verdict_class}, so nothing about it "
                "is decided by the instrument κ measures. A deterministic case's "
                "verdict comes from its success condition (ADR-0004)"
            )
        expected = self.rule.gold_transcripts_per_family
        if len(self.transcripts) != expected:
            raise GoldSetUnusable(
                f"{self.family} carries {len(self.transcripts)} labelled "
                f"transcripts and the declared set is {expected} per judged family. "
                "κ over some other number is not the declared figure"
            )
        ids = [transcript.id for transcript in self.transcripts]
        if len(set(ids)) != len(ids):
            raise GoldSetUnusable(
                f"{self.family} labels the same id twice, so a per-case result "
                "cannot be traced back to one transcript"
            )
        if {transcript.label for transcript in self.transcripts} != set(Verdict):
            raise GoldSetUnusable(
                f"{self.family} is labelled with only "
                f"{sorted({str(t.label) for t in self.transcripts})}. Cohen's κ is "
                "undefined when a rater used a single category, so a one-sided set "
                "measures nothing"
            )
        if not self.excluded.strip():
            raise GoldSetUnusable(
                f"{self.family} states nothing about what was excluded from it. A "
                "set that dropped its hard transcripts silently reports a κ about "
                "the easy ones (ADR-0009)"
            )

    @property
    def family(self) -> Family:
        """The judged family this set measures, read off the case record.

        Off the record and never off the file name, for the reason `verdict_class`
        is: a set moved between files cannot change which family its figure is
        about.
        """
        return self.case.family

    def brief_for(self, transcript: GoldTranscript) -> AdjudicationBrief:
        """The blinded evidence for one labelled reply.

        Built by the same function a run builds a brief with, so the instrument is
        measured on the input it is used on. No tool trace: neither judged criterion
        reads one, and the labels below were made on the reply text alone.
        """
        return AdjudicationBrief.about(self.case, transcript.reply, None)

    def golden_for(self, transcript: GoldTranscript) -> Golden:
        """One labelled reply as a DeepEval golden: input and expected output.

        `input` is the rendered brief rather than the raw reply, because the brief is
        what the instrument under test is given — a golden holding less than that
        would describe an evaluation nobody ran.

        Per transcript rather than only in bulk, so that `run_gold_set` builds each
        test case from the golden rather than deriving the same values a second time
        alongside it. That is what keeps the goldens the thing that ran instead of a
        description of it (ADR-0009), and it means there is no positional pairing of
        two sequences to get wrong.
        """
        return Golden(
            name=transcript.id,
            input=self.brief_for(transcript).rendered(),
            expected_output=str(transcript.label),
            # Text, always: every judged criterion is a question about words.
            multimodal=False,
        )

    def goldens(self) -> tuple[Golden, ...]:
        """The whole set as goldens, in the order the transcripts were labelled in."""
        return tuple(self.golden_for(transcript) for transcript in self.transcripts)

    def dataset(self) -> EvaluationDataset:
        """The goldens as a DeepEval dataset, with no test case in it yet.

        A dataset of goldens is the labelled set; the test cases arrive when an
        instrument has answered, which is `run_gold_set`.
        """
        return EvaluationDataset(goldens=list(self.goldens()))


class VerdictAgreesWithGoldLabel(BaseMetric):  # type: ignore[no-untyped-call]
    """Did the instrument's verdict match the hand label? One case, 1.0 or 0.0.

    A custom metric rather than one of DeepEval's built-ins, and it makes no model
    call of its own. Every stock semantic metric would score this with an LLM, which
    would put a second model between the instrument and its reference labels — the
    reliability figure would then be about the pair, and a disagreement would be
    unattributable. What is being measured is already a comparison of two labels, so
    the metric is that comparison.

    `success` is the per-case bar and decides nothing about the family. κ decides
    that, from the per-case results this metric produces.
    """

    def __init__(self) -> None:
        # No threshold parameter. `AGREEMENT_THRESHOLD` is the only value this metric
        # can be scored at, so taking one would offer a caller a bar that passes a
        # case where the instrument said the opposite of the label. The framework's
        # own `threshold` is set from the same constant, and the comparison below
        # reads the constant rather than the attribute — DeepEval declares
        # `threshold` optional, and a per-case bar that can go missing is a case that
        # can be scored against nothing.
        self.threshold = AGREEMENT_THRESHOLD
        self.async_mode = False
        self.include_reason = True

    def measure(self, test_case: LLMTestCase, *args: Any, **kwargs: Any) -> float:
        expected, actual = test_case.expected_output, test_case.actual_output
        score = 1.0 if expected == actual else 0.0
        self.score = score
        self.reason = (
            f"both {actual!r}"
            if score >= AGREEMENT_THRESHOLD
            else f"gold label {expected!r}, instrument verdict {actual!r}"
        )
        self.success = score >= AGREEMENT_THRESHOLD
        return score

    async def a_measure(
        self, test_case: LLMTestCase, *args: Any, **kwargs: Any
    ) -> float:
        """No I/O to await. Present because `BaseMetric` declares it abstract."""
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self) -> str:
        return AGREEMENT_METRIC


def load_gold_sets(directory: Path, library: Sequence[Case]) -> tuple[GoldSet, ...]:
    """Every gold set in a directory, ordered by file name for a stable run order."""
    return tuple(
        load_gold_set(path, library) for path in sorted(directory.glob("*.toml"))
    )


def load_gold_set(path: Path, library: Sequence[Case]) -> GoldSet:
    """One gold set, with its case resolved against the live library.

    Against the library rather than against a copy, so that a case whose criterion is
    edited invalidates the figure rather than silently keeping it: κ is a statement
    about the instrument applying *that* question, and a set pointing at an id the
    library does not hold cannot be run at all.
    """
    record: dict[str, Any] = tomllib.loads(path.read_text(encoding="utf-8"))
    case_id = record["case_id"]
    case = next((case for case in library if case.id == case_id), None)
    if case is None:
        raise GoldSetUnusable(
            f"{path.name} labels transcripts for {case_id!r}, which is not in the "
            "library it was given. The criterion κ is measured against lives on the "
            "case record, so a set that cannot find its case cannot be run"
        )
    return GoldSet(
        case=case,
        labelled_by=record["labelled_by"],
        labelled_on=record["labelled_on"],
        excluded=record["excluded"],
        transcripts=tuple(
            GoldTranscript(
                id=transcript["id"],
                label=Verdict(transcript["label"]),
                reply=transcript["reply"],
                labelled_because=transcript["labelled_because"],
            )
            for transcript in record["transcript"]
        ),
    )


def run_gold_set(gold: GoldSet, complete: Completion) -> tuple[TestResult, ...]:
    """Adjudicate every labelled reply, then let DeepEval score the set.

    **Each test case is built from its golden**, not from the gold record a second
    time: the golden supplies the `input` and the `expected_output`, and the
    instrument supplies the `actual_output`. That is the shape ADR-0009 describes, and
    building the input twice would leave the goldens as a description of an evaluation
    rather than the thing that ran — which is the "bolted-on DeepEval run alongside
    the real statistics" the ADR rejected.

    The instrument is asked once per transcript through `adjudicate`, so what is
    measured is the function a run calls and not a re-implementation of it. An
    unreadable answer raises `AdjudicationFailed` out of here rather than becoming a
    disagreement: an instrument that failed to answer is not an instrument that
    answered wrongly.

    Returns DeepEval's per-case results, which are the input κ is computed from.
    """
    _opt_out_of_telemetry()
    metrics: list[BaseMetric] = [VerdictAgreesWithGoldLabel()]
    dataset = gold.dataset()
    for transcript in gold.transcripts:
        golden = gold.golden_for(transcript)
        dataset.add_test_case(
            LLMTestCase(
                name=golden.name,
                input=golden.input,
                expected_output=golden.expected_output,
                actual_output=str(adjudicate(gold.brief_for(transcript), complete)),
            )
        )
    evaluated = evaluate(
        test_cases=[
            case for case in dataset.test_cases if isinstance(case, LLMTestCase)
        ],
        metrics=metrics,
        # Nothing here reaches the network, and the run has to stay that way: the
        # bench's own reliability figure is measured offline, and CI says so. The
        # metric is synchronous, the cache would carry a previous run's scores into
        # this one, and `inspect_after_run` would stop for a prompt no CI can answer.
        async_config=AsyncConfig(run_async=False),
        display_config=DisplayConfig(
            show_indicator=False, print_results=False, inspect_after_run=False
        ),
        cache_config=CacheConfig(write_cache=False, use_cache=False),
        error_config=ErrorConfig(ignore_errors=False),
    )
    return tuple(evaluated.test_results)


def reliability_from(
    family: Family, results: Sequence[TestResult], rule: GateRule = DECLARED_RULE
) -> Reliability:
    """κ for one judged family, computed from DeepEval's per-case results.

    From the results and from nothing else — both labels are read off each
    `TestResult`, and the metric's own per-case verdict is checked against them. If
    the two ever disagree, the harness is wrong about something and no figure is
    returned: a κ that does not match the pass marks printed beside it is worse than
    no κ, because both look authoritative.
    """
    if len(results) != rule.gold_transcripts_per_family:
        raise ReliabilityUnreadable(
            f"{family} was scored over {len(results)} cases and the declared gold "
            f"set is {rule.gold_transcripts_per_family} per judged family"
        )
    pairs = tuple(_labels_in(result) for result in results)
    return Reliability(
        family=family,
        kappa=cohens_kappa(pairs),
        agreements=sum(1 for gold, instrument in pairs if gold is instrument),
        transcripts=len(pairs),
        rule=rule,
    )


def measure_reliability(
    sets: Sequence[GoldSet], complete: Completion, rule: GateRule = DECLARED_RULE
) -> Mapping[Family, Reliability]:
    """Run every gold set and return κ per judged family.

    Per family and never pooled: a pooled figure would let a family the instrument
    reads well carry one it reads badly, and each judged family is reported with its
    own limits attached (spec story 34).
    """
    return {
        gold.family: reliability_from(gold.family, run_gold_set(gold, complete), rule)
        for gold in sets
    }


def _opt_out_of_telemetry() -> None:
    """Turn off the framework's usage telemetry before it is asked to run anything.

    Named for what it sets rather than for the state it leaves behind, because it is a
    process-global side effect and a caller reading `run_gold_set` has to be able to
    see that.

    Set rather than defaulted, and set here rather than left to whoever runs the
    bench. DeepEval reports usage events to its vendor unless told not to, and this
    run measures the bench's own instrument: an evaluation that posts an event about
    itself makes the suite's claim to reach no network false, and it does so in the
    one code path whose whole purpose is a figure a reader has to be able to trust.
    The setting is read per call, so this takes effect on the run below.
    """
    os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "1"


def _labels_in(result: TestResult) -> tuple[Verdict, Verdict]:
    """The gold label and the instrument's verdict, off one per-case result."""
    scored = [
        metric
        for metric in (result.metrics_data or [])
        if metric.name == AGREEMENT_METRIC
    ]
    if not scored:
        raise ReliabilityUnreadable(
            f"{result.name} carries no {AGREEMENT_METRIC!r} result, so this case was "
            "not scored and cannot be counted as agreement or disagreement"
        )
    gold, instrument = (
        _verdict_in(result.expected_output),
        _verdict_in(result.actual_output),
    )
    agreed = gold is instrument
    if any(metric.success is not agreed for metric in scored):
        raise ReliabilityUnreadable(
            f"{result.name} was scored {[m.success for m in scored]} and its labels "
            f"say {agreed}. The metric and κ would be reading the same case two ways"
        )
    return gold, instrument


def _verdict_in(label: object) -> Verdict:
    """One label off a per-case result, or a named failure.

    `Verdict`'s own members and nothing wider, so a result carrying a third label —
    or an absent one, or the image list DeepEval's field type also allows — stops the
    figure rather than being coerced into one of the two.
    """
    complaint = (
        f"a per-case result carries {label!r}, which is not one of "
        f"{', '.join(verdict for verdict in Verdict)}"
    )
    if not isinstance(label, str):
        raise ReliabilityUnreadable(complaint)
    try:
        return Verdict(label)
    except ValueError as unknown:
        raise ReliabilityUnreadable(complaint) from unknown
