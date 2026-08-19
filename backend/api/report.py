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
the route reports under its own name rather than by serving an unsigned payload.

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
from enum import StrEnum

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

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
from backend.bench.signing import SignedArtefact, signed

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
    repository that reads `AGENTAUDIT_SIGNING_KEY`, and the API layer reads no
    environment of its own (ADR-0007's cost figures are the reason the prohibition
    exists, and a second reader would be the first exception to it).

    `None` is a bench that cannot sign. Its runs complete and are measured; their
    reports are refused by name rather than served unsigned, because the word
    *signed* has to mean one thing.
    """

    models: DeclaredModels = UNDECLARED_MODELS
    """The three model identifiers this bench's runs were made under."""

    gate: GateCitation | None = None
    """The bench's own gate result, cited as provenance and never as a result.

    A fact about the instrument, supplied by the deployment that knows which run
    certified it (ADR-0018). `None` prints `UNCITED_GATE` — an uncited instrument is
    a fact about the report, and a report that omitted the line would read as one
    with nothing to declare.
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


def artefact_for(
    result: CalibrationResult,
    cases: Sequence[Case],
    rule: GateRule,
    config: ReportConfig,
) -> SignedArtefact | None:
    """The signed artefact for one completed run, or `None` on a bench with no key.

    `None` is *never signed* and is a fact the route states under its own name. It is
    not an error and not a failed run: the suite ran, the target was measured, and
    what this bench cannot do is produce a document that travels.
    """
    key = config.signing_key
    if key is None:
        return None
    return signed(payload_for(result, cases, rule, config), key)


class ReportRefusal(StrEnum):
    """Why a report is not being served, as a name rather than as a status code.

    Three members and three different facts, kept apart for the reason every other
    outcome in this bench is named: a caller that learned only *no report* would have
    to guess between a run it should poll again, a run that will never have one, and
    a run id it invented. Two of them share a status code and neither is readable
    from it.
    """

    NO_SUCH_RUN = "no_such_run"
    NOT_COMPLETED = "not_completed"
    NEVER_SIGNED = "never_signed"


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


def not_completed(status: str, statement: str) -> str:
    """What a run that has no report *yet* says, in its own current words."""
    return (
        f"this run is {status} and a report is served for a completed run only. "
        f"{statement}. Nothing partial is served in its place: half a report reads "
        "as a finished one, and the figures in it would be over attempts the run "
        "has not made"
    )
