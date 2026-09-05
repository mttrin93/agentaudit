"""The corpus is a search surface, and these are the tests that say so.

Five claims, each of which would be prose without a test: the case library did not
move, nothing in the bench can read a **candidate**, nothing in the corpus can write a
case, no family a query searches for has a judged case — so no retrieved phrasing can
reach a κ — and nothing the suite imports needs `chromadb`, which CI does not install.
What the corpus may read *from* the bench is the family enumerations and nothing
else — three closed sets where ADR-0045 decision 6 allowed one, widened by
[ADR-0046](../../docs/adr/0046-a-family-assignment-is-proposed-here-and-decided-by-a-person.md)
decision 7. The instrument that reads them is tested in `test_corpus_assignment.py`.

The last three are asserted over the tree rather than over a fixture, because what
they forbid is a future edit rather than a present value. An import added in six
months is exactly the way a second edge into the scored side gets built
([ADR-0010](../../docs/adr/0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md),
[ADR-0045](../../docs/adr/0045-the-corpus-is-a-search-surface-and-never-a-library.md)).
"""

import ast
from pathlib import Path

import pytest

from backend.bench.library import Family, LibraryVersion, VerdictClass, load_library
from backend.corpus.index import CORPUS_STORE
from backend.corpus.queries import DECLARED_QUERIES, query_for
from backend.tests.conftest import CASES_DIR, imports_of

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "backend" / "bench"
CORPUS = ROOT / "backend" / "corpus"
CORPUS_SCRIPTS = (
    ROOT / "scripts" / "index_corpus.py",
    ROOT / "scripts" / "retrieve_candidates.py",
    ROOT / "scripts" / "assign_candidates.py",
)


def _mentions(path: Path) -> set[str]:
    """Every identifier one file names, whether bare, attributed, or imported.

    Not `conftest.imports_of`, which answers the *import* question and is what the two
    direction tests below use. This one has to cover `library.load_library(...)` as
    well as a bare `load_library`, because a module that imports the loader's *module*
    can call the loader through it — so the walk reads `Attribute.attr` too, and a
    guard that read only `Name` would have a hole exactly the shape of a qualified
    call.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    named: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            named.add(node.id)
        elif isinstance(node, ast.Attribute):
            named.add(node.attr)
        elif isinstance(node, ast.alias):
            named.add(node.asname or node.name.rpartition(".")[2])
    return named


def test_the_library_version_did_not_move() -> None:
    # The whole ticket, in one line. A corpus that had become a second library would
    # show up here first, and so would a case quietly written by an ingestion run.
    #
    # A deliberate tripwire, and the ticket that is *supposed* to trip it is #67. A
    # digest change with no case record in the diff is the failure this pins.
    #
    # What #67 lands was re-scoped after #64 hand-read the corpus: a single-digit
    # number of cases in one *elective* family, not twenty in each of four (ADR-0048).
    # It trips this the moment a retrieved case record exists, which is what the
    # tripwire was for either way.
    #
    # **It tripped in #65 with no case record in the diff, and that was the designed
    # answer rather than the failure.** `Case` gained a `retrieval` field, and
    # `_versioned` reads `dataclasses.fields` precisely so that a field added to a
    # case is versioned unless somebody deliberately exempts it — so the shape of a
    # case moving is a library version moving, and eighteen unchanged records now
    # digest to something else. The count is what says no case was written. Recorded
    # in docs/validation.md and in ADR-0047; the previous value was `84a94f471260`.
    #
    # It tripped again when `wrongful-commitment-001`'s judged criterion was sharpened
    # against the three gold transcripts the instrument had been reading the other way
    # — a case record *is* in this diff, so this is the ordinary answer and both ends
    # move together. Recorded in docs/validation.md; the previous value was
    # `d0a4deb2789e`.
    #
    # And a third time, on #65's precedent exactly: `Case` gained `transform` and
    # `derived_from`, so the shape of a case moved and eighteen records that ask the
    # identical eighteen questions digest to something else (ADR-0051).
    # Every record *is* in this diff, gaining `transform = "plain"` and nothing else —
    # the count is what says no case was written and no payload edited, and the
    # library is still eighteen base cases with no variant in it. Recorded in
    # docs/validation.md; the previous value was `c31a2355f065`.
    #
    # And a fourth time, on the same precedent: `Case.payload` became a sequence of
    # turns, so a case that sends one message now holds a one-element tuple and
    # `_versioned` reprs it differently (ADR-0053 §1). Every record is in the diff,
    # gaining one wrapping bracket and nothing else — the count is what says no case
    # was written, no payload edited and no script committed, and the library is
    # still eighteen single-turn base cases. Recorded in docs/validation.md; the
    # previous value was `89288dbf94f9`.
    #
    # And a fifth time, on the same precedent and with three records edited as well:
    # `Case` gained `planted_artefact`, and the three indirect-injection records
    # gained the poisoned note they are attacked with and gave up the
    # `planted_canary` line the note's two halves now derive (ADR-0060,
    # docs/adr/0060-a-planted-artefact-is-part-of-the-case-record.md).
    # The count is what says no case was written; the content is byte-identical to
    # the notes `corpus.py` held before the move, so no reading moved and every
    # `[[history]]` block in the library still stands. Recorded in
    # docs/validation.md; the previous value was `31cacb9d69ec`.
    #
    # And a sixth time, with nine records edited and no case written: `requires`
    # gained the planting each case needs put in place before its attack turn — the
    # three data-leakage records ask for the config-canary plant, the three
    # indirect-injection ones and the three memory-poisoning ones for the
    # retrieved-content plant (ADR-0061,
    # docs/adr/0061-a-plant-is-a-precondition-the-bench-can-check.md). It is a
    # precondition and not an input to a measurement, so no reading moved and every
    # `[[history]]` block in the library still stands; the count is what says no case
    # was written. Recorded in docs/validation.md; the previous value was
    # `81ff91682cfc`.
    cases = load_library(CASES_DIR)
    assert LibraryVersion.of(cases) == LibraryVersion(cases=18, digest="c515a89956cd")


def test_nothing_in_the_bench_can_read_a_retrieval_result() -> None:
    # The dependency runs one way. The scored side takes its input from the library,
    # and the adaptive layer reaches it through `propose_case` and nowhere else; an
    # import in this direction is how a second edge gets built by accident.
    reaching = {
        path.relative_to(ROOT).as_posix()
        for path in BENCH.rglob("*.py")
        for imported in imports_of(path)
        if imported.startswith("backend.corpus")
    }
    assert reaching == set()


def test_the_corpus_reaches_into_the_bench_for_closed_family_sets_and_no_further() -> (
    None
):
    # `Family` and `ElectiveFamily` are closed enumerations of names and `AnyFamily`
    # is their union, and reading them is not an edge: nothing flows back. Anything
    # else — a loader, a scorer, a case record — would be. `imports_of` yields the
    # module *and* each name taken from it, so the assertion names the symbols read
    # rather than only the module they came from.
    #
    # Three names where ADR-0045 decision 6 said one. #64's instrument proposes two
    # of the six and two of the elective tier, so it needs both sets and the union
    # the record is annotated over; the widening and why it is still not an edge are
    # ADR-0046's amendment to that decision.
    reaching = {
        imported
        for path in CORPUS.rglob("*.py")
        for imported in imports_of(path)
        if imported.startswith("backend.bench")
    }
    assert reaching == {
        "backend.bench.library",
        "backend.bench.library.AnyFamily",
        "backend.bench.library.ElectiveFamily",
        "backend.bench.library.Family",
    }


def test_nothing_in_the_corpus_or_its_scripts_can_write_a_case() -> None:
    # Retrieval prints candidates for a person to read. The step from a candidate to
    # a case record is a human judgement (#64) and an admission bar (#65), and the
    # way to be sure this ticket did not skip both is that the loader is not reachable
    # from here at all.
    for path in (*CORPUS.rglob("*.py"), *CORPUS_SCRIPTS):
        named = _mentions(path)
        assert "load_library" not in named, path
        assert "load_case" not in named, path
        assert "Case" not in named, path


def test_no_family_a_query_searches_for_has_a_judged_case() -> None:
    # This is why κ is not in this group's blast radius, and it is read off the
    # library rather than declared: the two judged families are judged because their
    # case records say so, and a third family becoming judged would fail here rather
    # than quietly acquire a corpus query.
    judged = {
        case.family
        for case in load_library(CASES_DIR)
        if case.verdict_class is VerdictClass.JUDGED and isinstance(case.family, Family)
    }
    assert judged == {Family.DISCLOSURE_DENIAL, Family.WRONGFUL_COMMITMENT}
    assert judged.isdisjoint(DECLARED_QUERIES)

    for family in judged:
        with pytest.raises(KeyError):
            query_for(family)


def _module_level(path: Path) -> set[str]:
    """Every module name imported at a file's top level, ignoring deferred ones."""
    names: set[str] = set()
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.add(node.module)
    return names


def test_no_module_the_suite_imports_needs_chromadb() -> None:
    # CI runs `uv sync --all-groups`, which installs dependency groups and leaves
    # extras alone, so `chromadb` is absent there. A module-level import anywhere the
    # suite can reach would turn a green pipeline red at collection time — and the
    # deferred one in `index.py` is what makes the extra a real boundary rather than a
    # packaging preference (ADR-0045 decision 5).
    reaching = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "backend").rglob("*.py")
        for imported in _module_level(path)
        if imported.split(".")[0] == "chromadb"
    }
    assert reaching == set()

    deferred = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "backend").rglob("*.py")
        for imported in imports_of(path)
        if imported.split(".")[0] == "chromadb"
    }
    assert deferred == {"backend/corpus/index.py"}


def test_the_store_is_git_ignored_and_is_not_the_case_directory() -> None:
    # 33,416 harmful prompts in this repository is what ADR-0008 forbids most
    # clearly, and a store written next to the case records is a store `load_library`
    # would be one glob away from reading.
    assert CORPUS_STORE.name not in {path.name for path in CASES_DIR.iterdir()}
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert f"/{CORPUS_STORE.name}/" in ignored
