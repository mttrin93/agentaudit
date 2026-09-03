# Spec — The elective family tier

**Scope:** the tier itself, as a phase of its own. [PLAN.md](../../PLAN.md) §5 P2, and the first of the ten sub-issues of Group G.

**A phase of its own, deliberately.** [The pre-web bench](./pre-web-bench.md) lists "**everything in P2**, including new families to close declared coverage gaps" as out of scope, and [the signed report](./signed-report-and-delivery.md) has no family work in it at all. The tier is therefore not an amendment to either: it changes what a **family** can be, which is load-bearing arithmetic in both, and a phase that changes an arithmetic gets its own scope statement rather than a paragraph appended to a spec that was written before it.
**Governing documents:** [PLAN.md](../../PLAN.md) · [CONTEXT.md](../../CONTEXT.md) · [ADR-0035](../adr/0035-the-elective-family-tier-is-never-gate-deciding.md), and the four it stands on — [ADR-0003](../adr/0003-gate-decision-rule-and-sample-size.md), [ADR-0010](../adr/0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md), [ADR-0015](../adr/0015-the-gate-is-decided-over-families-fit-to-report.md), [ADR-0022](../adr/0022-the-retirement-window-is-two-readings-of-one-model.md)
**Vocabulary:** every term below is defined in `CONTEXT.md`. **Family** and **elective family** are two different things and every count in this spec depends on that, for the same reason **attempt** and **episode** are two different things. A **case**, an **attempt** and a **decay series** mean exactly what they already mean, whichever tier the family belongs to.

---

## Problem Statement

The bench tests six families and the gate is decided over those six. Group G selects three more — `ASI06` memory poisoning, `LLM01` direct prompt injection and `LLM02` PII leakage — and each of them is an attack the bench cannot currently hold. (Group G's fourth missing row, the Rule of Two, is [not a family](../adr/0038-the-rule-of-two-is-a-declared-property.md) and lands in the configuration scan, where it is read off what the operator declares.)

Adding them to `Family` is the obvious move and it re-opens a closed argument. [ADR-0015](../adr/0015-the-gate-is-decided-over-families-fit-to-report.md) spent its whole length proving that `families_required = 4` and `monotonic_families_required = 5` must be **fixed counts** over a fixed `family_count = 6`, and that a family leaving the decision may only ever remove a candidate from a count and never lower a bar. A seventh family in the denominator either re-opens that or forces the threshold move [ADR-0003](../adr/0003-gate-decision-rule-and-sample-size.md) exists to prevent — at hour 30, to make a run pass.

Keeping them out of the gate entirely is the other obvious move, and it is worse. A family the bench runs against a user's target and has never measured its own discriminating power on is exactly the unvalidated instrument this project's first spec exists to refuse. **Selectable is not ungated.**

And a family the operator can switch off introduces a lever nobody has argued about. On a target run a selection is a lever on the dominant cost, which is the point of having one. On a **gate** run the same lever is a way to skip a family that was about to fail, or to park one out of the runs that would have retired its cases. That reading has to be closed by an invariant rather than by nobody thinking of it.

## Solution

A second tier of families, measured by the gate on the gate's own terms and unable to decide it, with the prohibition carried by the type system rather than by a flag.

`library.ElectiveFamily` is a closed set disjoint from `Family`. An elective family runs against the three reference agents on every gate run it is requested for and faces `scorer.separation` — the *one* implementation of the per-family pass condition, `D ≥ discrimination_floor` with the two Wilson intervals apart, which `score_family` reads too — and accumulates a decay series on each of its cases. Its reading is carried by `ElectiveRates` and `ElectiveOutcome`, which are **not** the records `decide_gate` consumes — so there is no argument anywhere through which an elective figure could reach either of the gate's counts, and the only way to build one would be to write a union into a signature that a test asserts against.

The tier reports in its own section, on the discipline [ADR-0010](../adr/0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md) established for the adaptive layer: the part of a run that decides nothing prints beside the decision rather than inside it. The gate document names every declared elective family — measured with its figures, requested-and-unread with the reason, or **not requested** by name — which is ADR-0015 §6's rule that an exclusion prints in the decision, read one level down.

A target report says which elective families the run was not asked for and nothing else about the tier. That is a fifth kind of nothing beside the four `payload.py` already keeps apart, and it is where the tier meets [ADR-0018](../adr/0018-the-report-is-about-a-target-the-gate-is-about-the-bench.md): a `D` is a claim about the bench, so the tier's figures print where the bench's figures print.

**Promotion, not accretion.** Three consecutive gate runs on the field at `D ≥ 0.4` make an elective family eligible to enter the six. Entry is a library-version event that re-declares the gate rule before the run it applies to, so nothing in the code performs it. And the lever is closed by one invariant, tested as an invariant:

> Skipping an elective family can never be advantageous.

Two halves, and they pull in opposite directions. A skipped gate run breaks the promotion streak, so skipping buys no progress. A skipped gate run does not reset the retirement window, so skipping buys no protection. The first is read over a **ledger of gate runs** and the second over a **decay series**, and the difference between them is a type.

## User Stories

Numbered from one, as [the signed report](./signed-report-and-delivery.md)'s are: a bare *spec story 72* in a docstring means the pre-web bench's list, and a second list continuing its numbering would make every such reference ambiguous.

### The tier, declared

1. As a bench engineer, I want the six families and the elective families held in two separate closed sets, so that a value naming an elective family cannot be assigned where the gate's counts are taken.
2. As a bench engineer, I want the records the gate decision is built from annotated over the six alone, so that widening one is a visible edit a test fails on rather than a forgotten condition.
3. As a reviewer, I want no threshold in the gate rule to move when the tier arrives, so that the argument ADR-0015 settled is not re-opened by an addition.
4. As a bench engineer, I want the tier's own promotion threshold declared outside the gate rule, so that nothing which decides nothing about this run appears in the bar this run had to clear.

### Gate-measured, and held to the same bar

5. As a bench engineer, I want an elective family's `D`, interval separation and ordering computed by the same functions the gate is decided by, so that a figure printed beside the six was measured the way the six were.
6. As a bench engineer, I want an elective family held to the declared discrimination floor rather than a softer one, so that "selectable is not ungated" is a property and not a slogan.
7. As a bench engineer, I want an elective family's cases to carry a decay series and face the retirement rule like any others, so that a tier nobody has to pass cannot quietly accumulate cases that stopped discriminating.
8. As a reviewer, I want an elective family's reading printed on every gate run it was requested for, so that the tier's discriminating power is falsifiable rather than asserted at promotion time.

### Never gate-deciding

9. As a reviewer, I want an elective family that clears every clause of the per-family rule to move neither of the gate's two counts, so that the tier cannot prop up a pass.
10. As a reviewer, I want that property asserted by deciding one gate run twice — once with the elective reading and once without — and comparing the whole decision, so that a contribution nobody named a contribution is still caught.
11. As a bench engineer, I want the elective section held beside the gate decision and not within it, so that there is no field of the decision an elective figure can be reached through.

### Selection as a declared input

12. As an operator, I want to select elective families at a target run, so that I have a lever on the dominant cost of a run.
13. As an operator, I want to select elective families at a gate run, so that the bench can measure a family it is not yet ready to be decided over.
14. As a bench engineer, I want the selection stated before the run and unmovable by anything the run measures, so that it is a declared input on the footing of the declared models and the declared denominator.
15. As a reviewer, I want the families a run did not request named in the gate document, so that the scope of a gate run is recoverable from the gate run rather than from whoever started it.

### Skipping is never advantageous

16. As a reviewer, I want a gate run an elective family was not requested for to break its promotion streak, so that skipping the run that was about to read low buys no progress toward the six.
17. As a reviewer, I want a gate run an elective family was not requested for to leave the retirement window untouched, so that parking a family out of the next few runs buys its cases no protection.
18. As a bench engineer, I want a skipped run represented by a type rather than by an absence, so that the same fact can be counted by one rule and invisible to the other without either rule guessing.
19. As a bench engineer, I want a reading taken on a stub model to break the streak too, so that no run which produced no evidence about the field pays toward a claim about the field.
20. As a bench engineer, I want the streak to count only readings the per-family rule itself passes, so that promotion cannot be earned on separation the gate would refuse.
21. As a bench engineer, I want the promotion ledger read over a family-level reading and the retirement window over a case's decay series, so that a claim about a family is never read off one case's counts.

### The fifth kind of nothing

22. As a procurement reader, I want a family this run was not asked to test named as *not requested* rather than as a coverage gap or an unmeasurable family, so that I can tell the five reasons a family is missing from the figures apart without reading a footnote.
23. As a procurement reader, I want no rate, interval, band or `D` for any elective family in a target report, so that a figure about the bench cannot be read as a figure about the agent I am buying.
24. As a bench engineer, I want the fifth absence derived from the run's declared selection rather than supplied by a caller, so that forgetting to ask cannot delete it.
25. As a procurement reader, I want the elective families this run *was* asked to test named too, so that a run which requested all of them is not a report that says nothing about the tier at all.

### Promotion

26. As a bench engineer, I want promotion to confer **eligibility** and never perform entry, so that the rule the bench is held to is never changed by a counter reaching a number.
27. As a reviewer, I want the number of runs argued in an ADR rather than inherited from a planning table, so that the threshold has an author.

## Implementation Decisions

**The tier is two enumerations, not one enumeration and a flag.** Argued in [ADR-0035](../adr/0035-the-elective-family-tier-is-never-gate-deciding.md). The consequence in this scope is that `gate.family_rates`, `decide_gate`, `MeasuredSection` and `TargetRun.rates` are closed against the tier by the type checker, and the deciding records' annotations are asserted by a test that fails on a widening.

**The arithmetic is shared below the family type.** `scorer.discrimination`, `intervals_overlap`, `monotonicity` and `reaches` take `Rate`s and know nothing about families, so `score_elective` reuses them exactly. Nothing in `elective.py` divides anything, on the discipline `retirement.py` already follows.

**An elective family's case is an ordinary `Case`, and an elective attempt is an attempt.** No new unit. `Case.family` and `Attempt.family` widen to `Family | ElectiveFamily` when the first elective case lands, and the deciding containers deliberately do not follow — `TargetRun.rates` stays keyed on `Family` and the elective counts arrive in a second mapping. The type checker demands that split at every site that groups attempts by family.

**The promotion rule reads a family's ledger; the retirement rule reads a case's series.** `LedgerEntry = ElectiveReading | Skipped`, where an `ElectiveReading` carries the family's whole scored outcome for one gate run. A `GateReading` is *one per case per gate run* and belongs to the decay series, so reading a family-level streak off one would answer a question about a case. The window's transparency across a gap is the explicit form of a choice that used to fall out of `history[-2:]` being positional.

**No threshold moves, and the tier's own threshold is not in `GateRule`.** Asserted by a test that reads the fields of `GateRule` as well as the text it prints, mirroring the wall already held against `T` and `k`.

## Testing Decisions

**The two structural assertions are the ones worth reading.** The tier's central claim is a prohibition, and a prohibition is only kept by structure: the deciding records' annotations are asserted directly, and the indifference of the decision is asserted by deciding one gate run twice and comparing every field of the result. Neither depends on anyone having guessed where somebody would put a contribution.

**Both halves of the skipping invariant are tests, not remarks.** PLAN §5 P2 asked for this explicitly. Each half is driven red by the change that would break it — a transparent `Skipped` for the first, a gap-aware retirement window for the second.

**The gate run is constructed rather than measured.** What a reference agent does with a payload is a question about that agent; what is under test here is what the gate's counts do, and do not do, with an elective reading beside them. The same seam `test_retirement.py` and `test_scorer.py` already use.

**Every new test is driven red once, for the right reason, before it is committed.** `CLAUDE.md`'s standing rule. Two re-cuts on this scope are recorded in the commits: a floor test whose reading failed on interval overlap and so would have passed under any floor, and two substring assertions defeated by `direct_prompt_injection` sitting inside `indirect_prompt_injection`.

## Out of Scope

- **The three families themselves.** `ASI06` memory poisoning, `LLM01` direct prompt injection and `LLM02` PII leakage are #48, #49 and #50: cases, canaries, and a new capability on all three reference agents carrying a defensible hardened ≤ weak ≤ trivial gradient. This spec is the tier they arrive in.
- **`Case.family` and `Attempt.family` actually widening.** Decided in ADR-0035 and performed by the first ticket that has an elective case to load. A union written before there is a record to put in it is a union with no caller.
- **The gate run record's elective fields.** `gate_record.py` is a wire contract, and a pydantic field no run can fill is one the console renders empty and a reader reads as a bench that measured nothing. It arrives with the first elective reading.
- **The report screen.** `frontend/src/api/report.ts` parses the artefact by TypeScript interface rather than by a runtime schema, so the new key travels harmlessly and is not displayed. The fifth absence reaches the *rendered document* every recipient reads; putting it on the screen belongs with the rest of Group G's rendering work.
- **The console lever.** Selecting elective families from a screen is API and frontend work, on the pattern [ADR-0025](../adr/0025-the-console-may-set-a-runs-declared-inputs.md) established for a run's other declared inputs. The type it will set exists; nothing sets it yet.
- **Promotion actually happening.** Entry into the six is a library-version event with an ADR of its own, and no elective family has a single reading yet.
- **`ASI05` unexpected code execution.** PLAN §5 P2's other candidate. Not selected by #42, and a member of the tier is added by the ticket that gives it cases.
- **The published labels an elective family carries.** #45's label record and #47's stored LLM list. An elective family's identifiers are a labelling question and this spec is about the arithmetic.

## Further Notes

**The tier having no production caller is the ADR-0003 order, on purpose.** ADR-0003 fixed the gate rule before the code that evaluates it existed, because a threshold written after the first result is a threshold that can be moved to accommodate it. The same reasoning applies here with more force: the tier's rules are what will decide whether three families the bench does not yet have may ever join the six, and writing them now means writing them before anybody has a reading they would like the rule to accept.

**The invariant is ADR-0015's monotone-non-improving property one level down.** ADR-0015 shows that excluding a family can only remove a candidate from a count and never lower a bar. *Skipping is never advantageous* is the same shape applied to a lever the operator holds rather than to a fitness the run measures, and it needs two rules rather than one because the two things a skip could buy — progress and protection — are bought from two different rules.

**A family printed nowhere would make the tier unfalsifiable.** The temptation is to measure an elective family quietly and print it only once it is promoted. That would make the promotion streak a claim about readings no reader can see, which is the same defect as an unvalidated instrument and is refused in ADR-0035's considered options.
