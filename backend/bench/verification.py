"""The recipient's side: three checks over three files, offline, and never one answer.

`signing.py` produces the artefact. This module is what somebody who does not trust
the sender and cannot reach them can run against it, and it answers **three separate
questions** because a verifier that answered one would let its reader infer the
strongest claim from the weakest (ADR-0017 point 3):

1. **the signature** is this key's over exactly these bytes;
2. **the binding** holds — the Markdown beside the payload hashes to the digest inside
   the payload, so the document a human reads is the one a machine verified;
3. **the arithmetic re-derives** — every rate, interval and band the payload states is
   recomputed here from the counts printed beside it, through the same functions the
   bench used, and compared; and the rule and cut points it says those were read
   against are compared with the ones this repository declares, because a bar read out
   of the document is a bar a forger can move.

**The third is the point of the exercise.** The first two check the transport: they
say the artefact arrived as it left. Only the third checks the *bench*. It is what
makes *re-derivable* a property the recipient established rather than a sentence the
document asserted — and it can fail on a document that was never tampered with at all,
which is exactly why it is worth running.

**Nothing here is corrected.** A disagreement is reported with the path that reached
it, what the payload states and what re-derivation produced, and the payload on disk is
left as it was found. A verifier that silently recomputed a figure into agreement would
be a verifier that could never report the one failure it exists to find.

**Nothing here parses the payload back into the bench's own types.** The signature is
checked over the bytes of the file as they were read, and every other check reads the
serialised document as plain data — the discipline `rendering.py` follows for the same
reason. A verifier that reconstructed a `TargetPayload` and re-serialised it would be
checking a signature over its own reconstruction, and the recipient would be trusting
the round trip rather than the document.

**It reaches no network and needs no credential.** It imports the arithmetic and
nothing that can make a model call; the pinned public key is a file; there is no
environment variable it reads. A verification step that needed a service would be one
a recipient cannot run when the sender is gone, which is the entire situation this
artefact is for.

**No reference agent is named in anything this module prints** (ADR-0018 point 6). The
payload carries `band_stated`, whose wording names the hardened and weak agents because
it is also the gate's wording; the rendering already refuses to print it and so does
this. What a reader of a verification sees is the band member — `holds`, `weak`,
`fails` — and whether it follows from the counts. The wording *is* re-derived, because
a payload whose band says one thing and whose prose says another is a doctored document
and this is the only check that would notice; it is compared and never printed.
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from backend.bench.library import Transform
from backend.bench.payload import ARTEFACT, ARTEFACT_VERSION
from backend.bench.rendering import REPORT_MARKDOWN, REPORT_PAYLOAD
from backend.bench.rule import DECLARED_RULE, GateRule
from backend.bench.scorer import (
    DECLARED_BAND_CUTS,
    BandCuts,
    Rate,
    band_for,
    failure_rate,
    reaches,
)
from backend.bench.selection import EVERY_CONSTRUCTION, AttackLayer, AttackSelection
from backend.bench.signing import (
    ALGORITHM,
    SIGNATURE_FILE,
    decoded,
    fingerprint,
    verify_bytes,
)

TOLERANCE = 1e-12
"""How far a re-derived figure may sit from the stated one before it disagrees.

Not zero, and the reason is honesty about what the arithmetic is: a rate is exact
division, but a Wilson bound goes through `NormalDist.inv_cdf`, and a recipient whose
standard library differs from the bench's by one unit in the last place is not holding
a doctored document. Stated as a number and printed with the result, because a
tolerance nobody can read is a tolerance that can be widened. A figure somebody
changed is never wrong by 1e-12.
"""

INTEGRITY_CLAIM = (
    "Integrity, for the whole document. A valid signature says these bytes are the "
    "ones that were produced and that nothing has altered them — the adaptive section "
    "included, since the signature covers the whole payload and leaves no region "
    "unprotected (ADR-0017). It says nothing whatsoever about whether the agent is "
    "safe."
)
"""ADR-0017's first claim, printed beside the second and never alone."""

RE_DERIVABILITY_CLAIM = (
    "Re-derivability, for the scored layer only. Every figure in the scored sections "
    "follows from the recorded attempts, the case records and the rule the payload "
    "carries, which is what check 3 above recomputed. The adaptive layer is recorded "
    "and not reproducible: re-run it and the attacker takes a different path, so a "
    "valid signature over it is a claim about its bytes and never about its figures "
    "(ADR-0010, ADR-0017)."
)
"""ADR-0017's second claim, and the reason the first is not enough on its own.

Both are stated in the verifier's own voice rather than quoted out of the rendering,
because these two sentences are about what this run just checked where the document's
are about what it carries. They say the same two things, which is the point: a
recipient who reads only one of the two files is told the same pair.
"""


class NotThisArtefact(ValueError):
    """The file is not an AgentAudit target report, so there is nothing to verify.

    A refusal rather than a failed check. Reporting *signature invalid* over a
    document of an unknown kind would tell its reader that a signature was checked and
    found wanting, when what happened is that the verifier does not know what it is
    holding — and a shape this verifier does not understand may be a later artefact
    version whose figures live somewhere else entirely (`payload.ARTEFACT`).
    """


class SignatureOutcome(StrEnum):
    """What the signature check found. Four answers, and only one of them passes.

    `UNSIGNED` and `INVALID` are kept apart because they are different facts about
    the sender: one never signed, the other signed something else. `ANOTHER_KEY` is
    kept apart from `INVALID` for the sharper reason — a signature that is
    cryptographically valid under a key the recipient did not pin is the forgery a
    single boolean would report as tampering, and its reader would go looking for a
    transport fault instead of asking who signed it.
    """

    VALID = "signature_valid"
    UNSIGNED = "unsigned"
    ANOTHER_KEY = "signed_by_another_key"
    INVALID = "signature_invalid"


class BindingOutcome(StrEnum):
    """Whether the document a human reads is the one the payload was bound to."""

    MATCHES = "rendering_matches_its_digest"
    UNBOUND = "rendering_unbound"
    MISSING = "rendering_absent"
    ALTERED = "rendering_does_not_match_its_digest"


class ReDerivationOutcome(StrEnum):
    """Whether the payload's own arithmetic holds when it is recomputed.

    `NOTHING_RE_DERIVED` is a third answer rather than a pass. A report whose every
    family was withheld or unmeasurable states no figure for this check to disagree
    with, and telling its reader the arithmetic *agrees* would be a stated absence
    read as a result — the same mistake this project refuses four times over in the
    payload itself.

    `AGREES_OFF_DECLARED_RULE` is the fourth, and it is a **pass with a sentence
    attached**: every figure follows from the counts, and the denominator they were
    counted on is not the declared one, so the document is not a gate result
    (ADR-0027). It is not `DISAGREES`, because a run at an operator's cheaper `n` is
    a run the console offers (ADR-0025) and reporting it as a disagreement would
    teach a reader that `DISAGREES` is noise — which is the state in which a real
    tampering goes unnoticed. It is not `AGREES` either: a reader who is not told
    would compare a reading against ones taken at the published `n`.
    """

    AGREES = "arithmetic_agrees"
    AGREES_OFF_DECLARED_RULE = "arithmetic_agrees_not_a_gate_result"
    DISAGREES = "arithmetic_disagrees"
    NOTHING_RE_DERIVED = "nothing_to_re_derive"


@dataclass(frozen=True)
class SignatureResult:
    """The signature check, with the key the document claims and the key pinned."""

    outcome: SignatureOutcome
    claimed: str | None
    """The `key_id` inside the payload — a signed claim, when there is a signature."""

    pinned: str
    """The fingerprint of the key this verification was run against."""

    @property
    def held(self) -> bool:
        return self.outcome is SignatureOutcome.VALID

    def stated(self) -> str:
        match self.outcome:
            case SignatureOutcome.VALID:
                return (
                    f"a valid {ALGORITHM} signature by {self.pinned}, over the "
                    "canonical payload whole. The key's fingerprint is published in "
                    "this repository's README, so it is a key you can read the "
                    "history of rather than one that arrived with the document"
                )
            case SignatureOutcome.UNSIGNED:
                named = (
                    f"the payload names {self.claimed} as its signing key and no "
                    f"{SIGNATURE_FILE} sits beside it"
                    if self.claimed is not None
                    else "the payload names no signing key at all"
                )
                return (
                    f"there is no signature here: {named}. An unsigned report is not a "
                    "report that failed verification, it is one that was never signed, "
                    "and nothing about these bytes is vouched for by anybody"
                )
            case SignatureOutcome.ANOTHER_KEY:
                return (
                    f"this document claims to be signed by {self.claimed}, and this "
                    f"verification pinned {self.pinned}. **No signature was checked**: "
                    "the key it names is not the key in hand, so nothing here says "
                    "whether the signature is valid under it, and this outcome is also "
                    "what a rewritten `key_id` looks like — the field is inside the "
                    "signature, so altering it invalidates one. Either way this "
                    "document carries no provenance you can check against a published "
                    "fingerprint. Pass --pubkey if you have been told to trust another "
                    "key"
                )
            case SignatureOutcome.INVALID:
                return (
                    f"the signature does not verify under {self.pinned} over these "
                    "bytes. Either the payload was altered after it was signed, or "
                    "the signature was. One byte is enough, and which byte it was is "
                    "not something a signature can tell you"
                )


@dataclass(frozen=True)
class BindingResult:
    """The binding check: the rendering's digest against the one inside the payload."""

    outcome: BindingOutcome
    bound: str | None
    """The digest the payload carries in `rendered_sha256`."""

    found: str | None
    """The digest of the Markdown actually on disk, where there is one."""

    @property
    def held(self) -> bool:
        return self.outcome is BindingOutcome.MATCHES

    def stated(self) -> str:
        match self.outcome:
            case BindingOutcome.MATCHES:
                return (
                    f"{REPORT_MARKDOWN} hashes to sha256:{self.bound}, which is the "
                    f"digest inside {REPORT_PAYLOAD}. The document you read is the "
                    "one the signature above covers, so a doctored rendering cannot "
                    "travel beside a valid signature (ADR-0017)"
                )
            case BindingOutcome.UNBOUND:
                return (
                    f"{REPORT_PAYLOAD} carries no digest for a rendering, so there is "
                    "no document joined to these bytes. Nothing was bound; this is "
                    "not a rendering that failed to match"
                )
            case BindingOutcome.MISSING:
                return (
                    f"the payload is bound to a rendering with digest "
                    f"sha256:{self.bound} and no {REPORT_MARKDOWN} sits beside it. "
                    "The document a human reads is absent, so nothing here says what "
                    "anybody was shown"
                )
            case BindingOutcome.ALTERED:
                return (
                    f"{REPORT_MARKDOWN} hashes to sha256:{self.found} and "
                    f"{REPORT_PAYLOAD} is bound to sha256:{self.bound}. The two do "
                    "not agree, so the document beside this payload is not the "
                    "document that was signed. Read the payload and not the Markdown"
                )


@dataclass(frozen=True)
class Disagreement:
    """One figure the payload states and re-derivation did not produce.

    Carries the dotted path that reached it, so a reader can find the figure in the
    payload rather than being told that something, somewhere, does not add up.
    """

    path: str
    stated: str
    re_derived: str

    def line(self) -> str:
        return (
            f"{self.path}: the payload states {self.stated}, and re-derivation from "
            f"the counts beside it gives {self.re_derived}"
        )


@dataclass(frozen=True)
class ReDerivation:
    """The arithmetic check: what was recomputed, and what did not agree."""

    outcome: ReDerivationOutcome
    checked: int
    """How many stated figures were recomputed and compared."""

    disagreements: tuple[Disagreement, ...] = ()

    departure: str | None = None
    """What the payload says about a denominator that is not the declared one.

    The rule's own sentence, read out of the payload and re-derived from the number
    beside it, or `None` where the report was measured at the declared `n`. Carried
    on every outcome rather than only on `AGREES_OFF_DECLARED_RULE`: a report that
    states no figure, or one whose figures disagree, was still measured on some
    denominator, and a reader of either is owed the same sentence (ADR-0027).
    """

    @property
    def held(self) -> bool:
        """True only where figures were recomputed and every one of them agreed.

        **Nothing re-derived does not hold**, and that is the whole of this property.
        A report stating no per-family figure has not established re-derivability, so
        counting it as held would print *its arithmetic re-derives* over a check that
        never ran — a stated absence read as a result, which is the one mistake this
        project refuses everywhere else. It has not failed either: `Verification`
        carries that third answer rather than collapsing it into a fail.

        A departure from the declared denominator does not fail this check, and that
        is the whole of ADR-0027: the figures re-derived, and what they re-derived
        against is a rule the operator declared and the document states. The
        sentence saying so is in `stated()` and in the outcome's own name, where a
        reader cannot miss it — the one place it is not is a `False` here, which
        would report a run the console offers as an artefact that did not verify.
        """
        return self.outcome in (
            ReDerivationOutcome.AGREES,
            ReDerivationOutcome.AGREES_OFF_DECLARED_RULE,
        )

    def stated(self) -> str:
        """What this check found, with the denominator's departure under it."""
        return "\n".join(
            (self._found(), *(() if self.departure is None else (self.departure,)))
        )

    def _found(self) -> str:
        match self.outcome:
            case ReDerivationOutcome.AGREES:
                return (
                    f"{self.checked} stated figures recomputed from the counts beside "
                    "them — rates, Wilson bounds, bands and the κ floor — through the "
                    "same functions the bench used, and every one agrees to within "
                    f"{TOLERANCE:g}. This is the check on the bench rather than on "
                    "the transport: it is what makes re-derivable something you "
                    "established and not something the document told you"
                )
            case ReDerivationOutcome.AGREES_OFF_DECLARED_RULE:
                return (
                    f"{self.checked} stated figures recomputed from the counts beside "
                    "them and every one agrees to within "
                    f"{TOLERANCE:g} — and they were counted on a denominator that is "
                    "not the declared one. The figures follow from the counts; what "
                    "they may be compared with is the sentence below"
                )
            case ReDerivationOutcome.DISAGREES:
                return "\n".join(
                    (
                        f"{len(self.disagreements)} of {self.checked} recomputed "
                        "figures do not agree with what the payload states. Reported "
                        "and not corrected — the payload on disk is exactly as it "
                        "arrived:",
                        *(f"   - {one.line()}" for one in self.disagreements),
                    )
                )
            case ReDerivationOutcome.NOTHING_RE_DERIVED:
                return (
                    "this report states no per-family figure, so there was no "
                    f"arithmetic about a family to recompute — the {self.checked} "
                    "comparisons made here were of the rule and the cut points against "
                    "the declared ones. Not an agreement: a run whose every family was "
                    "withheld or could not be measured has nothing for this check to "
                    "disagree with, and reporting that as agreement would be a stated "
                    "absence read as a result"
                )


CHECKS = ("Signature", "Rendering binding", "Arithmetic re-derived")
"""What the three results are called, in the order they are always printed.

Held as data so the count is a property of this module: a fourth question about an
artefact is a fourth result and not a sentence appended to one of these three.
"""


@dataclass(frozen=True)
class Verification:
    """The three results, always all three, and the two claims they are scoped by."""

    artefact: str
    artefact_version: int
    target: str
    signature: SignatureResult
    binding: BindingResult
    arithmetic: ReDerivation

    @property
    def verified(self) -> bool:
        """Whether all three held. One word, and it is never printed on its own."""
        return self.signature.held and self.binding.held and self.arithmetic.held

    @property
    def contradicted(self) -> bool:
        """Whether any result actively failed, as against not having been established.

        Three answers rather than two, which is `scripts/gate.py`'s own discipline: it
        exits *passed*, *failed* and *not decided* under three codes because collapsing
        the third into the second would report a claim the run never measured. The same
        shape arrives here through `NOTHING_RE_DERIVED` — a report stating no figure
        has neither re-derived nor contradicted anything, and a verifier that called it
        either would be telling its reader something it does not know.
        """
        return (
            not self.signature.held
            or not self.binding.held
            or bool(self.arithmetic.disagreements)
        )

    def stated(self) -> str:
        """The whole of what a recipient reads: three results, then the two claims."""
        results = (
            (self.signature.outcome.value, self.signature.stated()),
            (self.binding.outcome.value, self.binding.stated()),
            (self.arithmetic.outcome.value, self.arithmetic.stated()),
        )
        return "\n".join(
            (
                f"{self.artefact}, artefact version {self.artefact_version}",
                f"one run against one target: {self.target}",
                "",
                "Three results, and all three are always reported — a verifier that "
                "printed one",
                "would let its reader infer the strongest claim from the weakest "
                "(ADR-0017).",
                "",
                *(
                    line
                    for index, (name, (outcome, stated)) in enumerate(
                        zip(CHECKS, results, strict=True), start=1
                    )
                    for line in (f"{index}. {name}: {outcome}", f"   {stated}", "")
                ),
                "The two claims this artefact carries, and they are printed together:",
                "",
                f"- {INTEGRITY_CLAIM}",
                f"- {RE_DERIVABILITY_CLAIM}",
            )
        )


@dataclass(frozen=True)
class Published:
    """The three files one run published, as bytes, however they were obtained.

    A directory is one way an artefact arrives and it is not the only one: the same
    three byte strings are held in memory by the run that made them and served over
    HTTP by the route that hands them out (#56, #59). So the checks are written
    against the bytes and the reading of a directory is one caller of them, which
    keeps a single definition of *what verifying is* — a second implementation over
    an in-memory artefact would be a second definition, and the two would only have
    to disagree once for a screen to report a property nobody checked.

    `rendering` and `signature` are `None` where the file is absent, which is one of
    the outcomes rather than an error: a payload with no rendering beside it is
    unbound, and one with no signature is unsigned, and a recipient is told which.
    """

    payload: bytes
    """The canonical bytes a signature covers, exactly as they were read."""

    rendering: bytes | None
    """The Markdown the payload's digest is taken over, or nothing."""

    signature: str | None
    """The detached signature in its hex form, or nothing.

    Text rather than bytes because that is the form the file and the response body
    hold, and a value that is not hex is reported as an invalid signature rather
    than raised: something between the signer and here changed the bytes, and which
    of the two files it was is not knowable.
    """


def verify(directory: Path, public: Ed25519PublicKey) -> Verification:
    """Verify the report published in that directory against that pinned key.

    Reads three files by their fixed names and touches nothing else. Raises
    `NotThisArtefact` where there is no artefact of a known kind to check; every other
    failure is one of the three results, because a recipient needs to learn *which*
    property failed rather than that something did.
    """
    payload_path = directory / REPORT_PAYLOAD
    if not payload_path.is_file():
        raise NotThisArtefact(
            f"no {REPORT_PAYLOAD} in {directory}. The signed artefact is the canonical "
            f"JSON payload; {REPORT_MARKDOWN} beside it is a view of it and verifies "
            "nothing on its own"
        )
    return checked(
        Published(
            payload=payload_path.read_bytes(),
            rendering=_bytes_at(directory / REPORT_MARKDOWN),
            signature=_text_at(directory / SIGNATURE_FILE),
        ),
        public,
        source=str(payload_path),
    )


def checked(
    published: Published, public: Ed25519PublicKey, source: str = "this payload"
) -> Verification:
    """The three results over three byte strings, whatever carried them here.

    `source` names what is being checked in the refusal a document of an unknown
    kind raises — a path for a recipient reading a directory, a run for a bench
    checking what it is about to serve. It appears nowhere else: the three results
    are about bytes and say nothing about where they came from.
    """
    signed = published.payload
    body = _body(signed, source)
    return Verification(
        artefact=_string(body, "artefact"),
        artefact_version=_integer(body, "artefact_version"),
        target=_string(body, "target"),
        signature=_signature(body, signed, published.signature, public),
        binding=_binding(body, published.rendering),
        arithmetic=_re_derive(body),
    )


def _bytes_at(path: Path) -> bytes | None:
    """That file's bytes, or nothing where there is no file. Absence is an outcome."""
    return path.read_bytes() if path.is_file() else None


def _text_at(path: Path) -> str | None:
    """That file as text, decoded permissively because a bad byte is a bad signature.

    A signature file that is not UTF-8 is not hex either, so it reaches
    `SignatureOutcome.INVALID` through the same path as any other unreadable
    signature rather than raising out of the file read — which would report a
    corrupted transport as a verifier that could not run.
    """
    return None if not path.is_file() else path.read_bytes().decode("utf-8", "replace")


def _body(signed: bytes, path: str) -> Mapping[str, Any]:
    """The payload as plain data, refusing anything that is not this artefact.

    Checked before any signature, because a signature over a document of an unknown
    kind is a check on the wrong thing: `payload.ARTEFACT` and its version say what
    shape the figures below are in, and a later version may keep them somewhere this
    code does not look.
    """
    try:
        parsed = json.loads(signed)
    except json.JSONDecodeError as unreadable:
        raise NotThisArtefact(f"{path} is not JSON: {unreadable}") from unreadable
    if not isinstance(parsed, dict):
        raise NotThisArtefact(f"{path} holds {type(parsed).__name__} and not an object")
    body: Mapping[str, Any] = parsed
    if body.get("artefact") != ARTEFACT:
        raise NotThisArtefact(
            f"{path} says it is {body.get('artefact')!r} and this verifier reads "
            f"{ARTEFACT!r}. Refused rather than checked, so nothing here reports a "
            "signature over a document of another kind"
        )
    if body.get("artefact_version") != ARTEFACT_VERSION:
        raise NotThisArtefact(
            f"{path} is artefact version {body.get('artefact_version')!r} and this "
            f"verifier reads version {ARTEFACT_VERSION}. A later shape is a different "
            "shape: its figures may not be where this code looks for them"
        )
    return body


def _signature(
    body: Mapping[str, Any],
    signed: bytes,
    detached: str | None,
    public: Ed25519PublicKey,
) -> SignatureResult:
    """Whether this is the pinned key's signature over exactly these bytes.

    The key the payload names is checked **before** the signature is verified, and
    that order is the whole of why a third outcome exists. Verifying first would
    report a document signed by an unpinned key as tampering, and send its reader
    looking for a transport fault instead of asking whose key signed their evidence.
    """
    pinned = fingerprint(public)
    claimed = body.get("key_id")
    if claimed is not None and not isinstance(claimed, str):
        raise NotThisArtefact(
            f"key_id is {type(claimed).__name__} and not a string, so this payload "
            "makes no readable claim about which key signed it"
        )
    if claimed is None or detached is None:
        # The key the payload named is carried through even here. A payload naming a key
        # with no signature beside it and one naming none at all are both unsigned and
        # are not the same fact, and the reader is told which they are holding.
        return SignatureResult(
            SignatureOutcome.UNSIGNED, claimed=claimed, pinned=pinned
        )
    if claimed != pinned:
        return SignatureResult(
            SignatureOutcome.ANOTHER_KEY, claimed=claimed, pinned=pinned
        )
    try:
        signature = decoded(detached)
    except ValueError:
        # A signature file that is not hex cannot verify, and saying so under the
        # invalid outcome is the honest report: something between the signer and here
        # changed the bytes, and which of the two files it was is not knowable.
        return SignatureResult(SignatureOutcome.INVALID, claimed=claimed, pinned=pinned)
    outcome = (
        SignatureOutcome.VALID
        if verify_bytes(signed, signature, public)
        else SignatureOutcome.INVALID
    )
    return SignatureResult(outcome, claimed=claimed, pinned=pinned)


def _binding(body: Mapping[str, Any], rendering: bytes | None) -> BindingResult:
    """Whether the Markdown beside the payload hashes to the digest inside it."""
    bound = body.get("rendered_sha256")
    if bound is None:
        return BindingResult(BindingOutcome.UNBOUND, bound=None, found=None)
    if not isinstance(bound, str):
        raise NotThisArtefact(
            f"rendered_sha256 is {type(bound).__name__} and not a digest, so this "
            "payload makes no readable claim about the document beside it"
        )
    if rendering is None:
        return BindingResult(BindingOutcome.MISSING, bound=bound, found=None)
    found = sha256(rendering).hexdigest()
    outcome = BindingOutcome.MATCHES if found == bound else BindingOutcome.ALTERED
    return BindingResult(outcome, bound=bound, found=found)


@dataclass
class _Comparisons:
    """Every figure recomputed so far, and the ones that did not agree.

    A collector rather than a list passed down and a count passed back up. The
    alternative had each helper reporting two things by two mechanisms — appending to
    an argument and returning a number — and the count is the one figure a
    verification prints about itself, so a helper that forgot to add its own would
    understate what was checked without anything failing.
    """

    checked: int = 0
    found: list[Disagreement] = field(default_factory=list)

    def same(
        self, path: str, node: Mapping[str, Any], key: str, re_derived: float
    ) -> None:
        """One stated number against one re-derived one, within the stated tolerance."""
        stated = _number(node, key)
        self.agrees(
            f"{path}.{key}",
            abs(stated - re_derived) <= TOLERANCE,
            repr(stated),
            repr(re_derived),
        )

    def agrees(self, path: str, holds: bool, stated: str, re_derived: str) -> None:
        """One comparison that is not between two numbers, in its own words.

        The band, the wording beside it and κ against its floor are all comparisons
        whose disagreement needs a sentence rather than two figures — and they are
        counted here rather than beside the code, so `checked` cannot drift from the
        number of comparisons actually made.
        """
        self.checked += 1
        if not holds:
            self.found.append(
                Disagreement(path=path, stated=stated, re_derived=re_derived)
            )

    def outcome(self, figures: int, departure: str | None) -> ReDerivation:
        """What these comparisons amount to: one of four answers, never two.

        `figures` is how many of them were about a **family** rather than about the bar
        the families were read against. The distinction decides the third answer: a
        report stating no per-family figure has had its rule and its cut points checked
        and still re-derived nothing, and counting those against it would report an
        agreement about figures nobody recomputed.

        `departure` is what the payload says about a denominator that is not the
        declared one, and it decides the fourth answer without deciding the first
        three. A disagreement is still a disagreement and a report stating no figure
        still re-derived nothing — those two facts are about the arithmetic, and the
        denominator a run was measured on cannot make either of them better or worse.
        So the departure travels on all four and names only the one where the figures
        agreed and the reader still must not compare them (ADR-0027).
        """
        if self.found:
            return ReDerivation(
                ReDerivationOutcome.DISAGREES,
                checked=self.checked,
                disagreements=tuple(self.found),
                departure=departure,
            )
        if figures == 0:
            return ReDerivation(
                ReDerivationOutcome.NOTHING_RE_DERIVED,
                checked=self.checked,
                departure=departure,
            )
        if departure is not None:
            return ReDerivation(
                ReDerivationOutcome.AGREES_OFF_DECLARED_RULE,
                checked=self.checked,
                departure=departure,
            )
        return ReDerivation(ReDerivationOutcome.AGREES, checked=self.checked)


def _re_derive(body: Mapping[str, Any]) -> ReDerivation:
    """Recompute every figure the payload states from the counts printed beside it.

    Every comparison goes through the function the bench itself used: `failure_rate`
    for the rate and its Wilson bounds, `band_for` for the band, `reaches` for the κ
    floor. Re-implementing the arithmetic here would produce a verifier that agrees
    with itself and tells a reader nothing about the bench.

    **Two questions, and they are different questions.** Whether the figures follow
    from the counts is asked against the rule and the cut points *the payload states*,
    because those are what this run says it measured under and internal consistency is
    what a recipient can check. Whether that stated rule is the **declared** one is
    asked separately, against `DECLARED_RULE` and `DECLARED_BAND_CUTS` — because
    ADR-0003's thresholds and ADR-0014's anchors are declared in the repository and
    never tuned, so a payload carrying its own would otherwise let a forger move the
    bar and re-derive cleanly against it.

    **The second question has two answers and not one** (ADR-0027). One number of the
    rule — the attempts per case — is a declared input an operator may set, so a
    payload stating another one is reported as *measured off the declared rule* and
    not as a disagreement; every other number of the bar is asserted, and a
    disagreement on one of them is a doctored document.
    """
    measured = _mapping(body, "measured")
    rule = _rule(body)
    cuts = _cuts(measured)
    comparisons = _Comparisons()
    departure = _declared_bar(body, measured, rule, cuts, comparisons)
    # Counted from here, so what decides the third answer is how many figures about a
    # family were recomputed and not how many comparisons this function happened to
    # make. The bar is checked on every report, including one that states no figure.
    bar = comparisons.checked
    for section in ("deterministic", "judged"):
        for index, entry in enumerate(_sequence(measured, section)):
            _entry(f"measured.{section}[{index}]", entry, rule, cuts, comparisons)
    for index, one in enumerate(_sequence(measured, "withheld")):
        _withheld(f"measured.withheld[{index}]", one, rule, comparisons)
    return comparisons.outcome(figures=comparisons.checked - bar, departure=departure)


def _declared_bar(
    body: Mapping[str, Any],
    measured: Mapping[str, Any],
    rule: GateRule,
    cuts: BandCuts,
    comparisons: _Comparisons,
) -> str | None:
    """The rule and the anchors this payload states, against the declared ones.

    Not a figure about the target: it is the question of whether the bar the figures
    were read against is the published bar. A report measured under an alternative
    rule is a report whose numbers mean something else, and the stated absence of that
    check is what would let a doctored `fails_at_or_above` promote a band with every
    other comparison still agreeing (ADR-0003, ADR-0014).

    **The attempts per case is read and not asserted, and it is the only one**
    (ADR-0027). It is a declared input the console offers, so a payload stating
    another number may be an operator probing a target cheaply; the rest of the bar
    is offered by no route, so a payload stating another number for one of those has
    been doctored. What is asserted instead is the *sentence* beside the number: it
    is re-derived from the number here, so a document cannot carry a non-declared
    denominator while telling its reader it carries the published one. Returns that
    sentence where the denominator departs, for the outcome to name, and `None`
    otherwise.
    """
    stated_rule = _mapping(_mapping(body, "provenance"), "rule")
    comparisons.same(
        "provenance.rule",
        stated_rule,
        "interval_confidence",
        DECLARED_RULE.interval_confidence,
    )
    comparisons.agrees(
        "provenance.rule.attempts_per_case_stated",
        stated_rule.get("attempts_per_case_stated") == rule.denominator_stated(),
        "wording that does not follow from the attempts per case beside it",
        f"the wording for {rule.attempts_per_case} attempts per case",
    )
    comparisons.same(
        "provenance.rule", stated_rule, "kappa_floor", DECLARED_RULE.kappa_floor
    )
    _selection(body, comparisons)
    stated_cuts = _mapping(measured, "cuts")
    comparisons.same(
        "measured.cuts",
        stated_cuts,
        "holds_at_or_below",
        DECLARED_BAND_CUTS.holds_at_or_below,
    )
    comparisons.same(
        "measured.cuts",
        stated_cuts,
        "fails_at_or_above",
        DECLARED_BAND_CUTS.fails_at_or_above,
    )
    # Compared and never printed, for the reason `band_stated` is: the shared wording
    # names the hardened and weak reference agents, and a target's report does not
    # (ADR-0018 point 6).
    comparisons.agrees(
        "measured.cuts.stated",
        stated_cuts.get("stated") == cuts.stated(),
        "wording that does not follow from the two cut points",
        (
            "the wording for these cut points. Not printed here: it names the bench's "
            "reference agents, which a target's report does not (ADR-0018)"
        ),
    )
    return None if rule.at_the_declared_denominator() else rule.denominator_stated()


def _selection(body: Mapping[str, Any], comparisons: _Comparisons) -> None:
    """The selection this payload states, against the sentence it states beside it.

    **Read and not asserted, and it is the second thing that is** (ADR-0027). The
    selection is a declared input the console offers, so a payload naming fewer
    constructions than the library holds may be an operator narrowing a run
    deliberately — asserting the full set against every document would report such a
    run as arithmetic that disagrees, which is the state in which a real tampering
    goes unnoticed. What is asserted is the *wording*: it is re-derived here from the
    members beside it, so a document cannot carry a narrowed selection while telling
    its reader every construction was sent
    ([ADR-0058](../../docs/adr/0058-the-console-selects-layers-and-constructions.md)).

    Rebuilt through `AttackSelection` rather than compared as strings, so what this
    checks the sentence against is the same type the bench wrote it from. A payload
    naming a layer or a construction this bench has no member for is a disagreement
    and not an exception: a recipient is owed the reading, and the two names travel in
    the message rather than in a traceback.

    **It is a check about the bar and never about a figure**, so it is counted before
    `_re_derive` takes its `bar` reading and does not make a report that states no
    per-family figure look as though something was recomputed.
    """
    stated = _mapping(_mapping(body, "provenance"), "selection")
    layers = [str(name) for name in _sequence_of_strings(stated, "layers")]
    transforms = [str(name) for name in _sequence_of_strings(stated, "transforms")]
    try:
        selection = AttackSelection(
            layers=frozenset(AttackLayer(name) for name in layers),
            transforms=frozenset(Transform(name) for name in transforms),
        )
    except ValueError as refused:
        comparisons.agrees(
            "provenance.selection",
            False,
            f"{layers} and {transforms}",
            (
                "layers and constructions this bench has members for, in a selection "
                f"that sends something: {refused}"
            ),
        )
        return
    comparisons.agrees(
        "provenance.selection.stated",
        stated.get("stated") == selection.stated(),
        "wording that does not follow from the selection beside it",
        "the wording for these layers and these constructions",
    )
    comparisons.agrees(
        "provenance.selection.whole_library",
        stated.get("whole_library") == (selection == EVERY_CONSTRUCTION),
        repr(stated.get("whole_library")),
        repr(selection == EVERY_CONSTRUCTION),
    )


def _sequence_of_strings(node: Mapping[str, Any], key: str) -> Sequence[str]:
    """That key as a list of strings, refusing anything else by name.

    `_sequence` next door reads a list of mappings, which is what every other list in
    this payload is. This one reads a list of member names, and it refuses as
    `NotThisArtefact` rather than coercing: a document whose selection is a string, a
    number or a list of objects is not the shape this verifier knows, and silently
    making a list out of it would report a check over something nothing here wrote.
    """
    found = node.get(key)
    if not isinstance(found, list) or any(not isinstance(name, str) for name in found):
        raise NotThisArtefact(f"{key} is not a list of names in this payload")
    return [name for name in found if isinstance(name, str)]


def _entry(
    path: str,
    entry: Mapping[str, Any],
    rule: GateRule,
    cuts: BandCuts,
    comparisons: _Comparisons,
) -> None:
    """One published family: its rate, its interval, its band and its instrument."""
    successes = _integer(entry, "successes")
    attempts = _integer(entry, "attempts")
    try:
        rate = failure_rate(successes, attempts, rule)
    except ValueError as impossible:
        # Counts that are not a rate — no attempts, or more successes than attempts —
        # are a disagreement and not a crash. `failure_rate` refuses them, which is
        # right where the bench is producing a figure and wrong here: a verifier that
        # raised on a doctored document would hand its reader a traceback in place of
        # the one thing they came for, which is to be told what is wrong with it.
        comparisons.agrees(
            f"{path}.successes/attempts",
            False,
            f"{successes} of {attempts}",
            f"no rate at all — {impossible}",
        )
        return
    _variants(path, entry, rate, comparisons)
    interval = _mapping(entry, "interval")
    comparisons.same(path, entry, "rate", rate.value)
    comparisons.same(f"{path}.interval", interval, "lower", rate.interval.lower)
    comparisons.same(f"{path}.interval", interval, "upper", rate.interval.upper)
    comparisons.same(path, entry, "interval_confidence", rule.interval_confidence)
    _band(path, entry, rate, cuts, comparisons)
    _reliability(path, entry, rule, comparisons)


def _variants(
    path: str,
    entry: Mapping[str, Any],
    rate: Rate,
    comparisons: _Comparisons,
) -> None:
    """The pooled denominator, re-derived from the per-variant counts beside it.

    **The one check that reads the family's `n` off the document rather than off the
    rule.** ADR-0027 has the verifier read the denominator and assert the rest of the
    bar, and until a family could hold more than one variant the denominator it read
    was the attempts per case times the cases the library held. It is now the sum of
    the counts published per variant, so that is what is added up here — a family
    whose `attempts` is not that sum is a document whose rate is over a denominator
    nothing in it accounts for, and no other check on this page would notice
    ([ADR-0055](../../docs/adr/0055-a-family-pools-its-variants-and-publishes-the-counts.md)).

    Three comparisons, because there are three ways the breakdown can fail to be the
    counts the rate was read off: the attempts, the successes, and a transform
    appearing twice — which would add up correctly while telling a recipient that one
    construction was sent twice as often as it was. Order is not checked here: it is
    the enumeration's rather than a claim about the run, so a reordered list is a
    document a recipient reads in a different order and not a figure that is wrong.

    A breakdown that is missing, empty, or **malformed** is a disagreement rather than
    a crash, on the terms `_entry` states for counts that are not a rate: a recipient
    of an older or doctored artefact is owed the sentence and not a traceback, and an
    element whose `attempts` is a string is exactly as doctored as one whose `attempts`
    is nine. So the two are one branch — the counts do not add up, because one of them
    is not a count.
    """
    counts = entry.get("variants")
    if not isinstance(counts, list) or not counts or not _countable(counts):
        comparisons.agrees(
            f"{path}.variants",
            False,
            "no per-variant counts that add up to anything",
            f"the counts {rate.attempts} attempts were pooled from, which is what a "
            "recipient takes this family's rate apart with (ADR-0055)",
        )
        return
    attempts = 0
    successes = 0
    transforms: list[Any] = []
    for one in counts:
        attempts += _integer(one, "attempts")
        successes += _integer(one, "successes")
        transforms.append(one.get("transform"))
    comparisons.agrees(
        f"{path}.variants.attempts",
        attempts == rate.attempts,
        f"{rate.attempts} attempts against a breakdown summing to {attempts}",
        f"{attempts}, the sum of the counts published per variant",
    )
    comparisons.agrees(
        f"{path}.variants.successes",
        successes == rate.successes,
        f"{rate.successes} successes against a breakdown summing to {successes}",
        f"{successes}, the sum of the counts published per variant",
    )
    comparisons.agrees(
        f"{path}.variants.transform",
        len(set(transforms)) == len(transforms),
        f"a breakdown naming {transforms}",
        "one entry per construction, or the counts double-count one of them",
    )


def _countable(counts: Sequence[Any]) -> bool:
    """Whether every element of a breakdown is an object with two whole counts on it.

    Asked before the sum rather than raised inside it, so that a malformed element
    lands in the one sentence a recipient can act on instead of a traceback out of
    `_integer` (`_variants` above, and `_entry`'s own refusal of counts that are not a
    rate).
    """
    return all(
        isinstance(one, dict)
        and all(
            isinstance(one.get(key), int) and not isinstance(one.get(key), bool)
            for key in ("attempts", "successes")
        )
        for one in counts
    )


def _band(
    path: str,
    entry: Mapping[str, Any],
    rate: Rate,
    cuts: BandCuts,
    comparisons: _Comparisons,
) -> None:
    """The band, re-read from the interval against the cut points the payload carries.

    Two comparisons and only one of them is printable: the band member, and the wording
    the payload carries beside it. The wording names the bench's two reference agents,
    so it is compared and never printed (ADR-0018 point 6) — but it is compared, because
    a payload whose band says `holds` and whose prose says the other thing is a doctored
    document and no other check here would notice.
    """
    derived = band_for(rate, cuts)
    stated = entry.get("band")
    comparisons.agrees(
        f"{path}.band", stated == derived.value, repr(stated), repr(derived.value)
    )
    if stated != derived.value:
        return
    comparisons.agrees(
        f"{path}.band_stated",
        entry.get("band_stated") == derived.stated(),
        "wording that does not follow from the band",
        (
            f"the wording for {derived.value}. Not printed here: it names the bench's "
            "reference agents, which a target's report does not (ADR-0018)"
        ),
    )


def _reliability(
    path: str, entry: Mapping[str, Any], rule: GateRule, comparisons: _Comparisons
) -> None:
    """A published judged family's κ against the floor it had to reach (ADR-0015).

    Re-derived because publishing the rate is itself a claim: a judged family whose
    adjudicator read below the declared floor may not have its rate published at all,
    so a rate sitting here with a κ under the floor is a payload contradicting the rule
    it prints in its own provenance block. Nothing is re-derived about κ itself — it is
    measured against the gold set and is not recoverable from the counts beside it.
    """
    reliability = entry.get("reliability")
    if reliability is None:
        return
    if not isinstance(reliability, dict):
        raise NotThisArtefact(f"{path}.reliability is not an object")
    comparisons.same(f"{path}.reliability", reliability, "floor", rule.kappa_floor)
    kappa = _number(reliability, "kappa")
    floor = _number(reliability, "floor")
    comparisons.agrees(
        f"{path}.reliability.kappa",
        reaches(kappa, floor),
        f"{kappa} with this family's rate published beside it, against a floor of "
        f"{floor}",
        "a family below the declared κ floor, whose rate a report may not publish at "
        "all (ADR-0015)",
    )


def _withheld(
    path: str, one: Mapping[str, Any], rule: GateRule, comparisons: _Comparisons
) -> None:
    """A withheld family's floor, and that its κ really is below it.

    The mirror of the check above, and it matters in the other direction: a payload
    that withheld a family whose adjudicator reached the floor would be a payload
    hiding a figure it was entitled to publish, and the reason printed beside the
    absence would be false.
    """
    comparisons.same(path, one, "floor", rule.kappa_floor)
    kappa = one.get("kappa")
    if kappa is None:
        return
    if not isinstance(kappa, int | float) or isinstance(kappa, bool):
        raise NotThisArtefact(f"{path}.kappa is not a number")
    comparisons.agrees(
        f"{path}.kappa",
        not reaches(float(kappa), _number(one, "floor")),
        f"{kappa}, with this family's rate withheld for it",
        "a κ that reaches the declared floor, so this family was fit to report and its "
        "absence has no reading behind it (ADR-0015)",
    )


def _rule(body: Mapping[str, Any]) -> GateRule:
    """The rule the payload says its figures were measured under.

    Three numbers, because three are what the payload states and what decided the
    figures: the interval's confidence, the attempts per case and the κ floor. The
    rest of `GateRule` decides the bench's own gate, which has no definition for one
    target (ADR-0018), and nothing re-derived here reads it.
    """
    stated = _mapping(_mapping(body, "provenance"), "rule")
    return GateRule(
        interval_confidence=_number(stated, "interval_confidence"),
        attempts_per_case=_integer(stated, "attempts_per_case"),
        kappa_floor=_number(stated, "kappa_floor"),
    )


def _cuts(measured: Mapping[str, Any]) -> BandCuts:
    """The two cut points the payload carries, which is what its bands were read
    against."""
    stated = _mapping(measured, "cuts")
    return BandCuts(
        holds_at_or_below=_number(stated, "holds_at_or_below"),
        fails_at_or_above=_number(stated, "fails_at_or_above"),
    )


def _mapping(node: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = node.get(key)
    if not isinstance(value, dict):
        raise NotThisArtefact(f"{key} is not an object in this payload")
    found: Mapping[str, Any] = value
    return found


def _sequence(node: Mapping[str, Any], key: str) -> Sequence[Mapping[str, Any]]:
    value = node.get(key)
    if not isinstance(value, list):
        raise NotThisArtefact(f"{key} is not a list in this payload")
    for entry in value:
        if not isinstance(entry, dict):
            raise NotThisArtefact(f"{key} holds something that is not an object")
    found: Sequence[Mapping[str, Any]] = value
    return found


def _string(node: Mapping[str, Any], key: str) -> str:
    value = node.get(key)
    if not isinstance(value, str):
        raise NotThisArtefact(f"{key} is not a string in this payload")
    return value


def _integer(node: Mapping[str, Any], key: str) -> int:
    value = node.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise NotThisArtefact(f"{key} is not a whole number in this payload")
    return value


def _number(node: Mapping[str, Any], key: str) -> float:
    value = node.get(key)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise NotThisArtefact(f"{key} is not a number in this payload")
    return float(value)
