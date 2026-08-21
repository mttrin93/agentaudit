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

from collections.abc import Sequence
from dataclasses import dataclass

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from backend.bench.assembler import assemble, reported_episodes
from backend.bench.calibration import CalibrationResult
from backend.bench.library import Case
from backend.bench.payload import (
    DeclaredModels,
    GateCitation,
    Provenance,
    TargetPayload,
)
from backend.bench.rule import GateRule
from backend.bench.signing import SignedArtefact, encoded, public_key, signed
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
)
"""The three identifiers of a bench that declared none of them."""


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
) -> TargetPayload:
    """The unsigned, unbound payload for one completed run.

    Every figure comes from the run and every field beside them comes from the
    configuration: there is no line here that computes anything, which is the
    structural form of *no composite score* (ADR-0005). The provenance block is the
    only place the two meet, and not one of its fields is a measurement of the
    target.
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
        ),
        provenance=Provenance(
            # Read off the record that authorised the run rather than off the
            # request, so a report cannot name somebody who never attested.
            attestation=target_run.registration.attestation,
            models=config.models,
            library=state.library,
            # Per layer, as the record keeps them. Nothing adds these two.
            calls_spent=dict(state.spent),
            gate=config.gate,
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
) -> SignedArtefact | Unsigned:
    """The signed artefact for one completed run, or the reason there is none.

    `Unsigned` is not an error and not a failed run: the suite ran, the target was
    measured, and what this bench cannot do is produce a document that travels.
    """
    key = config.signing_key
    if key is None:
        return Unsigned()
    return signed(payload_for(result, cases, rule, config), key)


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
