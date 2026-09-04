---
status: accepted
amends: 0048-a-retrieved-family-grows-by-technique-and-not-by-count.md
---

# An agentic scorer's canary is a two-part construction, and no general-purpose corpus contains one

[ADR-0048](./0048-a-retrieved-family-grows-by-technique-and-not-by-count.md) decided that a corpus-grown family grows by technique rather than by count, and predicted a single-digit family for `ElectiveFamily.DIRECT_PROMPT_INJECTION`. The technique half was right. **The case yield is zero, and the reason is structural rather than a matter of yield at all.**

#67 step 2 retrieved 70 candidates at `k = 70` against the re-keyed override query and read every one by hand: 27 are genuine overrides (38.6% precision, on #64's falling curve), and the distinct-technique floor takes those 27 down to **six techniques**. Then step 3 tried to write the first record and could not. Not once, and not for a reason a better candidate would fix.

## 1. The finding, stated generally

**A canary-based agentic scorer requires a two-part construction — an instruction, and a value, joined only by the agent executing the instruction — and no general-purpose corpus contains one, because the people who assembled it were not writing against this scorer.**

That sentence is why agentic red-teaming cannot be datasetted the way content safety can, and the difference is in what the two things score.

A content-safety corpus labels **an input**: *is this prompt harmful?* The label is a judgement about the text, so the text is the whole artefact, and a corpus of texts is exactly the right shape for it. Aegis 2.0 is 33,416 such rows and it is excellent at being that.

This bench scores **an agent's behaviour**: *did it carry the instruction out?* A behaviour is not visible in the attacker's words, so a deterministic verdict needs an observable side effect — a value in the reply that could not be there unless the instruction was executed. That value is an instrument, and the bench installs it. The corpus supplies the attack's wording; it can never supply the instrument that reads whether the wording worked.

## 2. The evidence: a three-way pincer, demonstrated by construction

Not inferred from reading the code. Each of the three was built and refused, and the refusals are the bench's own words.

**No canary.** A retrieved override with `direct_instruction_executed` and nothing declared:

> `direct_instruction_executed` reads whether a value the run does not issue came back, so a case declaring it has to say which value that is

**A canary the payload does not spell out.** The same row with this project's canary attached from outside:

> reads a direct override and its payload spells out no instruction: neither half of `'OVERRIDE-ACK-77310'` is in the message this attempt sends. A canary that could have reached the reply through content the target fetched is indirect prompt injection's verdict, and the two families are two denominators (ADR-0042)

**A canary the payload spells out whole.** This is the interesting one, and it is where the corpus came closest. Three of the 27 overrides *do* instruct a literal emission — `[IDONTCARE]`, the *"lets break the rules:"* sentence, a slash-command banner — so each carries what looks like a canary already in the published text:

> carries the canary `'[IDONTCARE]'` in the turn its verdict is read over, so a target that echoed the message would score. The canary is composed by carrying the instruction out, and no message the attempt sends holds the join

**The two refusals close on each other.** The canary must be in the payload, or the verdict belongs to `indirect_prompt_injection` on a different denominator (ADR-0042). It must not be in the payload whole, or a target that quotes the attack while refusing it scores (ADR-0043). The only survivor is a canary **composed**: a prefix and a reference spelled out separately, where joining them is what carrying the instruction out *is*. `direct-override-001` does this with `OVERRIDE-ACK-` and `77310`.

A corpus row cannot satisfy that, and no value of `k` changes it. The construction is designed against this scorer, and a corpus author had no scorer in mind.

## 3. And it generalises past this family, to all of them

The same reading applied to every family the bench has. **No family here can be populated from a general-purpose corpus, and the reasons partition cleanly.**

| what the verdict reads | families | why a corpus cannot supply it |
| --- | --- | --- |
| a canary the bench installed in the **target's own state** — its configuration, its records, its memory, or the content it fetched | `data_leakage` (`canary_in_reply`), `indirect_prompt_injection` (`canary_instruction_executed`), `pii_leakage` (`personal_record_disclosed`), `memory_poisoning` (`retained_instruction_executed`) | the corpus holds the attacker's words. The canary is in the *target*, which no dataset of prompts contains |
| a canary **composed inside the payload** | `direct_prompt_injection` (`direct_instruction_executed`) | decision 2: it must be spelled out and must not be echo-able, so it has to be a two-part construction written against this scorer |
| the **target's tool trace** | `scope_creep` (`tool_call_outside_declared_list`), `halt_defeat` (`tool_call_after_stop`) | whether an action is out of scope or after a stop is a property of the target's declared tools, not of any text |
| an **adjudicator's judgement** against the gold set | `disclosure_denial`, `wrongful_commitment` | not *cannot* but **must not**: a retrieved phrasing inside a κ-gated denominator is material nothing here measured reaching the one figure this bench has to earn (ADR-0013, ADR-0047 decision 4) |

Only the middle row was ever in doubt, and it is now decided. The bench's own vocabulary said this before it was measured — CONTEXT.md's **candidate** entry has always insisted that a retrieved row "has no family, no verdict, no **trigger** and no criterion, and it acquires none by being retrieved". *No criterion* turns out to be the load-bearing clause.

## 4. Nothing is removed, and the corpus track stays

The pipeline is kept exactly as it is. `ElectiveFamily.DIRECT_PROMPT_INJECTION` stays on the elective tier, still decides no gate, and keeps its three authored cases; the ChromaDB store, `scripts/index_corpus.py`, `scripts/retrieve_candidates.py`, `scripts/assign_candidates.py`, the near-duplicate floor, the assignment instrument and its κ, `RetrievedFrom`, `Trigger.PUBLISHED_CORPUS_SEARCHED`, `DiscoveredBy.RETRIEVED` and ADR-0048's technique floor all stay.

**What stops is trying to admit cases from it.** That is a decision about what to do next and not a repeal: the shape a retrieved case would take is decided, tested and unused, and the first corpus that carries a scorer's instrument would find it waiting. Deleting the apparatus would also delete the evidence for this ADR.

## Considered options

- **Part-author cases around retrieved skeletons: take the published override, splice a composed canary into it, extend the reference agents to recognise it.** Rejected, and it is the only option that would have produced cases. Two costs, both structural. It breaks [ADR-0047](./0047-a-retrieved-case-cites-its-row-and-a-person-signs-for-its-family.md)'s citation claim, whose whole argument is that "a reader can establish that this text is that row without this repository's help" — a payload that is the row *plus our canary instruction* is not that row, and `RetrievedFrom.address` would be citing something the record does not contain. And it means editing `backend/targets/reference/overrides.py`, whose three entries "differ in the mechanism rather than in the wording": the reference agents are the instrument this family's `D` is measured against, and extending them mid-group changes the calibration the gradient rests on. Paid for a family that decides no gate, on the strength of a corpus that supplied the wording and none of the mechanism.
- **Relax the canary discipline for retrieved cases — accept an echo-able canary and read the reply more cleverly.** Rejected on ADR-0043 and ADR-0042 together. The echo refusal exists because a target that quotes the attack while refusing it must not score, which is the difference between measuring a defence and measuring a parrot; and the spelled-out requirement exists because the same canary reachable through fetched content is the *other* family's verdict. Relaxing either one buys cases by making the verdicts mean less, which is the trade this bench exists to refuse.
- **A second corpus.** Not rejected — deferred, and this ADR is what a future one is measured against. HarmBench and WildGuardMix are prompt datasets of the same shape, so decision 3 predicts the same zero for both; `docs/validation.md` already records WildGuardMix as unusable as a κ reference. What *would* work is a corpus of agent **transcripts** with tool traces, or one built against a canary scorer. Neither is a search-surface problem.
- **Report the six techniques as six cases and note the canary as an outstanding task.** Rejected: a case that cannot load is not a case, and a library holding six of them would fail `load_elective` on every run. There is no partial credit available here, which is the type doing its job.
- **Widen `SuccessConditionKind` with a kind that reads a model's compliance in prose.** Rejected. That is an adjudicator, it would put a retrieved phrasing upstream of a κ, and ADR-0047 decision 4 refuses exactly that at both ends.

## Consequences

- **#67 is delivered, and the deliverable is the finding.** Not a populated family. What the RAG work shipped is the ChromaDB vector store over 28,214 indexed rows, the retrieval and selection pipeline with a measured near-duplicate floor, the family-assignment instrument with its κ, the retrieved-case record shape with its provenance and its technique floor — and this measured negative result, which is the most transferable thing in the group.
- **ADR-0048's single-digit prediction is corrected in the half that was wrong.** Six distinct techniques, and zero admissible cases. The floor was never reached, because the load refusals fire first.
- **`docs/validation.md` carries the k=70 reading** — 70 selected, 31 suppressed, 27 overrides at 38.6% precision, six techniques, zero cases — with the candidate-to-technique mapping in `scratchpad/hand-reading-k70.md`.
- **`test_no_case_in_the_library_claims_the_seventh_trigger_yet` stops being a tripwire and becomes a finding.** It pins the library at zero retrieved cases, and the reason is no longer "nobody has done the work yet" but "the work does not terminate". It stays, and its comment says which.
- **No rate, `D`, κ, band, gate decision, gate citation or library digest moves**, because no case was written. The gate run #67 planned has nothing to run on and is not deferred — it is withdrawn.
- **PLAN §14's RAG answer is complete now rather than provisional.** Retrieval over the case library was built, measured, and found to help with selection and not with population; and the reason is a property of agentic scoring rather than of this corpus.
