"""The artefact one finished run leaves behind, built once and served unchanged.

`assembler.py` turns a run into a structured result, `payload.py` turns that into
canonical bytes, `rendering.py` binds the document a human reads into them by digest
and `signing.py` signs the pair. This module is where a run started over HTTP meets
that chain: it is called once, when the run completes, and what it returns is held on
the record for the route to hand out.

**Built at completion and never on request.** A route that assembled the payload
each time it was asked would produce bytes that depend on when it was asked — a
second `AttestationRecord`, a clock, a library that has since moved — and a
signature is over one document rather than over a recipe for making one. So the
artefact is made once, by the thread that made the run, and every later request is a
read of the same bytes (#56).

**A bench with no key produces no report, and says so.** There is no fallback key
and nothing generates one: a report signed by a key nobody has published is a valid
signature over unknown provenance (ADR-0017, `signing.NoSigningKey`). A run on such a
bench still runs and is still measured — what it does not have is an artefact, which
the route reports under its own name rather than by serving an unsigned payload. That
state stays reachable on purpose, for a caller that declares it; what may not reach it
is a deployment that configured nothing, which is refused at the factory instead
(ADR-0020, `app.deployed_bench`).

**The three model identifiers are declared beside the instruments they name.** A
default naming a model would be this module asserting which instrument decided a
judged family, on a bench whose adjudicator is `None` and whose attacker is the
deterministic stand-in. So the default states the absence instead, and a deployment
that configures real instruments declares them here in the same record.

**Nothing here reads a gate.** `read_gate` is never called on a target run and there
is no field in the payload that could carry one (ADR-0018). The bench's own gate
result travels as a `GateCitation` in the provenance block, supplied by the
deployment that knows which run certified it, and its absence prints a stated
absence rather than a blank.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from backend.bench.assembler import assemble, reported_episodes
from backend.bench.calibration import CalibrationResult
from backend.bench.declared_gap import DeclaredGap
from backend.bench.fix_standing import FixStanding
from backend.bench.library import Case, Family
from backend.bench.payload import (
    DeclaredModels,
    GateCitation,
    Provenance,
    TargetPayload,
)
from backend.bench.rule import GateRule
from backend.bench.scorer import Reliability
from backend.bench.selection import AttackSelection
from backend.bench.signing import SignedArtefact, encoded, public_key, signed
from backend.bench.source_anchor import (
    NOT_RUN_WHERE_THE_CODE_IS,
    SourceAnchor,
)
from backend.bench.verification import Published, Verification, checked

UNDECLARED_MODEL = (
    "not declared — this bench was configured without naming the model behind this "
    "instrument. A stated absence, and not a model: a report that named one would "
    "be asserting which instrument produced its figures on the strength of a "
    "default (ADR-0004)"
)
"""What a model identifier says when the deployment declared none.

Said rather than guessed. The two instruments this bench can run without — an
adjudicator and a model-backed attacker — both have a deterministic stand-in, and a
default naming a real model would describe a run that did not happen.
"""

UNDECLARED_MODELS = DeclaredModels(
    calibration=UNDECLARED_MODEL,
    adjudicating=UNDECLARED_MODEL,
    attacking=UNDECLARED_MODEL,
    narrative=UNDECLARED_MODEL,
)
"""The four identifiers of a bench that declared none of them.

A bench with no narrative model declared holds no narrator either, so its findings
section reads *no narrative instrument was declared* — and the two absences agree
because they come from the same undeclared string (ADR-0030, ADR-0070)."""


@dataclass(frozen=True)
class ReportConfig:
    """What a bench needs in order to publish an artefact, and nothing it measures.

    One record rather than three fields on `BenchConfig`, because these three are one
    concern — how a finished run becomes a document that travels — and none of them
    changes what the run does to the target. A bench holding the default of every one
    of them runs exactly the same suite and produces no report.
    """

    signing_key: Ed25519PrivateKey | None = None
    """The key this bench signs with, or nothing.

    Handed in rather than read here: `signing.signing_key` is the one line in this
    repository that reads `AGENTAUDIT_SIGNING_KEY`, and no module of the API layer
    is an environment reader of its own — ADR-0007's cost figures are why that
    prohibition exists, and it is intact.

    `None` is a bench that cannot sign, and it is a state a caller has to ask for.
    Its runs complete and are measured; their reports are refused by name rather
    than served unsigned, because the word *signed* has to mean one thing. What a
    deployment may not do is arrive here by omission: `app.py`'s factory calls
    `signing.signing_key` when it was handed no configuration and refuses to boot
    without one, so a bench that cannot sign is one somebody declared rather than
    one nobody configured (ADR-0020).
    """

    models: DeclaredModels = UNDECLARED_MODELS
    """The three model identifiers this bench's runs were made under."""

    gate: GateCitation | None = None
    """The bench's own gate result, cited as provenance and never as a result.

    A fact about the instrument (ADR-0018). `None` prints `UNCITED_GATE` — an uncited
    instrument is a fact about the report, and a report that omitted the line would
    read as one with nothing to declare.

    **Where it comes from changed with ADR-0023.** It used to be supplied by the
    deployment that knew which gate run certified the bench, and it stays declarable
    that way — a caller constructing this record may still name one. What it is now,
    by default, is the citation the case library records: a gate run writes it there
    beside the readings it stored (`bench/cited.py`), `app.deployed_bench` reads it
    off the library it booted with, and a gate run started from the console replaces
    it in this process through one edge (`gate_runs.Cites`). So a bench that has
    passed its own gate cites it without anyone editing a configuration, and a bench
    whose last gate run failed cites *that*.

    Still nothing this module reads or computes: `read_gate` is never called on a
    target run and the citation arrives already made.
    """

    reliability: Mapping[Family, Reliability] = field(default_factory=dict)
    """κ per judged family, measured on the instrument that adjudicates these runs.

    ADR-0004 requires κ beside every judged rate, and a judged family that reaches
    this module without one is withheld rather than published (ADR-0015) — which is
    what an empty mapping means and what it does. It is **not** re-measured per run:
    κ is a reading about the adjudicator against the pre-registered gold set, the
    gate is where the bench measures its own instruments, and a target run that
    re-took it would be spending an operator's budget to learn something about the
    bench (ADR-0013, and the same division ADR-0018 draws for `D`).

    So it arrives already measured, from the gate run the case library cites
    (`bench/cited.the_reliability`), and only when that gate run adjudicated with the
    model these runs adjudicate with — `CitedReliability.for_adjudicator` is the
    guard, and `app.deployed_bench` is where it is applied. A κ measured on another
    model is a figure about another instrument, and it does not reach a rate it says
    nothing about.

    What crosses from the gate is this and nothing else: no rate, no interval, no
    band and no `D`, none of which has a definition for one target (ADR-0018).

    **Read at boot, and not through `gate_runs.Cites`.** A gate run started from the
    console updates the citation in this process through that one edge, and the edge
    is a `GateCitation` in and nothing out — a per-family κ crossing it is the
    widening ADR-0021 forbids. So a gate run made here becomes the κ these runs
    publish at the next process start, off the record it wrote into the library,
    which is the same durable path the citation already takes.
    """

    source_anchor: SourceAnchor = NOT_RUN_WHERE_THE_CODE_IS
    """Where the checkout this run was made beside is, or the absence of one.

    **The default is the absence, and for this route it is the only answer.** A hosted
    bench attacks a URL and has no source tree in the picture; the one circumstance in
    which the bench and the code are in the same place is the composite Action running
    in the caller's own repository (ADR-0066), and `scripts/bench.py` is the entrypoint
    that resolves one there
    ([ADR-0071](../../docs/adr/0071-a-finding-points-at-a-file-the-bench-read.md)).

    On this record rather than measured here, on `reliability`'s own terms: it arrives
    already resolved from the one process that had a checkout to resolve it against,
    and no module of the API layer reads a filesystem to fill it in.
    """

    standings: Mapping[str, FixStanding] = field(default_factory=dict)
    """Whether each fix was proven, per case id, from the run that could patch one.

    **Empty for every run this route serves, and that is the honest answer rather than
    a gap.** Proving a fix means patching a copy of the caller's checkout, re-serving
    the target out of it and re-attempting the case; a hosted bench attacks a URL and
    cannot restart somebody else's server, so its fixes are *proposed* by construction
    and a case with no entry here reads exactly that
    ([ADR-0073](../../docs/adr/0073-two-labels-on-a-fix-and-no-third.md) §2).

    Per case rather than per run, which is the one way it differs from the anchor
    above: a patch replaces one file to close one case, and a run that proved one fix
    has proved nothing about the next failure in the same report. On this record for
    the anchor's own reason — it arrives already derived from the one entrypoint that
    had a checkout to patch, and no module of the API layer patches anything.
    """

    pinned: Ed25519PublicKey | None = None
    """The public key a verification of this bench's reports is run against.

    `None` is the key committed to this repository, which is the key `verify.py`
    pins by default and whose fingerprint the README publishes — the one a recipient
    who does not trust the sender would use. It is the default here for exactly that
    reason: a bench that verified its own artefacts against its own signing key
    would report *valid* on every report it ever produced, including the ones no
    recipient can check, and the outcome that matters most would be unreachable
    (`SignatureOutcome.ANOTHER_KEY`).

    A deployment signing with a rotated key declares its published half here, which
    is `--pubkey` in the one place the API has for it.
    """


def payload_for(
    result: CalibrationResult,
    cases: Sequence[Case],
    rule: GateRule,
    config: ReportConfig,
    selection: AttackSelection,
    gaps: Mapping[Family, DeclaredGap],
) -> TargetPayload:
    """The unsigned, unbound payload for one completed run.

    Every figure comes from the run and every field beside them comes from the
    configuration: there is no line here that computes anything, which is the
    structural form of *no composite score* (ADR-0005). The provenance block is the
    only place the two meet, and not one of its fields is a measurement of the
    target.

    `gaps` are the families this run's caller declared away — `RunPlan.gaps`, which
    is the one thing about a run's shape that is not on its result. **Required and
    not defaulted**, on `DeclaredModels.narrative`'s terms: an entry point added
    later has to state its answer rather than inherit one, and what a default would
    say is *this run narrowed nothing*, which was silently false for the whole of
    `scripts/bench.py`'s existence and is the hole ADR-0075 closes. An empty mapping
    is the statement that nothing was narrowed, and it is said out loud.
    """
    [target_run] = result.target_runs
    state = result.run_state
    return TargetPayload(
        result=assemble(
            target_run=target_run,
            cases=cases,
            # No gate decision, and no argument that could carry one. The bench's own
            # citation reaches the provenance block below and nothing else (ADR-0018).
            episodes=reported_episodes(state.episodes, target_run.target.name),
            # κ does cross, and only κ: it is the figure ADR-0004 requires beside a
            # judged rate, it is about the adjudicator rather than about this target,
            # and the configuration is where it was already checked against the model
            # these runs adjudicate with.
            reliability=config.reliability,
            # Where the caller's checkout was, for a bench running as a step in the
            # repository that holds one. `NOT_RUN_WHERE_THE_CODE_IS` for every run
            # this route serves — a hosted bench never has a checkout, and the honest
            # reading is the default rather than an omission (ADR-0071 §3).
            source_anchor=config.source_anchor,
            # Whether each fix was proven, from the one entrypoint that could patch
            # anything. Empty on this route, always: the bench cannot restart
            # somebody else's server (ADR-0073 §2).
            standings=config.standings,
            # The plan's own gaps, passed through and not re-derived: this function
            # reads no figure out of one section and into another, and a narrowing
            # recomputed here would be a second answer to which families ran.
            not_run=gaps,
        ),
        provenance=Provenance(
            # Read off the record that authorised the run rather than off the
            # request, so a report cannot name somebody who never attested.
            attestation=target_run.registration.attestation,
            # What the endpoint did, never what the caller declared: a run started
            # with the proof waived and answered by a target that echoed anyway
            # proved control, and one that did not is said so in the document
            # (ADR-0007, as amended).
            control_proved=target_run.registration.echoed,
            models=config.models,
            library=state.library,
            # Per layer, as the record keeps them. Nothing adds these two.
            calls_spent=dict(state.spent),
            # What this run was asked to send, beside the version of the library it
            # sent it from: the two together are the condition under which a reader
            # holding two of these documents may compare them (ADR-0058). An argument
            # rather than a field on `ReportConfig`, because it is not a statement
            # about how a report is made — it is what the run did, and it reaches the
            # plan and the estimate from the same record (`BenchConfig.selection`).
            selection=selection,
            gate=config.gate,
            # What this run planted and whether the value came back, off the run's
            # own record. Empty for every endpoint target, which is what keeps the
            # verified claim on the served surface (ADR-0064 §5).
            plantings=target_run.plantings,
            # What became of anything this run planted, off the run's own record.
            # Matched by target name, so the equipment teardown a gate run performs —
            # which carries none — never reaches a target's artefact (ADR-0063 §5).
            teardown=next(
                (
                    dropped
                    for dropped in result.teardowns
                    if dropped.target_name == target_run.target.name
                ),
                None,
            ),
        ),
        rule=rule,
    )


NEVER_SIGNED_NO_KEY = (
    "this run has no signed report: the bench that ran it holds no signing key, so "
    "nothing signed the artefact and there is nothing to serve. An unsigned payload "
    "is not served in its place — a document presented as a report has been signed, "
    "or the word means two things (ADR-0017). The measurement happened and the run "
    "is on the record; what is missing is the document that travels"
)
"""What a run with no artefact says, when the reason is that nobody configured a key.

The default reason rather than a computed one, because it is the only reason a
correctly working bench ever has.
"""


@dataclass(frozen=True)
class Unsigned:
    """A run with no signed report, and the reason there is none.

    The other half of `SignedArtefact`, and a record rather than a `None`: a run
    either has an artefact or has this, so there is no state in which a reader has
    to know that one field is only meaningful while another is empty. What the route
    serves is the first; what it states by name is the second.
    """

    reason: str = NEVER_SIGNED_NO_KEY
    """Why this run has no artefact, in the words a caller is given.

    Defaulted to the one reason a correctly configured bench ever has. A refusal
    that could not say which of the two it was would send an operator looking for a
    key when what happened is that the artefact could not be assembled.
    """


def artefact_for(
    result: CalibrationResult,
    cases: Sequence[Case],
    rule: GateRule,
    config: ReportConfig,
    selection: AttackSelection,
    gaps: Mapping[Family, DeclaredGap],
) -> SignedArtefact | Unsigned:
    """The signed artefact for one completed run, or the reason there is none.

    `Unsigned` is not an error and not a failed run: the suite ran, the target was
    measured, and what this bench cannot do is produce a document that travels.
    """
    key = config.signing_key
    if key is None:
        return Unsigned()
    return signed(payload_for(result, cases, rule, config, selection, gaps), key)


VERIFY_SCRIPT = "uv run python -m scripts.verify"
"""The recipient's own check, named once so that two screens cannot name it twice.

`scripts/verify.py` is the offline verifier — three results over three files, no
network and no credential — and this is how it is invoked. Written down here rather
than in the sentences below it because it now appears in two places a person reads:
the statement saying whose check the bench's own reading is, and the command a
console prints beside the files it offers. Two literals would only have to disagree
once for a recipient to be told to run something that does not exist.
"""

VERIFY_COMMAND = f"{VERIFY_SCRIPT} path/to/the-three-files"
"""The whole command, with the directory as the placeholder it has to be.

One line and nothing but the command, because what happens to it is a selection and
a paste: a `$` in front of it is a command that fails. The argument is a directory
and never a run id — the verifier is handed the three files and is told nothing
else, which is the whole of what makes it something a recipient can run when the
sender is gone.
"""

CHECKED_BY_THE_BENCH_THAT_PRODUCED_IT = (
    "these three results were computed here, by the bench that produced the "
    "artefact, over the same bytes this run serves. That makes them a statement "
    "that the artefact is checkable and internally consistent — it is not the "
    "check a recipient makes, because a sender's word for their own document is "
    "the thing a signature exists to replace. Download the three files and run "
    f"`{VERIFY_SCRIPT}` over the directory: it reaches no network, "
    "needs no credential, and pins the key whose fingerprint this repository's "
    "README publishes"
)
"""Whose check this is, said on the artefact rather than left to be assumed.

The three results are the recipient's three, computed by the recipient's own code
(`verification.checked`) — and computed by the wrong party to be evidence. Saying so
is the difference between an interface that tells an engineer their artefact is
checkable and one that lets them believe it has been checked.
"""


def verification_of(artefact: SignedArtefact, config: ReportConfig) -> Verification:
    """The three results a recipient would get, over the bytes this bench serves.

    One definition of *verifying*, and it is `verification.checked` — the same
    function `scripts/verify.py` reaches through, over the same three byte strings.
    A second implementation for the API would be a second definition, and the two
    would only have to disagree once for a screen to report a property nobody
    checked.
    """
    return checked(
        Published(
            payload=artefact.canonical,
            rendering=artefact.rendering.encode("utf-8"),
            signature=encoded(artefact.signature),
        ),
        config.pinned if config.pinned is not None else public_key(),
        source="the payload this run signed",
    )
