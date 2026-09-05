"""Where in the caller's own checkout the thing that failed is defined — or which
of five reasons the bench cannot say.

**A target is a URL.** `TargetConfig` is a name, a url, a token, an `agent_type` and
two declarations, and `send_message` is the only path to one: there is no source tree
anywhere in the picture, and there has not been one since the contract was written.
The single circumstance in which the bench and the code are in the same place is the
composite Action of
[ADR-0066](../../docs/adr/0066-the-action-is-a-composite-step-in-the-callers-own-repository.md)
— the caller's repository, the caller's runner, the caller's checkout on disk, and a
`--callback` the bench imported out of it. So this module answers *sometimes*, and
the argument for how it says so is
[ADR-0071](../../docs/adr/0071-a-finding-points-at-a-file-the-bench-read.md).

**Read, never written.** Nothing here opens a file for writing, creates one, or
executes one; patching a checkout is #109's sixth sub-issue and must not arrive here
by accident (ADR-0071 §5). The whole of what this module does to somebody else's
filesystem is `stat` one file and read at most `MAX_ANCHORED_FILE_BYTES` of it to
count newlines, and not one byte of what it reads is published or returned.

**Nothing here reaches an instrument.** No `JudgeBrief`, no narrative prompt and no
remediation prompt carries a path: a filename in a brief un-blinds the judge more
thoroughly than a target name would (ADR-0004, ADR-0071 §6). The anchor is derived
after every verdict has been decided, on the report side, which is why this module is
imported by `assembler.py` and by the CI entrypoint and by nothing else.

**Nothing here is a figure.** A reading is a name off a closed set and a line number
is a position in a file; no rate, band, interval or `D` may read either (D13,
ADR-0006), and the line number is the only integer this module produces.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

MAX_ANCHORED_FILE_BYTES = 4 * 1024 * 1024
"""The most of a caller's file this bench will read in order to check one line.

A ceiling rather than a read to the end, because the bench is reading a file it was
not handed, on a runner it does not own, to verify one optional line of a report —
and there is no bound on what a checkout contains. Four mebibytes is two orders of
magnitude above the largest source file in this repository and is read in well under
a second on a hosted runner, so no honest module is refused by it; a file above it is
reported as unreadable, which is the same named absence a missing file gets and is
not a claim that anything is wrong.

The figure is a property of this literal: raise it and a run can be made to read an
arbitrary blob because a `.pyc` named one, lower it and ordinary generated modules
stop being anchorable. `test_source_anchor.py` writes a file over it and asserts the
reading, so editing the number without editing that test leaves the claim unmade.
"""


class SourceAnchorReading(StrEnum):
    """Whether a finding could be pointed at a file, and which absence holds if not.

    A closed set rather than a nullable path, on `payload.py`'s three-kinds-of-nothing
    rule: *the bench never saw this target's source*, *the target is an endpoint and
    no file on disk is known to be it*, and *the file the object named could not be
    read* are three different facts about a run, and a reader holding only the
    document has to be able to tell them apart. None of them is a finding with nothing
    wrong, and none of them renders blank (ADR-0071 §3).
    """

    ANCHORED = "anchored"
    """A file inside the checkout and a line inside that file, both verified."""

    NO_CHECKOUT = "no_checkout"
    """The bench did not run where the code is — the ordinary case, and no fault."""

    TARGET_IS_A_URL = "target_is_a_url"
    """A checkout was on disk and the target was an endpoint, so none of it is it."""

    SOURCE_NOT_ON_THE_OBJECT = "source_not_on_the_object"
    """The object names no source this bench can locate without guessing."""

    SOURCE_OUTSIDE_THE_CHECKOUT = "source_outside_the_checkout"
    """It resolved outside the workspace, so it is refused rather than published."""

    SOURCE_COULD_NOT_BE_READ = "source_could_not_be_read"
    """It is inside the checkout and absent, unreadable, over the ceiling, or short."""


_SAID: dict[SourceAnchorReading, str] = {
    SourceAnchorReading.NO_CHECKOUT: (
        "not anchored — the bench could not see this target's source. It ran against "
        "a target over the message contract with no checkout on disk, which is every "
        "run that is not an Action in the caller's own repository (ADR-0066). This "
        "says nothing about the code and nothing about the failure"
    ),
    SourceAnchorReading.TARGET_IS_A_URL: (
        "not anchored — the bench could not see this target's source. A checkout was "
        "on disk and this target is an endpoint, so nothing in that checkout is known "
        "to be the thing that answered"
    ),
    SourceAnchorReading.SOURCE_NOT_ON_THE_OBJECT: (
        "not anchored — the bench could not see this target's source. The object it "
        "served names no source file this bench can locate: a builtin, an extension "
        "module or a callable compiled from a string names none at all, and one that "
        "names a file only relative to some working directory is a file this bench "
        "would have to guess the root of"
    ),
    SourceAnchorReading.SOURCE_OUTSIDE_THE_CHECKOUT: (
        "not anchored — the file the target's object named resolved outside the "
        "checkout, so it was refused. A path outside the workspace names the runner's "
        "filesystem rather than this repository, and a signed document is the wrong "
        "place for it (ADR-0008)"
    ),
    SourceAnchorReading.SOURCE_COULD_NOT_BE_READ: (
        "not anchored — the file the target's object named is inside the checkout and "
        "the bench could not read it back: absent, not a regular file, larger than "
        "the bench will read, or shorter than the line it reported"
    ),
}
"""What the document says under each absence, in place of a location.

Said rather than omitted, and none of the five sentences says or implies that the
target's code is fine: an unanchored finding is a finding the bench could not point
at, which is a fact about where the bench ran (ADR-0071 §3).
"""


@dataclass(frozen=True)
class SourceAnchor:
    """A file and a line in the caller's own checkout, or the stated absence of one.

    **"Anchor" here is not ADR-0014's anchor.** That word is already load-bearing in
    this codebase for the two reference agents' constructed rates, which is why this
    record, its module, its payload key and its screen field are all *source* anchor
    and never the bare noun (ADR-0071 §1). A band is anchored to an agent; a finding
    is anchored to a file.

    **What it points at is the target's entrypoint, not the line that caused the
    failure.** The bench read one object off the checkout and asked the interpreter
    where it was defined; it has no mapping from a defeated control to a statement,
    and a model asked to invent one would be a fourth instrument producing
    unverifiable claims about somebody else's code. `stated()` says which of the two
    claims this is, because a reader who assumed the stronger one would take the line
    as an accusation (ADR-0071 §2).

    The path is **relative to the checkout root and never absolute**: the absolute
    one carries the runner's layout and the workspace's own name, and neither is
    material this document is about (ADR-0008, ADR-0071 §4).
    """

    reading: SourceAnchorReading
    """Which of the six holds, as a name a consumer can match rather than infer."""

    path: str | None = None
    """The file, relative to the checkout root, in POSIX form — or nothing."""

    line: int | None = None
    """The line that file defines the target's entrypoint on — or nothing."""

    def __post_init__(self) -> None:
        """Refuse a located absence and a blank location, at the record's own door.

        `Precedent`'s discipline: the invariant belongs to the type rather than to
        whoever calls `anchor_for`, so a later caller constructing one by hand cannot
        publish `no_checkout` with a path under it — which would read as a location
        the bench claims to have checked and did not.
        """
        anchored = self.reading is SourceAnchorReading.ANCHORED
        located = self.path is not None and self.line is not None
        if anchored is not located:
            raise ValueError(
                f"a source anchor reading {self.reading.value!r} carried "
                f"path={self.path!r} and line={self.line!r}. Exactly the anchored "
                "reading carries a location: an absence with a path under it would "
                "publish a file the bench never checked, and an anchored reading "
                "without one would print a location as a blank (ADR-0071)"
            )

    @property
    def location(self) -> str | None:
        """The file and the line as one string, `path:line`, or nothing.

        **One string and not two fields, and the line is never a number that
        travels.** The findings section of a signed document carries no figure at any
        depth — a reader who wants one builds it out of whatever is on the page, so
        the page offers none (ADR-0005, D12) — and `test_payload.py` holds that as a
        walk over every leaf under the section. A line number is a position in a file
        rather than a measurement, and this is the form that keeps it from being
        mistaken for one anyway. It is also the form every reviewer UI prints and
        every editor accepts, which is the convention this borrows from (ADR-0071 §4).
        """
        if self.path is None or self.line is None:
            return None
        return f"{self.path}:{self.line}"

    def stated(self) -> str:
        """This anchor in one sentence, for the two surfaces to print unchanged.

        On the record rather than in a renderer, in `Attribution.stated()`'s pattern
        and for its reason: the signed document and the report screen must print one
        claim about one anchor, and `frontend/src/report/report.ts` asserts that every
        string a block draws is the payload's own wording character for character.
        """
        if self.reading is not SourceAnchorReading.ANCHORED:
            return _SAID[self.reading]
        return (
            f"anchored at {self.path}, line {self.line} — where the bench read this "
            "target's entrypoint off the checkout it ran in. It is the definition "
            "site of the object that answered, and deliberately not a claim that this "
            "line is the defect: the bench has no mapping from a defeated control to "
            "a statement, and would not print a guess at one (ADR-0071)"
        )


NOT_RUN_WHERE_THE_CODE_IS = SourceAnchor(reading=SourceAnchorReading.NO_CHECKOUT)
"""The anchor of every run that is not an Action in the caller's own repository.

The default everywhere, so that a surface reaching this material gets the honest
absence rather than an optional field somebody forgot to fill: `POST /runs` serves a
hosted bench that never has a checkout, and the reading it publishes is this one.
"""


def anchor_for(target: object | None, *, checkout: Path | None) -> SourceAnchor:
    """Where the object this run served is defined, checked against the checkout.

    Three populations and one function (ADR-0071 §3): no checkout at all, a checkout
    with an endpoint target in front of it, and a checkout with an object the bench
    imported out of it. Only the third can produce a location, and it produces one
    only when the file is still there to be read.

    **It never raises.** Every way of failing to find a file is a reading, because
    this is an optional line of a report and a run reaching it has already spent an
    operator's inference budget — an exception escaping here would end the run over
    the one thing in it that decides nothing.

    ADR-0071 §5 argues the properties of reading a stranger's checkout; the lines
    below are where each one is enforced, in the order the argument makes them, and
    the sequence is what the argument means locally: resolve before comparing, refuse
    what is outside, verify the line, publish relative.
    """
    if checkout is None:
        return NOT_RUN_WHERE_THE_CODE_IS
    if target is None:
        return SourceAnchor(reading=SourceAnchorReading.TARGET_IS_A_URL)
    defined = _defined_at(target)
    if defined is None:
        return SourceAnchor(reading=SourceAnchorReading.SOURCE_NOT_ON_THE_OBJECT)
    named, line = defined
    try:
        root = checkout.resolve(strict=False)
        source = Path(named).resolve(strict=False)
    except OSError:
        return SourceAnchor(reading=SourceAnchorReading.SOURCE_COULD_NOT_BE_READ)
    if not source.is_relative_to(root):
        return SourceAnchor(reading=SourceAnchorReading.SOURCE_OUTSIDE_THE_CHECKOUT)
    if not _has_line(source, line):
        return SourceAnchor(reading=SourceAnchorReading.SOURCE_COULD_NOT_BE_READ)
    return SourceAnchor(
        reading=SourceAnchorReading.ANCHORED,
        path=source.relative_to(root).as_posix(),
        line=line,
    )


def _defined_at(target: object) -> tuple[str, int] | None:
    """The file and line the interpreter has for this object, off its code object.

    The code object rather than `inspect.getsourcelines`, which reads the whole file
    through `linecache` to find a block's extent: the extent is not published, and a
    helper that reads an unbounded file is exactly what the ceiling above exists to
    prevent. A callable instance is asked for its `__call__`, because a class with a
    `__call__` is a shape a caller's `--callback` is allowed to be.
    """
    instance_call = None if isinstance(target, type) else type(target).__call__
    for candidate in (target, instance_call):
        code = getattr(getattr(candidate, "__func__", candidate), "__code__", None)
        filename = getattr(code, "co_filename", None)
        first = getattr(code, "co_firstlineno", None)
        # Absolute only, and this is the guard rather than a tidiness: a relative
        # `co_filename` — what `python foo.py` produces — would be resolved against
        # *this process's* working directory, which in the Action is the bench's own
        # checkout and not the caller's. That resolution could land a file inside a
        # root it has no relation to, so an unlocatable name is refused rather than
        # placed (ADR-0071 §5).
        if isinstance(filename, str) and isinstance(first, int):
            if Path(filename).is_absolute():
                return filename, first
    return None


def _has_line(source: Path, line: int) -> bool:
    """Whether that file is one this bench will read and does have that line in it.

    The verification that makes the anchor evidence rather than a report of one: a
    checkout that moved under a long-running process, or a module imported from a
    `.pyc` whose source was replaced, would otherwise publish a line that is not
    there. Read in chunks and counted, never held: the content is a caller's source
    and this bench has no use for it beyond counting its newlines.
    """
    try:
        stat = source.stat()
        if not source.is_file() or stat.st_size > MAX_ANCHORED_FILE_BYTES:
            return False
        seen, last = 0, b""
        with source.open("rb") as reading:
            while chunk := reading.read(64 * 1024):
                seen += chunk.count(b"\n")
                last = chunk[-1:]
    except OSError:
        return False
    # A last line with no newline after it is still a line, which is what a file
    # ending mid-statement looks like and is a file the interpreter imported happily.
    return 0 < line <= seen + (1 if last and last != b"\n" else 0)
