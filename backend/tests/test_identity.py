"""The verifier seam: what the environment declares, and what a token is worth.

The module under test is the only reader of the issuer's environment in this
repository and the only statement of what a verified operator is. These tests
reach it at two seams and nowhere else: `declared_issuer`, and `verify` on a
`Verifier`.

**Every token here is minted in this file.** The keys are generated per module,
the tokens are signed locally, and no test holds an account at any issuer — which
is the property the protocol exists to buy (ADR-0120).

**The machine credential is the one thing that cannot be minted.** It is not a
signed document: it is an opaque secret the issuer holds a record of, and the only
way to a verified one is an account and a network call. So what is asserted here
is everything either side of that call — that a machine credential is refused by
name where this deployment declared nothing to check it with, that it reaches the
network where a session token does not, and that a verified answer becomes a
`Machine` and not an `Operator`, with the provider's own `RequestState` standing in
for the one call nothing in this suite may make (ADR-0124).
"""

from __future__ import annotations

import socket
import time
from typing import Any

import jwt
import pytest
from clerk_backend_api.security.types import AuthStatus, RequestState
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from backend.identity import (
    ISSUER_JWT_KEY_VARIABLE,
    ISSUER_SECRET_KEY_VARIABLE,
    MACHINE_NEEDS_SECRET_KEY,
    NOT_A_CALLER_THIS_BENCH_ADMITS,
    ClerkVerifier,
    Issuer,
    Machine,
    Operator,
    Unverifiable,
    Unverified,
    Verification,
    Verifier,
    declared_issuer,
)


def _pair() -> tuple[str, str]:
    """A throwaway RSA pair, as PEM: the private half to mint with, the public
    half to hand a verifier as the key it trusts."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public = (
        key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private, public


PRIVATE, PUBLIC = _pair()
OTHER_PRIVATE, _OTHER_PUBLIC = _pair()


def _token(private: str = PRIVATE, **claims: Any) -> str:
    """A session token of the shape the issuer mints, signed with `private`."""
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": "user_2abcDEF",
        "sid": "sess_1",
        "iat": now,
        "nbf": now,
        "exp": now + 600,
    }
    payload.update(claims)
    return jwt.encode(payload, private, algorithm="RS256")


MACHINE_CREDENTIAL = "m2m_aCredentialNoIssuerHereHasEverIssued"
"""A credential of the shape the issuer mints for a machine, and of no other worth.

The prefix is the whole of what the library reads before it decides to ask the
issuer, which is why a string is enough to assert the routing: nothing in this file
gets as far as an answer without standing one in.
"""


def _verifier() -> ClerkVerifier:
    return ClerkVerifier(Issuer(jwt_key=PUBLIC))


def test_the_declared_issuer_is_the_material_the_environment_holds() -> None:
    """Both values, read from the mapping handed in and from nowhere else.

    The PEM arrives with the newline every file and every dashboard puts on the
    end of it, and it is the surrounding whitespace that comes off — never the
    newlines inside, which are what makes it a PEM.
    """
    declared = declared_issuer(
        {
            ISSUER_JWT_KEY_VARIABLE: PUBLIC + "\n",
            ISSUER_SECRET_KEY_VARIABLE: " sk_test_nothing ",
        }
    )

    assert declared == Issuer(jwt_key=PUBLIC.strip(), secret_key="sk_test_nothing")
    assert declared is not None
    assert declared.jwt_key is not None and "\n" in declared.jwt_key


def test_an_environment_that_declares_no_issuer_declares_nothing() -> None:
    """Absent is nothing, and so is blank.

    The empty string is how half the tooling that sets an environment variable
    says unset, which `observability.trace_config` already treats as absent.
    """
    assert declared_issuer({}) is None
    assert (
        declared_issuer({ISSUER_JWT_KEY_VARIABLE: "  ", ISSUER_SECRET_KEY_VARIABLE: ""})
        is None
    )


def test_a_secret_key_alone_is_still_a_declared_issuer() -> None:
    """The networked fallback for a key this process has not seen (ADR-0116 §4).

    Declared, and declared as what it is: no `jwt_key`, so the caller can see
    that verification will have to ask the issuer.
    """
    declared = declared_issuer({ISSUER_SECRET_KEY_VARIABLE: "sk_test_nothing"})

    assert declared == Issuer(secret_key="sk_test_nothing")
    assert declared is not None and declared.jwt_key is None


def test_an_issuer_holding_neither_value_cannot_be_constructed() -> None:
    """The absence is `None` from the reader, never an `Issuer` with nothing in it.

    A verifier built on one could refuse every token in the deployment and look
    configured while doing it.
    """
    with pytest.raises(ValueError):
        Issuer()


def test_a_valid_token_yields_its_subject() -> None:
    verified = _verifier().verify(f"Bearer {_token(sub='user_2abcDEF')}")

    assert isinstance(verified, Operator)
    assert verified.subject == "user_2abcDEF"


def test_an_absent_token_is_refused_as_absent() -> None:
    """No header at all, and a header holding nothing, are the same refusal."""
    for authorization in (None, "", "Bearer "):
        refused = _verifier().verify(authorization)

        assert isinstance(refused, Unverified)
        assert refused.cause is Unverifiable.ABSENT
        assert "no token" in refused.reason


def test_a_malformed_token_is_refused_as_malformed() -> None:
    refused = _verifier().verify("Bearer not.a.token")

    assert isinstance(refused, Unverified)
    assert refused.cause is Unverifiable.MALFORMED


def test_a_token_signed_by_another_key_is_refused_as_untrusted() -> None:
    """The one a forger reaches for: well-formed, unexpired, wrong signature."""
    refused = _verifier().verify(f"Bearer {_token(OTHER_PRIVATE)}")

    assert isinstance(refused, Unverified)
    assert refused.cause is Unverifiable.UNTRUSTED


def test_an_expired_token_is_refused_as_expired_and_not_as_untrusted() -> None:
    """Its own cause, because the console has to tell an expiry from a forgery:
    one is a session to renew and the other is somebody at the door."""
    now = int(time.time())
    refused = _verifier().verify(f"Bearer {_token(iat=now - 7200, exp=now - 3600)}")

    assert isinstance(refused, Unverified)
    assert refused.cause is Unverifiable.EXPIRED


def test_a_token_naming_no_subject_is_refused_rather_than_verified_as_blank() -> None:
    """A signature over a token with no `sub` is a valid signature over nothing
    nameable. The refusal is the answer; an `Operator("")` is not."""
    refused = _verifier().verify(f"Bearer {_token(sub='')}")

    assert isinstance(refused, Unverified)
    assert refused.cause is Unverifiable.MALFORMED


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every socket in this process refuses to connect for the duration.

    A failed connection rather than a recorded one, so a test that depends on
    reaching an issuer fails here instead of depending on whether the machine
    running the suite happens to have a route to one.
    """

    def refuse(self: socket.socket, address: Any) -> None:
        raise OSError(f"this test opened no network, and something reached {address!r}")

    monkeypatch.setattr(socket.socket, "connect", refuse)


def test_a_verifier_that_cannot_reach_its_key_refuses_rather_than_raising(
    no_network: None,
) -> None:
    """An issuer declaring only a secret key, with no route to the issuer.

    The refusal is a value on `cause` and the exception does not leave the
    module: a verifier that raised would turn an issuer outage into a stack
    trace on a route that a console is polling mid-run (ADR-0120).
    """
    refused = ClerkVerifier(Issuer(secret_key="sk_test_nothing")).verify(
        "Bearer " + _token()
    )

    assert isinstance(refused, Unverified)
    assert refused.cause is Unverifiable.UNAVAILABLE


def test_verification_of_a_valid_token_reaches_no_network(
    no_network: None,
) -> None:
    """Asserted rather than assumed, because the console polls a run every two
    seconds and an issuer on that path would read as the bench failing.

    The fixture makes a connection an error, so a networked key fetch fails the
    test where a networked one that happened to succeed would not.
    """
    verified = _verifier().verify(f"Bearer {_token()}")

    assert isinstance(verified, Operator)


def test_a_machine_credential_is_refused_where_only_a_public_key_is_declared(
    no_network: None,
) -> None:
    """The deployment's own gap, named as the deployment's and not the caller's.

    A public key verifies a signed document and a machine credential is not one, so
    a bench declaring only `AGENTAUDIT_ISSUER_JWT_KEY` has nothing to check this
    with. Reported as `UNAVAILABLE` and refused before the library is reached: left
    to the provider it would be posted to the issuer under an empty bearer, come
    back as a token that did not verify, and tell an operator whose credential is
    perfectly good that their credential is bad (ADR-0124).
    """
    refused = _verifier().verify(f"Bearer {MACHINE_CREDENTIAL}")

    assert isinstance(refused, Unverified)
    assert refused.cause is Unverifiable.UNAVAILABLE
    assert refused.reason == MACHINE_NEEDS_SECRET_KEY
    assert ISSUER_SECRET_KEY_VARIABLE in refused.reason


def test_a_machine_credential_reaches_the_issuer_where_a_session_token_does_not(
    no_network: None,
) -> None:
    """The cost of ADR-0124, asserted rather than written down and hoped for.

    One verifier, one fixture, two credentials. The session token verifies with no
    socket opened, which is ADR-0116 §4's whole claim; the machine credential fails
    *because* a socket was refused, which is the offline argument not applying to
    it. If this test ever passes with both as an `Operator`, the provider has
    started verifying machine credentials locally and the module docstring is owed
    a correction.
    """
    verifier = ClerkVerifier(Issuer(jwt_key=PUBLIC, secret_key="sk_test_nothing"))

    assert isinstance(verifier.verify(f"Bearer {_token()}"), Operator)

    refused = verifier.verify(f"Bearer {MACHINE_CREDENTIAL}")

    assert isinstance(refused, Unverified)
    assert refused.cause is Unverifiable.UNAVAILABLE
    # And it got as far as the issuer to earn that: the refusal above is the one a
    # deployment that declared nothing to check with earns, and this deployment
    # declared one. A short circuit that stopped every machine credential here would
    # pass the cause assertion while never reaching a network at all.
    assert refused.reason != MACHINE_NEEDS_SECRET_KEY


def _answering(payload: dict[str, Any]) -> Any:
    """The issuer's verification endpoint, answering yes with that record.

    The one stand-in in this file, and it stands in for a network call rather than
    for any code of this repository's: `RequestState` is the provider's own type and
    what is under test is which key of its payload a machine's name is read from. A
    verified machine credential cannot be minted — it is an opaque secret and the
    issuer is the only thing that can say it is current — so the alternative to this
    is a test that only runs for somebody holding an account.
    """

    def answer(request: object, options: object) -> RequestState:
        return RequestState(
            status=AuthStatus.SIGNED_IN, token=MACHINE_CREDENTIAL, payload=payload
        )

    return answer


def test_a_verified_machine_credential_is_a_machine_and_never_an_operator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The subject comes off `subject`, and what comes back is the other type.

    Two facts in one test because they are one behaviour: the issuer answers about a
    machine credential with the credential's record, whose principal is `subject` and
    not the `sub` a JWT carries, and reading the wrong key would yield a refusal
    saying the credential named nobody. `Machine` rather than `Operator` is what
    keeps `attributed_to` able to tell a program from a person.
    """
    monkeypatch.setattr(
        "backend.identity.authenticate_request",
        _answering({"subject": "mch_2xyz", "claims": {}}),
    )

    verified = ClerkVerifier(Issuer(secret_key="sk_test_nothing")).verify(
        f"Bearer {MACHINE_CREDENTIAL}"
    )

    assert verified == Machine(subject="mch_2xyz")
    assert not isinstance(verified, Operator)


def test_a_machine_credential_naming_no_subject_is_refused_rather_than_verified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`Operator`'s rule, for the second type: a blank name is a refusal.

    The `sub` key is deliberately present and populated, because a reader that had
    fallen back to it would pass this test while recording a machine under a key the
    issuer does not use for one.
    """
    monkeypatch.setattr(
        "backend.identity.authenticate_request",
        _answering({"subject": "", "sub": "user_2abcDEF"}),
    )

    refused = ClerkVerifier(Issuer(secret_key="sk_test_nothing")).verify(
        f"Bearer {MACHINE_CREDENTIAL}"
    )

    assert isinstance(refused, Unverified)
    assert refused.cause is Unverifiable.MALFORMED


@pytest.mark.parametrize(
    "credential",
    ["oat_anOauthAccessTokenAPersonAuthorised", "ak_aUserScopedApiKey"],
)
def test_a_credential_the_issuer_reads_as_a_person_is_refused_and_not_named_a_machine(
    no_network: None, credential: str
) -> None:
    """The two prefixes that go to the same endpoint and come back naming somebody.

    `is_machine_token` is true of four prefixes and only two of them are machines:
    the issuer answers about an OAuth access token and about a user API key with a
    `subject` that is a person's id. Admitted as a `Machine`, either would be printed
    under the one sentence in the artefact that says *no person was present* — false,
    and false in the direction ADR-0123 forbids. So this bench admits the two kinds of
    caller it has and refuses the rest by name (ADR-0124 decision 6).

    `no_network` because the refusal is earned before the issuer is asked: a bench
    that posted these and read the answer would be deciding, after the fact, what to
    call a principal it had already accepted.
    """
    refused = ClerkVerifier(Issuer(secret_key="sk_test_nothing")).verify(
        f"Bearer {credential}"
    )

    assert isinstance(refused, Unverified)
    assert refused.cause is Unverifiable.UNTRUSTED
    assert refused.reason == NOT_A_CALLER_THIS_BENCH_ADMITS


def test_a_verified_machine_is_never_blank() -> None:
    with pytest.raises(ValueError):
        Machine(subject="   ")


def test_a_refusal_has_no_subject_to_read() -> None:
    """The invariant is the type's, not a caller's discipline: there is no
    attribute on the refusal a name could be read off, so a call site that
    forgot to narrow does not compile."""
    refused = _verifier().verify(None)

    assert not hasattr(refused, "subject")


def test_a_verified_operator_is_never_blank() -> None:
    with pytest.raises(ValueError):
        Operator(subject="   ")


def test_a_stub_with_no_account_and_no_network_is_a_verifier() -> None:
    """What every later task's tests declare. If this stops being enough, the
    seam has grown a dependency on the issuer and the ticket after it pays."""

    class Stub:
        def verify(self, authorization: str | None) -> Verification:
            return Operator(subject="operator@example.test")

    stub: Verifier = Stub()

    assert isinstance(stub, Verifier)
    assert stub.verify(None) == Operator(subject="operator@example.test")
