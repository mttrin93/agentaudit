"""Where a finding points, when the bench ran where the code is.

The bench's subject is a URL and has been since `TargetConfig`: there is no source
tree in the picture, and the one circumstance in which there is one is the Action
of ADR-0066 — the caller's own repository, on the caller's runner, with the
checkout on disk. So an anchor is *sometimes* available, and this file is mostly
about the times it is not: three populations, and the two that cannot have one say
so (ADR-0071).

Every case here is a read of a real directory rather than a patched `inspect`,
because what is under test is what the bench does to somebody else's filesystem.
"""

from pathlib import Path

import pytest

from backend.bench.source_anchor import (
    MAX_ANCHORED_FILE_BYTES,
    NOT_RUN_WHERE_THE_CODE_IS,
    SourceAnchor,
    SourceAnchorReading,
    anchor_for,
)
from backend.tests.conftest import BENCH, imports_of


def a_checkout(
    tmp_path: Path, source: str = "def answer(message):\n    return ''\n"
) -> Path:
    """A directory standing in for the caller's workspace, with one module in it."""
    checkout = tmp_path / "workspace"
    (checkout / "app").mkdir(parents=True)
    (checkout / "app" / "agent.py").write_text(source, encoding="utf-8")
    return checkout


def a_callback(path: Path, name: str = "answer") -> object:
    """The object a `--callback` reference resolves to, defined in `path`."""
    namespace: dict[str, object] = {}
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)
    return namespace[name]


def test_a_target_the_bench_ran_beside_is_anchored_at_its_own_entrypoint(
    tmp_path: Path,
) -> None:
    # The one circumstance the whole ticket is about: the Action ran in the caller's
    # repository, the callback was imported out of it, and the interpreter can say
    # which file and which line that object was defined on. Read off the checkout
    # rather than asked of a model — a filename a model invented for a repository it
    # cannot read would be a fourth instrument making unverifiable claims about
    # somebody else's code (ADR-0071 §2).
    checkout = a_checkout(tmp_path)
    anchor = anchor_for(a_callback(checkout / "app" / "agent.py"), checkout=checkout)

    assert anchor.reading is SourceAnchorReading.ANCHORED
    assert anchor.path == "app/agent.py"
    assert anchor.line == 1
    assert "app/agent.py" in anchor.stated()


def test_a_finding_whose_file_cannot_be_read_is_unanchored_and_says_so(
    tmp_path: Path,
) -> None:
    # The red-first case the issue names: the object points into the checkout and the
    # file is not there. A `FileNotFoundError` escaping into a run would end a run
    # that has already spent an operator's inference budget, over an optional line of
    # a report — so the absence is a reading and not an exception.
    checkout = a_checkout(tmp_path)
    source = checkout / "app" / "agent.py"
    callback = a_callback(source)
    source.unlink()

    anchor = anchor_for(callback, checkout=checkout)

    assert anchor.reading is SourceAnchorReading.SOURCE_COULD_NOT_BE_READ
    assert anchor.path is None and anchor.line is None
    assert anchor.stated()


def test_a_run_with_no_checkout_says_the_bench_could_not_see_the_source() -> None:
    # The third population, and the ordinary one: a plain hosted endpoint, attacked
    # from wherever the bench happens to run. `payload.py`'s three-kinds-of-nothing
    # rule governs it — this is not a finding with a blank in it and not a finding
    # with nothing wrong, it is a finding the bench could not point at.
    anchor = anchor_for(None, checkout=None)

    assert anchor is NOT_RUN_WHERE_THE_CODE_IS
    assert anchor.reading is SourceAnchorReading.NO_CHECKOUT
    assert "could not see" in anchor.stated()


def test_a_url_target_inside_a_checkout_is_a_different_absence_from_no_checkout(
    tmp_path: Path,
) -> None:
    # Both are unanchored and they are not the same fact. The Action can perfectly
    # well run against a staging URL with the caller's repository checked out beside
    # it, and in that run nothing on disk is known to be the thing that answered.
    checkout = a_checkout(tmp_path)

    assert anchor_for(None, checkout=checkout).reading is (
        SourceAnchorReading.TARGET_IS_A_URL
    )


def test_a_source_file_outside_the_checkout_is_refused_rather_than_published(
    tmp_path: Path,
) -> None:
    # The path is new material about somebody else's machine, and a path that
    # resolved outside the workspace names their filesystem rather than their
    # repository. Refused, and the refusal is its own reading (ADR-0071 §4).
    checkout = a_checkout(tmp_path)
    elsewhere = tmp_path / "elsewhere.py"
    elsewhere.write_text("def answer(message):\n    return ''\n", encoding="utf-8")

    anchor = anchor_for(a_callback(elsewhere), checkout=checkout)

    assert anchor.reading is SourceAnchorReading.SOURCE_OUTSIDE_THE_CHECKOUT
    assert anchor.path is None


def test_a_symlink_that_leaves_the_checkout_is_outside_it(tmp_path: Path) -> None:
    # The interesting half of the rule above: a file *named* inside the checkout can
    # be a link to anywhere, so containment is decided on the resolved path and not
    # on the one the interpreter reported.
    checkout = a_checkout(tmp_path)
    secret = tmp_path / "secret.py"
    secret.write_text("def answer(message):\n    return ''\n", encoding="utf-8")
    (checkout / "app" / "linked.py").symlink_to(secret)

    anchor = anchor_for(a_callback(checkout / "app" / "linked.py"), checkout=checkout)

    assert anchor.reading is SourceAnchorReading.SOURCE_OUTSIDE_THE_CHECKOUT


def test_a_file_larger_than_the_ceiling_is_not_read(tmp_path: Path) -> None:
    # The bench opens a file it was not given, on a runner it does not own, to check
    # one line number. A ceiling rather than a stream to the end, because there is no
    # bound on what a checkout contains and no report line is worth reading a
    # gigabyte for.
    checkout = a_checkout(tmp_path)
    huge = checkout / "app" / "huge.py"
    huge.write_text("x = 0\n" * (MAX_ANCHORED_FILE_BYTES // 6 + 1), encoding="utf-8")
    assert huge.stat().st_size > MAX_ANCHORED_FILE_BYTES

    assert anchor_for(_defined_in(huge), checkout=checkout).reading is (
        SourceAnchorReading.SOURCE_COULD_NOT_BE_READ
    )


def _defined_in(path: Path) -> object:
    """A callable whose code object names `path`, without reading `path`."""
    namespace: dict[str, object] = {}
    exec(compile("def answer(message):\n    return ''\n", str(path), "exec"), namespace)
    return namespace["answer"]


def test_a_line_past_the_end_of_the_file_is_not_anchored(tmp_path: Path) -> None:
    # The anchor is verified against the file rather than asserted from the object:
    # a checkout that moved under a long-running process, or a module imported from a
    # `.pyc` whose source was replaced, would otherwise publish a line that is not
    # there. Verifying it is what makes this evidence rather than a report of one.
    checkout = a_checkout(tmp_path)
    source = checkout / "app" / "agent.py"
    callback = a_callback(source)
    source.write_text("", encoding="utf-8")

    assert anchor_for(callback, checkout=checkout).reading is (
        SourceAnchorReading.SOURCE_COULD_NOT_BE_READ
    )


def test_an_object_with_no_source_at_all_is_its_own_absence() -> None:
    # A builtin, a C extension, a callable compiled from a string with no file: the
    # interpreter has nothing to point at, and that is a fourth thing to say rather
    # than a failure to say the first three.
    assert anchor_for(len, checkout=Path.cwd()).reading is (
        SourceAnchorReading.SOURCE_NOT_ON_THE_OBJECT
    )


def test_a_relative_filename_is_not_placed_against_a_root_it_may_not_belong_to(
    tmp_path: Path,
) -> None:
    # `python foo.py` produces a relative `co_filename`, and resolving one uses *this*
    # process's working directory — which in the Action is the bench's own checkout
    # and not the caller's. A file placed that way could land inside a root it has no
    # relation to, so it is refused rather than guessed at (ADR-0071 §5).
    checkout = a_checkout(tmp_path)
    namespace: dict[str, object] = {}
    exec(
        compile("def answer(message):\n    return ''\n", "app/agent.py", "exec"),
        namespace,
    )

    assert anchor_for(namespace["answer"], checkout=checkout).reading is (
        SourceAnchorReading.SOURCE_NOT_ON_THE_OBJECT
    )


def test_an_anchored_reading_is_the_only_one_that_may_carry_a_path() -> None:
    # The absence cannot be dressed up as a location by a later edit, and an anchored
    # reading cannot be blank: the record refuses both at its own door rather than
    # trusting the one function that builds it (`Precedent`'s discipline).
    with pytest.raises(ValueError):
        SourceAnchor(
            reading=SourceAnchorReading.NO_CHECKOUT, path="app/agent.py", line=1
        )
    with pytest.raises(ValueError):
        SourceAnchor(reading=SourceAnchorReading.ANCHORED)


# --- And none of it reaches an instrument (ADR-0004, ADR-0071 §6) --------------

THE_INSTRUMENTS = ("judge.py", "narration.py", "remediation.py", "adjudication.py")
"""The modules that put a question to a model about this target's own transcripts.

Named as files rather than as types because what is forbidden is the *import*: a path
reaching any of them is a path that can be interpolated into a prompt, and the
question is not whether today's prompt builder does it.
"""


def test_no_instrument_can_reach_an_anchor_at_all() -> None:
    """A filename in a brief un-blinds the judge, and the wall is an import.

    ADR-0004 blinds the adjudicator to which target it is reading, because a judge
    told whose agent it is scoring is a judge with a reason to score it differently. A
    repository path is a stronger identifier than a target name: it carries an
    organisation, a product and a directory layout, and it would arrive attached to
    the transcript the model is being asked to rule on (ADR-0071 §6).

    So the anchor is resolved on the report side, after every verdict is decided, and
    no module that talks to a model may import it. Asserted rather than reviewed, in
    `test_payload.py`'s pattern: the tempting version of the patching ticket is the
    one that hands a model a file to look at, and it would be one import.
    """
    for module in THE_INSTRUMENTS:
        source = BENCH / module
        named = sorted(
            name for name in imports_of(source) if "source_anchor" in name.lower()
        )

        assert not named, (
            f"{module} imports {named}. An instrument that can reach an anchor can "
            "put a path into a prompt, and a judge told which repository it is "
            "reading is a judge that is no longer blind to whose agent it is "
            "scoring (ADR-0004, ADR-0071 §6)"
        )
