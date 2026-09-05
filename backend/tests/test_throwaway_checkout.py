"""A patch goes to a throwaway copy of the checkout, and the copy is always dropped.

The invariant of ADR-0072, driven at one seam — `bench/throwaway.py` — and asked
the two questions that make this the most dangerous mechanism in the bench:

* **is the original ever written?** Every test in *the original is read-only* hashes
  the checkout before and after and compares.
* **is the copy ever left behind?** Every test in *the runs that end badly* asserts
  the workspace is gone, on each of the eight endings ADR-0072 §3 enumerates.

**The failure paths are the tests that matter here.** Moving the drop out of the
`finally` and onto the end of the happy path leaves the clean-finish test passing and
takes every test under *the runs that end badly* red with it, which is #86's red
drive applied to a working tree.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from backend.bench.contract import TargetFailure, TargetUnreachable
from backend.bench.source_anchor import (
    NOT_RUN_WHERE_THE_CODE_IS,
    SourceAnchor,
    SourceAnchorReading,
)
from backend.bench.throwaway import (
    MAX_PATCHED_FILE_BYTES,
    WORKSPACE_PREFIX,
    Patch,
    PatchRefusal,
    PatchRefused,
    Throwaway,
    apply_patch,
    throwaway_checkout,
    workspace_for,
)


def test_a_workspace_is_derived_from_the_run_id() -> None:
    assert workspace_for("0123456789abcdef") == f"{WORKSPACE_PREFIX}0123456789abcdef"


def test_a_run_id_that_could_not_be_a_directory_is_refused_and_not_sanitised() -> None:
    with pytest.raises(ValueError) as refused:
        workspace_for("../../etc")
    assert "refused" in str(refused.value)


# --- The copy ---------------------------------------------------------------


def a_checkout(root: Path) -> Path:
    """A checkout with one module in a package, a data file and a nested directory.

    Small on purpose and not a fixture of the repository: what these tests are about
    is the copy and the drop, and a checkout the test wrote is one whose every byte
    the test can hash.
    """
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (root / "pkg" / "agent.py").write_text("ANSWER = 'original'\n", encoding="utf-8")
    (root / "notes.txt").write_text("read me\n", encoding="utf-8")
    (root / ".git").mkdir()
    (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (root / "pkg" / "__pycache__").mkdir()
    (root / "pkg" / "__pycache__" / "agent.pyc").write_bytes(b"stale bytecode")
    return root


def fingerprint(root: Path) -> str:
    """Every path under this tree and every byte in it, as one digest.

    Paths as well as contents, so a file *added* to the original is as visible as a
    file changed in it — which is the half a content-only hash would miss.
    """
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        if path.is_file() and not path.is_symlink():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def test_the_copy_carries_the_checkouts_files(tmp_path: Path) -> None:
    checkout = a_checkout(tmp_path / "checkout")
    with throwaway_checkout(checkout, workspace=workspace_for("abc")) as throwaway:
        assert (
            throwaway.root / "pkg" / "agent.py"
        ).read_text() == "ANSWER = 'original'\n"
        assert (throwaway.root / "notes.txt").read_text() == "read me\n"


def test_the_copy_has_no_repository_in_it_to_commit_a_patch_to(tmp_path: Path) -> None:
    """ADR-0072 §1: no branch, stash or commit survives, because there is no `.git`."""
    checkout = a_checkout(tmp_path / "checkout")
    with throwaway_checkout(checkout, workspace=workspace_for("abc")) as throwaway:
        assert not (throwaway.root / ".git").exists()


def test_the_copy_carries_no_stale_bytecode_beside_a_file_it_will_patch(
    tmp_path: Path,
) -> None:
    """A `.pyc` the interpreter could load *instead of* the patch is the worst answer
    this loop could give: it would re-run the unpatched module and report a fix."""
    checkout = a_checkout(tmp_path / "checkout")
    with throwaway_checkout(checkout, workspace=workspace_for("abc")) as throwaway:
        assert not (throwaway.root / "pkg" / "__pycache__").exists()


def test_a_root_that_is_not_a_workspace_cannot_be_declared_a_throwaway(
    tmp_path: Path,
) -> None:
    """The one check that stops a hand-built record pointing the patch writer at the
    caller's own checkout."""
    with pytest.raises(ValueError) as refused:
        Throwaway(root=tmp_path / "checkout", workspace="proof-abc")
    assert "would make the patch writer write into their repository" in str(
        refused.value
    )


# --- The patch, and where it is allowed to land ------------------------------


PATCHED = "ANSWER = 'patched'\n"


def test_a_patch_lands_in_the_copy(tmp_path: Path) -> None:
    checkout = a_checkout(tmp_path / "checkout")
    with throwaway_checkout(checkout, workspace=workspace_for("abc")) as throwaway:
        apply_patch(throwaway, Patch(path="pkg/agent.py", contents=PATCHED))
        assert (throwaway.root / "pkg" / "agent.py").read_text() == PATCHED
        assert throwaway.patched == ("pkg/agent.py",)


def test_the_original_checkout_is_not_written(tmp_path: Path) -> None:
    """The claim ADR-0072 §1 is entirely about, asserted over every byte and path."""
    checkout = a_checkout(tmp_path / "checkout")
    before = fingerprint(checkout)
    with throwaway_checkout(checkout, workspace=workspace_for("abc")) as throwaway:
        apply_patch(throwaway, Patch(path="pkg/agent.py", contents=PATCHED))
    assert fingerprint(checkout) == before


def test_an_absolute_path_is_refused(tmp_path: Path) -> None:
    checkout = a_checkout(tmp_path / "checkout")
    with throwaway_checkout(checkout, workspace=workspace_for("abc")) as throwaway:
        with pytest.raises(PatchRefused) as refused:
            apply_patch(throwaway, Patch(path="/etc/passwd", contents=PATCHED))
    assert refused.value.refusal is PatchRefusal.NOT_A_RELATIVE_PATH


def test_a_path_that_walks_out_of_the_copy_is_refused(tmp_path: Path) -> None:
    checkout = a_checkout(tmp_path / "checkout")
    outside = tmp_path / "outside.py"
    outside.write_text("untouched\n", encoding="utf-8")
    with throwaway_checkout(checkout, workspace=workspace_for("abc")) as throwaway:
        with pytest.raises(PatchRefused) as refused:
            apply_patch(throwaway, Patch(path="../../outside.py", contents=PATCHED))
    assert refused.value.refusal is PatchRefusal.NOT_A_RELATIVE_PATH
    assert outside.read_text() == "untouched\n"


def test_a_symlink_out_of_the_copy_is_refused_on_the_resolved_path(
    tmp_path: Path,
) -> None:
    """Containment is decided after resolving, so a link *inside* the copy pointing
    out of it is outside it — a repository is a thing a caller can put links in."""
    outside = tmp_path / "outside.py"
    outside.write_text("untouched\n", encoding="utf-8")
    checkout = a_checkout(tmp_path / "checkout")
    (checkout / "escape.py").symlink_to(outside)
    with throwaway_checkout(checkout, workspace=workspace_for("abc")) as throwaway:
        with pytest.raises(PatchRefused) as refused:
            apply_patch(throwaway, Patch(path="escape.py", contents=PATCHED))
    assert refused.value.refusal is PatchRefusal.LEFT_THE_CHECKOUT
    assert outside.read_text() == "untouched\n"


def test_a_patch_replaces_and_never_creates(tmp_path: Path) -> None:
    checkout = a_checkout(tmp_path / "checkout")
    with throwaway_checkout(checkout, workspace=workspace_for("abc")) as throwaway:
        with pytest.raises(PatchRefused) as refused:
            apply_patch(throwaway, Patch(path="pkg/new.py", contents=PATCHED))
        assert not (throwaway.root / "pkg" / "new.py").exists()
    assert refused.value.refusal is PatchRefusal.NO_SUCH_FILE


def test_a_directory_is_not_a_patchable_file(tmp_path: Path) -> None:
    checkout = a_checkout(tmp_path / "checkout")
    with throwaway_checkout(checkout, workspace=workspace_for("abc")) as throwaway:
        with pytest.raises(PatchRefused) as refused:
            apply_patch(throwaway, Patch(path="pkg", contents=PATCHED))
    assert refused.value.refusal is PatchRefusal.NOT_A_REGULAR_FILE


def test_a_patch_over_the_ceiling_is_refused(tmp_path: Path) -> None:
    """The figure on `MAX_PATCHED_FILE_BYTES` is the claim this test makes true."""
    checkout = a_checkout(tmp_path / "checkout")
    with throwaway_checkout(checkout, workspace=workspace_for("abc")) as throwaway:
        with pytest.raises(PatchRefused) as refused:
            apply_patch(
                throwaway,
                Patch(path="notes.txt", contents="x" * (MAX_PATCHED_FILE_BYTES + 1)),
            )
        assert (throwaway.root / "notes.txt").read_text() == "read me\n"
    assert refused.value.refusal is PatchRefusal.TOO_LARGE


def test_a_patch_is_addressed_at_the_file_the_anchor_pointed_at() -> None:
    anchor = SourceAnchor(
        reading=SourceAnchorReading.ANCHORED, path="pkg/agent.py", line=1
    )
    assert Patch.for_anchor(anchor, PATCHED).path == "pkg/agent.py"


def test_a_patch_cannot_be_addressed_at_an_absence() -> None:
    """Five of the six readings name no file, and a patch to one has no target."""
    with pytest.raises(PatchRefused) as refused:
        Patch.for_anchor(NOT_RUN_WHERE_THE_CODE_IS, PATCHED)
    assert refused.value.refusal is PatchRefusal.NO_SUCH_FILE


# --- The runs that end badly -------------------------------------------------
#
# ADR-0072 §3's eight endings. These are the tests that matter in this file: move
# the drop out of the `finally` and onto the end of the happy path and the first of
# them still passes while every other one goes red.


def kept(tmp_path: Path) -> tuple[Path, list[Throwaway]]:
    """A checkout, and a list the copy is put in so a test can look for it after."""
    return a_checkout(tmp_path / "checkout"), []


def test_a_clean_finish_drops_the_copy(tmp_path: Path) -> None:
    checkout, seen = kept(tmp_path)
    with throwaway_checkout(checkout, workspace=workspace_for("abc")) as throwaway:
        seen.append(throwaway)
    assert not seen[0].root.exists()
    assert seen[0].drop_error is None


def test_a_refused_patch_drops_the_copy(tmp_path: Path) -> None:
    checkout, seen = kept(tmp_path)
    with pytest.raises(PatchRefused):
        with throwaway_checkout(checkout, workspace=workspace_for("abc")) as throwaway:
            seen.append(throwaway)
            apply_patch(throwaway, Patch(path="/etc/passwd", contents=PATCHED))
    assert not seen[0].root.exists()


def test_a_patched_module_that_will_not_load_drops_the_copy(tmp_path: Path) -> None:
    """The patch landed and the re-serve never got as far as a port."""
    checkout, seen = kept(tmp_path)
    with pytest.raises(SyntaxError):
        with throwaway_checkout(checkout, workspace=workspace_for("abc")) as throwaway:
            seen.append(throwaway)
            apply_patch(throwaway, Patch(path="pkg/agent.py", contents="def ("))
            compile(
                (throwaway.root / "pkg" / "agent.py").read_text(), "agent.py", "exec"
            )
    assert not seen[0].root.exists()


def test_a_re_serve_that_never_bound_a_port_drops_the_copy(tmp_path: Path) -> None:
    checkout, seen = kept(tmp_path)
    with pytest.raises(TimeoutError):
        with throwaway_checkout(checkout, workspace=workspace_for("abc")) as throwaway:
            seen.append(throwaway)
            raise TimeoutError("the patched target's server did not start")
    assert not seen[0].root.exists()


def test_a_patched_target_that_never_answered_drops_the_copy(tmp_path: Path) -> None:
    checkout, seen = kept(tmp_path)
    with pytest.raises(TargetUnreachable):
        with throwaway_checkout(checkout, workspace=workspace_for("abc")) as throwaway:
            seen.append(throwaway)
            raise TargetUnreachable(
                TargetFailure.UNAVAILABLE, "http://127.0.0.1:0/messages", sends=3
            )
    assert not seen[0].root.exists()


def test_a_raise_after_the_re_attempt_landed_drops_the_copy(tmp_path: Path) -> None:
    checkout, seen = kept(tmp_path)
    with pytest.raises(RuntimeError):
        with throwaway_checkout(checkout, workspace=workspace_for("abc")) as throwaway:
            seen.append(throwaway)
            apply_patch(throwaway, Patch(path="pkg/agent.py", contents=PATCHED))
            raise RuntimeError("the verdict route fell over with the reply in hand")
    assert not seen[0].root.exists()


def test_a_cancellation_drops_the_copy(tmp_path: Path) -> None:
    """`finally` and not `except Exception`: a `KeyboardInterrupt` is a
    `BaseException` and passes straight through a clause written for the other
    seven (ADR-0063 §2, ADR-0072 §3)."""
    checkout, seen = kept(tmp_path)
    with pytest.raises(KeyboardInterrupt):
        with throwaway_checkout(checkout, workspace=workspace_for("abc")) as throwaway:
            seen.append(throwaway)
            raise KeyboardInterrupt
    assert not seen[0].root.exists()


def test_a_copy_that_failed_partway_is_still_dropped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The one ending where nothing is ever yielded, so the copy is made *after* the
    directory it goes in is known — a half-copied tree is still a tree to remove."""
    checkout = a_checkout(tmp_path / "checkout")
    made: list[Path] = []

    def half(src: object, dst: str, **_: object) -> None:
        made.append(Path(dst))
        Path(dst).mkdir(parents=True)
        (Path(dst) / "notes.txt").write_text("half a checkout\n", encoding="utf-8")
        raise OSError("the runner ran out of disk")

    monkeypatch.setattr(shutil, "copytree", half)
    with pytest.raises(OSError):
        with throwaway_checkout(checkout, workspace=workspace_for("abc")):
            pass
    assert made and not made[0].exists() and not made[0].parent.exists()


def test_a_drop_that_failed_is_a_string_and_never_a_raise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It runs in a `finally` that is usually carrying the run's real answer out, and
    a cleanup that raised there would cost the operator the more important of the
    two (ADR-0063 §2)."""
    checkout, seen = kept(tmp_path)

    def refuses(*_: object, **kwargs: object) -> None:
        onexc = kwargs["onexc"]
        assert callable(onexc)
        onexc(None, None, OSError("the directory is held open"))

    monkeypatch.setattr(shutil, "rmtree", refuses)
    with pytest.raises(RuntimeError, match="the run's own answer"):
        with throwaway_checkout(checkout, workspace=workspace_for("abc")) as throwaway:
            seen.append(throwaway)
            raise RuntimeError("the run's own answer")
    assert seen[0].drop_error == "the directory is held open"


def test_a_throwaway_must_be_named_the_way_this_module_names_one(
    tmp_path: Path,
) -> None:
    """`workspace_for`'s grammar, checked again at the record's door: a root whose
    name is not its own workspace is a record nothing here made."""
    with pytest.raises(ValueError, match="named for its own workspace"):
        Throwaway(root=tmp_path / "proof-abc", workspace="proof-def")
    with pytest.raises(ValueError, match="named for its own workspace"):
        Throwaway(root=tmp_path / "proof-../..", workspace="proof-../..")
