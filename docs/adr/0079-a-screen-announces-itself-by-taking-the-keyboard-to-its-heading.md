# ADR-0079: A screen announces itself by taking the keyboard to its heading

**Status:** accepted (#121, under #119)
**Date:** 2026-09-06

## Context

The console is a router app whose screens replace each other under one document. Two
things follow that nothing in `frontend/src/` was doing anything about.

A screen change moved nothing. There were no `aria-live` regions anywhere in the app
and nothing touched focus on a route change, so a screen reader was told nothing when
the screen changed and the next Tab resumed from the top of the document — worst in
the registration walk, which swaps its whole screen four times without the route
changing at all.

And no screen said which screen it was. `index.html` set `<title>AgentAudit</title>`
once and nothing has set it since, so all seven screens are one entry in the tab strip
and one name in the browser's history — for an app whose long screen is a run that
takes minutes and is meant to be left open in a background tab.

Both are liveness rather than decoration, and #119 is explicit that nothing under it
may make a screen louder, faster or more decorated. So the question is what the
minimum honest announcement is, and what counts as an arrival to announce.

## Decision

**The arriving screen's own `h1` takes the keyboard, and the title says which screen
it is.**

**The `h1` and not a wrapper.** It is the sentence that names the screen, so a screen
reader focusing it reads out exactly what a sighted reader has just been shown, and a
keyboard reader resumes from the top of the screen rather than the top of the
document. It carries `tabIndex={-1}`, which makes it focusable by script without
adding a tab stop — the rail already has seven, and #122 is the issue about that.

**An arrival is the heading's own name, held for the document rather than per
component.** The registration walk changes screen without changing route, so a rule
keyed on the path would announce three of the console's screens and none of the
walk's. And each screen is a different component, so a ref inside one cannot tell
*this screen has replaced another* from *this screen is being drawn for the first
time*: it is a first render either way. One name, held in the module, answers both —
the console is one document with one screen on it at a time.

**The first screen of a session does not take the keyboard.** Nobody navigated to it.
It is where the address bar landed, and focus belongs where a freshly opened document
puts it.

**A refusal that names a field still wins the keyboard.** On the registration screen a
`422` naming a field walks the operator back to the step drawing it *and* puts the
keyboard on the field (ADR-0076), so on that one render two effects want focus. The
field is the more specific answer — it is the thing the bench refused — and the
heading above it is one Shift-Tab away.

**The title is the screen's name, then the app's; what the screen is doing goes in
front of both.** A tab strip and a history list truncate from the right, so what has
to survive the cut is what tells two screens apart, and on a run screen the next most
useful thing is whether it is still running. Nothing puts the title back on the way
out: the next screen sets its own, and a restore between two named screens would put
`AgentAudit` in the tab for a frame.

**A run's title carries its phase and never a figure.** The run screen's counts are
per family and per layer and this app adds none of them up. A number in a tab strip
has left behind the label it was drawn beside, which is the one place a reader would
take a length for a rate (ADR-0005). *Running* rather than *40 / 181* is the whole of
what a backgrounded run reports, and it is the half a reader can act on.

## Consequences

- `frontend/src/console/announce.ts` holds both rules: `screenTitle` is pure and
  asserted in node, and the two hooks are asserted in a browser
  (`frontend/e2e/liveness.spec.ts`), which is the division `vite.config.ts` sets out.
- The screen names come from `console/rail.ts`, where the rail already draws them. A
  literal in a `<title>` would be a second copy of a name and would drift from the
  rail on the first rename.
- The module-level name is written and read only inside an effect, so it is not state
  React renders from and the compiler has nothing to memoise around it. Under
  StrictMode's double-invoked effects the second run early-returns, so a screen
  announces once.
- A screen that unmounts and remounts under the same name does not re-announce. That
  is the same rule read from the other side — the screen on this document has not
  changed — and it is the reason the name is the key rather than a counter.

## Alternatives rejected

- **A live region in the shell that says *navigated to X*.** It announces without
  moving focus, so the keyboard reader is still resuming from the top of the
  document — half the problem, and the half that is harder to notice. It also adds a
  sentence no sighted reader sees, which is the console explaining itself in the
  margin that `rail.ts` already deleted once.
- **Focus the `<main>` or a wrapper.** It moves the tab order correctly and announces
  either nothing or the whole screen, depending on the reader. The heading is the one
  element whose text is the answer to *what is this screen*.
- **Key the arrival on `useLocation()`.** It is the more obvious rule and it misses
  the registration walk entirely, which is the screen the issue names as worst.
- **Set the title from a table in the router.** One place instead of eight, and it
  cannot say what a screen is *doing* — the run's phase, the walk's step — because
  the router does not know. Both of those are the half of the title that changes.
