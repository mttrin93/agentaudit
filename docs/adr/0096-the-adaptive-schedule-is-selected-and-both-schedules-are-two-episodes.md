---
status: accepted
---

# The adaptive schedule is selected, and both schedules are two episode sets

[ADR-0057](./0057-a-tree-is-the-harnesss-schedule-and-a-turn-is-still-one-probe.md)
built tree jailbreaking and left it unreachable. Its §2 says so in as many words:
*"What it does not yet have is a selection path — no flag, no environment variable and
no place in provenance, so today the schedule is declared in the record the run is
held to and printed in the adaptive block, and nothing but a caller constructing an
`AdaptiveBudget` can change it."* The schedule was a field on the budget with one
value, `LINEAR_CHAIN`, and the console's own box for the adaptive layer said *nothing
to choose inside this layer — the switch above is the whole of it*, which was true.

So the tree was implemented, tested against its scheduling and pruning rules, exercised
by the CI stand-in, and it had never run for anybody. This record is the selection path
ADR-0057 parked, and the arithmetic of asking for both.

## Decision

1. **The schedules are a closed set of two names, and an operator selects from it.**
   `BranchSchedule` — `linear_jailbreak` and `tree_jailbreak`, the names the catalogues
   ADR-0057 cites carry — each standing for one policy the bench declares:
   `LINEAR_CHAIN` and `DECLARED_TREE`, which is breadth three at a frontier cap of
   three, the values `test_tree_jailbreaking.py` drove the rules red against.

   **The width is not selectable and the enum is why.** A `BranchPolicy` on the wire
   is two numbers a caller could set, and two numbers a caller could set are two
   numbers a caller could set at hour 30 — the tuning ADR-0057 §2 refuses. What an
   operator answers is *which schedules*, and every answer is a schedule this bench has
   a stated rule for.

2. **A schedule is not a `Transform`.** `AttackLayer.ADAPTIVE` has always carried no
   construction, on ADR-0051 §3's refusal to name the loops in that enum, and this does
   not reverse it: a construction is an operation on the payload a case commits and is
   scored on its own attempts (ADR-0055), while a schedule is how an episode's turns are
   spent and an episode is a summand of nothing (ADR-0010). So the selection gains a
   third field, `AttackSelection.schedules`, and the wire gains a third list beside
   `layers` and `transforms` rather than a wider second one.

3. **Both selected is `k` episodes per schedule, and the ceiling doubles.**
   `AdaptiveBudget.episode_count` multiplies by the number of selected schedules, so
   `turn_ceiling` does too, and `RunBudget.declare` prices what the layer will actually
   open. This is the whole content of the feature: two schedules is **two episode sets
   per family** and not one wider search. A tree episode still spends one episode's turn
   budget across its branches — ADR-0057 §2's claim is untouched, and the per-episode cap
   is the same under either schedule — so the only thing that moved is how many episodes
   there are.

   The alternative was splitting `k` between the schedules, keeping the ceiling fixed.
   Rejected: `k` is two *so that a single unlucky trajectory is not the whole reading on
   a family* (`AdaptiveBudget.episodes_per_family`), and splitting it would buy the
   second schedule by halving the first's protection against exactly that — and would
   make `k` a number that has to divide by the size of a selection.

4. **The estimate carries the doubling, and it carries it by name.** The adaptive
   figure's basis names the schedules — `6 families × T=8 × k=2 × 2 schedules
   (linear_jailbreak, tree_jailbreak), × 1 target` — because a figure that doubled with
   nothing beside it saying why is the figure an operator reads as a bug in the bench.
   ADR-0007's mechanism is that nothing exceeds what a human confirmed, and what they
   are confirming here is a second attacker's turns.

5. **`AdaptiveBudget.under` is the only join, and the caller that knows the selection
   applies it.** The budget's `schedules` field is filled from
   `AttackSelection.schedules` at two call sites and by one method: `runs.start`, which
   prices the run, and `run_calibration`, which spends it. Deliberately **not** derived
   inside `RunBudget.declare` the way `elective_families` is: that one is read off cases
   the function was handed, while a budget arrives already carrying its schedules, and a
   `declare` that read the selection would overwrite a hand-built tree budget with the
   default and price a tree run as a line.

6. **The default is the line, which is where this parts from every other default on
   this bench.** `transforms` defaults to everything the library holds, because a
   forgotten field should over-measure rather than report a thin reading as a full one.
   A second schedule is not more of the same library — it is a different attacker — and
   the three reference agents were gated under the line, so `EVERY_CONSTRUCTION` names
   one schedule and `SelectRequest.schedules` defaults to it. A caller written before
   this field existed asks for the run this bench has always made.

   **A gate run passes no selection and therefore gets the line.** `gate_runs` prices
   and calibrates without one, so the citation a report carries stays a claim about the
   attacker the reference agents actually faced (ADR-0023). A gate under the tree is a
   thing this bench could be asked for and is not asked for here.

7. **An empty selection is refused at both records.** `AdaptiveBudget` refuses a budget
   with no schedule and `AttackSelection` refuses a selection with none, each with its
   own sentence, because either could be built by a caller that never touched the other.
   A layer running under no schedule opens no episode, which is what switching the layer
   off already says, and two ways of saying one thing are two things a reader has to
   reconcile.

8. **The provenance states which schedules ran, and that both is two sets.**
   `AttackSelection.schedules_stated()` is part of the selection's own sentence, which
   the artefact carries: `VARIANTS_STATED` says two runs are comparable only at equal
   library version and equal selection, so a document that named the constructions and
   not the schedules would state half of its own condition. And the adaptive block
   prints **one rule per selected schedule**, named, beside `A_effort` — a block that
   printed one scheduling rule for a median taken over two schedules' turns would tell a
   reader the wrong thing about the number above it (ADR-0057 §3).

9. **The console draws the schedules in the adaptive box, and prints one sentence under
   them.** They sit in the footer the constructions would have been in, behind the word
   *Schedules*, and are grouped off the `layer` field the wire puts on every row — the
   discipline `TransformSelected` already follows, so no console holds a copy of the
   mapping. The sentence about what the second tick costs *is* printed, unlike the two
   the route serves beside the constructions: those are written for a reader holding a
   document, and this one says that the tick doubles the turns the next run may put on
   the operator's own endpoint, which is a thing to know before answering rather than
   after.

## Considered and rejected

**A number of episodes per schedule.** A second knob for a reader to reconcile with
`k`, and the question it answers — *how much of this schedule do I want* — is `k`'s
question asked twice.

**Making the tree the default now that it can be selected.** It changes what every
citation on this bench means without a gate run saying so (ADR-0023), and ADR-0057 §2
already declined it for that reason. An operator who wants it selects it.

**Recording the schedule on `AdaptiveEpisode`.** It is the honest per-episode fact, and
ADR-0057 §4 decided the shape reaches no signed artefact: `parents` already tells a
reader whether an episode branched, the record carries it, and the run-level selection
is where *what was asked for* belongs. Worth reopening if a reader ever has to sort a
run's episodes by schedule without walking their parents.

**A schedule switch per family.** The refusal `AttackSelection` already makes about
per-family constructions: a grid of switches produces runs nobody can compare, and the
operator's real question is answered by the layer.

## Consequences

- Tree jailbreaking is reachable for the first time since ADR-0057 built it — from the
  console's adaptive box, and through `AttackSelection` for any caller.
- A run under both schedules puts twice the adaptive turns on the operator's endpoint,
  and the estimate says so before the interrupt. Nothing about the scored layer moves:
  the schedules touch no case, no attempt and no denominator.
- `A_effort`'s median over a both-schedules run is a median over two schedules' turns.
  It is still probes-to-first-success, because a turn is one probe under either, and the
  block names both rules — but a reader comparing that median with a single-schedule
  run's is comparing two different searches, and the selection sentence is what tells
  them so.
- `docs/validation.md`'s *what has never been validated* gains nothing and keeps its
  standing line: no gate run has ever been decided under the tree, and the discrimination
  readings this bench publishes are the line's.
