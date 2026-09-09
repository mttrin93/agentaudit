---
status: accepted
---

# A compact reading may drop prose, and never a label

The signed payload is composed for a reader who holds only the document. That is why
almost every figure in it travels beside a `stated` sentence: the rate has the rule it
was measured at written out next to it, the temperature says which of two silences it
is, the discovery count says what it is not a summand of. The argument under all of
them is one argument — a figure without its qualification is the badge
[D3](../../PLAN.md) forbids, which is the line
[ADR-0005](./0005-no-composite-risk-score.md) refused a composite score on.

`run_report` is the first place this project summarises its own report, and the reason
it must is arithmetic about somebody else's context window: a whole payload is
thousands of tokens of procurement prose per run, and the two fields the caller wants —
*what went wrong* and *what to change*
([ADR-0069](./0069-the-judge-writes-why-it-failed-the-remediation-tool-writes-what-to-change.md))
— are buried in it. But summarising is exactly how a figure loses its qualification,
and the summariser here is a function this project writes rather than a model it can
blame. So the question this record answers is not *whether* to compact, it is *what a
compaction is not allowed to lose*, in a form a test can hold.

## Decision

**A compact reading may drop prose. It may never drop a label.**

1. **Every closed-set member survives.** `findings.reading`, `reproducibility`,
   `fix_standing.reading`, `source_anchor.reading` and `withheld` are `StrEnum`s, and
   `assembler.FindingsReading`'s docstring already says why. The consequence here is
   the one that binds a compaction: a reading dropped in favour of its sentence hands
   a machine-read caller exactly the prose-matching problem the closed set was made to
   rescue a consumer from — and this caller has no other interface.

2. **Only `stated` and `*_stated` sentences are dropped, and only where a label
   already carries the same fact.** The test is not the field's name; it is whether
   something else in the compact reading still says it. `reproducibility_stated` goes,
   because `reproducibility` beside it is the same fact as a member. The
   attempts-per-case reading stays, and stays verbatim, because it carries a fact **no
   label holds** — the number alone cannot say whether it is the published denominator
   or an operator's cheaper reading (ADR-0025, ADR-0027).

   The rule is about qualification and not about field names, so it reaches one field
   that is neither: where a sentence was withheld for quoting the payload, the finding
   still travels with `PROSE_QUOTED_THE_PAYLOAD` in place of it. That text *is* the
   `reason` or the `fix`, and the spec returns both sentences, so it survives — the
   `withheld` member says which instrument was silenced and not what stands in its
   place.

3. **Nothing is reworded, and nothing is computed.** A sentence that survives survives
   as the bench wrote it. No figure in the compact reading is derived, defaulted or
   recomputed; every number is a payload field copied
   ([ADR-0006](./0006-overrides-never-change-a-measured-rate.md)). A compaction that
   summarised a sentence would be a second author of a claim the signature covers.

4. **The artefact travels as three URLs and not as three bodies.** The payload, the
   rendering and the signature are handed back as locations. A caller that wants the
   document fetches it deliberately, rather than having it summarised into a context
   window by accident, and the signed thing stays the thing that was signed.

5. **The rule is a walk over the payload's own keys, in one function.** A test walks the
   served findings section, collects every closed-set member it finds, and asserts each
   is present in the compact reading. The compaction lives in one function, from the
   payload and nothing else — one place a label could be dropped, so one place to hold.

## Considered options

**Return the whole payload and let the caller ignore what it does not need.** The safe
answer, and it is the one that fails on the consumer this surface exists for: thousands
of tokens per run, most of them addressed to a procurement reader, with `reason` and
`fix` somewhere inside. The predictable outcome is a caller that stops fetching the
report at all, which loses the labels far more completely than a compaction does. It
also makes the document's *deliberate* fetch — decision 4 — meaningless, because the
document arrives whether it was wanted or not.

**A hand-picked list of fields to keep.** This is the shape the code wants to be, and it
stops being correct the day a member is added to any of the five closed sets: the new
member is simply not on the list, nothing fails, and a caller silently never sees it.
That is precisely the failure mode `WithheldProse` and `FindingsReading` were made
closed sets to prevent, reintroduced one layer out. The rule above is a set difference
over the payload's own keys, so a new member is kept by default and a *drop* is what has
to be argued for.

**A rule stated by field name — drop everything matching `*_stated`.** Mechanical, and
wrong at `attempts_per_case_stated`, where the sentence is the only carrier of the fact.
A name-shaped rule would have taken a rate's denominator qualification off a figure a
model then quotes, which is the exact harm.

**Let the model do the compaction.** It would put the summariser on the far side of the
seam, where nothing is testable and the wording of the result is a model's. The reason
`reason` and `fix` are two fields rather than one paragraph is that this project keeps
authorship of its sentences; handing them to a summariser gives that up at the last hop.

## Consequences

- **The rule is testable as a set difference**, and it is tested that way rather than
  reviewed. All four readings of `narrations` are exercised at the tool boundary —
  particularly `instruments_broke`, whose evidence already exists: a compact reading
  that turned a broken judge into an empty findings list would tell a caller the target
  had no failures when the truth is that nothing could be read
  ([ADR-0050](./0050-a-run-whose-narrative-instruments-broke-is-measured-explained-nowhere-and-signable.md)).
- **A fix reaches the caller with its standing beside it**
  ([ADR-0073](./0073-two-labels-on-a-fix-and-no-third.md)), because the standing is a
  label. A suggestion a reviewer acts on is never handed over looking like a change this
  bench proved.
- **Adding a member to any of these closed sets adds it to the compact reading**, with
  no edit here. Adding a *field* does not: a field is prose until some label carries it,
  and the walk is over members.
- **What this record cannot prevent**, and the honest thing to write down now: a caller
  that reads the figures and never fetches the document. The defence here is structural
  — labels survive, prose does not, and the walk enforces it — but whether an agent
  acting on `reason` and `fix` alone acts *well* is unmeasured, and this bench has no
  instrument that would measure it. That is a property of the consumer, not of this
  surface.
