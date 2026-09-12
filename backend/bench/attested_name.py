"""Where a name in a signed report came from, and what that is worth.

One field of the artefact names a *party*: `identity`, in the provenance block's
attestation. Three surfaces write it — the API behind a door, the Action in a
caller's own repository, and a terminal — and until this module existed they wrote
the same `str`, so a recipient holding two reports could not tell a verified subject
from a name somebody typed.

[ADR-0123](../../docs/adr/0123-the-identity-in-the-payload-states-what-established-it.md)
decides that the field says what established it and what that does not amount to,
that the sentence travels in the field's own value rather than in a key beside it,
and why the three alternatives lost. None of that is re-argued here.

What this module is, locally: four types, one per *reading* a surface may make.
Four rather than three because the API's door admits two kinds of caller and what it
established about them differs — a person at a session, and a machine at a credential
(ADR-0124). They are the only things `Attestation` accepts, so a name cannot reach
the artefact without one of them having been chosen where the name arrived.
`stated()` is the only way a name gets out, and each of the four composes its own
middle clause — so a surface cannot borrow another's evidence, and nothing reads as
verified by accident.

**One shape, so that the parts that must not differ cannot.** The blank refusal, the
`name — claim. refusals` shape and the closing sentence are on the base and are
written once; what a subclass supplies is the one clause that is genuinely its own.
A further surface is then a `_claim` and a docstring, and the thing it cannot do by
forgetting is drop the limits (ADR-0123 §4). `VerifiedMachine` is the first one added
on those terms
([ADR-0124](../../docs/adr/0124-a-machine-credential-is-verified-at-the-issuer-and-named-as-a-machine.md)),
and adding it cost a `_claim`, a docstring and a name on the union below.
"""

from __future__ import annotations

from dataclasses import dataclass

NO_NAME = "an attestation has to record who made it"
"""The refusal a blank name earns, in the wording `Attestation` used to raise itself.

Unchanged on purpose: the console asserts this exact sentence back
(`frontend/src/register/declarations.test.ts`), and the rule did not change when the
check moved — only where it is made.
"""

NOT_ESTABLISHED = (
    "It is not a legal person, not an employer, and not a claim that the named "
    "party was authorised by their organisation to attest anything."
)
"""The three things no surface here establishes, printed after every one of them.

On the base rather than in three sentences, so that a wording that changes changes
for every surface at once (ADR-0123 §4).
"""


@dataclass(frozen=True)
class _AttestedName:
    """A name, the claim its surface may make about it, and the limits on all three.

    Not exported and not usable as itself — `_claim` is unimplemented here, so the
    only way to a sentence is through one of the four below. What lives on this
    class is everything that must be identical across them.
    """

    name: str
    """Who the record names. What kind of name it is is the subclass."""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError(NO_NAME)

    def _claim(self) -> str:
        """What this surface established, in its own words, and nothing else.

        One clause, ending in a full stop, and never a wording about what the name
        is *not*: the limits belong to every surface and are written once, below.
        """
        raise NotImplementedError

    def stated(self) -> str:
        """The name, what established it, and what that does not amount to.

        What the signed document prints at `provenance.attestation.identity` and what
        `report.md` prints twice. The shape is the same for all three so that a
        reader meeting two reports compares two sentences and not two formats.
        """
        return f"{self.name} — {self._claim()} {NOT_ESTABLISHED}"


@dataclass(frozen=True)
class VerifiedSubject(_AttestedName):
    """A name off a token the issuer this deployment declares put its signature on.

    The name is the subject `identity.Operator` carries: the identifier an issuer
    puts on a *session*. A machine credential's subject is never this one —
    `VerifiedMachine` is where that goes, because a session at an issuer is a person
    having signed in and this sentence would say so about a program (ADR-0124).

    Constructed at one place — the route that turns a request into a record, from the
    operator the door admitted — because that is the only place a verification
    happened. A caller that constructs one by hand is writing a claim the signature
    cannot speak to, which is the defect ADR-0116 records.
    """

    def _claim(self) -> str:
        """See `_AttestedName._claim`."""
        return (
            "the subject of a verified session at the issuer this deployment "
            "declares. That is the whole of what verification established: a token "
            "that issuer signed, naming this subject."
        )


@dataclass(frozen=True)
class VerifiedMachine(_AttestedName):
    """The subject of a machine credential the declared issuer checked, and no person.

    Held apart from `VerifiedSubject` for the reason `WorkflowActor` is held apart
    from both: a different thing was established. A session token says somebody
    signed in; a machine credential says a secret somebody provisioned is current,
    and there is nobody at the other end of it. Printing the verified reading over a
    machine credential would put *the subject of a verified session* on a run a
    coding agent started while its operator was reading something else — which is
    the sentence ADR-0116 exists to stop the bench from writing.

    Constructed where `VerifiedSubject` is, off the same door, from the credential
    the caller presented (`api.app.attributed_to`).
    """

    def _claim(self) -> str:
        """See `_AttestedName._claim`."""
        return (
            "the subject of a machine credential the issuer this deployment "
            "declares verified at its own endpoint. That is the whole of what "
            "verification established: a credential that issuer holds, current at "
            "the moment of the request, naming this machine. No person was present, "
            "and this field names none."
        )


@dataclass(frozen=True)
class WorkflowActor(_AttestedName):
    """The actor a workflow run was started as — `github.actor` (ADR-0066).

    Held apart from `VerifiedSubject` because a different party did the checking:
    the runner authenticated this actor, and the issuer this deployment declares has
    never heard of them. Folding the two together would print one issuer's name over
    the other's evidence, and folding this into `NameGiven` would understate a check
    that really happened — `unattended.py` has called this "an authenticated identity
    rather than a name typed at a prompt" since ADR-0066, and this is where a reader
    of the document finally sees which of the two they are holding.
    """

    def _claim(self) -> str:
        """See `_AttestedName._claim`."""
        return (
            "the actor a workflow run was started as, authenticated by the runner "
            "that ran it and by no issuer this deployment declares. What that "
            "established is which account the workflow ran under."
        )


@dataclass(frozen=True)
class NameGiven(_AttestedName):
    """A name nothing checked: typed at a terminal, or recorded by a bench with no door.

    The two surfaces are one reading because the fact is one fact — nobody verified
    this — and the name itself is what separates them for a reader: a terminal run
    carries whatever the operator typed, and a bench that declared `NO_DOOR` carries
    the sentence `api.app.NOBODY_VERIFIED` holds, which names nobody at all
    (ADR-0122).

    It is the weakest of the four and it is deliberately the one a caller reaches by
    default: the failure this module exists to prevent is a document claiming more
    than was checked, so the reading that claims least is the one that costs nothing
    to choose.
    """

    def _claim(self) -> str:
        """See `_AttestedName._claim`."""
        return (
            "a name nothing verified. No issuer was asked and no token was checked, "
            "so this field records who was named and not who was there."
        )


AttestedName = VerifiedSubject | VerifiedMachine | WorkflowActor | NameGiven
"""What may name somebody in an attestation. Four types, never one type with a flag.

`identity.Verification`'s shape, one layer out and for its reason: a boolean beside a
string can be set by anybody, and a union can only be narrowed. Spelled as the four
rather than as the base, so that a type added to this module is a type added to this
line — a subclass is not admitted to the artefact by inheriting.
"""
