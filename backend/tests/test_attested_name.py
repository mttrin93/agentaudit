"""What a name in a signed report is worth, per surface that can write one.

The sentences themselves are asserted here rather than in `test_payload.py`, because
they are a property of the attested name and not of the serialiser: the document prints
`stated()` and nothing else, so a wording that stopped ruling something out would
travel through every artefact this bench signs (ADR-0123).
"""

from __future__ import annotations

import pytest

from backend.bench.attested_name import (
    NO_NAME,
    NOT_ESTABLISHED,
    AttestedName,
    NameGiven,
    VerifiedSubject,
    WorkflowActor,
)

EVERY_ATTESTED_NAME: tuple[AttestedName, ...] = (
    VerifiedSubject(name="user_2abc"),
    WorkflowActor(name="ada"),
    NameGiven(name="Ada Lovelace"),
)
"""One of each, named differently so that a sentence cannot be matched by accident."""


@pytest.mark.parametrize("attested", EVERY_ATTESTED_NAME)
def test_every_attested_name_names_the_party_and_rules_out_the_same_three_readings(
    attested: AttestedName,
) -> None:
    """Including the verified one. ADR-0116's cost paragraph, in the document.

    Verification moves this field from *unchecked* to *checked against one issuer*,
    which is a real improvement and is not identity assurance — so the strongest
    reading this bench can print still says it is not a legal person, not an employer
    and not a claim of organisational authorisation.
    """
    stated = attested.stated()

    assert attested.name in stated
    assert NOT_ESTABLISHED in stated
    for reading in ("legal person", "employer", "authorised by their organisation"):
        assert reading in stated


def test_a_verified_subject_names_the_issuer_as_the_thing_that_verified() -> None:
    """What established the name, and by whose signature.

    The issuer is named as *the issuer this deployment declares* rather than as a
    provider's brand: which issuer this deployment trusts is a property of the
    deployment, and a document that printed a vendor's name would be making a claim
    about the bench's build rather than about the run (ADR-0116 §3).
    """
    stated = VerifiedSubject(name="user_2abc").stated()

    assert "verified session at the issuer this deployment declares" in stated
    assert "a token that issuer signed, naming this subject" in stated


def test_a_workflow_actor_says_the_runner_checked_it_and_no_issuer_here_did() -> None:
    """The Action's name, which is checked, and checked by somebody else.

    `unattended.py` has called this an authenticated identity since ADR-0066 and the
    document could not say so. It may not say the issuer verified it: nothing this
    deployment declares has heard of a workflow actor.
    """
    stated = WorkflowActor(name="ada").stated()

    assert "authenticated by the runner that ran it" in stated
    assert "no issuer this deployment declares" in stated


def test_a_name_given_says_that_nothing_checked_it() -> None:
    """The terminal path and the bench that declared no door.

    The sentence is the one that makes `NOBODY_VERIFIED`'s string unmistakable: a
    reader who took *an operator this bench did not verify* for an unusual username
    reads, in the same field, that no issuer was asked (ADR-0122, ADR-0123).
    """
    stated = NameGiven(name="an operator this bench did not verify").stated()

    assert "a name nothing verified" in stated
    assert "No issuer was asked and no token was checked" in stated
    assert "who was named and not who was there" in stated


@pytest.mark.parametrize("attested", EVERY_ATTESTED_NAME)
def test_no_attested_name_can_be_read_as_another(attested: AttestedName) -> None:
    """Three sentences, and no two of them say the same thing about the checking.

    The whole point of three types rather than one string: a reader can tell which
    surface wrote the field, and a surface cannot borrow another's evidence.
    """
    others = [one for one in EVERY_ATTESTED_NAME if one is not attested]
    claim = attested.stated().removeprefix(f"{attested.name} — ")

    for one in others:
        assert claim not in one.stated()


@pytest.mark.parametrize("blank", ["", "   ", "\n"])
@pytest.mark.parametrize("of", [VerifiedSubject, WorkflowActor, NameGiven])
def test_no_attested_name_can_be_made_over_a_blank(
    of: type[AttestedName], blank: str
) -> None:
    """An attestation nobody signed is not a liability record, per type.

    Refused here rather than at the record, because this is where the name arrives:
    a type that accepted a blank would put a document's one sentence about a person
    after an em dash with nothing in front of it.
    """
    with pytest.raises(ValueError) as refusal:
        of(blank)

    assert NO_NAME in str(refusal.value)
