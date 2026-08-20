"""One writer at a time on a case library, and the file that says who it is.

A gate run reads every case record in a library and then writes back to every one
of them — a `[[history]]` block per case, and a status line moved on the cases the
rule retires (`retirement.store`). That is a read-modify-write over a directory of
files, so two gate runs overlapping on one library is not slow, it is wrong: the
second one's `store` re-reads a record the first one is halfway through writing, and
the retirement decision it takes is read off a series that is missing a reading it
should have seen.

**So the library has one writer at a time, and the lease is the whole of that
mechanism.** It is taken before the library is read and released after the
write-back, by whoever is about to run a gate — the command line and the console
alike — so the two entry points exclude each other rather than only themselves. A
second gate run does not queue and is not silently made to wait: it is refused by
name, with the holder and the time in the refusal, because a gate run is 830-odd
calls on the operator's provider and a request that blocked for an hour before
spending them is worse than one that says *not now*.

**A lease is a file created exclusively, in the directory it is a lease on.** Not a
lock in one process's memory: the command-line gate run and the console gate run are
two processes over one directory, and a lock either of them held privately would be
invisible to the other. `Path.open("x")` is the whole of the exclusion — the create
fails when the file is already there, and the failure is the refusal.

**A lease is released by the holder, and one left behind is removed by hand.**
There is no expiry and nothing here reaps a stale file, because every rule for
deciding that a lease has gone stale is a rule for deciding that a gate run which
is merely slow has: a full one is many minutes of model calls, and a timeout short
enough to catch a killed process is short enough to unlock a library somebody is
still writing to. So the file names its holder and the moment it was taken, the
refusal prints both and the path, and clearing it is a person's decision.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

LEASE_FILE = ".gate-run.lease"
"""What the lease is called inside the library it holds.

Beside the case records rather than under a directory of its own, because the thing
being held is this library: a lease kept somewhere central would be a lease that
did not travel with the volume the records are on. Dot-prefixed and not a `.toml`,
so nothing that loads the library reads it as a case.
"""


class LibraryBusy(RuntimeError):
    """This library is already held by a gate run, so another may not start.

    Raised rather than waited out. A caller that blocked would hold an HTTP request
    open across somebody else's gate run, and a caller that carried on would be the
    overlap this module exists to prevent.
    """


@dataclass(frozen=True)
class LibraryLease:
    """One held library: the file that holds it, who holds it, and since when.

    Frozen, and `release` is the only thing that ends it. The fields are what the
    refusal prints for the *next* caller, which is the whole reason they are written
    into the file rather than kept in the holder's memory.
    """

    path: Path
    holder: str
    taken_at: datetime

    def stated(self) -> str:
        """The lease as the next caller is told about it."""
        return (
            f"a gate run holds this case library: taken by {self.holder} at "
            f"{self.taken_at.isoformat(timespec='seconds')}, and the lease is at "
            f"{self.path}"
        )

    def release(self) -> None:
        """Give the library back. Missing is not an error — it is already given."""
        self.path.unlink(missing_ok=True)


def held_by(directory: Path) -> str:
    """What the lease on this library says, or the empty string when there is none.

    Read rather than parsed: what is in the file is the sentence the holder wrote,
    and a reader that took it apart would be a second definition of the format.
    """
    lease = directory / LEASE_FILE
    try:
        return lease.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def take_the_library(directory: Path, holder: str) -> LibraryLease:
    """Hold this library for one gate run, or refuse because somebody else does.

    The create is exclusive, so the check and the claim are one operation: two
    callers arriving in the same instant produce one lease and one `LibraryBusy`,
    and never two leases.
    """
    lease = directory / LEASE_FILE
    taken_at = datetime.now(tz=UTC)
    held = LibraryLease(path=lease, holder=holder, taken_at=taken_at)
    try:
        with lease.open("x", encoding="utf-8") as writing:
            writing.write(f"{held.stated()}\n")
    except FileExistsError as busy:
        raise LibraryBusy(
            f"{held_by(directory) or f'a gate run holds {lease}'}. A gate run reads "
            "every case record and writes back to every one of them, so one runs at "
            "a time on one library: nothing has been sent and nothing has been "
            "spent. If the run that took this lease is gone, delete the file above "
            "and start again — nothing here expires it, because a timeout short "
            "enough to catch a dead run is short enough to unlock a library a live "
            "one is still writing to"
        ) from busy
    return held


@contextmanager
def holding_the_library(directory: Path, holder: str) -> Iterator[LibraryLease]:
    """Hold it for the length of a block, and give it back however the block ends.

    The form both entry points use, because the failure this module guards against
    is a lease that outlives its gate run: a run that raised on its third family
    would otherwise leave a library nobody may write to and no process writing to it.
    """
    lease = take_the_library(directory, holder)
    try:
        yield lease
    finally:
        lease.release()
