"""The second layer of a run. Nothing in this package may write into a rate.

ADR-0010 keeps the two layers apart with a type rather than a discipline: an
`AdaptiveEpisode` cannot be constructed from an `Attempt`, so no adaptive turn
can reach a denominator. The attacker, its tools and the adaptive statistics
arrive in #16 and #17.

`budget.py` and `episode.py` land first, and on purpose. The attacker spends a
user's inference budget by a route nobody can predict, so the ceiling it spends
under is declared before the thing that spends it exists — #16 must not be able
to start without one. And an episode records which of the five tools the
attacker actually had, because a target without tool-call visibility costs it
`read_tool_trace`: an attacker that found nothing while running one-eyed must not
read as an attacker that found nothing.
"""
