"""What worked against similar targets, with nothing in it that says which target.

`retrieve_precedent` is one of the attacker's five tools and the store behind it
is phase 6a, so what lands here is the **interface** and an empty implementation —
enough for the tool to be a real decision the model makes, and no more (spec:
Carved out, "The precedent store and retrieval").

Two constraints on this store are already recorded and both are structural rather
than remembered. ADR-0004 forbids precedent reaching the judge, and
`test_judge.py` fails on an import of anything named `precedent` from the judge's
module. ADR-0011 adds the second consumer: precedent returned to the *attacker*
carries no target identity, because long-term memory is otherwise the channel that
un-blinds an instrument every other channel was closed against. The stripping
happens in `tools.retrieve_precedent`, against the run's `Blinding`, so a store
that later holds real routes cannot deliver identity by having been written
carelessly.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from backend.bench.library import Family


@dataclass(frozen=True)
class Precedent:
    """One route that worked before, as prose.

    Prose and never payload text, for the reason CONTEXT.md gives under **route**:
    a route that beat a target is a working unpublished exploit, and the
    disclosure posture withholds exactly that (ADR-0008).
    """

    family: Family
    route: str


class PrecedentStore(Protocol):
    """Where past routes are read from. One method, so 6a can replace it whole."""

    def for_family(self, family: Family) -> Sequence[Precedent]:
        """The routes recorded against this family, most useful first."""
        ...


@dataclass(frozen=True)
class RecordedPrecedents:
    """A store held in memory. The stand-in until 6a, and the fixture after it."""

    entries: tuple[Precedent, ...] = ()

    def for_family(self, family: Family) -> Sequence[Precedent]:
        return tuple(entry for entry in self.entries if entry.family is family)


NO_PRECEDENT = RecordedPrecedents()
"""The empty store every run uses until 6a builds one.

Empty rather than absent, so `retrieve_precedent` is a tool that answers rather
than a tool that is missing: an attacker that spent a turn discovering the bench
has no memory yet has learned something true.
"""
