---
status: accepted
---

# DeepEval executes the gold set; the discrimination statistics sit on top

The hard optional task is worded "provide an AI evaluation report that proves the quality of your application using Ragas or DeepEval." This project's evaluation harness is bespoke — discrimination scores, Wilson intervals, monotonicity across three reference agents, Cohen's κ against a hand-labelled gold set — and is stronger than a stock framework run, but a strict reviewer could rule the named-tool requirement unmet, leaving exactly one hard task with no margin.

**Decision.** DeepEval **executes** the judge-reliability evaluation rather than sitting beside it. The 30-transcript κ gold set is already a labelled dataset in DeepEval's shape: a `Golden` carries `input` and `expected_output` (the transcript and its hand label), an `LLMTestCase` carries `actual_output` from the instrument under test, a custom `BaseMetric` implements `measure` / `is_successful` as instrument-verdict-versus-gold-label, and `dataset.evaluate()` runs the set. **κ is then computed from DeepEval's per-case results**, not alongside them.

## Amendment: the instrument under test is `adjudicate`, not `assess_finding`

This ADR was written when the judge was the only semantic component in the design, and it named `assess_finding` as the source of `actual_output`. That is now the wrong component. [ADR-0013](./0013-adjudication-is-a-third-instrument.md) records why a judged verdict cannot come from the judge — ADR-0004 forbids it — and gives that verdict its own instrument, `adjudication.adjudicate`.

**κ measures whatever produces the judged verdict.** A reliability figure on `assess_finding` would be a figure about narrative fields that decide nothing, printed beside a rate it did not produce, and it would satisfy ADR-0004's "stated reliability figure" in letter while measuring the wrong object. So `actual_output` in the `LLMTestCase` is the `Verdict` returned by `adjudicate`, `expected_output` is the hand label, and the custom metric compares those two. The gold set is unchanged: 30 transcripts, 15 per judged family, hand-labelled.

Two consequences follow from the amendment rather than from the original decision:

- **The gold label is binary, because the verdict is.** Adjudication has no `unclear` (ADR-0013), so a transcript a labeller could not decide is not a `Golden` with a third label — it is a transcript that does not belong in a set measuring agreement on a binary decision, and the reason it was excluded is recorded with the set.
- **The blinding has to survive the harness.** `assess_finding` is blinded by ADR-0004 and `adjudicate` by ADR-0013, and a DeepEval `Golden` carrying a transcript is the obvious place for a target name to re-enter: `input` is a field a labeller fills by hand. The gold set therefore stores the same `AdjudicationBrief` the instrument sees in a run, not the raw transcript it was built from.

## Considered options

- **Argue the requirement away in the README** — "Ragas measures RAG faithfulness and this system has no retrieval." True of Ragas, and it defeats only half the sentence: the task says Ragas *or* DeepEval, and DeepEval carries no RAG assumption. The argument does not reach it.
- **A bolted-on DeepEval run alongside the real statistics** — duplicated work that reads as compliance theatre, and a strict reviewer is precisely the reader who notices.

## Consequences

DeepEval is load-bearing: remove it and the κ figure loses its execution harness. The bespoke statistics remain, because no off-the-shelf framework offers a discrimination test *between reference systems* — that claim goes in the README beside the DeepEval one, and "used the named tool, then went past it" is the position that survives a strict review.

`LLMTestCase` also carries `tools_called`, which is the natural home for the scope-creep and halt-defeat success conditions if the deterministic families are ever expressed as DeepEval test cases. Not now — the deterministic verdict path stays independent of any evaluation framework, per [ADR-0004](./0004-deterministic-verdicts-judge-is-narrative.md).
