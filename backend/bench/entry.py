"""The one write into the case library: a route the gate admitted, filed as a record.

Where the loop [PLAN](../../PLAN.md) §10 claims closes actually closes. The adaptive
attacker finds a route the fixed suite missed, `propose_case` drafts it, the admission
gate decides it against a declared threshold — and until this module existed the
admitted case was *returned* and nothing put it anywhere, so the library the next run
loaded was the library the repository shipped. `scripts/swap.py` printed that fact at
the end of every run.

The decision, its alternatives, and what it does to the citation and to the printed
denominator are
[ADR-0033](../../docs/adr/0033-an-admitted-route-is-written-into-the-library.md).
Three of its points decide the shape of everything below:

**This is ADR-0010's single sanctioned crossing, and it is sanctioned by a number.**
A case written here entered the scored population — the next run draws **attempts**
from it — and the only thing that let it in is
[ADR-0012](../../docs/adr/0012-adaptive-discovered-cases-face-a-cross-model-admission-bar.md)'s
cross-model bar: three reference agents, two underlying models, `D` over the declared
floor. So `enter` re-derives that decision off the record it is about to write and
refuses a case that does not clear it. Nothing here takes a bar, a floor or a rule
that would let a caller name a weaker one.

**Nothing here reads a clock.** A record's `admission.admitted_on` is the day the
three reference agents were run, which for a route answered from the admission
memory is a day in the past (`decided.DecidedRoutes.recall`, ADR-0032). There is no
`today` parameter in this module and no call to `date.today` in it, so a
year-old measurement cannot be dated to this morning by the run that files it.

**Remembering an admission is not admitting, and the library is the record of what
was admitted.** The de-duplication key is `decided.RouteKey` — the family and a
digest of the probe — but what it is looked up against is *the library on disk*, not
the admission memory. ADR-0032 states the distinction and this module honours it:
the memory says what was decided, and a route it holds a row for may never have been
written anywhere.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, fields
from pathlib import Path

from backend.bench.admission import NotAdmitted, outcome_for
from backend.bench.cited import moved_past
from backend.bench.decided import RouteKey
from backend.bench.lease import holding_the_library
from backend.bench.library import (
    AdmissionBar,
    AdmissionReading,
    AdmissionRecord,
    Case,
    CaseStatus,
    JudgedCondition,
    LibraryVersion,
    RetrievedFrom,
    SuccessCondition,
    load_case,
    load_library,
)
from backend.bench.payload import GateCitation
from backend.bench.retirement import history_block, retirement_block

CASE_SUFFIX = ".toml"
"""What a case record is called. `library.load_library` globs for exactly this."""


def case_record(case: Case) -> str:
    """One whole `Case` as the TOML a library holds, in the shape `load_case` reads.

    **There was no TOML writer in this tree and this is it.** `library.py` reads with
    `tomllib`, which has no writer at all, and `scripts/admit.py` hand-builds the
    lines of one small `[admission]` block and appends them to a record a human
    already authored. A whole record is a different problem: every field, both
    criterion shapes, the admission block, the decay series and the retirement.

    **The assertion that stands for this function is the round trip**, and it is not
    only a test: `enter` reads back every record it writes and refuses to leave one
    on disk that does not load equal. A record `load_case` cannot read is not a bad
    record, it is a library no run can load at all.

    The key order is the order a human authored these files in, so that a written
    record and an authored one diff against each other rather than against a
    serialiser's alphabet.
    """
    lines = [
        f"id = {_basic(case.id)}",
        f"family = {_basic(str(case.family))}",
        f"verdict_class = {_basic(str(case.verdict_class))}",
        f"applies_to = [{', '.join(_basic(name) for name in case.applies_to)}]",
        f"requires = [{', '.join(_basic(str(name)) for name in case.requires)}]",
        f"added_on = {case.added_on.isoformat()}",
        f"trigger = {_basic(str(case.trigger))}",
        f"discovered_by = {_basic(str(case.discovered_by))}",
        f"transform = {_basic(str(case.transform))}",
        f"status = {_basic(str(case.status))}",
    ]
    # Written only on a variant, because TOML has no null and a base case's record
    # says nothing at all — the shape `load_case` reads with `get` and the pairing
    # on the record then checks (ADR-0051).
    if case.derived_from is not None:
        lines.append(f"derived_from = {_basic(case.derived_from)}")
    if case.citation is not None:
        lines.append(f"citation = {_basic(case.citation)}")
    lines.extend(("", f"payload = {_payload_array(case.payload)}"))
    lines.extend(
        (
            "",
            "[external_id]",
            f"identifier = {_basic(case.external_id.identifier)}",
            f"not_tested = {_multiline(case.external_id.not_tested)}",
        )
    )
    if case.retrieval is not None:
        lines.extend(_retrieval(case.retrieval))
    if case.success_condition is not None:
        lines.extend(_success_condition(case.success_condition))
    if case.judged_condition is not None:
        lines.extend(_judged_condition(case.judged_condition))
    record = "\n".join((*lines, ""))
    if case.admission is not None:
        record += admission_block(
            bar=case.admission.bar,
            admitted_on=case.admission.admitted_on.isoformat(),
            readings=case.admission.readings,
        )
    # The two blocks a *gate run* writes, through the functions that gate run
    # writes them with. A second copy of either would be a second definition of
    # the decay series' format, and the copy nobody exercises is the one that rots
    # (`retirement.store` is the caller that appends one to a record in place).
    for reading in case.history:
        record += history_block(reading)
    if case.retirement is not None:
        record += retirement_block(case.retirement.retired_on)
    return record


def _retrieval(retrieval: RetrievedFrom) -> list[str]:
    """The `[retrieval]` block a case retrieved from a published corpus carries.

    Five values and all five are written, because a record that lost any of them
    reads back as a payload with no provenance and `Case.__post_init__` refuses it
    — the round trip `enter` performs is where that would be caught, which is the
    point of writing the whole block rather than the fields a caller thought of
    ([ADR-0047](../../docs/adr/0047-a-retrieved-case-cites-its-row-and-a-person-signs-for-its-family.md)).

    The attribution is multi-line because it is a notice a person reads and it does
    not fit a line, and it is written last so that a hand-edit dropping an earlier
    line cannot leave a stray delimiter behind it; the other four are single-line
    values on `_basic`'s terms.
    """
    return [
        "",
        "[retrieval]",
        f"address = {_basic(retrieval.address)}",
        f"licence = {_basic(retrieval.licence)}",
        f"assigned_by = {_basic(retrieval.assigned_by)}",
        f"technique = {_basic(retrieval.technique)}",
        f"attribution = {_multiline(retrieval.attribution)}",
    ]


def admission_block(
    *, bar: AdmissionBar, admitted_on: str, readings: Sequence[AdmissionReading]
) -> str:
    """The `[admission]` block one measurement puts on a record.

    Takes the parts rather than an `AdmissionRecord` for one caller's sake:
    `scripts/admit.py` prints this block for a *rejected* case too — a reader
    deciding whether to believe a discard needs the counts as much as one deciding
    whether to believe an entry — and a rejected cross-model case is exactly the
    record `AdmissionRecord.__post_init__` refuses to build. One writer of these
    lines rather than two, because two would only have to disagree once for a
    printed block and a written one to describe different evidence.

    `admitted_on` is a string this function does not compute. It is the day the three
    reference agents were run and it arrives from the record, so nothing here can
    date a measurement to today.
    """
    lines = [
        "",
        "[admission]",
        f"bar = {_basic(str(bar))}",
        f"admitted_on = {admitted_on}",
    ]
    for reading in readings:
        lines.append("[[admission.readings]]")
        lines.extend(_counts(reading))
    return "\n".join((*lines, ""))


def _success_condition(condition: SuccessCondition) -> Iterable[str]:
    """The `[success_condition]` block of a deterministic case."""
    yield ""
    yield "[success_condition]"
    yield f"kind = {_basic(str(condition.kind))}"
    if condition.planted_canary is not None:
        yield f"planted_canary = {_basic(condition.planted_canary)}"


def _judged_condition(condition: JudgedCondition) -> Iterable[str]:
    """The `[judged_condition]` block of a judged case."""
    yield ""
    yield "[judged_condition]"
    yield f"question = {_multiline(condition.question)}"
    yield f"succeeded_when = {_multiline(condition.succeeded_when)}"
    yield f"resisted_when = {_multiline(condition.resisted_when)}"


def _counts(reading: AdmissionReading) -> Iterable[str]:
    """The six lines one reading is, in the keys `AdmissionReading.read` takes back."""
    yield f"model = {_basic(reading.model)}"
    yield f"attempts = {reading.attempts}"
    yield f"hardened = {reading.hardened}"
    yield f"weak = {reading.weak}"
    yield f"trivial = {reading.trivial}"
    if reading.adjudicator is not None:
        yield f"adjudicator = {_basic(reading.adjudicator)}"


class UnwritableRecord(ValueError):
    """A value that cannot be put in a TOML record without changing what it says.

    Raised rather than escaped away, because every value that reaches this point
    came off a `Case` that a run measured, and a serialiser that silently rewrote
    one would write a record whose payload is not the payload that ran.
    """


def _basic(value: str) -> str:
    """One short value as a TOML basic string, escaped.

    Refuses a newline rather than escaping it: every field written through here is a
    single-line value on the record — an id, a family, a model — and one that had
    acquired a line break is a record that would read back as something else.
    """
    if "\n" in value:
        raise UnwritableRecord(
            f"{value!r} spans lines and is written as a single-line value. A record "
            "field that acquired a line break is a field that means something else"
        )
    _refuse_control_characters(value)
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _payload_array(turns: tuple[str, ...]) -> str:
    """A case's payload as the TOML array of multi-line strings a record holds.

    An array whichever it is — one turn or several — because `Case.payload` is a
    sequence and a record written two ways is two shapes for `load_case` to read
    (ADR-0053). A single-turn record therefore reads with one wrapping bracket,
    which is exactly what the eighteen on disk gained.
    """
    written = ", ".join(_multiline(turn) for turn in turns)
    return f"[{written}]"


def _multiline(value: str) -> str:
    """One prose value as a TOML multi-line basic string, escaped.

    Multi-line and not a one-line string with `\\n` in it, because these are the
    fields a person reads: a payload, an `external_id.not_tested` paragraph, a
    judged criterion. The authored records in `backend/cases/` are written this way
    and a run-written record has to diff against them.

    The newline after the opening delimiter is the one TOML discards, so the value
    is reproduced exactly whether or not it ends in one. **Two escapes and no more:**
    a backslash, and a run of three quotes. Everything else is left as the author
    wrote it, which is the point of choosing this form.

    A quote or two *abutting* the closing delimiter needs no escape and does not get
    one, which is a fact about TOML rather than an oversight: the delimiter match is
    greedy, so `a quote"` inside these markers reads back as `a quote"`. An escape
    for it was written here first and removed when the break that was supposed to
    prove it necessary passed — a guard whose absence nothing can detect is a guard
    that guards nothing, and `test_entry.py`'s hostile payload ends in a quote so
    that the reading this rests on is asserted rather than assumed.
    """
    _refuse_control_characters(value)
    escaped = value.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    return f'"""\n{escaped}"""'


def _refuse_control_characters(value: str) -> None:
    """Refuse a value TOML cannot hold literally, naming the character.

    Tab and newline are the two a record legitimately carries. A carriage return, a
    form feed or a null arrived from something other than an author's editor, and
    escaping one here would put a record on disk whose payload is not the payload
    the target was sent.
    """
    for character in value:
        if character in "\t\n":
            continue
        if character < " " or character == "\x7f":
            raise UnwritableRecord(
                f"a case record cannot hold {character!r} literally, and escaping it "
                "would write a payload that is not the one that ran"
            )


@dataclass(frozen=True)
class Entered:
    """One case this run wrote into the library, and the record it wrote.

    The case rather than its id, on `Filing.filed`'s reasoning: the one question a
    reader has about a library that now grows per run is *what went into it*, and a
    count cannot be checked against what the directory holds.
    """

    case: Case
    path: Path

    admission: AdmissionRecord
    """The measurement that let this case in, held rather than reached for.

    `Case.admission` is `AdmissionRecord | None` because a *proposed* case has none,
    and an `Entered` is only ever built for a case `_entered` has re-derived an
    admission for. Carrying the record makes that the type's invariant instead of a
    branch in `stated()` that would have to render a sentence about a state this
    record cannot be in.
    """

    def stated(self) -> str:
        """The record as the run that wrote it names it, and what let it in."""
        models = sorted({one.model for one in self.admission.readings})
        return (
            f"written: {self.path.name} — {self.case.family}, "
            f"discovered_by {self.case.discovered_by}, admitted under the "
            f"{self.admission.bar} bar on the reading of "
            f"{self.admission.admitted_on.isoformat()} against {', '.join(models)}"
        )


@dataclass(frozen=True)
class AlreadyInTheLibrary:
    """A route this library already holds a record for, so nothing was written.

    The de-duplication ADR-0032 left this module a surface for, and the reason it
    is a *reported* answer rather than a silent skip: `proposal.py` mints a fresh
    `uuid` per proposal, so two records for one route is what a run does by default
    and the reader has to be able to see that it did not.
    """

    route: RouteKey
    proposed_as: str
    """The id this run proposed the route under — a fresh `uuid` every time."""

    held_as: str
    """The id the library already holds it under, which is the record that stands."""

    status: CaseStatus
    """Whether the record that stands is still run, or was retired.

    Reported because a retired collision is the one worth reading. A rediscovery
    written as a fresh active record would un-retire a case the rule retired, under
    a new id, and the retirement rule's own reading would sit on a record nothing
    now runs.
    """

    def stated(self) -> str:
        """Why nothing was written for this route."""
        return (
            f"not written: {self.route.stated()} is already in this library as "
            f"{self.held_as} ({self.status}), and this run proposed it as "
            f"{self.proposed_as}. One route is one record — a second would grow the "
            "family's n twice for one payload"
        )


@dataclass(frozen=True)
class Entry:
    """What one run's admitted routes did to the library it was run against.

    Returned rather than logged, on `Filing`'s terms: a write nobody is handed is a
    write nobody reads, and a run that admitted a route and wrote nothing has to be
    a statement a reader can find rather than an absence they have to notice.
    """

    version: LibraryVersion
    """The version the library is at now, read off the records on disk.

    Read after the write rather than computed from the write, so that it is the
    version the *next* run will compute for itself. A count and a digest of what is
    there, which is the only form in which "the library changed" is checkable.
    """

    entered: tuple[Entered, ...] = ()
    held: tuple[AlreadyInTheLibrary, ...] = ()

    cited: GateCitation | None = None
    """The gate run this library cites, as it now stands, or `None` where it cites none.

    Carried back so that `stated()` below prints the superseding rather than leaving
    an operator to notice it in a file: a library that has grown past the version its
    own gate run was decided at is the one fact about this write a *reader of the next
    report* will meet, and it is better met here first.

    Read back through `cited.moved_past` after the write rather than composed, so the
    sentence a run prints is the sentence the citation holds.
    """

    @property
    def changed(self) -> bool:
        """Whether this run moved the library at all."""
        return bool(self.entered)

    def stated(self) -> str:
        """The lines a run prints about what it put in the library."""
        if not self.entered and not self.held:
            return (
                "no route cleared the cross-model bar, so this library is the "
                f"library this run was made against — {self.version.stated()}"
            )
        lines = [
            *(one.stated() for one in self.entered),
            *(one.stated() for one in self.held),
        ]
        if self.changed:
            lines.append(
                f"this library is no longer the library this run was made against: "
                f"{self.version.stated()}. Every case above entered on ADR-0012's "
                "cross-model bar and on nothing else — the next run executes it, "
                "and the gate run this library cites was decided without it"
            )
            if self.cited is not None and self.cited.moved is not None:
                lines.extend(f"  {line}" for line in self.superseded())
        return "\n".join(lines)

    def superseded(self) -> tuple[str, ...]:
        """What this write did to the gate run the library cites, in that record's
        own words, or nothing where it cites none.

        The citation's sentence and not a second one written here, so an operator
        reading the terminal and a recipient reading the next signed report are told
        the same thing (`payload.LibraryMoved.stated`).
        """
        if self.cited is None or self.cited.moved is None:
            return ()
        return tuple(self.cited.moved.stated().splitlines())


def enter(cases: Iterable[Case], library: Path, *, holder: str) -> Entry:
    """Write each admitted case this library does not already hold a route for.

    **The lease is taken here and not by the caller** — why, and why that differs
    from `cited.cite`, is ADR-0033's "Who takes the lease, and why not the caller".
    The consequence at this call site is `_entered`'s shape: the whole
    read-modify-write is inside the block, so the key set cannot be read before a
    concurrent writer adds to the directory.

    **The de-duplication reads the library and never the admission memory** (module
    docstring, ADR-0032). Every record on disk, retired ones included, because a
    rediscovery written as a fresh active record would un-retire what the retirement
    rule retired.

    **Admission is re-derived off each record** and raised on rather than selected
    out, unlike `filing.file_precedent`'s judged findings (ADR-0031 point 3): a
    proposed case reaching here is a caller that has lost its own invariant, not a
    data condition this function is asked to sort. `promote` returns a case only when
    it cleared.

    **No `today`, here or anywhere in this module** (module docstring).
    """
    with holding_the_library(library, holder):
        return _entered(cases, library)


def _entered(cases: Iterable[Case], library: Path) -> Entry:
    """The write itself, under the lease `enter` is holding."""
    held = {RouteKey.of(case): case for case in load_library(library)}
    entered: list[Entered] = []
    already: list[AlreadyInTheLibrary] = []
    for case in cases:
        # Bound before the decision is re-derived, and refused here rather than left
        # to `outcome_for`'s own message: a case with no block is the *proposed*
        # state, and the sentence a reader needs names this library and the reason
        # entry is not the proposer's to grant.
        admission = case.admission
        if admission is None:
            raise NotAdmitted(
                f"{case.id} records no admission, so it is not written into "
                f"{library}. A case enters the library by separating the three "
                "reference agents, and the gate decides that rather than the run "
                "that files the record (ADR-0010, spec story 69)"
            )
        outcome = outcome_for(case)
        if not outcome.admitted:
            raise NotAdmitted(
                f"{case.id} does not clear the {outcome.bar} bar its provenance "
                f"requires, so it is not written into {library}:\n"
                f"{outcome.stated()}"
            )
        route = RouteKey.of(case)
        standing = held.get(route)
        if standing is not None:
            already.append(
                AlreadyInTheLibrary(
                    route=route,
                    proposed_as=case.id,
                    held_as=standing.id,
                    status=standing.status,
                )
            )
            continue
        entered.append(
            Entered(
                case=case,
                path=_written(case, library),
                # The block this loop refused a case for lacking, so the type
                # carries what was verified rather than `stated()` reaching back
                # for a field that could be `None`.
                admission=admission,
            )
        )
        held[route] = case
    version = LibraryVersion.of(load_library(library))
    return Entry(
        version=version,
        entered=tuple(entered),
        held=tuple(already),
        # The citation is a claim about a library version, and this run has just
        # moved one. Under the lease and after the write, on `cited.cite`'s terms:
        # the version claimed is the version the records on disk now compute.
        cited=moved_past(library, version, [one.case.id for one in entered]),
    )


def _written(case: Case, library: Path) -> Path:
    """One record onto disk, proved to load back as the case that was written.

    **Serialised before the name is claimed**, which is the order and not an
    accident: a payload TOML cannot hold makes `case_record` raise, and doing that
    inside an open `"x"` handle leaves a zero-byte `.toml` in the directory —
    which is not one lost record, it is a library `load_library` fails on from then
    on. The test that says so is `test_entry.py`'s carriage-return refusal, which
    found exactly that.

    **Created exclusively.** A file already at this name is a different case under
    this one's id, and appending to it or replacing it are both ways to lose a
    record that a `uuid` collision or a hand-authored name put there first.

    **Read back before the call returns, and removed if it does not match.** The
    round trip is `case_record`'s whole contract and this is where it is enforced
    rather than only asserted: a record `load_case` cannot read is not one bad case,
    it is a directory `admitted_library` refuses in its entirety, and a library that
    stops loading is a bench that stops running. Unreachable while the serialiser is
    correct, and that is the point of it — the two checks above have tests because
    they are conditions a caller can arrive in, and this one has none because
    nothing but a defect in this module can reach it.
    """
    path = library / f"{_file_name(case.id)}{CASE_SUFFIX}"
    body = case_record(case)
    with path.open("x", encoding="utf-8") as record:
        record.write(body)
    written = load_case(path)
    if written != case:
        path.unlink()
        raise UnwritableRecord(
            f"{path.name} did not read back as the case that was written, so it has "
            "been removed. A record this library's own loader cannot recover is a "
            "library no run can load, and the difference is in "
            f"{_differing(case, written)}"
        )
    return path


def _file_name(case_id: str) -> str:
    """That case id as a file name, or a refusal.

    Every id in this library is lower-case letters, digits, hyphens and underscores
    — `proposal.py` mints `adaptive-{family}-{uuid4}` — and an id with a separator or
    a dot in it would name a path outside the directory the lease is on. Refused
    rather than sanitised: the file name and the `id` field have to be the same
    string, because `retirement.store` finds a record by composing one from the
    other.
    """
    if not case_id or not all(
        character.isalnum() or character in "-_" for character in case_id
    ):
        raise UnwritableRecord(
            f"{case_id!r} is not a case id this library can hold as a file name. "
            "A record is found by composing its path from its id "
            "(`retirement.store`), so the two have to be the same string"
        )
    return case_id


def _differing(intended: Case, reloaded: Case) -> str:
    """Which fields a record lost, for the refusal above to name.

    `intended` is the case that was handed in and `reloaded` is what came back off
    disk, in that order — the same order the refusal's sentence reads in.
    """
    return (
        ", ".join(
            field.name
            for field in fields(intended)
            if getattr(intended, field.name) != getattr(reloaded, field.name)
        )
        or "no field, which means the difference is in a nested record"
    )
