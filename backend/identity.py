"""Who is asking, and the one place this repository reads an issuer's environment.

Two things live here and nothing else: what a deployment declared about its
identity provider — read once, and handed on as the verifier that declaration
makes — and the type the API declares so that it never has to know whose provider
it is.

[ADR-0116](../docs/adr/0116-the-identity-in-a-report-is-a-verified-claim-and-not-a-typed-string.md)
decides *why* — `Attestation.identity` is the one field in a signed report the
signature cannot speak to, and it stops being a string a caller types.
[ADR-0120](../docs/adr/0120-a-verification-is-a-subject-or-a-refusal-and-never-an-exception.md)
decides the shape of this seam, which is what the rest of this docstring is the
local consequence of.

**It is top-level and not a module of `backend/api/`, for the reason
`backend/observability.py` is.** Two tests assert that no module of the API is an
environment reader of its own (`test_api_runs.py`), because a price, a target URL
or a bearer token arriving that way is exactly what that prohibition exists to
stop. So the environment is read here, once, by a named function, and the API is
handed what it needs. ADR-0020 narrowed that rule for the signing key and did not
lift it; this is the second reader admitted on the same terms.

**A verification is a value and an unverified identity has no name on it**, both
decided in ADR-0120 and neither re-argued here. What they come to in this file:
`verify` returns `Operator | Unverified` and every `return` in it is one of the
two, so a `raise` added later is a visible departure; and `Unverified` has no
`subject` field, so narrowing the union is the only way to read a name.

**Verification is offline on the happy path.** `authenticate_request` with
`jwt_key` set checks the signature against the public key this process holds and
opens no socket (ADR-0116 §4). A `secret_key` with no `jwt_key` beside it is the
fallback for a key this process has not seen, and it *does* reach the issuer —
which is why `Issuer` keeps the two values separate rather than collapsing them
into one credential: a caller can see, before a request arrives, whether this
deployment will have to ask somebody.

**What is deliberately not here.** No route, no dependency and no decision about
an undeclared issuer: the factory declares the door and decides what an
undeclared one means (ADR-0116 §2), and this module is imported by it rather than
knowing it exists. No role, no organisation and no permission — one authenticated
principal and no tiers is the spec's scope, and a bench where some operators may
start a gate run and others may not is a different decision with its own ADR.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from clerk_backend_api.security import authenticate_request
from clerk_backend_api.security.types import (
    AuthenticateRequestOptions,
    AuthErrorReason,
    TokenVerificationErrorReason,
)

ISSUER_JWT_KEY_VARIABLE = "AGENTAUDIT_ISSUER_JWT_KEY"
"""The issuer's public key, in PEM, as the provider's dashboard prints it.

Public material, so it is the one credential in this repository that could be
committed and is not: a deployment that pinned the wrong instance's key would
verify tokens minted for somebody else's application, and which instance this is
is a property of the deployment rather than of the source.
"""

ISSUER_SECRET_KEY_VARIABLE = "AGENTAUDIT_ISSUER_SECRET_KEY"
"""The credential the fallback path presents to fetch a key this process has not
seen. Absent is the ordinary reading: with `ISSUER_JWT_KEY_VARIABLE` set, nothing
on the happy path needs it."""

BEARER = "bearer"
"""The one scheme this seam reads. A token arriving under another scheme is
refused by name rather than guessed at, because a verifier that shrugged and tried
the value anyway would accept credentials it was never handed."""


@dataclass(frozen=True)
class Issuer:
    """What a deployment declared about the identity provider it trusts.

    Two values and no behaviour. It is separate from the verifier that uses it so
    that the thing read out of the environment and the thing that checks a
    signature are two objects: a test declares the second with no environment at
    all, and `declared_issuer` is the only function in this repository that can
    produce the first.
    """

    jwt_key: str | None = None
    secret_key: str | None = None

    def __post_init__(self) -> None:
        """An issuer holding neither value is not an issuer.

        The configured absence is `None` from `declared_issuer` and never an
        `Issuer` with nothing in it — one of those would refuse every token in
        the deployment while reading, on every screen and in every log, as
        configured.
        """
        if not self.jwt_key and not self.secret_key:
            raise ValueError(
                f"an issuer declares {ISSUER_JWT_KEY_VARIABLE}, "
                f"{ISSUER_SECRET_KEY_VARIABLE}, or both. One holding neither "
                "could verify nothing, and a deployment declaring nothing is "
                "None rather than this"
            )


def declared_issuer(environment: Mapping[str, str] | None = None) -> Issuer | None:
    """The issuer the environment declares, or `None` for no authentication.

    The one function that reads the environment for identity, on
    `observability.trace_config`'s shape and for its stated reason.

    **Blank is nothing**, as it is there and in `completion.declared_model`: an
    environment variable set to the empty string is how half the tooling that sets
    one says unset, and a deployment whose variable was cleared by a redeploy has
    declared nothing rather than declared an empty key.

    **`None` is not a decision about what to do.** This function says what was
    declared; whether an undeclared issuer means an open bench or a refusal to
    boot is the factory's to decide, and ADR-0116 §2 decides it there.
    """
    values = os.environ if environment is None else environment
    jwt_key = values.get(ISSUER_JWT_KEY_VARIABLE, "").strip()
    secret_key = values.get(ISSUER_SECRET_KEY_VARIABLE, "").strip()
    if not jwt_key and not secret_key:
        return None
    return Issuer(jwt_key=jwt_key or None, secret_key=secret_key or None)


@dataclass(frozen=True)
class Operator:
    """A principal a verifier established, and the name a record may carry.

    `subject` is the identifier the issuer puts on a session — a user id or, for
    a machine credential, the id of the machine. It is deliberately not called a
    name, an email or a person: ADR-0116's cost paragraph is that verification
    moves this field from *unchecked* to *checked against one issuer* and that
    this is not identity assurance.

    **Only a verifier should be constructing one**, and the type says so by being
    the only thing in this module with a subject on it. A blank one is refused
    here rather than at the three call sites that will read it, on
    `Attestation.identity`'s reasoning: an attestation nobody signed is not a
    liability record, and a blank subject is that with extra steps.
    """

    subject: str

    def __post_init__(self) -> None:
        if not self.subject.strip():
            raise ValueError(
                "a verified operator has a subject. A token that named nobody is "
                "an Unverified and not an Operator with an empty name in it"
            )


class Unverifiable(StrEnum):
    """Why a token did not yield an operator. Five, because five consumers branch
    (ADR-0120 §3, which is also why a sixth is a change to argue rather than add).

    Each member's own docstring says what it means, since what a member means is
    a property of the member and not of the decision to have members.
    """

    ABSENT = "absent"
    """No token was presented. Not a failure of verification — nothing was
    offered to verify — and the ordinary state of a browser that has not signed
    in yet."""

    MALFORMED = "malformed"
    """Something was presented and it is not a token of a shape this issuer
    mints. Held apart from `UNTRUSTED` because it is almost always a client bug
    and almost never an attack."""

    EXPIRED = "expired"
    """Signed by the right key, and its window has passed. The one refusal that
    is a normal event in a long session."""

    UNTRUSTED = "untrusted"
    """Well-formed, and this deployment will not accept it: the signature does
    not verify against the declared key, or a claim names a party or an audience
    this deployment does not admit."""

    UNAVAILABLE = "unavailable"
    """The check could not be completed. This is not a statement about the
    caller's token, and a surface that reported it as one would tell an operator
    their credentials were rejected when the issuer was down."""


@dataclass(frozen=True)
class Unverified:
    """A refusal, carrying which one it was and a sentence saying so.

    **There is no subject on this type and there must not be one** — the whole of
    ADR-0120 §1 at the one line that could undo it. Adding a field here is how
    this seam stops working, and nothing else is.
    """

    cause: Unverifiable
    reason: str


Verification = Operator | Unverified
"""What a verifier answers with. Two types, never one type with a flag."""


@runtime_checkable
class Verifier(Protocol):
    """What the API declares, and the whole of what it knows about an issuer.

    A protocol and not an import of the concrete class (ADR-0116 §3, ADR-0120 §4),
    which is what a test relies on when it declares a stub with no account and no
    network — `runtime_checkable` so that such a stub can be asserted to satisfy
    this and not merely annotated as satisfying it.
    """

    def verify(self, authorization: str | None) -> Verification:
        """That header's token as an operator, or a refusal saying why not.

        Total: every input has an answer and none of them is an exception.
        """
        ...


_REFUSALS: Mapping[object, Unverifiable] = {
    AuthErrorReason.SESSION_TOKEN_MISSING: Unverifiable.ABSENT,
    AuthErrorReason.TOKEN_TYPE_NOT_SUPPORTED: Unverifiable.MALFORMED,
    AuthErrorReason.SECRET_KEY_MISSING: Unverifiable.UNAVAILABLE,
    TokenVerificationErrorReason.SECRET_KEY_MISSING: Unverifiable.UNAVAILABLE,
    TokenVerificationErrorReason.TOKEN_EXPIRED: Unverifiable.EXPIRED,
    TokenVerificationErrorReason.TOKEN_INVALID: Unverifiable.MALFORMED,
    TokenVerificationErrorReason.INVALID_TOKEN_TYPE: Unverifiable.MALFORMED,
    TokenVerificationErrorReason.TOKEN_INVALID_SIGNATURE: Unverifiable.UNTRUSTED,
    TokenVerificationErrorReason.TOKEN_INVALID_AUDIENCE: Unverifiable.UNTRUSTED,
    TokenVerificationErrorReason.TOKEN_INVALID_AUTHORIZED_PARTIES: (
        Unverifiable.UNTRUSTED
    ),
    TokenVerificationErrorReason.TOKEN_NOT_ACTIVE_YET: Unverifiable.UNTRUSTED,
    TokenVerificationErrorReason.TOKEN_IAT_IN_THE_FUTURE: Unverifiable.UNTRUSTED,
    TokenVerificationErrorReason.JWK_KID_MISMATCH: Unverifiable.UNTRUSTED,
    TokenVerificationErrorReason.JWK_FAILED_TO_LOAD: Unverifiable.UNAVAILABLE,
    TokenVerificationErrorReason.JWK_FAILED_TO_RESOLVE: Unverifiable.UNAVAILABLE,
    TokenVerificationErrorReason.JWK_REMOTE_INVALID: Unverifiable.UNAVAILABLE,
    TokenVerificationErrorReason.SERVER_ERROR: Unverifiable.UNAVAILABLE,
}
"""Every reason the library defines today, mapped onto the five this bench
distinguishes (ADR-0120 §3).

Written out member by member rather than defaulted, because the two enums hold
two same-named `SECRET_KEY_MISSING` members that are different objects — a table
built by name would silently drop one of them, and that one is a configuration
fault. A reason the table does not hold is still `UNAVAILABLE`, and `_refusal`
says it was not recognised: the library's set changes under us, and a verifier
that no longer understands its library should say so rather than report every
new reason as an outage.
"""


@dataclass(frozen=True)
class _Headers:
    """The one thing `authenticate_request` asks of a request: a headers mapping.

    A shim rather than the real request, because this module takes a header value
    and the library takes something request-shaped. Building the smallest object
    that satisfies its protocol keeps the framework out of here.
    """

    headers: Mapping[str, str]


@dataclass(frozen=True)
class ClerkVerifier:
    """The concrete verifier: Clerk's `authenticate_request`, offline where it can be.

    Named for the provider it speaks to, because it does speak to one and calling
    it `DefaultVerifier` would hide the single binding ADR-0116 admits to. The API
    declares `Verifier` and never this.

    The broad `except` below is ADR-0120 §2 and its cost paragraph, and it is here
    rather than anywhere else because this is the only line in the module that
    calls into the provider's library.
    """

    issuer: Issuer

    def verify(self, authorization: str | None) -> Verification:
        """Satisfies `Verifier`. See that protocol for the contract."""
        presented = _token_in(authorization)
        if isinstance(presented, Unverified):
            return presented
        try:
            state = authenticate_request(
                _Headers({"Authorization": f"Bearer {presented}"}),
                AuthenticateRequestOptions(
                    jwt_key=self.issuer.jwt_key, secret_key=self.issuer.secret_key
                ),
            )
        except Exception as unexpected:  # noqa: BLE001 — see the class docstring
            return Unverified(
                cause=Unverifiable.UNAVAILABLE,
                reason=(
                    "the token could not be checked against the issuer this "
                    f"deployment declared: {unexpected}. This says nothing about "
                    "the token that was presented"
                ),
            )
        if not state.is_signed_in:
            return _refusal(state.reason, state.message)
        subject = str((state.payload or {}).get("sub", "")).strip()
        if not subject:
            return Unverified(
                cause=Unverifiable.MALFORMED,
                reason=(
                    "the token verified and names no subject. A signature over a "
                    "token with no `sub` is a valid signature over nobody, and "
                    "there is nothing here to record against a run"
                ),
            )
        return Operator(subject=subject)


def _token_in(authorization: str | None) -> str | Unverified:
    """The bearer token in that header value, or the refusal it earns.

    Parsed here rather than left to the library because the library reads an
    empty bearer as a token and refuses it as malformed. A header saying `Bearer`
    and nothing else is a client that has no token, which is `ABSENT` — the
    difference matters to a console deciding whether to show a sign-in or an
    error.
    """
    presented = (authorization or "").strip()
    if not presented:
        return Unverified(
            cause=Unverifiable.ABSENT,
            reason=(
                "no token was presented. Every route on this surface is reached "
                "by an authenticated operator, and the Authorization header "
                "carries who that is"
            ),
        )
    scheme, _, token = presented.partition(" ")
    if scheme.lower() != BEARER:
        return Unverified(
            cause=Unverifiable.MALFORMED,
            reason=(
                f"the Authorization header presented a {scheme!r} credential and "
                "this surface reads a Bearer token"
            ),
        )
    if not token.strip():
        return Unverified(
            cause=Unverifiable.ABSENT,
            reason=(
                "the Authorization header carried the Bearer scheme and no token "
                "after it"
            ),
        )
    return token.strip()


def _refusal(reason: object | None, message: str | None) -> Unverified:
    """The library's reason as one of this bench's five, with its sentence kept.

    The provider's own wording travels through rather than being replaced: it is
    the more specific statement, and a refusal that discarded it would leave an
    operator with a category and no detail.
    """
    cause = _REFUSALS.get(reason, Unverifiable.UNAVAILABLE)
    recognised = reason in _REFUSALS
    said = message or (str(reason) if reason is not None else "no reason given")
    return Unverified(
        cause=cause,
        reason=(
            said
            if recognised
            else (
                f"the token was refused for a reason this bench does not "
                f"recognise ({reason!r}): {said}"
            )
        ),
    )


def declared_verifier(environment: Mapping[str, str] | None = None) -> Verifier | None:
    """The verifier this deployment's declaration makes, or `None` for none declared.

    `declared_issuer` says what a deployment declared and this says what it would
    verify with. Two functions rather than one, because this is the only place the
    concrete implementation is named: `backend/api/` imports this and the protocol
    and never `ClerkVerifier`, which is what keeps ADR-0116 §3's reversibility real
    at the boundary that matters.

    **Still not a decision about what to do with `None`.** Whether an undeclared
    issuer is an open bench or a refusal to boot is the factory's, and `create_app`
    is where ADR-0116 §2 decides it.
    """
    issuer = declared_issuer(environment)
    return None if issuer is None else ClerkVerifier(issuer)
