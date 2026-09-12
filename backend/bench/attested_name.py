"""Where a name in a signed report came from, and what that is worth.

One field of the artefact names a *person*: `identity`, in the provenance block's
attestation. Three surfaces write it — the API behind a door, the Action in a
caller's own repository, and a terminal — and until this module existed they wrote
the same `str`, so a recipient holding two reports could not tell a verified subject
from a name somebody typed.

[ADR-0123](../../docs/adr/0123-the-identity-in-the-payload-states-what-established-it.md)
decides that the field says what established it and what that does not amount to,
that the sentence travels **in the field's own value** rather than in a key beside
it, and why the three alternatives lost. None of that is re-argued here.

What this module is, locally: three types, one per surface that can name somebody,
each holding the name it was given and each able to state what it is. They are the
only things `Attestation` accepts, so a record cannot be constructed without one —
which is what keeps *this name was verified* a thing a verifier produced rather than
a flag a caller set. `NameGiven` cannot pretend to be `VerifiedSubject`, and nothing
here can be read as verified by accident: `stated()` is the only way out and every
one of the three says, in its own words, what was and was not checked.

**Every sentence ends in the same three refusals** (`NOT_ESTABLISHED`), including the
verified one. ADR-0116's cost paragraph is that verification moves this field from
*unchecked* to *checked against one issuer*, which is a real improvement and is not
identity assurance — so the strongest reading this bench can print still says what it
is not. PLAN.md D4 applies to the bench's own scores first, and this is the field
where the bench is scoring itself.
"""

from __future__ import annotations

from dataclasses import dataclass

NO_NAME = "an attestation has to record who made it"
"""The refusal every attested name makes on a blank.

One wording, held here rather than at the three types, because it is one rule: a
record nobody signed is not a liability record (`registration.Attestation`), and the
console asserts this exact sentence back (`frontend/src/register/declarations.test.ts`).
"""

NOT_ESTABLISHED = (
    "It is not a legal person, not an employer, and not a claim that the named "
    "party was authorised by their organisation to attest anything."
)
"""The three things no surface here establishes, printed after every one of them.

Three and not one, because they are the three readings a procurement reader takes off
a name in a document that travels, and the strongest of the three readings rules
out none of them. Shared rather than repeated so that a wording that changes changes
for every surface at once — a document where one surface dropped a refusal would be
the same defect ADR-0116 was written about, one layer down.
"""


@dataclass(frozen=True)
class VerifiedSubject:
    """A name off a token the issuer this deployment declares put its signature on.

    The strongest of the three readings here, and the sentence still says what it is
    not. `subject` is what `identity.Operator` carries: the identifier an issuer puts
    on a session, which for a machine credential is the machine's.

    Constructed at one place — the route that turns a request into a record, from the
    operator the door admitted — because that is the only place a verification
    happened. A caller that constructs one by hand is writing a claim the signature
    cannot speak to, which is the defect ADR-0116 records.
    """

    subject: str

    def __post_init__(self) -> None:
        if not self.subject.strip():
            raise ValueError(NO_NAME)

    @property
    def name(self) -> str:
        """What the record carries where a name goes."""
        return self.subject

    def stated(self) -> str:
        """The name and what verification established, as the document prints it."""
        return (
            f"{self.subject} — the subject of a verified session at the issuer this "
            "deployment declares. That is the whole of what verification "
            "established: a token that issuer signed, naming this subject. "
            f"{NOT_ESTABLISHED}"
        )


@dataclass(frozen=True)
class WorkflowActor:
    """The actor a workflow run was started as — `github.actor` (ADR-0066).

    Held apart from `VerifiedSubject` because a different party did the checking:
    the runner authenticated this actor, and the issuer this deployment declares has
    never heard of them. Folding the two together would print one issuer's name over
    the other's evidence, and folding this into `NameGiven` would understate a check
    that really happened — `unattended.py` has called this "an authenticated identity
    rather than a name typed at a prompt" since ADR-0066, and this is where a reader
    of the document finally sees which of the two they are holding.
    """

    actor: str

    def __post_init__(self) -> None:
        if not self.actor.strip():
            raise ValueError(NO_NAME)

    @property
    def name(self) -> str:
        """What the record carries where a name goes."""
        return self.actor

    def stated(self) -> str:
        """The name and what verification established, as the document prints it."""
        return (
            f"{self.actor} — the actor a workflow run was started as, authenticated "
            "by the runner that ran it and by no issuer this deployment declares. "
            "What that established is which account the workflow ran under. "
            f"{NOT_ESTABLISHED}"
        )


@dataclass(frozen=True)
class NameGiven:
    """A name nothing checked: typed at a terminal, or recorded by a bench with no door.

    The two surfaces are one reading because the fact is one fact — nobody
    verified this — and the name itself is what separates them for a reader: a
    terminal run carries whatever the operator typed, and a bench that declared
    `NO_DOOR` carries the sentence `api.app.NOBODY_VERIFIED` holds, which names
    nobody at all (ADR-0122).

    It is the weakest of the three and it is deliberately the one a caller reaches by
    default: the failure this module exists to prevent is a document claiming more
    than was checked, so the reading that claims least is the one that costs nothing
    to choose.
    """

    given: str

    def __post_init__(self) -> None:
        if not self.given.strip():
            raise ValueError(NO_NAME)

    @property
    def name(self) -> str:
        """What the record carries where a name goes."""
        return self.given

    def stated(self) -> str:
        """The name and what verification established, as the document prints it."""
        return (
            f"{self.given} — a name nothing verified. No issuer was asked and no "
            "token was checked, so this field records who was named and not who was "
            f"there. {NOT_ESTABLISHED}"
        )


AttestedName = VerifiedSubject | WorkflowActor | NameGiven
"""What may name somebody in an attestation. Three types, never one type with a flag.

`identity.Verification`'s shape, one layer out and for its reason: a boolean beside a
string can be set by anybody, and a union can only be narrowed. The document's
sentence is `stated()` on whichever of the three was constructed, so there is no path
from a name to a claim about it that does not go through choosing one.
"""
