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
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.bench.assembler import TargetResult
from backend.bench.library import Family
from backend.bench.measurability import NotMeasurable
from backend.bench.payload import canonical
from backend.bench.rendering import REPORT_MARKDOWN, REPORT_PAYLOAD, publish
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
from backend.tests.test_payload import a_payload, a_result
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


def _publish(directory: Path, result: TargetResult | None = None) -> Publication:
    """One signed report in that directory, under a key generated for this test."""
    key = generate()
    publish_signed(a_payload(result=result), directory, key)
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
