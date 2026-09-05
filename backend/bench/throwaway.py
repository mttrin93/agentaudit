"""A throwaway copy of the caller's own checkout: patched, served, and always dropped.

The bench does not write into somebody's repository. What #109's sixth sub-issue
needs is a working tree it can change — apply a patch, re-serve the entrypoint out of
it, re-attempt the case — and what an operator agreed to is a bench that reads their
code ([ADR-0071](../../docs/adr/0071-a-finding-points-at-a-file-the-bench-read.md)
§5). This module is the whole of the difference between the two: **everything written
is written inside a copy this module made, and the copy is dropped from one `finally`
however the run ends**
([ADR-0072](../../docs/adr/0072-a-post-patch-re-run-is-its-own-record.md)).

That is [ADR-0063](../../docs/adr/0063-one-run-scoped-namespace-dropped-wholesale.md)
applied to a working tree rather than to somebody's vector store, and the shape is
copied deliberately: the workspace name is **derived once** from the run id, reaches
every operation **as an argument**, and is dropped **wholesale** rather than by
deleting the files this bench remembers writing. A manifest of what was patched would
be a second copy of the truth, going stale, whose failure mode is a working tree left
half-changed with nobody told.

**Nothing here executes anything.** It copies, writes one file, and removes a
directory. What re-serves the patched entrypoint is `proving.py`, one module out, so
that the module holding the filesystem write is not also the module holding the
import — the same separation ADR-0071 §5 drew between reading a checkout and
patching one.

**Nothing here reaches an instrument, and no model writes a patch.** A `Patch` is a
value a caller constructs; there is no parameter on anything in this module through
which a model's prose could become a file on disk, and ADR-0072 §2 is why.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from backend.bench.source_anchor import SourceAnchor, SourceAnchorReading

WORKSPACE_PREFIX = "proof-"
"""What every directory this module creates is named for.

`NAMESPACE_PREFIX`'s reason, one storey down (ADR-0063 §1): an operator who finds one
of these on their runner can tell at a glance whose it is, and `Throwaway` refuses a
root that is not named this way — which is the one check that stops a hand-built
record from pointing the patch writer at the original checkout.
"""

MAX_PATCHED_FILE_BYTES = 4 * 1024 * 1024
"""The most this bench will write into one file of a throwaway checkout.

`source_anchor.MAX_ANCHORED_FILE_BYTES`'s figure and its argument, applied to the
write rather than to the read: four mebibytes is two orders of magnitude above the
largest source file in this repository, so no honest module is refused by it, and a
bounded write is what keeps a patch from being a way to fill a runner's disk. Both
the file being replaced and the replacement are measured against it, because either
one being enormous is the same fact about this patch.

The figure is a property of this literal, and `test_throwaway_checkout.py` writes a
patch over it and asserts the refusal: editing the number without editing that test
leaves the claim unmade.
"""

NOT_COPIED = (".git", "__pycache__")
"""What a throwaway copy of a checkout deliberately does not contain.

Two entries and each has its own argument, so neither is housekeeping.

**`.git`** is the one that carries a decision, and ADR-0072 §1 argues it: a patch
applied inside a tree with no repository in it cannot be committed by anything,
including by code this bench has not written yet.

**`__pycache__`** is correctness. A stale `.pyc` beside a patched source is a file the
interpreter is entitled to load *instead of* the patch, and a proof loop that re-ran
the unpatched module and reported the case fixed would be the worst answer this
mechanism could give.
"""


_WORKSPACE_BODY = re.compile(r"[A-Za-z0-9._-]+")
"""What a run id may contribute to a workspace name.

A workspace becomes a directory name on the runner's filesystem, so what reaches it
is restricted here rather than at the `mkdir`: `..` and `/` are the two things a
directory name must not be able to carry, and both are refused by this being an
allow-list rather than a list of things to strip.
"""


def workspace_for(run_id: str) -> str:
    """The one workspace this run patches in, derived from the run's own id.

    `proof-<id>`, and derived rather than stored, on `planting.namespace_for`'s own
    reasoning (ADR-0063 §1): the name the copy is made under and the name the drop
    runs against are computed from the same run id, so there is no field between the
    two that a later run could have overwritten.

    A run id that could not be a directory name is **refused rather than sanitised**.
    A name quietly rewritten on the way in is a name the drop may not recognise on
    the way out, and here the cost of that is a patched copy of somebody's repository
    left on their runner.
    """
    if not _WORKSPACE_BODY.fullmatch(run_id):
        raise ValueError(
            f"a throwaway workspace cannot be derived from {run_id!r}: the name "
            "becomes a directory on the runner's filesystem, so it is letters, "
            "digits, dot, dash and underscore or it is refused. Sanitising it "
            "instead would hand the drop a name the copy was never made under"
        )
    return f"{WORKSPACE_PREFIX}{run_id}"


class PatchRefusal(StrEnum):
    """Why a patch was not applied — one named refusal per mode.

    A closed set rather than prose, for the reason every closed set in this codebase
    is one: a caller telling five refusals apart by matching an exception's message
    stops telling them apart the day the message is reworded. Four of the five are
    about **where** the patch pointed and one is about how big it was, and none of
    them is a fact about the target's code.
    """

    NOT_A_RELATIVE_PATH = "not_a_relative_path"
    """It was absolute, or carried a `..` segment. Refused before anything resolves."""

    LEFT_THE_CHECKOUT = "left_the_checkout"
    """It resolved outside the copy — which is what a symlink out of one looks like."""

    NO_SUCH_FILE = "no_such_file"
    """There is no such file in the checkout. A patch replaces; it never creates."""

    NOT_A_REGULAR_FILE = "not_a_regular_file"
    """A directory, a device or a socket. Not a source file, so not patchable."""

    TOO_LARGE = "too_large"
    """The file or its replacement is over `MAX_PATCHED_FILE_BYTES`."""


class PatchRefused(ValueError):
    """A patch this bench will not write, and which of the five reasons holds.

    Raised rather than returned, and raised **before the write** in every case: a
    patch that pointed outside the copy is not a degraded result to carry into a
    report, it is the one thing this module exists to make impossible. `proving.py`
    catches it and turns it into a reading, because a run that has already spent an
    operator's inference budget may not end over the proof loop (ADR-0072 §4).
    """

    def __init__(self, refusal: PatchRefusal, said: str) -> None:
        super().__init__(said)
        self.refusal = refusal


@dataclass(frozen=True)
class Patch:
    """One file of the checkout, and what this bench would put in its place.

    **A whole file and never a diff**, argued in ADR-0072 §2. The consequence here is
    the shape of this record: two strings and no instruction, applied by one
    `write_text` into a path `apply_patch` resolved itself, with nothing in between
    that could resolve a path of its own.

    **One file, and it is the file the anchor points at.** `for_anchor` is the only
    constructor with a story about where the path came from: it is the definition
    site of the object the bench served, verified against the checkout by
    `source_anchor.anchor_for` before this record could be built (ADR-0071 §2). That
    is also the only file `proving.py` knows how to re-execute, so a patch to a
    second file would be a write with no re-serve behind it.

    **And no model wrote it.** `Remediation.fix` is prose about what to change, and
    it stays prose: nothing in this module or in `proving.py` imports `judge.py`,
    `narration.py`, `remediation.py` or `adjudication.py`, and an import-level test
    holds that. What a `Patch` is, is the operator's own code — the same code
    `serve_callback` already runs in this process (ADR-0059) — and ADR-0072 §2 says
    why a bench that wrote its own would be a different and much larger decision.
    """

    path: str
    """The file to replace, relative to the checkout root, in POSIX form.

    The same string `SourceAnchor.path` publishes, and relative for the same reason:
    an absolute path names the runner's filesystem rather than the repository
    (ADR-0071 §4), and a patch addressed absolutely is a patch that could name a file
    outside any checkout at all.
    """

    contents: str
    """The whole of what the file becomes, as text.

    Text and not bytes: the population this can be applied to is a Python module the
    bench is about to re-execute, and a binary a patch replaced would be a file
    nothing in this loop could serve.
    """

    @classmethod
    def for_anchor(cls, anchor: SourceAnchor, contents: str) -> Patch:
        """A patch to the file this run's anchor points at, or a refusal.

        The constructor with the provenance, and the reason `path` is not a free
        string in practice: an anchored reading is one where the bench opened that
        exact file inside that exact checkout and verified a line of it, so a patch
        built this way is addressed at a file that was there a moment ago. Every
        other reading is a run with no checkout, no located file, or a file the bench
        refused — and a patch to one of those has nothing to be applied to.
        """
        if anchor.reading is not SourceAnchorReading.ANCHORED or anchor.path is None:
            raise PatchRefused(
                PatchRefusal.NO_SUCH_FILE,
                f"a patch was addressed at a source anchor reading "
                f"{anchor.reading.value!r}, which names no file. Only an anchored "
                "reading names a file this bench opened inside the checkout, and a "
                "patch to any of the five absences is a write with no target "
                "(ADR-0071 §3, ADR-0072 §2)",
            )
        return cls(path=anchor.path, contents=contents)


@dataclass
class Throwaway:
    """The copy of the checkout this run is allowed to write in, and how it ended.

    The record `apply_patch` takes, and the whole of why the original is safe: there
    is no signature in this module through which a bare `Path` can be handed to the
    patch writer, so a caller cannot address the original checkout by mistake. What
    stops one being addressed *on purpose* is `__post_init__`, which refuses a root
    this module did not name.

    Mutable, alone among the records in this module, because two of its three fields
    are written by the `finally` that drops it — and a frozen record would mean the
    drop had nowhere to report to except a raise, which is the one thing a `finally`
    unwinding somebody else's exception must not do (ADR-0063 §2).
    """

    root: Path
    """The copy's own root. Everything written by this run is written under it."""

    workspace: str
    """The name it was made under, derived once from the run id."""

    patched: tuple[str, ...] = ()
    """Which files of the copy were replaced, in the order they were written.

    A record of what happened rather than a manifest to clean up from: the drop is
    wholesale and does not read this, and nothing else does either — what a proof
    publishes about the file it replaced it reads off the `Patch` (`proving.py`).
    Kept because *what this run wrote into the copy* is the question a person
    debugging the loop asks first, and the copy is gone by the time they ask it.
    """

    drop_error: str | None = field(default=None)
    """The operating system's own words, if the copy could not be removed.

    `None` on every run that cleaned up, which is every run this suite has seen. It
    is the operator's runner and the operator's disk, so on the one path where a
    directory survives, the message that says why is theirs to read — `Teardown.error`
    is the same decision about somebody's store (ADR-0063 §3).
    """

    def __post_init__(self) -> None:
        """Refuse a root this module would not have named, at the record's own door.

        The invariant belongs to the type rather than to whoever calls `apply_patch`:
        there is no `Path` parameter on the patch writer, so the only way to address
        a directory with it is to build one of these, and a record whose root is not
        named the way `workspace_for` names one is refused here. The whole of
        ADR-0072 §1 rests on it.

        **What it is and what it is not.** A name is a weak proof of provenance — it
        is exactly as strong as the claim *this directory is called what this module
        calls its copies* — and it is deliberately the proof that survives being
        pickled, passed and reconstructed, which a private token would not. What it
        stops is the accident: a caller reaching for `apply_patch` with the record
        they happen to be holding.
        """
        if self.root.name != self.workspace or not _WORKSPACE_BODY.fullmatch(
            self.workspace.removeprefix(WORKSPACE_PREFIX)
        ):
            raise ValueError(
                f"a throwaway checkout was declared at {self.root.name!r} under the "
                f"workspace {self.workspace!r}. Only a directory named the way "
                "`workspace_for` names one, and named for its own workspace, may be "
                "patched: a record pointing at the caller's own checkout would make "
                "the patch writer write into their repository (ADR-0072 §1)"
            )


@contextmanager
def throwaway_checkout(checkout: Path, *, workspace: str) -> Iterator[Throwaway]:
    """Copy the checkout, hand back the copy, and drop it however this ends.

    **One `finally`, and it covers every ending.** Not a line at the end of the happy
    path — the runs that end badly are exactly the runs that would leave a patched
    copy of somebody's repository on their runner. ADR-0072 §3 enumerates the eight
    and `test_throwaway_checkout.py` holds each of them; the reason it is a `finally`
    and not an `except Exception` is the eighth, a cancellation, which is a
    `BaseException` and passes straight through an `except` clause written for the
    other seven.

    The copy is made **before** anything else can fail, and the directory it goes in
    is created before the copy, so that a copy which fell over halfway is still a
    directory this function knows the name of and drops.

    `symlinks=True`: links are copied as links rather than followed. Following them
    would let a checkout with a link to `/` be copied for as long as the disk lasted,
    and a link is safe to keep because `apply_patch` decides containment on the
    **resolved** path — a link inside the copy pointing at `/etc/passwd` resolves
    outside it and is refused, which is ADR-0071 §5's rule applied to the write.
    """
    root = Path(tempfile.mkdtemp(prefix=f"{workspace}-")) / workspace
    throwaway = Throwaway(root=root, workspace=workspace)
    try:
        shutil.copytree(
            checkout,
            root,
            symlinks=True,
            ignore=shutil.ignore_patterns(*NOT_COPIED),
            ignore_dangling_symlinks=True,
        )
        yield throwaway
    finally:
        throwaway.drop_error = drop_workspace(root.parent)


def drop_workspace(root: Path) -> str | None:
    """Remove a throwaway workspace wholesale, and never raise doing it.

    Wholesale rather than file by file, on ADR-0063's own argument: deleting what
    this bench remembers writing needs a manifest, the manifest is a second copy of
    the truth, and its failure mode is a half-patched tree nobody hears about. One
    `rmtree` either removes everything or reports that it did not.

    **It never raises**, because it is called from a `finally` that is very often
    unwinding the exception that is the run's actual answer. A cleanup that raised
    there would replace the reason the run ended with the reason its cleanup failed,
    and the operator would lose the more important of the two (ADR-0063 §2). Both are
    kept: the original propagates, and this comes back as a string.
    """
    failures: list[str] = []
    shutil.rmtree(
        root, onexc=lambda _function, _path, error: failures.append(str(error))
    )
    return failures[0] if failures else None


def apply_patch(throwaway: Throwaway, patch: Patch) -> Path:
    """Write one patch into the copy, or refuse it, and never touch the original.

    The order below is the argument of ADR-0072 §2 made executable, and the sequence
    is what it means locally: refuse a path that is not relative before resolving
    anything, resolve both ends before comparing them, refuse what is outside, refuse
    what is not already a file, and only then write.

    **A patch replaces and never creates.** A file that is not in the checkout is not
    part of what the caller handed over, and a mechanism that could add one is a
    mechanism that can add a module the re-serve would then import.
    """
    if Path(patch.path).is_absolute() or ".." in Path(patch.path).parts:
        raise PatchRefused(
            PatchRefusal.NOT_A_RELATIVE_PATH,
            f"a patch was addressed at {patch.path!r}. A patch names a file relative "
            "to the checkout root, with no `..` in it: an absolute path names the "
            "runner's filesystem rather than this repository, and a `..` names its "
            "way out of the copy (ADR-0072 §2)",
        )
    root = throwaway.root.resolve(strict=False)
    written = (throwaway.root / Path(patch.path)).resolve(strict=False)
    if not written.is_relative_to(root):
        raise PatchRefused(
            PatchRefusal.LEFT_THE_CHECKOUT,
            f"a patch addressed at {patch.path!r} resolved outside the throwaway "
            "checkout. Containment is decided on the resolved path, so a symlink "
            "inside the copy pointing out of it is outside it — and a repository is "
            "a thing a caller can put links in (ADR-0071 §5)",
        )
    if not written.exists():
        raise PatchRefused(
            PatchRefusal.NO_SUCH_FILE,
            f"a patch addressed at {patch.path!r} names no file in this checkout. A "
            "patch replaces a file the bench read; it never creates one, because a "
            "file the caller did not hand over is not part of what is being tested",
        )
    if not written.is_file():
        raise PatchRefused(
            PatchRefusal.NOT_A_REGULAR_FILE,
            f"a patch addressed at {patch.path!r} names something that is not a "
            "regular file. A directory, a device or a socket is not a source file, "
            "and writing over one is not patching",
        )
    if (
        written.stat().st_size > MAX_PATCHED_FILE_BYTES
        or len(patch.contents.encode("utf-8")) > MAX_PATCHED_FILE_BYTES
    ):
        raise PatchRefused(
            PatchRefusal.TOO_LARGE,
            f"a patch addressed at {patch.path!r} is over "
            f"{MAX_PATCHED_FILE_BYTES} bytes, on one side or the other. The bench "
            "writes a bounded amount into a runner it does not own, for one optional "
            "claim about one case",
        )
    written.write_text(patch.contents, encoding="utf-8")
    throwaway.patched = (*throwaway.patched, patch.path)
    return written
