---
status: accepted
---

# A family's row states what the library holds for it

[ADR-0091](./0091-the-console-draws-the-nine-families-as-one-list.md) decided how the
bench page draws the nine families, and its decision 5 was absolute:

> **No figure in any column.** Not a rate, not an interval, not a band, not a `D`. The
> screen says what the nine *are* and what they are read onto; how a target answered
> one is the report's business (ADR-0018), and how well this bench discriminates on an
> elective family is the gate document's (ADR-0035, ADR-0088).

The four things it names are four kinds of **measurement**, and the sentence after them
says what the objection is: they are all readings taken against somebody's agent. The
prohibition was written as *no figure* because at the time no figure that was not a
measurement had any reason to be on a family's row.

One now does. The two switch blocks are drawn identically — the layers block already
carries a column stating how much of each layer the mounted library holds, in the
bench's own words — and an operator ticking a family is asking the same question one
level up: how much is there to send about this one. The answer was on the screen for
the layer and not for the family, which is the asymmetry this ADR removes.

## Decision

**A family's row states the number of cases the mounted library holds for it, and
nothing else that is a figure.** ADR-0091 §5 is narrowed to what its own next sentence
argues: no rate, no interval, no band, no `D`, and no reading of any kind taken against
a registered target. A count of records this bench holds is not one of those.

1. **It is a fact about this bench and not about anybody's agent.** The library is
   mounted before a target is registered and the count does not move when one is. That
   is the whole of why it is admissible where a rate is not — ADR-0018's line is
   between the bench's own properties and a customer's, and this figure is on the
   bench's side of it, exactly as `LayerSelected.holds` is.

2. **Worded by the bench, on `LayerSelected.holds`'s terms.** `FamilyCovered.holds`
   arrives as a sentence — *3 cases*, or *no cases in this library* — and the console
   prints it. A console that received `3` and wrote the noun itself would be composing
   a figure no route stated, which is the rule the layers' two columns are already
   under.

3. **The same figure for a family of either tier, counted over both directories the
   library is.** `_what_a_family_holds` takes `AnyFamily`: an elective family's case is
   an ordinary case, and the tier decides what the gate is read over rather than what
   the library holds (ADR-0035). The tier's records are loaded into
   `BenchConfig.elective_cases` and deliberately not folded into `cases` — so that a run
   asking for none of them does not move its library digest — and this row counts both,
   or three of the nine would report an empty library while nine records sat in
   `cases/elective/`. Counted off what is **loaded** and never off what is requested:
   the row is what an operator reads before ticking. It still says nothing about which
   set it came from, so ADR-0091's decision 1 is intact.

4. **Not a denominator, and nothing two rows may be added over.** It is a count of
   records, not of attempts: what a run makes of them is `attempts_per_case` times the
   cases of the families it covers, and that multiplication belongs to the estimate the
   operator confirms before a run starts (ADR-0007, ADR-0005, ADR-0010).

## What this does not decide

Whether the report may carry it. The report states a family over its own denominator
with its interval beside it, and a case count there would sit next to a measurement and
be read as part of one. Nothing about this screen argues for that.

## The reservation

A count beside a switch is the beginning of a column of counts, and a column of counts
is where the pressure to print a rate comes from. The guard is the one ADR-0091 §5 keeps
after this narrowing: any figure on this screen has to be a property of the bench, and
any reading against a target belongs on the report.
