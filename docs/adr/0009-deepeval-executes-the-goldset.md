---
status: accepted
---

# DeepEval executes the gold set; the discrimination statistics sit on top

The hard optional task is worded "provide an AI evaluation report that proves the quality of your application using Ragas or DeepEval." This project's evaluation harness is bespoke — discrimination scores, Wilson intervals, monotonicity across three reference agents, Cohen's κ against a hand-labelled gold set — and is stronger than a stock framework run, but a strict reviewer could rule the named-tool requirement unmet, leaving exactly one hard task with no margin.

**Decision.** DeepEval **executes** the judge-reliability evaluation rather than sitting beside it. The 30-transcript κ gold set is already a labelled dataset in DeepEval's shape: a `Golden` carries `input` and `expected_output` (the transcript and its hand label), an `LLMTestCase` carries `actual_output` from `assess_finding`, a custom `BaseMetric` implements `measure` / `is_successful` as judge-verdict-versus-gold-label, and `dataset.evaluate()` runs the set. **κ is then computed from DeepEval's per-case results**, not alongside them.

## Considered options

- **Argue the requirement away in the README** — "Ragas measures RAG faithfulness and this system has no retrieval." True of Ragas, and it defeats only half the sentence: the task says Ragas *or* DeepEval, and DeepEval carries no RAG assumption. The argument does not reach it.
- **A bolted-on DeepEval run alongside the real statistics** — duplicated work that reads as compliance theatre, and a strict reviewer is precisely the reader who notices.

## Consequences

DeepEval is load-bearing: remove it and the κ figure loses its execution harness. The bespoke statistics remain, because no off-the-shelf framework offers a discrimination test *between reference systems* — that claim goes in the README beside the DeepEval one, and "used the named tool, then went past it" is the position that survives a strict review.

`LLMTestCase` also carries `tools_called`, which is the natural home for the scope-creep and halt-defeat success conditions if the deterministic families are ever expressed as DeepEval test cases. Not now — the deterministic verdict path stays independent of any evaluation framework, per [ADR-0004](./0004-deterministic-verdicts-judge-is-narrative.md).
