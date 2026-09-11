---
status: accepted
---

# The band is coloured on the report screen

[ADR-0005](./0005-no-composite-risk-score.md) refused a composite risk score and put a
per-family band in its place: `holds`, `weak`, `fails`, defined by the interval's
position against declared cut points ([ADR-0014](./0014-band-cut-points-are-the-reference-agents-constructed-rates.md)),
and "legible, not addable, and awkward to rank vendors with".

The consequence the stylesheet drew from it was absolute, and written at the colour
tokens:

> No band, rate, verdict or verification result anywhere is coloured — a scale over
> holds, weak and fails is the severity scale ADR-0005 exists to refuse, and a green
> tick beside somebody's agent is the badge the report refuses.

That was never an ADR's decision. This one makes it a decision and then reverses the
narrower half of it.

## Decision

**The band takes a colour, on the report screen's per-family table, and nowhere else.**

1. **Three hues on three words, and the word is always printed.** The hue is redundant
   with the label at every size, so nothing is carried by colour alone and a reader who
   cannot tell the three apart loses nothing.

2. **On the word, never as a fill.** A tinted cell is a status pill and six pills in a
   column is the badge a report refuses. The colour is ink on the band's own word.

3. **Aliases of colours already in use.** `holds` takes the held verdict's green,
   `fails` the broken verdict's red, `weak` the amber the weak reference agent carries.
   A fourth green would be a second answer to *which green means held*.

4. **The rate takes the band's colour — the figure and its bar alike.** The band is
   read off that quantity — the interval's position against the declared cut points
   (ADR-0014) — so the number, the length and the word two columns along are three
   marks of one reading, and giving them two colours leaves a reader deciding which to
   believe. Both take the band's hue rather than changing colour at a cut point of their
   own, which would be a second band drawn by the stylesheet.

5. **Nothing else moved.** No verdict, no interval, no verification result and no figure
   on any other screen is coloured.

6. **The signed artefact has no colour in it.** The band travels in the payload as a
   `StrEnum` member with no ordinal and no cut point of its own, `report.md` is text,
   and what a recipient is handed is unchanged. This is a decision about one screen an
   operator reads their own run on.

## What this does not decide

That the band may be ordered, summed, or ranked. `Band` stays a `StrEnum` and never an
`IntEnum` — an ordinal puts a six-family total one line of arithmetic away, which is
ADR-0005's refusal rebuilt by the next reader — and nothing sums this column.

## The reservation

This is the severity scale ADR-0005 was written against, admitted in one place under
three conditions. The conditions are the whole of the protection, and there are three of them left: the
band's word printed beside every hue, no cell filled, and the artefact colourless. A
fourth — the rate's figure left in ink, so the number was the thing both the bar and the
word were checked against — was given up when the figure was coloured too. A green `holds` beside a customer's
agent is a badge the moment any of the three goes, and the pressure to put it on a card,
in the document, or beside a total will come from this precedent. It is here because
the operator whose run it is asked for it, having been shown the rule it breaks.
