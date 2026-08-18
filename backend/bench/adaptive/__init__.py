"""The second layer of a run. Nothing in this package may write into a rate.

ADR-0010 keeps the two layers apart with a type rather than a discipline: an
`AdaptiveEpisode` cannot be constructed from an `Attempt`, so no adaptive turn
can reach a denominator. The attacker, its tools and the adaptive statistics
arrive in #16 and #17.

`budget.py` and `episode.py` landed first, and on purpose. The attacker spends a
user's inference budget by a route nobody can predict, so the ceiling it spends
under was declared before the thing that spends it existed. And an episode records
which of the five tools the attacker actually had, because a target without
tool-call visibility costs it `read_tool_trace`: an attacker that found nothing
while running one-eyed must not read as an attacker that found nothing.

What #16 added, in the order a turn passes through it:

- `layer.py` — which episodes run, against what, in what order. Called once, after
  the whole fixed suite, by the calibration entry point.
- `attacker.py` — one episode: the loop, its caps, and how it ends.
- `prompt.py` — everything the attacker is told, which is published (ADR-0008).
- `tools.py` — the five tools, and the only transport this layer has.
- `blinding.py` — the per-run handles, and the redaction that enforces them.
- `precedent.py` — the store interface `retrieve_precedent` reads. Empty until 6a.
- `proposal.py` — the one edge back into the scored layer, decided by #17.
- `scripted.py` — a deterministic stand-in attacker, so the plumbing above is
  testable without a model call. Test equipment, like `stub_models.py`.

The adaptive statistics — `A_break`, `A_effort`, the sign test — are #17.
"""
