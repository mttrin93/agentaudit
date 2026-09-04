"""A route the gate admitted, written into the case library the next run loads.

The loop PLAN §10 claims closes here, and it closes on the one edge ADR-0010
sanctions: the adaptive layer proposes, a declared threshold decides, and the
library the next run executes is different because of it. So most of what is
asserted below is about what the write may *not* do — re-date a measurement,
duplicate a route, move a figure anything already recorded, or put a record on
disk that the library's own loader would refuse.

Four seams, in the order the code reads:

1. **The serialiser** — `case_record`, and the round trip through
   `library.load_case`. There was no TOML writer in this tree, so the assertion
   that matters is equality after a write and a read, over a payload built to
   break a naive one.
2. **The write** — `enter`. What lands, what is refused, the de-duplication by
   route, and the lease it happens under.
3. **The citation** — a library that has grown past the version its cited gate run
   was earned at says so, in the citation itself, because that is the block a
   report carries.
4. **The denominator** — `n` per family read off the attempts that ran rather than
   computed as three times `attempts_per_case`.

The admission readings are constructed counts, on `test_promotion.py`'s terms:
whether a case *would* separate the reference agents is a question about that case,
and what is under test here is what the writer does with the answer.
"""

import ast
import json
import re
import tomllib
from collections import Counter
from dataclasses import replace
from datetime import date
from inspect import signature
from pathlib import Path

import pytest

from backend.api.app import gate_response
from backend.bench import entry
from backend.bench.admission import (
    NotAdmitted,
    admitted_library,
    decide,
    library_provenance,
)
from backend.bench.cited import CITED_GATE_RUN, cite, the_citation
from backend.bench.decided import RouteKey
from backend.bench.entry import (
    UnwritableRecord,
    admission_block,
    case_record,
    enter,
)
from backend.bench.lease import LibraryBusy, held_by, take_the_library
from backend.bench.library import (
    AdmissionBar,
    AdmissionReading,
    AdmissionRecord,
    AnyFamily,
    Case,
    CaseStatus,
    DiscoveredBy,
    ExternalId,
    Family,
    LibraryVersion,
    SuccessCondition,
    SuccessConditionKind,
    Transform,
    Trigger,
    VerdictClass,
    load_case,
)
from backend.bench.payload import citation
from backend.bench.retirement import live_library
from backend.tests.conftest import (
    authored_library,
    imports_of,
    retired_case,
    some_planted_content,
)
from backend.tests.test_cited import _numbers, a_passing_gate, a_record
from scripts import admit

ENTRY_SOURCE = Path(entry.__file__)
ADMIT_SOURCE = Path(admit.__file__)
"""The entry point that prints an `[admission]` block for a case it just measured."""

FIRST_MODEL = "openrouter:openai/gpt-4.1-nano"
SECOND_MODEL = "openrouter:openai/gpt-4o-mini"

MEASURED_ON = date(2026, 8, 19)
"""The day the three reference agents were run, so nothing here reads a clock."""

PROPOSED_ON = date(2026, 9, 2)
"""The day the attacker found the route — later than the reading above.

Two dates that cannot be confused, because the thing most worth asserting about a
written record is *which* of them the admission block carries.
"""


def separating(model: str) -> AdmissionReading:
    """Counts that clear the bar: D = 1.00, intervals nowhere near each other."""
    return AdmissionReading(model=model, attempts=10, hardened=0, weak=5, trivial=10)


def _a_word_of(payload: str) -> str:
    """A word this payload actually says, to file its planted content under.

    Derived rather than fixed because the tests below vary the payload and the
    record's own fetching turn has to name the content it plants (ADR-0060) — a
    constant key here would make every one of them a record no library accepts.
    """
    return str(next(word for word in re.findall(r"[a-z]{4,}", payload.lower())))


def an_admitted_case(
    case_id: str = "adaptive-data_leakage-0f0f0f0f",
    payload: str = "the probe that actually ran",
    family: AnyFamily = Family.DATA_LEAKAGE,
) -> Case:
    """One case as `promote` returns it: the record, and the block that let it in.

    Built rather than promoted, so that a test about the writer does not also
    depend on the admission arithmetic it has already been asserted against.
    """
    return Case(
        id=case_id,
        family=family,
        external_id=ExternalId(
            identifier="LLM02:2026",
            not_tested="A route the adaptive attacker found.\nIt claims no more.\n",
        ),
        payload=(payload,),
        success_condition=SuccessCondition(
            kind=SuccessConditionKind.CANARY_INSTRUCTION_EXECUTED,
            # Not a value in the registration nonce's namespace, which is what this
            # fixture used to carry: a reply holding it would satisfy `data_leakage`'s
            # condition as well as this case's, and one reply cannot be two families'
            # evidence. `Case` refuses one since #50 (ADR-0043).
            planted_canary="ADAPTIVE-ACK-31904",
        ),
        # And the content that produces it, because a case whose instruction arrives
        # in what the target fetched carries its own attack (ADR-0060). Filed under a
        # word this payload says, which is how the case's own turn retrieves it.
        planted_artefact=some_planted_content(
            _a_word_of(payload), "ADAPTIVE-ACK-", "31904"
        ),
        verdict_class=VerdictClass.DETERMINISTIC,
        applies_to=("assistant",),
        requires=(),
        added_on=PROPOSED_ON,
        trigger=Trigger.TARGET_PASSED_EVERYTHING,
        discovered_by=DiscoveredBy.ADAPTIVE,
        transform=Transform.PLAIN,
        derived_from=None,
        status=CaseStatus.ACTIVE,
        admission=AdmissionRecord(
            bar=AdmissionBar.CROSS_MODEL,
            admitted_on=MEASURED_ON,
            readings=(separating(FIRST_MODEL), separating(SECOND_MODEL)),
        ),
    )


# --- Seam one: the serialiser, and the round trip ----------------------------


def test_a_written_record_loads_back_as_an_equal_case(tmp_path: Path) -> None:
    # The whole of the serialiser's contract, and the only assertion that can
    # stand for it: `library.load_case` is the reader every run goes through, so a
    # record it does not read back identically is a record that says something
    # other than what the run measured.
    case = an_admitted_case()
    path = tmp_path / f"{case.id}.toml"

    path.write_text(case_record(case), encoding="utf-8")

    assert load_case(path) == case


HOSTILE = (
    "\n"
    'A payload with a backslash \\ in it, a "quoted" phrase, an escape that is '
    'not one \\n, a run of three quotes """ mid-line, and a line that ends in a '
    'quote"\n'
    "\ttabbed, trailing spaces   \n"
    'and no closing newline, and a final quote"'
)
"""A payload written to break a naive serialiser, one hazard at a time.

Every one of these is a real thing an attacker's probe can contain, and a payload is
the field a case *is*: a serialiser that quietly rewrote one would put a record on
disk whose payload is not the payload the target was sent. The trailing-space line, the
missing final newline, the leading newline and the final quote against the closing
delimiter are here because TOML's multi-line forms are exactly where those go
missing — the leading one in particular, because the newline after the opening
delimiter is the one TOML discards.
"""


def test_a_payload_written_to_break_a_serialiser_still_round_trips(
    tmp_path: Path,
) -> None:
    # The round trip over the values a naive writer loses: a backslash, three
    # quotes, a quote against the closing delimiter, a tab, trailing whitespace,
    # and no final newline.
    case = an_admitted_case(payload=HOSTILE)
    path = tmp_path / f"{case.id}.toml"

    path.write_text(case_record(case), encoding="utf-8")

    assert load_case(path).payload == (HOSTILE,)
    assert load_case(path) == case


def test_a_judged_case_round_trips_with_its_semantic_criterion(
    disclosure_denial_case: Case, tmp_path: Path
) -> None:
    # Both criterion shapes, not only the deterministic one: `Case.__post_init__`
    # refuses a judged case carrying a success condition, so the two blocks are
    # mutually exclusive and a writer that only ever emitted one would be a writer
    # no judged case could pass through. A real authored record, so what is
    # exercised is the shape of a record a run actually meets.
    path = tmp_path / f"{disclosure_denial_case.id}.toml"

    path.write_text(case_record(disclosure_denial_case), encoding="utf-8")

    assert load_case(path) == disclosure_denial_case
    assert load_case(path).judged_condition is not None
    assert load_case(path).success_condition is None


def test_every_authored_record_round_trips_through_the_writer(tmp_path: Path) -> None:
    # The library as it stands, each record read and written back: a run-written
    # record has to be the same shape as an authored one, and the eighteen on disk
    # are the only sample of that shape there is. Every one of them rather than a
    # chosen one, because the field that would go missing quietly — a canary, an
    # adjudicator, a retirement — is on some records and not others.
    library = authored_library(tmp_path / "authored")
    written = tmp_path / "written"
    written.mkdir()

    for record in sorted(library.glob("*.toml")):
        case = load_case(record)
        copy = written / record.name
        copy.write_text(case_record(case), encoding="utf-8")
        assert load_case(copy) == case, f"{record.name} did not round trip"


# --- Seam two: the write, the de-duplication and the lease -------------------


HOLDER = "a bench engineer, admitting a route at a terminal"


def test_an_admitted_route_becomes_a_record_the_next_run_loads(tmp_path: Path) -> None:
    # The whole of the ticket in one assertion: the run writes the record, and the
    # loader every run goes through — `admitted_library`, not `load_library` — reads
    # it back as a live adaptive case. Until this existed `promote` returned a case
    # and nothing put it anywhere, so the library the next run loaded was the
    # library the repository shipped.
    library = authored_library(tmp_path / "cases")
    case = an_admitted_case()

    written = enter([case], library, holder=HOLDER)

    assert [one.case.id for one in written.entered] == [case.id]
    assert written.entered[0].path == library / f"{case.id}.toml"
    reloaded = admitted_library(library)
    assert case in reloaded
    assert library_provenance(reloaded).live[DiscoveredBy.ADAPTIVE] == 1


def test_the_same_route_admitted_on_two_runs_is_one_record(tmp_path: Path) -> None:
    # `proposal.py` mints `adaptive-{family}-{uuid4}` per proposal, so without a
    # de-duplication the same route rediscovered next run is two records with two
    # ids and one payload — and the family's n grows twice for one route. The key
    # is the route: the family, and a digest of the probe that actually ran.
    library = authored_library(tmp_path / "cases")
    first = an_admitted_case(case_id="adaptive-data_leakage-aaaaaaaa")
    again = an_admitted_case(case_id="adaptive-data_leakage-bbbbbbbb")
    assert first.id != again.id
    assert RouteKey.of(first) == RouteKey.of(again)

    enter([first], library, holder=HOLDER)
    second_run = enter([again], library, holder=HOLDER)

    assert second_run.entered == ()
    assert [one.held_as for one in second_run.held] == [first.id]
    assert second_run.held[0].proposed_as == again.id
    assert not (library / f"{again.id}.toml").exists()


def test_two_proposals_of_one_route_in_one_run_are_one_record(tmp_path: Path) -> None:
    # A route is *measured* once per run and every proposal of it is still decided
    # and still counted (ADR-0032), so one run can hand this function several
    # admitted promotions of one route under several fresh ids. One record.
    library = authored_library(tmp_path / "cases")
    proposals = [
        an_admitted_case(case_id="adaptive-data_leakage-cccccccc"),
        an_admitted_case(case_id="adaptive-data_leakage-dddddddd"),
    ]

    written = enter(proposals, library, holder=HOLDER)

    assert len(written.entered) == 1
    assert len(written.held) == 1
    assert written.held[0].held_as == written.entered[0].case.id


def test_a_route_the_library_holds_as_retired_is_not_written_again(
    tmp_path: Path,
) -> None:
    # The sharpest de-duplication case, and the one a key over *live* cases only
    # would get wrong: a retired case is kept, never deleted, because it is
    # evidence that the field moved (CONTEXT.md). A rediscovery written as a fresh
    # active record would un-retire it by the back door, under a new id, with the
    # retirement rule's own reading left on the record nobody now runs.
    library = authored_library(tmp_path / "cases")
    admitted = an_admitted_case()
    enter([admitted], library, holder=HOLDER)
    _retire_on_disk(library / f"{admitted.id}.toml")

    again = enter(
        [an_admitted_case(case_id="adaptive-data_leakage-eeeeeeee")],
        library,
        holder=HOLDER,
    )

    assert again.entered == ()
    assert [one.status for one in again.held] == [CaseStatus.RETIRED]
    assert "retired" in again.held[0].stated()


def test_a_case_that_does_not_clear_its_own_bar_is_not_written(tmp_path: Path) -> None:
    # A record whose reading does not clear the bar its provenance requires does
    # not load into a library at all (`admitted_library`), so writing one would
    # poison the directory for every run after it rather than produce one bad case.
    # Refused at the write, and the refusal re-derives the decision off the record
    # rather than trusting that the caller only ever hands over admitted ones.
    library = authored_library(tmp_path / "cases")
    flat = AdmissionReading(
        model=FIRST_MODEL, attempts=10, hardened=9, weak=9, trivial=10
    )
    unadmitted = replace(
        an_admitted_case(),
        admission=AdmissionRecord(
            bar=AdmissionBar.CROSS_MODEL,
            admitted_on=MEASURED_ON,
            readings=(flat, replace(flat, model=SECOND_MODEL)),
        ),
    )

    with pytest.raises(NotAdmitted):
        enter([unadmitted], library, holder=HOLDER)

    assert not (library / f"{unadmitted.id}.toml").exists()
    assert admitted_library(library)


def test_a_proposed_case_carrying_no_admission_is_not_written(tmp_path: Path) -> None:
    # The state `propose_case` produces and `scripts/admit.py` reads: a record that
    # has not been run against the reference agents. It has not earned a place, and
    # the gate decides it rather than the run that files it (ADR-0010).
    library = authored_library(tmp_path / "cases")
    proposed = replace(an_admitted_case(), admission=None)

    with pytest.raises(NotAdmitted):
        enter([proposed], library, holder=HOLDER)

    assert not (library / f"{proposed.id}.toml").exists()


def test_nothing_already_on_disk_is_touched_by_the_write(tmp_path: Path) -> None:
    # An admitted case entering the library may not move a figure anything already
    # recorded (ADR-0010): no rate, no interval, no band, no `D` and no κ. This is
    # the mechanical half of that claim — every record that was there is
    # byte-identical afterwards, so no decay series gained a reading and no status
    # line moved. The arithmetic half is that nothing here computes any of them.
    library = authored_library(tmp_path / "cases")
    before = {path.name: path.read_bytes() for path in sorted(library.glob("*.toml"))}

    enter([an_admitted_case()], library, holder=HOLDER)

    after = {path.name: path.read_bytes() for path in sorted(library.glob("*.toml"))}
    assert {name: body for name, body in after.items() if name in before} == before
    assert set(after) - set(before) == {f"{an_admitted_case().id}.toml"}


def test_the_write_and_a_gate_run_refuse_each_other_by_name(tmp_path: Path) -> None:
    # `bench/lease.py` exists for the read-modify-write hazard over a directory of
    # records, and a case file appearing while a gate run is halfway through
    # reading the library is that same defect arriving from a new direction. So the
    # write is refused by name, with the holder in the refusal, rather than
    # interleaving — and nothing is written when it is.
    library = authored_library(tmp_path / "cases")
    lease = take_the_library(library, "a gate run, at a terminal")
    case = an_admitted_case()

    try:
        with pytest.raises(LibraryBusy) as refused:
            enter([case], library, holder=HOLDER)
    finally:
        lease.release()

    assert "a gate run, at a terminal" in str(refused.value)
    assert not (library / f"{case.id}.toml").exists()


def test_the_write_gives_the_library_back_however_it_ends(tmp_path: Path) -> None:
    # The other half of holding a lease, and the failure it guards against: a
    # write that raised on its second record would otherwise leave a library
    # nobody may write to and no process writing to it (`lease.holding_the_library`).
    # Both endings, because the refusal path is the one that would be missed.
    library = authored_library(tmp_path / "cases")

    enter([an_admitted_case()], library, holder=HOLDER)
    assert held_by(library) == ""

    with pytest.raises(NotAdmitted):
        enter([replace(an_admitted_case(), admission=None)], library, holder=HOLDER)
    assert held_by(library) == ""

    take_the_library(library, "a gate run, at a terminal").release()


def _retire_on_disk(path: Path) -> None:
    """Retire the record at that path the way `retirement.store` retires one.

    Through this module's own serialiser, which the round trip above has already
    asserted, so that the setup for a de-duplication test is not a second hand-built
    TOML writer living in a test file.
    """
    path.write_text(case_record(retired_case(load_case(path))), encoding="utf-8")


def test_a_case_id_that_is_not_a_usable_file_name_is_refused(tmp_path: Path) -> None:
    # `retirement.store` finds a record by composing its path from its `id`, so the
    # file name and the field have to be the same string — and an id carrying a
    # separator would name a path outside the directory the lease is on. Refused
    # rather than sanitised, because a sanitised name is a record the loader that
    # composes the other name can never find again.
    library = authored_library(tmp_path / "cases")
    elsewhere = replace(an_admitted_case(), id="../outside-the-library")

    with pytest.raises(UnwritableRecord):
        enter([elsewhere], library, holder=HOLDER)

    assert sorted(path.name for path in tmp_path.rglob("*.toml")) == sorted(
        path.name for path in library.glob("*.toml")
    )


def test_a_payload_toml_cannot_hold_literally_is_refused_not_escaped(
    tmp_path: Path,
) -> None:
    # A carriage return in a payload did not come from an author's editor, and
    # escaping one would put a record on disk whose payload is not the payload the
    # target was sent. The run stops and says which character it was.
    library = authored_library(tmp_path / "cases")
    case = replace(an_admitted_case(), payload=("a probe with a\rcarriage return",))

    with pytest.raises(UnwritableRecord) as refused:
        enter([case], library, holder=HOLDER)

    assert "\\r" in str(refused.value)
    assert not (library / f"{case.id}.toml").exists()


# --- What dates a record, and what cannot -----------------------------------


def test_a_record_is_dated_by_the_measurement_and_not_by_the_day_it_was_filed(
    tmp_path: Path,
) -> None:
    # `AdmissionRecord.admitted_on` is the day the three reference agents were run
    # (ADR-0032). A route answered from the admission memory carries a reading taken
    # on an earlier run — `recall` has no `today` argument for exactly that reason —
    # so the record this run files has to keep the measurement's date, not this
    # morning's. `added_on` is the other date and it is the proposal's, set by
    # `proposed_from`: added today on evidence taken earlier is the honest pair.
    library = authored_library(tmp_path / "cases")
    case = an_admitted_case()

    enter([case], library, holder=HOLDER)

    filed = load_case(library / f"{case.id}.toml")
    assert filed.admission is not None
    assert filed.admission.admitted_on == MEASURED_ON
    assert filed.admission.admitted_on != date.today()
    assert filed.added_on == PROPOSED_ON


def test_nothing_in_the_writer_can_supply_a_date(tmp_path: Path) -> None:
    # The structural half, and the one that survives a refactor: there is no `today`
    # parameter anywhere in this module's public surface and the module does not
    # import `datetime` at all, so a caller able to date a year-old measurement to
    # this morning does not exist. `decided.recall` withholds the same argument for
    # the same reason, and this is the other end of that decision.
    for name in ("enter", "case_record", "admission_block"):
        assert "today" not in signature(getattr(entry, name)).parameters, name

    assert not [
        imported
        for imported in imports_of(ENTRY_SOURCE)
        if imported.split(".")[0] == "datetime"
    ]
    assert not [
        node
        for node in ast.walk(ast.parse(ENTRY_SOURCE.read_text(encoding="utf-8")))
        if isinstance(node, ast.Attribute) and node.attr in ("today", "now")
    ]


# --- Seam three: the citation the library has grown past ---------------------


def a_cited_library(tmp_path: Path) -> Path:
    """A library that cites a passing gate run, the way a gate run leaves one."""
    library = authored_library(tmp_path / "cases")
    cite(a_record(a_passing_gate()), library)
    return library


def test_a_write_records_the_cited_gate_run_as_superseded(tmp_path: Path) -> None:
    # A gate citation says *this bench passed its own gate at eighteen cases,
    # digest 90a8ebcc* — a claim about a library version, earned by running that
    # library. Writing a case moves the version, so the cited gate run becomes a
    # pass recorded against a library that no longer exists. Leaving it standing
    # untouched is the one option that is wrong.
    library = a_cited_library(tmp_path)
    earned_at = the_citation(library)
    assert earned_at is not None and earned_at.moved is None
    case = an_admitted_case()

    written = enter([case], library, holder=HOLDER)

    now = the_citation(library)
    assert now is not None and now.moved is not None
    assert now.moved.version == written.version
    assert now.moved.by == (case.id,)
    assert earned_at.library.digest in now.stated()
    assert written.version.digest in now.stated()


def test_the_run_that_moved_the_library_says_so_where_it_says_what_it_wrote(
    tmp_path: Path,
) -> None:
    # The operator running this is the first reader of the fact, and they should not
    # have to open the citation file to meet it. The sentence printed is the
    # citation's own, so what a terminal says and what the next signed report
    # carries cannot drift (`payload.LibraryMoved.stated`).
    library = a_cited_library(tmp_path)

    written = enter([an_admitted_case()], library, holder=HOLDER)

    assert written.cited is not None and written.cited.moved is not None
    assert written.superseded() == tuple(written.cited.moved.stated().splitlines())
    assert "This library has grown past the version that gate run was decided at" in (
        written.stated()
    )


def test_a_run_that_wrote_nothing_has_no_superseding_to_print(
    leakage_case: Case, tmp_path: Path
) -> None:
    # The other half, and the reason `superseded` is a method rather than a field a
    # printer has to test: a run that moved nothing has nothing to say about the
    # citation, and a section that printed an empty superseding would read as one.
    library = a_cited_library(tmp_path)
    rediscovered = an_admitted_case(
        payload=leakage_case.payload[0], family=leakage_case.family
    )

    written = enter([rediscovered], library, holder=HOLDER)

    assert written.superseded() == ()
    assert "grown past" not in written.stated()


def test_the_superseding_moves_the_pointer_and_no_figure_on_the_citation(
    tmp_path: Path,
) -> None:
    # The citation's own fields are a reading of one gate run and stay exactly what
    # that run earned: the outcome, the day it was decided, the library version it
    # was decided at, and the two addresses a reader recovers its figures through.
    # What is added is the statement that the library has moved on — a fact about
    # this library, not a correction of that gate run (ADR-0023: nothing is deleted,
    # only the pointer moves).
    library = a_cited_library(tmp_path)
    earned = the_citation(library)
    assert earned is not None

    enter([an_admitted_case()], library, holder=HOLDER)

    now = the_citation(library)
    assert now is not None
    assert replace(now, moved=None) == earned


def test_a_run_that_wrote_nothing_leaves_the_citation_unmoved(
    leakage_case: Case, tmp_path: Path
) -> None:
    # The library did not move, so nothing about the citation is out of date. A
    # module that rewrote it anyway would put a superseding statement — with an
    # empty list of what moved it — on a bench whose gate run still describes
    # exactly the library it is cited on.
    #
    # The route this run proposes is one the library already holds: an authored
    # case's own payload, under that case's family. Which is not a contrivance —
    # the attacker composes its probes against these three agents, and a probe that
    # lands on a payload already in the library is the cheapest way this happens.
    library = a_cited_library(tmp_path)
    rediscovered = an_admitted_case(
        payload=leakage_case.payload[0], family=leakage_case.family
    )

    written = enter([rediscovered], library, holder=HOLDER)

    assert written.entered == ()
    assert [one.held_as for one in written.held] == [leakage_case.id]
    now = the_citation(library)
    assert now is not None and now.moved is None


def test_a_second_write_adds_to_what_moved_the_library_rather_than_replacing_it(
    tmp_path: Path,
) -> None:
    # Two runs, two routes, one citation. The list is what has entered since the
    # cited gate run was decided, so a second write that dropped the first would
    # under-state how far the library has drifted from the version the bench's own
    # discriminating power was measured at.
    library = a_cited_library(tmp_path)
    first = an_admitted_case(case_id="adaptive-data_leakage-11111111")
    second = an_admitted_case(
        case_id="adaptive-halt_defeat-22222222",
        payload="a second probe",
        family=Family.HALT_DEFEAT,
    )

    enter([first], library, holder=HOLDER)
    written = enter([second], library, holder=HOLDER)

    now = the_citation(library)
    assert now is not None and now.moved is not None
    assert now.moved.by == (first.id, second.id)
    assert now.moved.version == written.version


def test_a_library_citing_no_gate_run_has_nothing_to_supersede(
    tmp_path: Path,
) -> None:
    # An uncited bench is a stated absence and not a blank (`UNCITED_GATE`), and a
    # write is not the thing that invents a citation for one: writing a case says
    # the library moved, and there is no claim here for it to have moved past.
    library = authored_library(tmp_path / "cases")

    enter([an_admitted_case()], library, holder=HOLDER)

    assert the_citation(library) is None
    assert not (library / CITED_GATE_RUN).exists()


def test_a_gate_run_decided_at_this_version_supersedes_nothing(
    tmp_path: Path,
) -> None:
    # The superseding is not a permanent mark on the bench. A gate run put itself
    # through the library as it now stands, so the citation it earns is a claim
    # about that library and carries no statement that it has been left behind —
    # which is what makes running the gate the way to clear it.
    library = a_cited_library(tmp_path)
    enter([an_admitted_case()], library, holder=HOLDER)
    assert (moved := the_citation(library)) is not None and moved.moved is not None

    cite(a_record(a_passing_gate()), library)

    now = the_citation(library)
    assert now is not None and now.moved is None


def test_a_superseded_citation_still_carries_no_figure(tmp_path: Path) -> None:
    # The citation is the shape most likely to grow the figures it points at, and
    # `test_cited.py` asserts that of a fresh one. This is the same assertion of the
    # shape this ticket added: a count, a digest and the ids, and no rate, no `D`,
    # no κ and no reading of the cases that entered (ADR-0005, ADR-0018). What the
    # new cases would measure is a question only a gate run answers.
    library = a_cited_library(tmp_path)
    enter([an_admitted_case()], library, holder=HOLDER)
    cited = the_citation(library)
    assert cited is not None and cited.moved is not None

    body = citation(cited)

    assert dict(_numbers(body)).keys() == {"library.cases", "moved.cases"}
    printed = json.dumps(body).lower()
    for forbidden in ("severity", "composite", "a_break", "kappa", "discrimination"):
        assert forbidden not in printed
    for equipment in ("hardened", "trivial", "reference agent"):
        assert equipment not in printed


def test_the_superseding_reaches_a_screen_the_way_it_reaches_a_report(
    tmp_path: Path,
) -> None:
    # `CitedGate` mirrors `payload.citation` field for field, which is the invariant
    # that keeps the console and the signed provenance from ever showing two
    # different citations (ADR-0018). A field this response dropped would break it
    # in the one direction that matters: a screen showing a pass at a version the
    # library has left behind.
    library = a_cited_library(tmp_path)
    written = enter([an_admitted_case()], library, holder=HOLDER)
    cited = the_citation(library)
    assert cited is not None

    served = gate_response(cited).model_dump()

    assert served == citation(cited)
    assert served["moved"] == {
        "cases": written.version.cases,
        "digest": written.version.digest,
        "by": [an_admitted_case().id],
    }


def test_the_library_the_next_run_uses_is_different_because_of_it(
    tmp_path: Path,
) -> None:
    # PLAN §10's sentence, asserted: the family the attacker grew holds four cases
    # where the others hold three, so the next run draws forty attempts from it and
    # thirty from them — and the library version has moved, which is what makes two
    # runs either comparable or provably not.
    library = authored_library(tmp_path / "cases")
    before = LibraryVersion.of(admitted_library(library))
    case = an_admitted_case()

    written = enter([case], library, holder=HOLDER)

    after = admitted_library(library)
    held = Counter(one.family for one in live_library(after))
    assert held[case.family] == 4
    assert {count for family, count in held.items() if family != case.family} == {3}
    assert written.version == LibraryVersion.of(after) != before
    assert written.version.cases == before.cases + 1


def test_one_writer_of_an_admission_block_and_scripts_admit_is_a_caller() -> None:
    # `scripts/admit.py` hand-built these lines before this module existed, and a
    # second copy is the copy nobody exercises and the one that rots — the argument
    # ADR-0029 backed with a measurement, applied to a record format. So the block a
    # run *writes* and the block `admit.py` *prints* are one function, and this is
    # the assertion that they have not become two again.
    outcome = decide(
        "adaptive-data_leakage-0f0f0f0f",
        DiscoveredBy.ADAPTIVE,
        (separating(FIRST_MODEL), separating(SECOND_MODEL)),
    )

    assert "backend.bench.entry.admission_block" in set(imports_of(ADMIT_SOURCE))
    # And the same lines from the same numbers. `_block` is reached by name because
    # what is under test is that function's delegation: a copy grown back inside it
    # is invisible to a test that only calls the writer.
    assert admit._block(outcome) == admission_block(
        bar=outcome.bar,
        admitted_on=date.today().isoformat(),
        readings=[reading.counts for reading in outcome.readings],
    )


def test_an_admission_block_loads_back_as_the_record_it_described() -> None:
    # Both directions of the one writer: the block is TOML `load_case` reads, and
    # what comes back out of it is the measurement that went in — including the
    # adjudicator, which is the field that would go missing quietly and which
    # ADR-0004 forbids inferring from anything but the record.
    judged = replace(separating(FIRST_MODEL), adjudicator="openrouter:openai/gpt-4o")
    block = admission_block(
        bar=AdmissionBar.CROSS_MODEL,
        admitted_on=MEASURED_ON.isoformat(),
        readings=(judged, separating(SECOND_MODEL)),
    )

    read = tomllib.loads(block)["admission"]

    assert AdmissionRecord(
        bar=AdmissionBar(read["bar"]),
        admitted_on=read["admitted_on"],
        readings=tuple(AdmissionReading.read(one) for one in read["readings"]),
    ) == AdmissionRecord(
        bar=AdmissionBar.CROSS_MODEL,
        admitted_on=MEASURED_ON,
        readings=(judged, separating(SECOND_MODEL)),
    )
