"""The verifier seam: what the environment declares, and what a token is worth.

The module under test is the only reader of the issuer's environment in this
repository and the only statement of what a verified operator is. These tests
reach it at two seams and nowhere else: `declared_issuer`, and `verify` on a
`Verifier`.

**Every token here is minted in this file.** The keys are generated per module,
the tokens are signed locally, and no test holds an account at any issuer — which
is the property the protocol exists to buy (ADR-0120).
"""

from __future__ import annotations

import socket
import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from backend.identity import (
    ISSUER_JWT_KEY_VARIABLE,
    ISSUER_SECRET_KEY_VARIABLE,
    ClerkVerifier,
    Issuer,
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
