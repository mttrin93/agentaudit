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
   bench used, and compared.

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
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from backend.bench.payload import ARTEFACT, ARTEFACT_VERSION
from backend.bench.rendering import REPORT_MARKDOWN, REPORT_PAYLOAD
from backend.bench.rule import GateRule
from backend.bench.scorer import BandCuts, Rate, band_for, failure_rate, reaches
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

RE_DERIVABILITY_CLAIM = (
    "Re-derivability, for the scored layer only. Every figure in the scored sections "
    "follows from the recorded attempts, the case records and the rule the payload "
    "carries, which is what check 3 above recomputed. The adaptive layer is recorded "
    "and not reproducible: re-run it and the attacker takes a different path, so a "
    "valid signature over it is a claim about its bytes and never about its figures "
    "(ADR-0010, ADR-0017)."
)
"""The two claims, printed together and never one of them.

Stated in the verifier's own voice rather than quoted out of the rendering, because
these two sentences are about what this run just checked, where the document's are
about what it carries. Both say the same two things, which is the point: a recipient
who reads only one of the two files is told the same pair.
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
    """

    AGREES = "arithmetic_agrees"
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
                return (
                    "there is no signature here. The payload names no signing key, or "
                    f"no {SIGNATURE_FILE} sits beside it — and an unsigned report is "
                    "not a report that failed verification, it is one that was never "
                    "signed. Nothing about these bytes is vouched for by anybody"
                )
            case SignatureOutcome.ANOTHER_KEY:
                return (
                    f"this document was signed by {self.claimed}, and this "
                    f"verification pinned {self.pinned}. The signature may be "
                    "perfectly valid under the key it names — that is not the "
                    "question. Nobody who has only the published fingerprint can "
                    "tell whose key that is, so this document carries no provenance "
                    "you can check. Pass --pubkey if you have been told to trust "
                    "another key"
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

    @property
    def held(self) -> bool:
        """True where nothing disagreed, which includes having had nothing to check.

        The outcome word is what distinguishes the two: this says the payload was not
        contradicted, and only `AGREES` says its arithmetic was checked and held.
        """
        return not self.disagreements

    def stated(self) -> str:
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
                    "arithmetic to recompute. Not an agreement: a run whose every "
                    "family was withheld or could not be measured has nothing for "
                    "this check to disagree with, and reporting that as agreement "
                    "would be a stated absence read as a result"
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
    signed = payload_path.read_bytes()
    body = _body(signed, payload_path)
    return Verification(
        artefact=_string(body, "artefact"),
        artefact_version=_integer(body, "artefact_version"),
        target=_string(body, "target"),
        signature=_signature(body, signed, directory, public),
        binding=_binding(body, directory),
        arithmetic=re_derive(body),
    )


def _body(signed: bytes, path: Path) -> Mapping[str, Any]:
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
    body: Mapping[str, Any], signed: bytes, directory: Path, public: Ed25519PublicKey
) -> SignatureResult:
    """Whether this is the pinned key's signature over exactly these bytes.

    The key the payload names is checked **before** the signature is verified, and
    that order is the whole of why a third outcome exists. Verifying first would
    report a document signed by an unpinned key as tampering, and send its reader
    looking for a transport fault instead of asking whose key signed their evidence.
    """
    pinned = fingerprint(public)
    claimed = body.get("key_id")
    path = directory / SIGNATURE_FILE
    if claimed is None or not path.is_file():
        return SignatureResult(SignatureOutcome.UNSIGNED, claimed=None, pinned=pinned)
    if not isinstance(claimed, str):
        raise NotThisArtefact(
            f"key_id is {type(claimed).__name__} and not a string, so this payload "
            "makes no readable claim about which key signed it"
        )
    if claimed != pinned:
        return SignatureResult(
            SignatureOutcome.ANOTHER_KEY, claimed=claimed, pinned=pinned
        )
    try:
        signature = decoded(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
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


def _binding(body: Mapping[str, Any], directory: Path) -> BindingResult:
    """Whether the Markdown on disk hashes to the digest inside the payload."""
    bound = body.get("rendered_sha256")
    if bound is None:
        return BindingResult(BindingOutcome.UNBOUND, bound=None, found=None)
    if not isinstance(bound, str):
        raise NotThisArtefact(
            f"rendered_sha256 is {type(bound).__name__} and not a digest, so this "
            "payload makes no readable claim about the document beside it"
        )
    path = directory / REPORT_MARKDOWN
    if not path.is_file():
        return BindingResult(BindingOutcome.MISSING, bound=bound, found=None)
    found = sha256(path.read_bytes()).hexdigest()
    outcome = BindingOutcome.MATCHES if found == bound else BindingOutcome.ALTERED
    return BindingResult(outcome, bound=bound, found=found)


def re_derive(body: Mapping[str, Any]) -> ReDerivation:
    """Recompute every figure the payload states from the counts printed beside it.

    Exposed rather than private because it is the check that is about the bench, and a
    caller holding a payload — the API of #56, a screen of #59 — has the same reason to
    ask as a recipient with a directory does.

    Every comparison goes through the function the bench itself used: `failure_rate`
    for the rate and its Wilson bounds, `band_for` for the band, `reaches` for the κ
    floor. Re-implementing the arithmetic here would produce a verifier that agrees
    with itself and tells a reader nothing about the bench.
    """
    measured = _mapping(body, "measured")
    rule = _rule(body)
    cuts = _cuts(measured)
    found: list[Disagreement] = []
    checked = 0
    for section in ("deterministic", "judged"):
        for index, entry in enumerate(_sequence(measured, section)):
            checked += _entry(f"measured.{section}[{index}]", entry, rule, cuts, found)
    for index, one in enumerate(_sequence(measured, "withheld")):
        checked += _withheld(f"measured.withheld[{index}]", one, rule, found)
    if found:
        return ReDerivation(
            ReDerivationOutcome.DISAGREES, checked=checked, disagreements=tuple(found)
        )
    if checked == 0:
        return ReDerivation(ReDerivationOutcome.NOTHING_RE_DERIVED, checked=0)
    return ReDerivation(ReDerivationOutcome.AGREES, checked=checked)


def _entry(
    path: str,
    entry: Mapping[str, Any],
    rule: GateRule,
    cuts: BandCuts,
    found: list[Disagreement],
) -> int:
    """One published family: its rate, its interval, its band and its instrument.

    Returns how many figures were compared, so the count a verification reports is the
    number of comparisons it actually made rather than a number somebody maintained
    beside the code.
    """
    successes = _integer(entry, "successes")
    attempts = _integer(entry, "attempts")
    rate = failure_rate(successes, attempts, rule)
    interval = _mapping(entry, "interval")
    compared = _same(path, entry, "rate", rate.value, found)
    compared += _same(f"{path}.interval", interval, "lower", rate.interval.lower, found)
    compared += _same(f"{path}.interval", interval, "upper", rate.interval.upper, found)
    compared += _same(
        path, entry, "interval_confidence", rule.interval_confidence, found
    )
    compared += _band(path, entry, rate, cuts, found)
    compared += _reliability(path, entry, rule, found)
    return compared


def _band(
    path: str,
    entry: Mapping[str, Any],
    rate: Rate,
    cuts: BandCuts,
    found: list[Disagreement],
) -> int:
    """The band, re-read from the interval against the cut points the payload carries.

    Two comparisons and one of them is printed: the band member, and the wording the
    payload carries beside it. The wording names the bench's two reference agents, so
    it is compared and never printed (ADR-0018 point 6) — but it is compared, because a
    payload whose band says `holds` and whose prose says the other thing is a doctored
    document and no other check here would notice.
    """
    derived = band_for(rate, cuts)
    stated = entry.get("band")
    compared = 1
    if stated != derived.value:
        found.append(
            Disagreement(
                path=f"{path}.band",
                stated=repr(stated),
                re_derived=repr(derived.value),
            )
        )
        return compared
    compared += 1
    if entry.get("band_stated") != derived.stated():
        found.append(
            Disagreement(
                path=f"{path}.band_stated",
                stated="wording that does not follow from the band",
                re_derived=(
                    f"the wording for {derived.value}. Not printed here: it names the "
                    "bench's reference agents, which a target's report does not "
                    "(ADR-0018)"
                ),
            )
        )
    return compared


def _reliability(
    path: str, entry: Mapping[str, Any], rule: GateRule, found: list[Disagreement]
) -> int:
    """A published judged family's κ against the floor it had to reach (ADR-0015).

    Re-derived because publishing the rate is itself a claim: a judged family whose
    adjudicator read below the declared floor may not have its rate published at all,
    so a rate sitting here with a κ under the floor is a payload contradicting the rule
    it prints in its own provenance block. Nothing is re-derived about κ itself — it is
    measured against the gold set and is not recoverable from the counts beside it.
    """
    reliability = entry.get("reliability")
    if reliability is None:
        return 0
    if not isinstance(reliability, dict):
        raise NotThisArtefact(f"{path}.reliability is not an object")
    compared = _same(
        f"{path}.reliability", reliability, "floor", rule.kappa_floor, found
    )
    kappa = _number(reliability, "kappa")
    floor = _number(reliability, "floor")
    compared += 1
    if not reaches(kappa, floor):
        found.append(
            Disagreement(
                path=f"{path}.reliability.kappa",
                stated=(
                    f"{kappa} with this family's rate published beside it, against a "
                    f"floor of {floor}"
                ),
                re_derived=(
                    "a family below the declared κ floor, whose rate a report may not "
                    "publish at all (ADR-0015)"
                ),
            )
        )
    return compared


def _withheld(
    path: str, one: Mapping[str, Any], rule: GateRule, found: list[Disagreement]
) -> int:
    """A withheld family's floor, and that its κ really is below it.

    The mirror of the check above, and it matters in the other direction: a payload
    that withheld a family whose adjudicator reached the floor would be a payload
    hiding a figure it was entitled to publish, and the reason printed beside the
    absence would be false.
    """
    compared = _same(path, one, "floor", rule.kappa_floor, found)
    kappa = one.get("kappa")
    if kappa is None:
        return compared
    if not isinstance(kappa, int | float) or isinstance(kappa, bool):
        raise NotThisArtefact(f"{path}.kappa is not a number")
    compared += 1
    if reaches(float(kappa), _number(one, "floor")):
        found.append(
            Disagreement(
                path=f"{path}.kappa",
                stated=f"{kappa}, with this family's rate withheld for it",
                re_derived=(
                    "a κ that reaches the declared floor, so this family was fit to "
                    "report and its absence has no reading behind it (ADR-0015)"
                ),
            )
        )
    return compared


def _same(
    path: str,
    node: Mapping[str, Any],
    key: str,
    re_derived: float,
    found: list[Disagreement],
) -> int:
    """One stated number against one re-derived number, within the stated tolerance."""
    stated = _number(node, key)
    if abs(stated - re_derived) > TOLERANCE:
        found.append(
            Disagreement(
                path=f"{path}.{key}", stated=repr(stated), re_derived=repr(re_derived)
            )
        )
    return 1


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
