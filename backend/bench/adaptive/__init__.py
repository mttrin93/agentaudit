"""The second layer of a run. Nothing in this package may write into a rate.

ADR-0010 keeps the two layers apart with a type rather than a discipline: an
`AdaptiveEpisode` cannot be constructed from an `Attempt`, so no adaptive turn
can reach a denominator. The attacker, its tools, the episode record and the
adaptive statistics arrive in #16 and #17.

`budget.py` lands first, and on purpose. The attacker spends a user's inference
budget by a route nobody can predict, so the ceiling it spends under is declared
before the thing that spends it exists — #16 must not be able to start without one.
"""
