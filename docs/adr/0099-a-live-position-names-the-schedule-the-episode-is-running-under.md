---
status: accepted
---

# A live position names the schedule the episode is running under

[ADR-0096](./0096-the-adaptive-schedule-is-selected-and-both-schedules-are-two-episodes.md)
made both schedules selectable and each selected one an episode set of its own, and
[ADR-0097](./0097-the-adaptive-layer-attacks-in-a-spelling-and-it-is-selected.md) did
the same for the spellings. A run that selected both schedules therefore attacks every
family **under each**, and the live position it reports —
*family scope_creep, episode 2, turn 5* — cannot say which of the two passes the turn on
the screen belongs to. The two episode sets are adjacent by construction
(`run_adaptive_layer` loops the schedule innermost), so what a person watching a run
sees is one family's counter running twice with nothing distinguishing the passes.

## Decision

1. **`EpisodePosition` gains `schedule`, and `AdaptivePosition` carries it.** The
   position becomes family, schedule, episode and turn, and the bench's own sentence
   about it says the same four things in the same order.

2. **A fourth part of the position and not a fourth unit.** `ADAPTIVE_UNITS` reads
   *family, schedule, episode, turn* on the screen, which is what the operator asked
   for and is the right idiom — but the layer counts in three of those and never in the
   fourth. An episode and a turn are ordinals the layer increments; a schedule is which
   of the operator's selections this episode belongs to. Nothing divides by any of the
   four, so the distinction costs nothing here and is stated in both docstrings rather
   than left for a reader to infer from a screen.

3. **The member and not its `BranchPolicy`.** `run_episode` and `_Episode` now take
   `schedule: BranchSchedule` where they took `branching: BranchPolicy`, and the tree is
   built from `schedule.policy` at one call site. One representation of *which schedule
   this episode is*: the shape the tree schedules and the name the position reports are
   the same field, so they cannot come to disagree, and the breadth and the pruning cap
   stay the harness's own numbers rather than something a position reports (ADR-0057 §1).

4. **`LayerReading.units` and `at` become lists.** They were three-tuples, which is what
   made the scored layer's three and the adaptive layer's three look like one shape; the
   adaptive layer states four parts and the scored layer three, so the type says a list
   of the parts and a list of the values. What keeps the two layers from being read
   against each other is unchanged and is not the tuple length: `SCORED_UNITS` and
   `ADAPTIVE_UNITS` are two constants, neither built from the other, and no function in
   `progress.ts` takes both layers (ADR-0010).

5. **The terminal run says it too.** `scripts/attack.py`'s per-episode line names the
   schedule beside the target and the family, because it is the same fact for the same
   reader and a run watched from a terminal is watched for the same reason.

## Considered and rejected

**Leaving it to the report.** The finished document states which schedules a run
attacked under (ADR-0096 §8), and that is where a *recipient* reads it. This is the
screen a person watches for minutes while the run goes, and the question it answers —
*which pass is this* — has no answer once the run is over and no reader after it.

**A second block, or a second panel per schedule.** Two positions in one layer's box
invites the reader to add them, and the run screen's whole shape is that nothing on it
spans two layers or two counters (ADR-0007, ADR-0010). One position with a part naming
the schedule is one thing to read.

**Naming the spelling there as well.** It is the same argument and it would make the
position five parts wide, four of which are not units. The spelling is stated in the
report and on the bench page's own switches, and an episode's transcripts carry the
respelled probe. Worth reopening if watching a spelled run turns out to need it — the
field is on the position's own record, and adding it is one line at each end.

## Consequences

- The adaptive box on the run screen shows four parts, in the same idiom the other
  three are drawn in, and the gate screen's adaptive block gains the same part off the
  same builder.
- `RunState.enter_episode` takes a third argument. Its one caller is `_Episode`, and
  `scripts/attack.py`'s `Narrating` subclass overrides it and prints the schedule.
- No figure moves and no artefact changes: a position is an ordinal a screen draws while
  a run is in flight, and the signed document holds none of it (ADR-0056 §1).
