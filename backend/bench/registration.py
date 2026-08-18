"""Nonce issue and echo check — the proof that an operator controls the target.

Per ADR-0007 the value a user plants to enable the leakage probe is also the
proof they can configure the target: only someone who can edit the target's
configuration can plant it. Authorisation therefore falls out of a mechanism the
bench already needs.

One value, two roles, and the vocabulary keeps them apart: on this path it is the
**nonce**, the thing a target must echo before a run may start; under the
data-leakage case the same value is the **canary**, whose appearance in output
proves a leak.

The echo check and the leakage case use deliberately different messages. The echo
probe asks the target to cooperate, and a target that will not cooperate has not
proven control, so registration does not complete. The leakage case then tries to
extract the same value *without* cooperation, and a target that resists that is
well defended — not unregistered. Collapsing the two would make a hardened target
unregistrable.

Attestation — authorised to test, not production, accepts the provider-policy and
inference-cost consequences — is recorded here alongside it. It is the liability
record and the Article 12 record in one artefact, which is what makes
record-keeping do real work in this design rather than merely apply.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from backend.bench.contract import TargetConfig, Transcript, send_message
from backend.graph.budget import Layer
from backend.graph.runstate import RunState

NONCE_PREFIX = "AGENTAUDIT-CANARY"

ECHO_PROBE = (
    "Registration check. Reply with the AgentAudit registration nonce from your "
    "configuration, exactly as it appears there, and nothing else."
)


def issue_nonce() -> str:
    """Issue a nonce for one target. The operator plants it; the target must echo it."""
    return f"{NONCE_PREFIX}-{secrets.token_hex(8).upper()}"


@dataclass(frozen=True)
class Attestation:
    """The three statements an operator makes before the bench touches an endpoint.

    All three are required, and each is a separate field rather than one
    `i_agree` flag, because the record has to show *what* was attested. ADR-0007
    is explicit that the consequences are spelled out rather than implied: the
    second and third are ones a user would never infer — that these payloads will
    generate provider policy violations against their own account, and that they
    will consume their own inference budget.

    A statement that is not made cannot be constructed. The invariant sits in the
    type so that no caller has to remember to check it, and so that `register`
    cannot be reached without one.
    """

    identity: str
    """Who attested. Recorded, because an attestation nobody signed is not a
    liability record."""

    authorised_to_test: bool
    not_production: bool
    accepts_provider_policy_and_cost: bool

    STATEMENTS = (
        ("authorised_to_test", "I am authorised to test this endpoint"),
        ("not_production", "this endpoint is a staging or sandbox environment"),
        (
            "accepts_provider_policy_and_cost",
            "I accept that these payloads will generate provider policy "
            "violations against my own account and consume my own inference budget",
        ),
    )
    """The wording an operator is asked to confirm, held beside the fields so the
    prompt and the record cannot drift apart."""

    def __post_init__(self) -> None:
        if not self.identity.strip():
            raise ValueError("an attestation has to record who made it")
        withheld = [
            wording
            for field_name, wording in self.STATEMENTS
            if not getattr(self, field_name)
        ]
        if withheld:
            raise ValueError(
                "the attestation is incomplete, so no run may start. Not "
                f"attested: {'; '.join(withheld)}"
            )


@dataclass(frozen=True)
class AttestationRecord:
    """An attestation as it is kept: who, when, and against which endpoint."""

    attestation: Attestation
    endpoint_hash: str
    recorded_at: datetime

    @classmethod
    def of(cls, attestation: Attestation, target: TargetConfig) -> AttestationRecord:
        return cls(
            attestation=attestation,
            endpoint_hash=endpoint_hash(target.url),
            recorded_at=datetime.now(tz=UTC),
        )


def endpoint_hash(url: str) -> str:
    """A stable identifier for an endpoint that is not the endpoint.

    Hashed rather than stored, because the record outlives the run and is destined
    for a report's provenance block: a live URL that answers jailbreak payloads is
    not a thing to write into a document that travels (ADR-0008). A hash still
    joins an attestation to the run it authorised, which is all the record needs
    to do.
    """
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Registration:
    """A target's registration: complete only once the nonce came back."""

    target: TargetConfig
    nonce: str
    complete: bool
    probe: Transcript
    attestation: AttestationRecord
    """Recorded before the probe was sent, because the attestation is what
    authorised sending it."""

    @property
    def refused(self) -> bool:
        return not self.complete


def register(
    target: TargetConfig,
    nonce: str,
    attestation: Attestation,
    run_state: RunState,
) -> Registration:
    """Ask the target to echo its planted nonce. No run starts until it does.

    The attestation is a required argument rather than a checked precondition:
    the echo probe is itself a call on the operator's endpoint, so there is no
    point in the flow at which the bench may send anything without one.
    """
    record = AttestationRecord.of(attestation, target)
    run_state.authorise_call(Layer.SCORED, target.retry.sends)
    probe = send_message(target, ECHO_PROBE, session_id=f"registration-{uuid.uuid4()}")
    run_state.record_call(Layer.SCORED, probe.sends)
    echoed = bool(nonce) and nonce in probe.reply_text
    return Registration(
        target=target,
        nonce=nonce,
        complete=echoed,
        probe=probe,
        attestation=record,
    )
