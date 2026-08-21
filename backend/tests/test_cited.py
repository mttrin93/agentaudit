"""The gate run a library cites: rendered off one reading, and replaced out loud.

[ADR-0023](../../docs/adr/0023-a-gate-run-updates-the-citation-it-earned.md) reverses
two things ADR-0021 recorded as shut. The **gate run record** becomes what the **gate
citation** points at, so a reader holding a report's provenance block reaches each
agent's rate and each family's `D` without parsing the dated document. And a gate run
updates the citation, so a bench that has passed its own gate says so without anybody
editing a configuration.

Every assertion here is about a way that could go wrong rather than about the shape of
a dict.

**That the citation cannot disagree with the record.** Not that they *happen* to
agree: the citation is rendered off the record, field for field, and the test compares
every field of one against the other rather than against a literal. Two readings of
one `GateResult` would be two answers, and the whole point of the arrangement is that
there is one.

**That a failing gate run takes a passing citation off this bench, and says so.**
The decision ADR-0023 had to make and the reason it needed making: a stale pass left
in place is a report claiming a certification the instrument has since lost, in the
flattering direction, and a citation cleared to nothing states *no gate run is cited*
about a bench that has just measured its own discriminating power and found it
wanting. So the last gate run wins, and the loss is named — asserted both ways, on the
citation that results and on the sentence that reports it.

**That nothing recovers a figure from prose.** A library holding a document and no
record cites nothing; the module imports no renderer and no script; and it has no
reader for a `.md` at all. This is #75's refusal, kept: the parse was never written,
and after ADR-0023 there is a `.json` to point at instead of a reason to try.

**That the citation still carries no figure.** It reaches the per-family figures by
naming the file they are in. Two addresses and a library version, and nothing that
could be read as a rate, a `D`, a mean of six of them or a severity (ADR-0005,
ADR-0018).
"""

from __future__ import annotations

import ast
import json
from collections.abc import Iterator, Sequence
from pathlib import Path

from backend.bench.admission import admitted_library
from backend.bench.cited import (
    CITED_GATE_RUN,
    NO_DATED_DOCUMENT,
    Replaced,
    citation_of,
    cite,
    the_citation,
)
from backend.bench.gate import GateResult
from backend.bench.gate_record import (
    RecordedGateRun,
    recorded_gate_run,
    write_the_record,
)
from backend.bench.library import Family, LibraryVersion
from backend.bench.payload import UNCITED_GATE, GateCitation, citation
from backend.bench.scorer import GateDecision, GateOutcome, Reliability, decide_gate
from backend.tests.test_gate import INVERTED, SEPARATES, TOO_CLOSE, judged, outcomes_for

CITED_SOURCE = Path(__file__).resolve().parents[1] / "bench" / "cited.py"

CASES_DIR = Path(__file__).resolve().parents[1] / "cases"
"""The repository's own case library, read to prove the citation file is invisible."""

A_VERSION = LibraryVersion(cases=18, digest="90a8ebcc3d0c")


def a_passing_gate() -> GateResult:
    """A gate run that passed: six families apart and both judged ones fit."""
    return _result(
        decide_gate(
            outcomes_for(*[SEPARATES] * 6),
            reliability=judged(wrongful=_fit(Family.WRONGFUL_COMMITMENT)),
        )
    )


def a_failing_gate() -> GateResult:
    """A gate run that failed: too close on four families, and one inverted."""
    return _result(
        decide_gate(
            outcomes_for(
                SEPARATES, TOO_CLOSE, TOO_CLOSE, TOO_CLOSE, TOO_CLOSE, INVERTED
            ),
            reliability=judged(wrongful=_fit(Family.WRONGFUL_COMMITMENT)),
        )
    )


def a_record(
    gate: GateResult,
    *,
    decided_at: str = "2026-08-19T09:38:37+00:00",
    document: str = "gate-2026-08-19T09-38-37Z.md",
) -> RecordedGateRun:
    """One gate run as the record both entry points write it in."""
    return recorded_gate_run(
        gate,
        decided_at=decided_at,
        document=document,
        record=document.replace(".md", ".json"),
    )


# --- one reading, three renderings -------------------------------------------


def test_the_citation_is_rendered_off_the_record_and_cannot_disagree_with_it() -> None:
    """Every field of the citation, compared with the record rather than a literal.

    The guarantee is structural: `citation_of` reads the record and computes nothing,
    so there is no second arithmetic for the two to differ over. Asserted field for
    field against the record — a test that compared the citation with a hand-written
    expectation would pass just as happily against a citation composed beside the
    record instead of off it.
    """
    record = a_record(a_passing_gate())

    cited = citation_of(record)

    assert cited.outcome.value == record.decision.outcome
    assert cited.decided_on.isoformat() == record.decided_at[:10]
    assert cited.library.cases == record.decision.library.cases
    assert cited.library.digest == record.decision.library.digest
    assert cited.document == record.document
    assert cited.record == record.record


def test_the_citation_names_the_record_the_writer_actually_wrote(
    tmp_path: Path,
) -> None:
    """The name on the citation is the name on disk, because the record carries it.

    `write_the_record` takes a directory and composes the path from the record's own
    field, so a citation rendered off that record points at the file that exists. A
    name the citation composed for itself would be a second rule for where a record
    lives, and the two would only have to disagree once for a report to point a
    reader at nothing.
    """
    record = a_record(a_passing_gate())

    written = write_the_record(record, tmp_path)

    assert written.name == citation_of(record).record
    assert written.exists()


def test_a_reader_with_the_citation_reaches_the_figures_without_a_document(
    tmp_path: Path,
) -> None:
    """The per-family figures, recovered from what the citation names.

    The whole of the first reversal, end to end and with no Markdown in existence: a
    gate run writes its record and its citation, a reader takes the citation off the
    library, follows `record`, and finds each agent's rate and each family's `D`. The
    directory holds no `.md` at all, so the figures cannot have come from prose.
    """
    gate = a_passing_gate()
    record = a_record(gate, document=NO_DATED_DOCUMENT)
    write_the_record(record, tmp_path)
    cite(record, tmp_path)

    cited = the_citation(tmp_path)
    assert cited is not None
    figures = json.loads((tmp_path / cited.record).read_text(encoding="utf-8"))

    assert list(tmp_path.glob("*.md")) == []
    families = {one["family"]: one for one in figures["decision"]["families"]}
    assert set(families) == {str(family) for family in Family}
    for outcome in gate.decision.outcomes:
        one = families[str(outcome.family)]
        assert one["discrimination"] == outcome.discrimination
        assert [rate["agent"] for rate in one["rates"]] == [
            "hardened",
            "weak",
            "trivial",
        ]
        assert one["rates"][2]["value"] == outcome.rates.trivial.value

    # And the citation that led here carries not one of those figures. It is an
    # address, and the arithmetic stayed where the run put it (ADR-0018).
    assert not {"discrimination", "rates", "kappa"} & set(citation(cited))


def test_a_console_gate_run_states_the_absent_document_and_still_names_a_record(
    tmp_path: Path,
) -> None:
    """No prose to point at is a sentence, and the figures are reachable anyway.

    ADR-0021 recorded that the two entry points leave different traces. They still
    leave different *prose* — a console gate run writes no dated document — and the
    citation says so where a file name would be rather than naming one a reader would
    go looking for. What is no longer different is the record.
    """
    record = a_record(a_passing_gate(), document=NO_DATED_DOCUMENT)
    write_the_record(record, tmp_path)
    cite(record, tmp_path)

    cited = the_citation(tmp_path)
    assert cited is not None
    assert cited.document == NO_DATED_DOCUMENT
    assert "no dated document" in cited.stated()
    assert (tmp_path / cited.record).exists()


# --- what a gate run that did not pass does to the citation ------------------


def test_a_failing_gate_run_replaces_a_passing_citation_and_names_what_it_took(
    tmp_path: Path,
) -> None:
    """The decision ADR-0023 makes, enforced from both ends.

    A stale pass left in place would be every later report claiming a certification
    this instrument has just lost, and it would be wrong in the flattering direction
    — which is the direction ADR-0018 says a wrong field survives review in. So the
    last gate run wins. What makes that safe rather than silent is the second half of
    the assertion: the replacement names the outcome it displaced, says the displaced
    record is still on disk, and raises its voice about a pass specifically.
    """
    passed = a_record(a_passing_gate())
    cite(passed, tmp_path)
    assert the_citation(tmp_path) == citation_of(passed)

    failed = a_record(
        a_failing_gate(),
        decided_at="2026-08-20T11:00:00+00:00",
        document="gate-2026-08-20T11-00-00Z.md",
    )
    replaced = cite(failed, tmp_path)

    # The stale pass is gone from every surface that reads the citation, and the
    # outcome that replaced it is the one this bench last measured.
    now = the_citation(tmp_path)
    assert now == citation_of(failed)
    assert now is not None and now.outcome is GateOutcome.FAILED
    assert "passed" not in now.stated()

    # And it did not happen quietly. The previous citation is named with its outcome
    # and its date, the record behind it is stated as kept, and the loss of a pass
    # gets its own sentence.
    assert replaced.previous == citation_of(passed)
    assert replaced.displaced_a_pass
    said = replaced.stated()
    assert "2026-08-19" in said and "passed" in said
    assert passed.record in said
    assert "is not deleted" in said
    assert "last put itself through" in said


def test_a_first_gate_run_displaces_nothing_and_says_that_instead(
    tmp_path: Path,
) -> None:
    """A library citing nothing yet is not a library that lost a pass.

    Two different facts and the sentence is not the same one with a blank in it: an
    operator reading *this displaced a passing gate run* on a first run would be
    reading about something that never happened.
    """
    replaced = cite(a_record(a_passing_gate()), tmp_path)

    assert replaced.previous is None
    assert not replaced.displaced_a_pass
    assert "cited no gate run before now" in replaced.stated()


def test_a_passing_gate_run_replacing_a_failure_is_not_announced_as_a_loss(
    tmp_path: Path,
) -> None:
    """The louder sentence is about losing a pass, not about any replacement.

    `displaced_a_pass` is the reading a caller raises its voice about, and a bench
    that has just recovered its own gate has nothing to be warned about. The
    replacement is still stated — nothing changes in silence — and it does not claim
    a loss.
    """
    cite(a_record(a_failing_gate()), tmp_path)
    replaced = cite(
        a_record(
            a_passing_gate(),
            decided_at="2026-08-21T08:00:00+00:00",
            document="gate-2026-08-21T08-00-00Z.md",
        ),
        tmp_path,
    )

    assert not replaced.displaced_a_pass
    assert "last put itself through" not in replaced.stated()
    assert "failed" in replaced.stated()


# --- absence, and the shapes that are not a citation -------------------------


def test_a_library_with_no_citation_states_the_absence_rather_than_guessing(
    tmp_path: Path,
) -> None:
    """No file, an unreadable file and a shape from another version all answer none.

    A citation assembled out of whatever keys happened to be present is exactly how a
    bench would come to claim an outcome nothing decided, so anything unreadable is
    the stated absence — which is a fact about the bench and not a blank
    (`payload.UNCITED_GATE`).
    """
    assert the_citation(tmp_path) is None

    (tmp_path / CITED_GATE_RUN).write_text("{ not json", encoding="utf-8")
    assert the_citation(tmp_path) is None

    (tmp_path / CITED_GATE_RUN).write_text(
        json.dumps({"cited": True, "outcome": "passed"}), encoding="utf-8"
    )
    assert the_citation(tmp_path) is None

    (tmp_path / CITED_GATE_RUN).write_text(
        json.dumps({"cited": False, "stated": UNCITED_GATE}), encoding="utf-8"
    )
    assert the_citation(tmp_path) is None

    # And a document with no record beside it is not a citation either: the figures
    # are recovered from a record or from nothing, never from prose.
    (tmp_path / CITED_GATE_RUN).unlink()
    (tmp_path / "gate-2026-08-19T09-38-37Z.md").write_text("# Gate run", "utf-8")
    assert the_citation(tmp_path) is None


def test_the_citation_survives_the_round_trip_it_is_written_and_read_through(
    tmp_path: Path,
) -> None:
    """Written through `payload.citation` and read back into the same record.

    One serialiser on the way out — the one the signed provenance block and the
    console's own route already share — so the citation a library holds is the
    citation a report carries, byte for byte in the fields that matter.
    """
    record = a_record(a_passing_gate())

    cite(record, tmp_path)

    assert the_citation(tmp_path) == citation_of(record)
    written = json.loads((tmp_path / CITED_GATE_RUN).read_text(encoding="utf-8"))
    assert written == citation(citation_of(record))


# --- what may not be here ----------------------------------------------------


def test_nothing_here_recovers_a_figure_by_parsing_a_document() -> None:
    """No renderer, no script, and no reader for a `.md` anywhere in the module.

    The import-level form of #75's refusal. A figure recovered from a document
    written for a person breaks on a rewording, and this module's whole reason for
    existing is that there is a record to point at instead. It reads exactly one
    thing: the `.json` it wrote itself.
    """
    imported = set(_imports_of(CITED_SOURCE))

    assert not [name for name in imported if name.startswith("scripts")]
    assert "backend.bench.rendering" not in imported
    assert "re" not in imported

    code = _code_of(CITED_SOURCE)
    assert ".md" not in code, "cited.py names a Markdown file in its code"
    assert ".json" in code, "cited.py names the record shape it does read"
    assert code.count("read_text(") == 1, "cited.py reads more than its own citation"


def test_the_citation_carries_no_per_family_figure_and_nothing_that_spans_two() -> None:
    """Two addresses, a library version, an outcome and a date. No arithmetic.

    The citation travels inside the provenance block of a signed report and is the
    shape most likely to grow the figures it now points at. Every number on it is
    checked: the only one is the library's own case count, so there is no rate, no
    interval, no `D`, no κ, and nothing that could be the sum or the mean of six
    discrimination scores (ADR-0005, ADR-0018).
    """
    gate = a_passing_gate()
    body = citation(citation_of(a_record(gate)))

    scores = [one.discrimination for one in gate.decision.outcomes]
    combined = {sum(scores), sum(scores) / len(scores), *scores}
    numbers = dict(_numbers(body))
    assert set(numbers) == {"library.cases"}
    assert not set(numbers.values()) & combined

    printed = json.dumps(body).lower()
    # `interval` is absent from this list on purpose: the citation's own sentence
    # says a target has rates, intervals and bands, which is the wording ADR-0018
    # reserves for the target and refuses for the bench.
    for forbidden in ("severity", "composite", "a_break", "kappa", "discrimination"):
        assert forbidden not in printed, f"{forbidden} reached a gate citation"

    # And the reference agents are not named on it, which is the half of ADR-0018
    # that the record's own figures are the reason to keep: `hardened` and `trivial`
    # are in the file this points at and never in a user's report (point 6).
    for equipment in ("hardened", "trivial", "reference agent"):
        assert equipment not in printed


def test_the_citation_file_is_invisible_to_the_thing_that_loads_the_library(
    tmp_path: Path,
) -> None:
    """A `.json` beside the cases is not a case, and does not move the digest.

    The citation lives in the library because it is a claim about that library at a
    version — and it would be a poor claim if writing it changed the version. Asserted
    over the loader itself rather than over the glob: the count and the digest of the
    admitted library are the same before and after.
    """
    library = tmp_path / "cases"
    library.mkdir()
    for record in CASES_DIR.glob("*.toml"):
        (library / record.name).write_text(
            record.read_text(encoding="utf-8"), encoding="utf-8"
        )
    before = LibraryVersion.of(admitted_library(library))

    cite(a_record(a_passing_gate()), library)

    assert (library / CITED_GATE_RUN).exists()
    assert LibraryVersion.of(admitted_library(library)) == before


def test_a_citation_is_not_a_gate_result_and_carries_no_decision() -> None:
    """The type that reaches `ReportConfig.gate` holds an address, not a decision.

    ADR-0021's condition 2 on a new axis: the one edge from a gate run onto the bench
    a run is measured with carries a `GateCitation`, and a `GateCitation` has five
    fields and none of them is a `GateDecision`, a `GateResult` or a
    `RecordedGateRun`. A contributor who wanted the figures on the report would have
    to widen this type, which is the signal ADR-0010 established.
    """
    fields = {field for field in GateCitation.__dataclass_fields__}

    assert fields == {"outcome", "decided_on", "library", "document", "record"}
    for held in (GateResult, GateDecision, RecordedGateRun, Replaced):
        assert held.__name__ not in {
            str(GateCitation.__dataclass_fields__[field].type) for field in fields
        }


# --- helpers -----------------------------------------------------------------


def _fit(family: Family) -> Reliability:
    """A κ reading above the floor, so a judged family is fit to report."""
    return Reliability(family=family, kappa=0.86, agreements=14, transcripts=15)


def _result(decision: GateDecision) -> GateResult:
    """A gate result around a decision, at the library version under test."""
    return GateResult(
        decision=decision,
        library=A_VERSION,
        reliability={},
        attempts=540,
        agents=("trivial", "weak", "hardened"),
    )


def _code_of(source: Path) -> str:
    """The module with every docstring removed, so a scan is about code.

    A prose paragraph explaining that this module never reads a document contains the
    words a naive scan would fail on, and stripping by string surgery would depend on
    where the paragraphs are. So the docstrings come off through the parser.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list):
            continue
        kept = [statement for statement in body if not _is_prose(statement)]
        node.body = kept or [ast.Pass()]  # type: ignore[attr-defined]
    return ast.unparse(tree)


def _is_prose(statement: ast.stmt) -> bool:
    """Whether that statement is a bare string: a docstring, of either kind.

    Both kinds, because this repository documents module constants and model fields
    with a string underneath them and those are prose too — a paragraph explaining
    that nothing here reads a document contains every word a scan for one looks for.
    """
    return (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and isinstance(statement.value.value, str)
    )


def _imports_of(source: Path) -> Iterator[str]:
    """Every module the given module imports, dotted."""
    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            yield node.module


def _numbers(body: object, name: str = "") -> Iterator[tuple[str, float]]:
    """Every number anywhere in a serialised citation, under its dotted path."""
    if isinstance(body, bool):
        return
    if isinstance(body, int | float):
        yield name, float(body)
    elif isinstance(body, dict):
        for key, value in body.items():
            yield from _numbers(value, f"{name}.{key}" if name else str(key))
    elif isinstance(body, Sequence) and not isinstance(body, str):
        for index, value in enumerate(body):
            yield from _numbers(value, f"{name}[{index}]")
