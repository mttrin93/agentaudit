"""A patch, a re-served target, one case re-attempted — and a record that is not an
`Attempt`.

The mechanism that makes a fix **proven** rather than **suggested**: apply the patch
to a throwaway copy of the checkout (`throwaway.py`), re-serve the entrypoint out of
it over the message contract
([ADR-0059](../../docs/adr/0059-a-callback-target-is-served-over-the-contract.md)),
re-attempt the one case that succeeded, and see whether the verdict flips. It is
possible at all because the shim serves a user's function on an ephemeral loopback
port and tears down, so nothing outside this process has to redeploy anything.

**And what it produces is not an `Attempt`, by type.** A post-patch re-run is made
against a *different target revision*: counting it would put two revisions under one
name and one denominator, which is
[ADR-0010](../../docs/adr/0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md)'s
error committed a second time in a new place. So `PostPatchAttempt` is its own
record, in its own field, with its own call counter, and there is no signature
anywhere that accepts both — the invariant is carried by the type, exactly as it is
for `AdaptiveEpisode`
([ADR-0072](../../docs/adr/0072-a-post-patch-re-run-is-its-own-record.md) §4).

**A flipped case is not a fixed family.** `n = 30` per family (ADR-0003), and a patch
that defeats one case's exact payload while leaving the family open is overfitting to
the test — the failure mode a proof loop invites. The only claim this module makes is
per-case, `PostPatchAttempt.stated()` says so in the sentence both surfaces print, and
nothing here computes a rate, a proportion or a count of cases (ADR-0072 §5).

**Nothing here reaches an instrument, and no model writes a patch.** This module
imports no `judge`, `narration`, `remediation` or `adjudication`, an import-level test
holds that, and ADR-0072 §2 has the argument: what would be a *fourth instrument*
writing code into somebody's checkout is out of scope on purpose, and a `Patch` is a
value its caller constructs.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
import time
import uuid
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from backend.bench.contract import TargetConfig, Transcript, send_message
from backend.bench.evaluator import Verdict, evaluate_script
from backend.bench.library import AnyFamily, Case, VerdictClass
from backend.bench.shim import Callback, serve_callback
from backend.bench.throwaway import Patch, apply_patch, throwaway_checkout

LOGGER = logging.getLogger(__name__)
"""Where the reason a re-run never happened goes.

`shim.py`'s decision for a callback that raises on the wire, one storey up (ADR-0059
§2): the four ways of failing to re-attempt are one *reading* for a reader of a
report, and the traceback behind it is the operator's own to read on their own
runner. A document about somebody's code is not the place an exception from their
build travels (ADR-0008); a log line on the machine that raised it is.
"""


class PostPatchOutcome(StrEnum):
    """What a re-run against the patched copy found — and never a `Verdict`.

    A closed set of its own rather than `evaluator.Verdict`, on `EpisodeOutcome`'s
    reasoning (ADR-0010): a `Verdict` is the scored quantity, and a record carrying
    one is a record a consumer can group with attempts and divide. These four are
    answers to a different question — *does this case still succeed against the
    patched revision* — and the vocabulary keeps them from being read as the first.
    """

    NO_LONGER_SUCCEEDS = "no_longer_succeeds"
    """The case that succeeded before does not succeed against the patched copy.

    The strongest claim this loop is allowed to make, and it is about **one case**.
    """

    STILL_SUCCEEDS = "still_succeeds"
    """It succeeded again. The patch did not close this case."""

    JUDGED_AND_NOT_RE_DECIDED = "judged_and_not_re_decided"
    """A judged case, which this loop does not re-decide (ADR-0072 §4).

    An adjudicator is an instrument whose κ is measured over the scored layer against
    a gold set of that layer's transcripts (ADR-0013), and a proof is not the place to
    spend an unvalidated reading. Named rather than silently skipped, because a reader
    of a judged family's finding has to be able to tell *not proven* from *not tried*.
    """

    NOT_RE_ATTEMPTED = "not_re_attempted"
    """The copy, the patch or the re-serve never got as far as a reply.

    A refused patch, a patched module that would not load, a server that never bound
    a port, a target that outlived its retry policy. One reading for all of them
    because the distinction a reader can act on is *this fix was not tested*, and the
    detail belongs in the operator's own logs rather than in a document about their
    code (ADR-0008).
    """


@dataclass(frozen=True)
class PostPatchAttempt:
    """One case re-run against a patched revision of the target. **Not an `Attempt`.**

    `Attempt` is the unit of the denominator (CONTEXT.md). This record deliberately
    shares none of the fields that make one countable: it has no `index`, because
    there is no *ten of these*; no `verdict_class`, because nothing groups it by how
    it was decided; no `transform`, because no breakdown is published over it; and
    **no `verdict`**, because a verdict is the scored quantity and a record holding
    one is a record something will eventually divide by (ADR-0010, ADR-0072 §4).

    It cannot be constructed from an `Attempt` and an `Attempt` cannot be constructed
    from it. There is no converter, no `of` and no widened signature, and the reason
    is the one ADR-0010 gives: the arithmetic would stay valid, the population would
    change, and no test would fail.
    """

    case_id: str
    """The one case this is a claim about — and the claim is about no other."""

    family: AnyFamily
    """Which family that case belongs to, so a reader knows what was being tested.

    Carried and **never counted**. `Attempt.family` exists so that a rate can be
    grouped by it; this one exists so a sentence can name it, and ADR-0072 §5's
    prohibition is what keeps the two apart — there is no `n`, no denominator and no
    second re-attempt of this case to pool with.
    """

    target_name: str
    outcome: PostPatchOutcome
    patched: str
    """The file that was replaced, relative to the checkout root, in POSIX form.

    The same string `SourceAnchor.path` publishes and for the same reasons: an
    absolute path names the runner's filesystem rather than the repository, and a
    signed artefact is the wrong place for it (ADR-0071 §4).
    """

    transcripts: tuple[Transcript, ...] = ()
    """Every turn of the re-run, in send order — and empty on `NOT_RE_ATTEMPTED`.

    Empty rather than absent for a re-run that never reached a reply, which is the
    one difference from `Attempt.transcripts`: an attempt with no exchange behind it
    is refused there, because a verdict has to be re-derivable. Here *no exchange*
    is one of the four answers, so it is a state this record is allowed to be in.
    """

    started_at: float = field(default_factory=time.monotonic)
    """When the re-run began, so the ordering ADR-0010's test asserts stays checkable.

    A post-patch re-run happens strictly after every scored attempt and every episode
    of the target it is about — it is made against a *different revision*, so one
    arriving mid-suite would contaminate the suite by a route no type can prevent.
    """

    def stated(self) -> str:
        """This re-run in one sentence, for both surfaces to print unchanged.

        On the record rather than in a renderer, in `SourceAnchor.stated()`'s pattern
        and for its reason. **Every sentence names one case and none of them names
        the family as fixed**: that is ADR-0072 §5 carried in the prose a reader
        actually reads, beside the type that carries it in the arithmetic.
        """
        # `match` with no fallback branch, on `attacker.verdict_of`'s terms: a fifth
        # outcome must fail the type check rather than inherit somebody else's
        # sentence, and the sentence is what a reader is handed.
        match self.outcome:
            case PostPatchOutcome.NO_LONGER_SUCCEEDS:
                return (
                    f"{self.case_id} no longer succeeds against a copy of this "
                    f"checkout with {self.patched} replaced. That is a claim about "
                    "this one case and deliberately not about its family: a family "
                    "is measured over thirty attempts against every live case in "
                    "it, and re-running one is the operator's to ask for "
                    "(ADR-0003, ADR-0072)"
                )
            case PostPatchOutcome.STILL_SUCCEEDS:
                return (
                    f"{self.case_id} still succeeds against a copy of this checkout "
                    f"with {self.patched} replaced. The change was applied and "
                    "re-attempted, and this case was not closed by it"
                )
            case PostPatchOutcome.JUDGED_AND_NOT_RE_DECIDED:
                return (
                    f"{self.case_id} was not re-attempted: its verdict is judged, "
                    "and this loop does not re-decide a judged case. An "
                    "adjudicator's agreement is measured over the scored layer, and "
                    "a proof is not the place to spend a reading nothing has "
                    "validated (ADR-0013)"
                )
            case PostPatchOutcome.NOT_RE_ATTEMPTED:
                return (
                    f"{self.case_id} was not re-attempted. The patch, the copy or "
                    "the re-served target did not get as far as a reply, so this "
                    "fix is untested rather than tested and found wanting"
                )


class NotAPostPatchAttempt(TypeError):
    """What a proof says when it was handed a scored `Attempt` instead of a re-run.

    `judge.NotAScoredAttempt` in the other direction, and the runtime half of the
    wall the annotations already hold: mypy refuses the call, and this refuses it
    again for a caller who silenced mypy. An `Attempt` inside a `PatchProof` would be
    a scored attempt reported as evidence about a revision it was never made against.
    """


@dataclass(frozen=True)
class PatchProof:
    """One patch, one case, one re-run, and what it cost on the wire.

    **One case and not a family**, which is the shape of the whole record: there is
    no list of re-attempts here to be counted, no `successes`, and no arithmetic over
    which a proof rate could be computed. Re-running a family is thirty attempts of
    the operator's money and is the operator's to ask for (ADR-0072 §5).
    """

    patch: Patch
    re_attempt: PostPatchAttempt
    post_patch_calls: int
    """What the re-run put on the wire, retries included. **Its own counter.**

    Separate from `RunState.spent`, which is keyed on `Layer` and holds the two
    figures ADR-0007 asks an operator to consent to. A third `Layer` member would put
    this spend inside a ceiling declared for the scored suite and would make it
    addable to the other two, which is the blending ADR-0007 exists to prevent — so
    the count lives here, on the record of the thing that spent it, and `RunState`
    never sees it.

    **The ceiling is the construction rather than a declared number**: `prove_patch`
    re-attempts one case exactly once, so the most this can be is one attempt's worth
    of sends. A loop that could re-run a family would need a ceiling of its own, and
    that is the same decision as re-running a family (ADR-0072 §5).
    """

    def __post_init__(self) -> None:
        if self.post_patch_calls < 0:
            raise ValueError(
                f"a proof reported {self.post_patch_calls} calls. A counter is what "
                "went on the wire, and a negative one is a counter nothing could "
                "have produced"
            )
        if not isinstance(self.re_attempt, PostPatchAttempt):
            raise NotAPostPatchAttempt(
                f"a proof was built around a {type(self.re_attempt).__name__}. A "
                "proof is evidence about a *patched* revision of the target, and a "
                "scored attempt was made against the revision that failed — one "
                "reported as the other would put two revisions under one name "
                "(ADR-0010, ADR-0072 §4)"
            )


class ReServe(Protocol):
    """How the patched entrypoint gets back behind the message contract.

    A protocol and an argument rather than a hard call to `serve_callback`, so that
    this module is testable without a port and so that the one place a patched object
    is *executed* is a value the caller chose. The default is `serve_callback`, which
    is the only implementation the bench has and the one ADR-0059 argued.
    """

    def __call__(
        self, callback: Callback, *, name: str
    ) -> AbstractContextManager[TargetConfig]: ...


def prove_patch(
    patch: Patch,
    case: Case,
    *,
    checkout: Path,
    workspace: str,
    entrypoint: str,
    canary: str,
    target_name: str = "patched",
    serve: ReServe = serve_callback,
) -> PatchProof:
    """Patch a throwaway copy, re-serve it, re-attempt one case, and report.

    **It never raises for anything but a cancellation.** A run reaching this has
    already spent the operator's inference budget and has every figure it will ever
    report; an exception escaping here would end that run over the one thing in it
    that decides nothing, which is `source_anchor.anchor_for`'s argument arriving one
    field along (ADR-0071 §5). A `BaseException` is not caught: a cancellation is the
    operator asking for the run to stop, and the copy is dropped as it passes.

    **The copy is dropped however this ends** — `throwaway_checkout` holds that in one
    `finally` over the eight endings ADR-0072 §3 enumerates, and every line below is
    inside it.
    """
    began = time.monotonic()
    if case.verdict_class is VerdictClass.JUDGED:
        # Before the copy and before the port: a judged case is not re-decided here,
        # so there is nothing for a patched revision to answer (ADR-0072 §4).
        return PatchProof(
            patch=patch,
            re_attempt=PostPatchAttempt(
                case_id=case.id,
                family=case.family,
                target_name=target_name,
                outcome=PostPatchOutcome.JUDGED_AND_NOT_RE_DECIDED,
                patched=patch.path,
                started_at=began,
            ),
            post_patch_calls=0,
        )
    outcome = PostPatchOutcome.NOT_RE_ATTEMPTED
    transcripts: tuple[Transcript, ...] = ()
    calls = 0
    with throwaway_checkout(checkout, workspace=workspace) as throwaway:
        try:
            written = apply_patch(throwaway, patch)
            with _patched_entrypoint(
                written, throwaway.workspace, entrypoint
            ) as served:
                with serve(served, name=target_name) as target:
                    # One session for every turn, fresh per re-run: a script's turns
                    # depend on each other and the session id is what carries the
                    # dependence, which is `attacker._send`'s reasoning unchanged.
                    #
                    # The three lines below are that function's three lines and are
                    # deliberately not shared with it. What makes `_send` `_send` is
                    # everything around them — the `RunState`, the two ceilings, the
                    # position, the span, the adjudication pool — and a helper this
                    # could call would either carry that in (a proof loop holding a
                    # scored counter, which is the one thing ADR-0072 §4 forbids) or
                    # be the three lines with a name. The transport is shared, which
                    # is where ADR-0010 says two layers should share: `send_message`,
                    # and nothing above it.
                    session = f"{case.id}-proof-{uuid.uuid4()}"
                    # Counted as each exchange comes back rather than summed at the
                    # end, because a re-run that fell over on its second turn still
                    # put its first turn on the wire — a counter that reported zero
                    # for it would be the counter lying about spend that happened,
                    # which is `RunState.record_call`'s reasoning without a ceiling
                    # to enforce (ADR-0007, ADR-0072 §4).
                    planted = None
                    if case.planting is not None:
                        planted = send_message(
                            target, case.planting, session_id=session
                        )
                        calls += planted.sends
                    sent: list[Transcript] = []
                    for turn in case.payload:
                        sent.append(send_message(target, turn, session_id=session))
                        calls += sent[-1].sends
                    transcripts = tuple(sent)
                    # The success condition and nothing else — the same deterministic
                    # reading the scored attempt got, so that *flipped* means what it
                    # meant the first time (ADR-0004).
                    decided = evaluate_script(
                        case, transcripts, target, canary, planted
                    )
            outcome = (
                PostPatchOutcome.STILL_SUCCEEDS
                if decided.verdict is Verdict.SUCCEEDED
                else PostPatchOutcome.NO_LONGER_SUCCEEDS
            )
        except Exception:
            # `Exception` and not `BaseException`: the four ways of failing to
            # re-attempt are one reading, and a cancellation is not one of them.
            outcome = PostPatchOutcome.NOT_RE_ATTEMPTED
            LOGGER.exception("the re-run of %s was not made", case.id)
    if throwaway.drop_error is not None:
        # The one path on which a patched copy of somebody's repository is still on
        # their runner. It reaches no artefact because nothing here reaches one yet
        # (#116), and it reaches the log rather than nothing, on `Teardown.error`'s
        # reasoning: the operator is the only person who can act on it (ADR-0063 §3).
        LOGGER.warning(
            "the throwaway checkout at %s was not dropped: %s",
            throwaway.root,
            throwaway.drop_error,
        )
    return PatchProof(
        patch=patch,
        re_attempt=PostPatchAttempt(
            case_id=case.id,
            family=case.family,
            target_name=target_name,
            outcome=outcome,
            patched=patch.path,
            transcripts=transcripts
            if outcome is not PostPatchOutcome.NOT_RE_ATTEMPTED
            else (),
            started_at=began,
        ),
        post_patch_calls=calls,
    )


@contextmanager
def _patched_entrypoint(
    written: Path, workspace: str, attribute: str
) -> Iterator[Callback]:
    """Execute the patched file out of the copy and hand back the named attribute.

    **Under a name of its own, and dropped with the copy.** The module is registered
    in `sys.modules` under a synthesised name derived from the workspace, so a patched
    revision of a file can never be found by anything importing that file's real
    dotted name — the bench's own module table is not somewhere a patch is allowed to
    land, and this is a process that holds the signing key and the operator's tokens.
    It is removed in a `finally` for the reason the copy is: the endings that leave it
    behind are the endings nobody tests.

    **One file, and the copy is never on `sys.path`.** Everything the patched module
    imports resolves the ordinary way, to the unpatched originals, so exactly one
    revision of exactly one file is under test — which is the only claim the anchor
    licenses (ADR-0071 §2) and the only one `Patch` can address (ADR-0072 §2). Putting
    the copy on the path instead would let a patched revision of *any* module in that
    tree be found by anything importing it for the rest of this process, which is the
    same hazard the synthesised name closes, arriving by the other door.

    The cost is stated rather than worked around: an entrypoint whose module uses a
    **relative** import cannot be executed this way, and a re-run that cannot be
    executed is `NOT_RE_ATTEMPTED` — a named reading, and not a claim about the fix
    (ADR-0072 §2).
    """
    name = f"{workspace.replace('-', '_')}_{written.stem}"
    spec = importlib.util.spec_from_file_location(name, written)
    if spec is None or spec.loader is None:
        raise ImportError(f"the patched file at {written} names no module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        served: Callback = getattr(module, attribute)
        yield served
    finally:
        sys.modules.pop(name, None)
