"""The recipient's side, tested by tampering rather than by round-tripping.

A test that publishes a report and verifies it proves that the signature library
works. What a recipient needs to know is that each of the four ways an artefact can be
wrong is reported **as itself**: one altered byte, a rendering that no longer matches
its digest, a valid signature made by a key they were not told to trust, and figures
that do not follow from the counts printed beside them. Each has its own named outcome,
because a reader who learns only that "verification failed" goes looking for a
transport fault.

Every doctored payload below is **re-signed** where the point is a later check. A
tampered payload that also failed its signature would prove nothing about whether the
arithmetic is re-derived at all, so the forger here is given the key: what is being
tested is the check that survives a perfectly valid signature.

The keys are generated per test and pinned with `--pubkey`. The committed key's private
half is deliberately absent from this repository, which is why the one test that pins it
by default is the one about a document signed by somebody else.
"""

import ast
import json
import socket
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.bench.assembler import PROSE_QUOTED_THE_PAYLOAD, TargetResult
from backend.bench.library import Case, Family, Transform
from backend.bench.measurability import NotMeasurable
from backend.bench.payload import Provenance, canonical
from backend.bench.rendering import REPORT_MARKDOWN, REPORT_PAYLOAD, publish
from backend.bench.rule import DECLARED_RULE, GateRule
from backend.bench.selection import AttackLayer, AttackSelection
from backend.bench.signing import (
    SIGNATURE_FILE,
    encoded,
    generate,
    public_pem,
    publish_signed,
)
from backend.bench.verification import (
    CHECKS,
    BindingOutcome,
    ReDerivationOutcome,
    SignatureOutcome,
)
from backend.tests.conftest import A_FIX
from backend.tests.test_payload import (
    MODELS,
    a_payload,
    a_provenance,
    a_result,
    explaining,
)
from scripts.verify import (
    EXIT_DID_NOT_VERIFY,
    EXIT_NOT_ESTABLISHED,
    EXIT_UNREADABLE,
    main,
)

CREDENTIALS = ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "AGENTAUDIT_SIGNING_KEY")
"""Every credential this repository reads anywhere. None of them is read here."""

REFERENCE_AGENTS_ARE_NOT_NAMED = ("hardened", "trivial", "reference agent")
"""Words a target's report and its verification do not contain (ADR-0018 point 6).

`weak` is not on the list and cannot be: it is one of the three band members, so a
report that never printed it could not report a band. What must not appear is the
*agent* — the wording of `Band.stated()`, which describes the bench's calibration
equipment and belongs to a gate document.
"""


def test_a_verified_report_prints_three_named_results_and_both_claims(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # ADR-0017 point 3: three results, always all three, and both claims under them.
    # A verifier that printed "signature valid" alone would let its reader infer
    # re-derivability from integrity, which is the whole failure the ADR is about.
    published = _publish(tmp_path)

    code = main([str(tmp_path), "--pubkey", str(published.pubkey)])

    printed = capsys.readouterr().out
    assert code == 0
    for name in CHECKS:
        assert name in printed
    assert SignatureOutcome.VALID.value in printed
    assert BindingOutcome.MATCHES.value in printed
    assert ReDerivationOutcome.AGREES.value in printed
    assert "Integrity, for the whole document" in printed
    assert "Re-derivability, for the scored layer only" in printed
    assert "recorded and not reproducible" in printed


def test_a_report_carrying_findings_verifies_and_the_section_is_inside_the_signature(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], library: list[Case]
) -> None:
    """ADR-0070's whole claim, end to end and from the recipient's side.

    The scope item this ticket was cut for says the findings section lands **inside**
    the signature — ADR-0017 covers the whole document, so this adds material to both
    claims rather than a new unprotected region — and the honest way to show that is
    to publish one, verify it, and then delete a sentence from it the way a vendor
    with something to hide would.

    All three results hold on the published artefact: the signature is over these
    bytes, the Markdown hashes to the digest inside them, and the arithmetic still
    re-derives — because a finding is prose about a verdict and no figure reads a word
    of it (D13, ADR-0006).
    """
    published = _publish(tmp_path, result=explaining(library))

    code = main([str(tmp_path), "--pubkey", str(published.pubkey)])

    printed = capsys.readouterr().out
    assert code == 0
    assert SignatureOutcome.VALID.value in printed
    assert ReDerivationOutcome.AGREES.value in printed

    # The prose reached the document a human reads, both sentences and apart.
    rendered = (tmp_path / REPORT_MARKDOWN).read_text(encoding="utf-8")
    assert "**What went wrong** — The reply carried the configured secret" in rendered
    assert f"**What to change** — {A_FIX}" in rendered
    assert "data-leakage-001" in rendered
    # And what informed the fix, in one wording rather than two: the sentence is
    # composed on the record and printed from the payload, so this surface and the
    # report screen cannot make two claims about one fix (ADR-0019, ADR-0070 §2).
    assert "written against no precedent" in rendered
    # The fourth declared model, in the provenance section beside the other three.
    # An unattributed sentence in a signed artefact is what that line prevents.
    assert "### The four declared models" in rendered
    assert (
        f"- **{MODELS.narrative}** — the model the judge and the remediation tool "
        "ran on" in rendered
    ), (
        "the provenance block does not name the model that wrote section 3b, or "
        "names another one. An unattributed sentence in a signed artefact is the "
        "one thing this project's provenance rules exist to prevent (ADR-0070 §5)"
    )
    assert MODELS.narrative != MODELS.adjudicating, (
        "this fixture declares one string for both, so the assertion above would "
        "hold over a document naming the adjudicator"
    )

    # And the payload it is a view of carries the same two sentences, so nothing in
    # the document is a sentence the recipient cannot find in what they verified.
    body = json.loads((tmp_path / REPORT_PAYLOAD).read_text(encoding="utf-8"))
    [finding] = body["findings"]["findings"]
    assert finding["fix"] == A_FIX
    assert body["provenance"]["models"]["narrative"] == MODELS.narrative

    # Now take the fix out, the way a vendor handing this to a customer would. The
    # section is inside the signature, so the recipient is told.
    payload_path = tmp_path / REPORT_PAYLOAD
    payload_path.write_text(
        payload_path.read_text(encoding="utf-8").replace(A_FIX, "no fix needed"),
        encoding="utf-8",
    )

    code = main([str(tmp_path), "--pubkey", str(published.pubkey)])

    printed = capsys.readouterr().out
    assert code == EXIT_DID_NOT_VERIFY
    assert SignatureOutcome.INVALID.value in printed


def test_no_case_payload_reaches_a_published_report_through_a_models_sentence(
    tmp_path: Path, library: list[Case]
) -> None:
    """The disclosure answer, from the recipient's side rather than the record's.

    `test_reported_findings.py` holds the rule at the record. This holds the property
    the rule exists for, over the two files that actually leave the building: a
    remediation that reproduced the case's payload is published as a statement that
    it was withheld, and the payload itself is in neither file (ADR-0008, ADR-0070).
    """
    case = next(one for one in library if one.id == "data-leakage-001")
    _publish(tmp_path, result=explaining(library, fix=case.payload[0]))

    published = [
        (tmp_path / name).read_text(encoding="utf-8")
        for name in (REPORT_PAYLOAD, REPORT_MARKDOWN)
    ]

    for text in published:
        assert case.payload[0] not in text, (
            "a committed payload reached a published report through the prose a "
            "model wrote about it, which is the one route ADR-0070 §2 closes"
        )
    assert PROSE_QUOTED_THE_PAYLOAD in published[1]
    # And the finding is still here: a finding dropped for its prose would take the
    # case id and the attributed cause with it.
    assert "data-leakage-001" in published[1]


def test_one_altered_byte_of_the_payload_fails_under_its_own_named_outcome(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Not re-signed: this is the plain case of a document altered in transit, and the
    # signature is the check that catches it.
    published = _publish(tmp_path)
    path = tmp_path / REPORT_PAYLOAD
    path.write_bytes(path.read_bytes().replace(b"customer-agent", b"customer-agenz", 1))

    code = main([str(tmp_path), "--pubkey", str(published.pubkey)])

    printed = capsys.readouterr().out
    assert code == EXIT_DID_NOT_VERIFY
    assert SignatureOutcome.INVALID.value in printed
    assert SignatureOutcome.VALID.value not in printed
    # Still all three, so a reader learns which property failed and not that one did.
    assert BindingOutcome.MATCHES.value in printed
    assert ReDerivationOutcome.AGREES.value in printed


def test_a_rendering_altered_without_its_digest_fails_under_a_different_outcome(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The failure the binding exists to prevent: a doctored document travelling beside
    # a signature that is perfectly valid over the payload it no longer describes.
    published = _publish(tmp_path)
    rendering = tmp_path / REPORT_MARKDOWN
    rendering.write_text(
        rendering.read_text(encoding="utf-8") + "\nEvery family holds.\n",
        encoding="utf-8",
    )

    code = main([str(tmp_path), "--pubkey", str(published.pubkey)])

    printed = capsys.readouterr().out
    assert code == EXIT_DID_NOT_VERIFY
    assert BindingOutcome.ALTERED.value in printed
    assert BindingOutcome.MATCHES.value not in printed
    assert SignatureOutcome.VALID.value in printed, (
        "The payload was untouched, so reporting the signature as anything but valid "
        "would send the reader looking for the wrong fault."
    )


def test_a_valid_signature_by_another_key_is_a_third_outcome_and_pubkey_overrides_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # A signature that is cryptographically valid under a key nobody published is not
    # tampering and must not be reported as it: the question a recipient has to be
    # asked is *whose key is this*, and the answer is the README's fingerprint.
    published = _publish(tmp_path)

    code = main([str(tmp_path)])

    printed = capsys.readouterr().out
    assert code == EXIT_DID_NOT_VERIFY
    assert SignatureOutcome.ANOTHER_KEY.value in printed
    assert SignatureOutcome.INVALID.value not in printed
    assert SignatureOutcome.VALID.value not in printed

    assert main([str(tmp_path), "--pubkey", str(published.pubkey)]) == 0, (
        "--pubkey did not pin the key it was given, so a recipient told to trust "
        "another key has no way to act on it."
    )


def test_an_unsigned_payload_cannot_be_presented_as_signed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # ADR-0017 point 3, in its strongest form: there is no state in which the word
    # applies without a verified signature. Two states reach it — a payload naming no
    # key, and a signature file that is not there — and neither may pass.
    pubkey = _pubkey(tmp_path.parent, generate())
    publish(a_payload(), tmp_path)
    assert not (tmp_path / SIGNATURE_FILE).exists()

    code = main([str(tmp_path), "--pubkey", str(pubkey)])

    printed = capsys.readouterr().out
    assert code == EXIT_DID_NOT_VERIFY
    assert SignatureOutcome.UNSIGNED.value in printed
    assert SignatureOutcome.VALID.value not in printed

    signed = _publish(tmp_path)
    (tmp_path / SIGNATURE_FILE).unlink()
    assert main([str(tmp_path), "--pubkey", str(signed.pubkey)]) == EXIT_DID_NOT_VERIFY
    assert SignatureOutcome.UNSIGNED.value in capsys.readouterr().out


def test_the_arithmetic_is_re_derived_from_the_counts_and_is_never_corrected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The point of the exercise. Signed by the real key and bound to its own rendering,
    # so the first two checks hold and the only thing wrong with this document is that
    # its arithmetic does not follow from its own counts — which is a check on the
    # bench rather than on the transport.
    published = _publish(tmp_path)

    def half(body: dict[str, Any]) -> None:
        body["measured"]["deterministic"][0]["rate"] = 0.5

    _doctor(tmp_path, published.key, half)
    before = (tmp_path / REPORT_PAYLOAD).read_bytes()

    code = main([str(tmp_path), "--pubkey", str(published.pubkey)])

    printed = capsys.readouterr().out
    assert code == EXIT_DID_NOT_VERIFY
    assert SignatureOutcome.VALID.value in printed
    assert BindingOutcome.MATCHES.value in printed
    assert ReDerivationOutcome.DISAGREES.value in printed
    assert "measured.deterministic[0].rate" in printed
    assert "0.5" in printed and "1.0" in printed
    assert (tmp_path / REPORT_PAYLOAD).read_bytes() == before, (
        "The verifier wrote to the artefact. A disagreement is reported and never "
        "corrected: a verifier that recomputed a figure into agreement could never "
        "report the one failure it exists to find."
    )


def test_a_band_that_does_not_follow_from_the_counts_names_no_reference_agent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The band is re-read from the interval against the cut points the payload carries,
    # and what a reader is shown is the band member. The wording beside it in the
    # payload names the bench's reference agents (ADR-0018 point 6), so it is compared
    # and never printed — which is the question #50 left for this ticket.
    published = _publish(tmp_path)

    def promote(body: dict[str, Any]) -> None:
        body["measured"]["deterministic"][0]["band"] = "holds"

    _doctor(tmp_path, published.key, promote)

    code = main([str(tmp_path), "--pubkey", str(published.pubkey)])

    printed = capsys.readouterr().out
    assert code == EXIT_DID_NOT_VERIFY
    assert ReDerivationOutcome.DISAGREES.value in printed
    assert "measured.deterministic[0].band" in printed
    assert "'holds'" in printed and "'fails'" in printed
    for named in REFERENCE_AGENTS_ARE_NOT_NAMED:
        assert named not in printed.lower(), (
            f"{named!r} appears in a target's verification. The bench's calibration "
            "equipment is not named in a user's report or in the check of one, "
            "because it invites the comparison ADR-0018 point 6 refuses."
        )


def test_the_kappa_floor_is_re_derived_in_both_directions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # ADR-0015 in both directions. A judged family whose adjudicator read below the
    # floor may not have its rate published; a family withheld for a κ that in fact
    # reached the floor is a figure hidden behind a reason that is false.
    published = _publish(tmp_path)

    def below(body: dict[str, Any]) -> None:
        body["measured"]["judged"][0]["reliability"]["kappa"] = 0.4

    _doctor(tmp_path, published.key, below)
    assert (
        main([str(tmp_path), "--pubkey", str(published.pubkey)]) == EXIT_DID_NOT_VERIFY
    )
    printed = capsys.readouterr().out
    assert "measured.judged[0].reliability.kappa" in printed
    assert "ADR-0015" in printed

    def above(body: dict[str, Any]) -> None:
        body["measured"]["withheld"][0]["kappa"] = 0.95

    published = _publish(tmp_path)
    _doctor(tmp_path, published.key, above)
    assert (
        main([str(tmp_path), "--pubkey", str(published.pubkey)]) == EXIT_DID_NOT_VERIFY
    )
    assert "measured.withheld[0].kappa" in capsys.readouterr().out


def test_counts_that_are_not_a_rate_are_reported_rather_than_raised(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # `failure_rate` refuses counts that are not a rate, which is right where the bench
    # is producing a figure and wrong here: a verifier that raised on a doctored
    # document would hand its reader a traceback in place of the one thing they came
    # for, which is to be told what is wrong with it.
    published = _publish(tmp_path)

    def impossible(body: dict[str, Any]) -> None:
        body["measured"]["deterministic"][0]["attempts"] = 0

    _doctor(tmp_path, published.key, impossible)

    code = main([str(tmp_path), "--pubkey", str(published.pubkey)])

    printed = capsys.readouterr().out
    assert code == EXIT_DID_NOT_VERIFY
    assert ReDerivationOutcome.DISAGREES.value in printed
    assert "measured.deterministic[0].successes/attempts" in printed


def test_a_report_with_no_figure_to_recompute_is_not_reported_as_re_derived(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # A run whose every family was withheld or could not be measured states no
    # per-family figure, so the third check has nothing to recompute. Neither an
    # agreement nor a disagreement — a third answer under its own exit code, on
    # `scripts/gate.py`'s precedent, because collapsing it either way would report a
    # claim this verification never made.
    published = _publish(
        tmp_path,
        result=a_result(
            families=(),
            judged=(),
            not_measurable={Family.SCOPE_CREEP: NotMeasurable.NO_TOOL_CALL_VISIBILITY},
        ),
    )

    code = main([str(tmp_path), "--pubkey", str(published.pubkey)])

    printed = capsys.readouterr().out
    assert code == EXIT_NOT_ESTABLISHED
    assert ReDerivationOutcome.NOTHING_RE_DERIVED.value in printed
    assert ReDerivationOutcome.AGREES.value not in printed
    assert "All three held" not in printed, (
        "A report stating no figure was reported as having re-derived one. That is a "
        "stated absence read as a result, which is the one mistake this project "
        "refuses everywhere else."
    )


def test_the_bar_the_figures_were_read_against_is_checked_against_the_declared_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The rule is declared in the repository (ADR-0003) and the cut points are the
    # reference agents' constructed rates, "declared, never tuned" (ADR-0014). A
    # verifier that read both out of the payload would re-derive cleanly against a bar
    # a forger had moved — so the stated bar is compared against the declared one, and
    # a promoted band arrives with the moved anchor beside it.
    published = _publish(tmp_path)

    def move_the_anchor(body: dict[str, Any]) -> None:
        body["measured"]["cuts"]["fails_at_or_above"] = 0.99

    _doctor(tmp_path, published.key, move_the_anchor)

    code = main([str(tmp_path), "--pubkey", str(published.pubkey)])

    printed = capsys.readouterr().out
    assert code == EXIT_DID_NOT_VERIFY
    assert ReDerivationOutcome.DISAGREES.value in printed
    assert "measured.cuts.fails_at_or_above" in printed

    published = _publish(tmp_path)

    def lower_the_floor(body: dict[str, Any]) -> None:
        body["provenance"]["rule"]["kappa_floor"] = 0.1

    _doctor(tmp_path, published.key, lower_the_floor)
    assert (
        main([str(tmp_path), "--pubkey", str(published.pubkey)]) == EXIT_DID_NOT_VERIFY
    )
    assert "provenance.rule.kappa_floor" in capsys.readouterr().out


def test_a_run_at_a_non_declared_denominator_verifies_and_says_it_is_not_a_gate_result(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The console offers `attempts_per_case` and ADR-0025 argues why: an operator
    # probing a new target does not want 181 calls to find out whether the wire works.
    # A verifier that reported such a run as arithmetic_disagrees would teach its
    # reader that the outcome is noise, which is the state in which a real tampering
    # goes unnoticed — so the departure is a fourth answer and not a disagreement
    # (ADR-0027).
    published = _publish(tmp_path, rule=replace(DECLARED_RULE, attempts_per_case=1))

    code = main([str(tmp_path), "--pubkey", str(published.pubkey)])

    printed = capsys.readouterr().out
    assert code == 0
    assert ReDerivationOutcome.AGREES_OFF_DECLARED_RULE.value in printed
    assert ReDerivationOutcome.DISAGREES.value not in printed
    assert "not a gate result" in printed
    assert "1 attempt per case where the declared rule reads 10" in printed


def test_a_denominator_altered_after_the_fact_still_fails_under_its_own_outcome(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The distinction ADR-0027 draws is between a rule the operator declared and the
    # document states, and one altered after the fact. Both halves are asserted here,
    # because reading the denominator instead of asserting it is only admissible if
    # the second half still fails: a rewritten `n` with the signature left as it was,
    # and a rewritten `n` re-signed with the key, keeping the wording the declared
    # denominator would have carried.
    published = _publish(tmp_path)
    path = tmp_path / REPORT_PAYLOAD
    path.write_bytes(
        path.read_bytes().replace(
            b'"attempts_per_case":10', b'"attempts_per_case":1', 1
        )
    )

    code = main([str(tmp_path), "--pubkey", str(published.pubkey)])

    printed = capsys.readouterr().out
    assert code == EXIT_DID_NOT_VERIFY
    assert SignatureOutcome.INVALID.value in printed

    published = _publish(tmp_path)

    def one_attempt_stated_as_ten(body: dict[str, Any]) -> None:
        body["provenance"]["rule"]["attempts_per_case"] = 1

    _doctor(tmp_path, published.key, one_attempt_stated_as_ten)

    code = main([str(tmp_path), "--pubkey", str(published.pubkey)])

    printed = capsys.readouterr().out
    assert code == EXIT_DID_NOT_VERIFY, (
        "A payload whose denominator was rewritten while its own sentence kept the "
        "declared wording verified. The sentence is re-derived from the number for "
        "exactly this case: a document may not carry one and mean the other."
    )
    assert ReDerivationOutcome.DISAGREES.value in printed
    assert "provenance.rule.attempts_per_case_stated" in printed


def test_a_selection_rewritten_after_the_fact_is_reported_rather_than_believed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The third surface *switched off is not measured at zero* reaches.

    A screen states the gap, the document states the selection, and this is the
    verifier's half: the selection is **read and not asserted**, on the denominator's
    exact terms (ADR-0027), because it is a declared input an operator may set — and
    what is asserted is the **sentence beside it**. A document that carried a narrowed
    selection while telling its reader every construction was sent would be claiming a
    denominator it does not have, with every other comparison still agreeing
    (ADR-0058).

    A run that narrowed its selection verifies. Only the disagreement between the
    members and the wording is a doctored document.
    """
    published = _publish(
        tmp_path,
        provenance=replace(
            a_provenance(),
            selection=AttackSelection(
                layers=frozenset({AttackLayer.SINGLE_TURN}),
                transforms=frozenset({Transform.PLAIN}),
            ),
        ),
    )

    code = main([str(tmp_path), "--pubkey", str(published.pubkey)])
    printed = capsys.readouterr().out
    assert code == 0, "a run at a narrowed selection is a real run (ADR-0058)"
    assert ReDerivationOutcome.DISAGREES.value not in printed

    published = _publish(tmp_path)

    def a_narrowed_run_claiming_the_whole_library(body: dict[str, Any]) -> None:
        # The members say one construction in one layer; the sentence and the flag are
        # left saying what a full suite carries. Nothing else on the page contradicts
        # either, which is why the verifier has to.
        body["provenance"]["selection"]["transforms"] = ["plain"]
        body["provenance"]["selection"]["layers"] = ["single_turn"]

    _doctor(tmp_path, published.key, a_narrowed_run_claiming_the_whole_library)

    code = main([str(tmp_path), "--pubkey", str(published.pubkey)])
    printed = capsys.readouterr().out
    assert code == EXIT_DID_NOT_VERIFY, (
        "A payload whose selection was rewritten while its own sentence kept the "
        "whole-library wording verified. The sentence is re-derived from the members "
        "for exactly this case: a document may not carry one selection and tell its "
        "reader about another."
    )
    assert ReDerivationOutcome.DISAGREES.value in printed
    assert "provenance.selection.stated" in printed

    # And the derived flag on its own, with the members and the sentence left
    # agreeing. It is carried rather than inferred so that a consumer does not have to
    # count the enum to answer *did this run narrow anything* — which is exactly why a
    # forger could set it and leave everything a reader looks at consistent.
    published = _publish(
        tmp_path,
        provenance=replace(
            a_provenance(),
            selection=AttackSelection(
                layers=frozenset({AttackLayer.SINGLE_TURN}),
                transforms=frozenset({Transform.PLAIN}),
            ),
        ),
    )

    def a_narrowed_run_flagged_as_the_whole_library(body: dict[str, Any]) -> None:
        body["provenance"]["selection"]["whole_library"] = True

    _doctor(tmp_path, published.key, a_narrowed_run_flagged_as_the_whole_library)

    code = main([str(tmp_path), "--pubkey", str(published.pubkey)])
    printed = capsys.readouterr().out
    assert code == EXIT_DID_NOT_VERIFY
    assert "provenance.selection.whole_library" in printed


def test_the_verifier_reaches_no_network_and_reads_no_credential(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The situation the artefact exists for is a recipient who cannot reach the sender.
    # A verification step that phoned home, or that wanted an API key, would be one
    # they cannot perform — so this asserts both halves: nothing in the import graph
    # can make a model call or read a credential file, and a run with every socket
    # refused still verifies.
    reachable = set(_reachable("backend.bench.verification", "scripts.verify"))
    assert "backend.bench.completion" not in reachable, (
        "The verifier reaches the bench's model call. Offline means the import graph "
        "cannot make one, not that this run happened not to."
    )
    assert "dotenv" not in reachable, (
        "The verifier loads a credential file. It needs no credential, and one that "
        "read one would be a verifier a recipient cannot run."
    )
    assert "openai" not in reachable

    published = _publish(tmp_path)
    for credential in CREDENTIALS:
        monkeypatch.delenv(credential, raising=False)

    def refused(*args: object, **kwargs: object) -> None:
        raise AssertionError("the verifier opened a socket")

    monkeypatch.setattr(socket, "socket", refused)
    monkeypatch.setattr(socket, "create_connection", refused)

    assert main([str(tmp_path), "--pubkey", str(published.pubkey)]) == 0


def test_an_artefact_of_another_kind_is_refused_rather_than_reported_as_unverified(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # `payload.ARTEFACT` says what kind of document this is so a verifier can refuse
    # one it does not know. Reporting *signature invalid* over an unknown shape would
    # tell its reader a signature was checked and found wanting, when what happened is
    # that the figures may not be where this code looks for them.
    published = _publish(tmp_path)

    def rename(body: dict[str, Any]) -> None:
        body["artefact"] = "agentaudit.gate-run"

    _doctor(tmp_path, published.key, rename)

    code = main([str(tmp_path), "--pubkey", str(published.pubkey)])

    printed = capsys.readouterr().out
    assert code == EXIT_UNREADABLE
    assert "Nothing here to verify" in printed
    for outcome in SignatureOutcome:
        assert outcome.value not in printed


# --- Helpers -----------------------------------------------------------------


@dataclass(frozen=True)
class Publication:
    """One signed report: the key that signed it, and the PEM a recipient would pin."""

    key: Ed25519PrivateKey
    pubkey: Path


def _publish(
    directory: Path,
    result: TargetResult | None = None,
    rule: GateRule | None = None,
    provenance: Provenance | None = None,
) -> Publication:
    """One signed report in that directory, under a key generated for this test."""
    key = generate()
    publish_signed(
        a_payload(result=result, rule=rule, provenance=provenance), directory, key
    )
    return Publication(key, _pubkey(directory.parent, key))


def _pubkey(directory: Path, key: Ed25519PrivateKey) -> Path:
    """That key's public half in PEM, where `--pubkey` can be pointed at it."""
    path = directory / "pinned.pub"
    path.write_bytes(public_pem(key.public_key()))
    return path


def _doctor(
    directory: Path, key: Ed25519PrivateKey, change: Callable[[dict[str, Any]], None]
) -> None:
    """Alter the payload, re-serialise it canonically and sign it again.

    The forger is given the key on purpose. A doctored document that also failed its
    signature would tell us nothing about whether the later checks run at all, and the
    checks worth having are the ones that survive a valid signature.
    """
    path = directory / REPORT_PAYLOAD
    body: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    change(body)
    doctored = canonical(body).encode("utf-8")
    path.write_bytes(doctored)
    (directory / SIGNATURE_FILE).write_text(
        encoded(key.sign(doctored)), encoding="utf-8"
    )


def _reachable(*roots: str) -> Iterator[str]:
    """Every module reachable from those, following this repository's own imports.

    The pattern `test_gate.py` and `test_judge.py` already use, walked transitively
    rather than one level deep: what matters is not what `verification.py` imports but
    what a recipient's process ends up holding.
    """
    seen: set[str] = set()
    pending = list(roots)
    while pending:
        module = pending.pop()
        if module in seen:
            continue
        seen.add(module)
        yield module
        source = Path(module.replace(".", "/") + ".py")
        if not source.is_file():
            continue
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                pending.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                pending.append(node.module)
