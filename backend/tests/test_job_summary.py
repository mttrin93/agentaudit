"""What a step writes onto a CI run's own page, and what it refuses to write there.

A job summary is the most public thing this project produces. A report travels to a
recipient somebody chose; a summary on a public repository is world-readable, is
indexed, and outlives the artefact's retention window. So the disclosure rule
(ADR-0008) is checked here rather than argued here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.bench.admission import admitted_library
from backend.bench.library import AnyFamily, Family
from backend.bench.signing import SIGNING_KEY_VARIABLE, encoded_private, generate
from backend.tests import headless_agent
from backend.tests.headless_agent import RecordingAgent
from scripts import bench, summary
from scripts.probe_target import CASES_DIR, OperatorGap

TARGET = "https://staging.example/agent/messages"

ATTESTATION = f"""# AgentAudit attestation

target: {TARGET}

- I am authorised to test this endpoint
- this endpoint is a staging or sandbox environment
- I accept that these payloads will generate provider policy violations
  against my own account and consume my own inference budget
"""

RENDERING = """# AgentAudit report

## 1. Description

The document the run signed.
"""


def test_the_summary_is_the_signed_rendering_and_says_where_the_artefact_is() -> None:
    """No second assembly, for the reason `payload_for` has one caller in the script.

    The rendering is the document whose sha256 the payload carries, so a reader who
    downloads the artefact and a reader who reads the page are reading the same
    bytes. A summary composed out of the result a second time would be a second
    document with nothing binding it to the first.
    """
    page = summary.job_summary(
        RENDERING, artifact="agentaudit-report", out="/tmp/report"
    )

    assert RENDERING in page
    assert "agentaudit-report" in page
    assert "scripts.verify" in page


def test_a_family_nothing_planted_for_is_on_the_page_with_the_sentence_why() -> None:
    """The withdrawal is not in the signed rendering, and it belongs on the page.

    `bench.withdrawn_for_want_of_a_plant` drops those cases before the run, so the
    family is absent from the measured section rather than present at zero — correct
    in the artefact, and unreadable on a page where the alternative reading is that
    the family passed.
    """
    withdrawn: dict[AnyFamily, OperatorGap] = {
        Family.INDIRECT_PROMPT_INJECTION: OperatorGap.NOTE_NOT_PLANTED
    }

    page = summary.job_summary(
        RENDERING, artifact="a", out="/tmp/report", withdrawn=withdrawn
    )

    assert str(Family.INDIRECT_PROMPT_INJECTION) in page
    assert OperatorGap.NOTE_NOT_PLANTED.stated() in page


def test_a_case_payload_on_the_page_is_a_disclosure_and_is_named() -> None:
    """The tripwire. A whole turn of a live case, copied onto a world-readable page.

    Nothing in the rendering can put one there — the payload is not serialised, so
    the document cannot carry it (ADR-0008) — which is exactly why this is checked
    rather than trusted: the claim is about a document assembled in a script, and a
    line added to that script later has no other thing standing in its way.
    """
    cases = admitted_library(CASES_DIR)
    case = next(one for one in cases if one.payload)
    leaked = case.payload[0]

    found = summary.disclosures(f"{RENDERING}\n{leaked}\n", cases=cases, secrets=())

    assert found, "a whole turn of a live case was copied onto the page"
    assert any(case.id in disclosure for disclosure in found)
    # The report names what leaked and never quotes it: a disclosure notice that
    # printed the turn would be the disclosure, one file further on.
    assert not any(leaked[:80] in disclosure for disclosure in found)


def test_the_endpoint_and_the_token_are_disclosures_too() -> None:
    """A live URL that answers jailbreak payloads, in a log that travels further.

    `registration.endpoint_hash` exists because the URL may not go into a document
    that travels; a job log travels further than the document does.
    """
    url = "https://staging.example/agent/messages"

    found = summary.disclosures(
        f"target {url}", cases=(), secrets=(url, "bearer-token")
    )

    assert len(found) == 1
    assert url not in found[0], "naming the secret would print it"


def test_a_clean_page_over_the_live_library_discloses_nothing() -> None:
    cases = admitted_library(CASES_DIR)

    assert summary.disclosures(RENDERING, cases=cases, secrets=()) == ()


def test_the_writer_refuses_a_disclosing_page_and_writes_nothing(
    tmp_path: Path,
) -> None:
    """Refused, not filtered, and the file is left as it was.

    A summary with a turn cut out of it is a document somebody has to trust the
    cutter of. The artefact is already on disk and signed by the time this runs, so
    a refusal costs the page and not the run.
    """
    cases = admitted_library(CASES_DIR)
    page = tmp_path / "summary.md"
    page.write_text("what a previous step wrote\n", encoding="utf-8")
    leaked = next(one for one in cases if one.payload).payload[0]

    with pytest.raises(summary.Disclosed) as refused:
        summary.write_summary(page, leaked, cases=cases, secrets=())

    assert page.read_text(encoding="utf-8") == "what a previous step wrote\n"
    assert "ADR-0008" in str(refused.value)


def test_the_page_is_appended_because_a_job_summary_is_one_file(
    tmp_path: Path,
) -> None:
    cases = admitted_library(CASES_DIR)
    page = tmp_path / "summary.md"
    page.write_text("what a previous step wrote\n", encoding="utf-8")

    summary.write_summary(
        page,
        summary.job_summary(RENDERING, artifact="a", out="/tmp/report"),
        cases=cases,
        secrets=(),
    )

    written = page.read_text(encoding="utf-8")
    assert written.startswith("what a previous step wrote\n")
    assert RENDERING in written


def test_a_step_writes_the_page_and_puts_no_payload_text_on_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End to end through the entrypoint, onto the file a runner would name.

    The claim is not that a file appears. It is that what appears is the rendering
    the payload's `rendered_sha256` covers, that the families this run never
    attempted are named on it with a sentence, and that not one turn of the live
    library is anywhere in it — on the surface where a copy would be world-readable
    and would outlive the artefact (ADR-0008).
    """
    key = generate()
    monkeypatch.setenv(SIGNING_KEY_VARIABLE, encoded_private(key))
    agent = RecordingAgent()
    monkeypatch.setattr(headless_agent, "AGENT", agent)
    published = tmp_path / "artefact"
    page = tmp_path / "summary.md"
    reference = "backend.tests.headless_agent:AGENT"
    document = tmp_path / "agentaudit-attestation.md"
    document.write_text(ATTESTATION.replace(TARGET, reference), encoding="utf-8")

    code = bench.main(
        [
            "--identity",
            "octocat",
            "--attestation-file",
            str(document),
            "--out",
            str(published),
            "--deterministic-only",
            "--max-calls",
            "100000",
            "--callback",
            reference,
            "--summary",
            str(page),
            "--artifact-name",
            "agentaudit-report",
        ]
    )

    assert code == 0
    written = page.read_text(encoding="utf-8")
    assert (published / "report.md").read_text(encoding="utf-8") in written
    assert "agentaudit-report" in written
    # `--deterministic-only` builds no adjudicator, so the two judged families were
    # not attempted. They are absent from the rendering and named here.
    assert OperatorGap.ADJUDICATOR_NOT_SUPPLIED.stated() in written
    assert (
        summary.disclosures(written, cases=admitted_library(CASES_DIR), secrets=())
        == ()
    )


def test_a_refused_page_makes_the_step_red_and_leaves_the_artefact_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The recoverable half of the pair, and the only reading of a green step.

    A control that fails closed and returns 0 is a control nobody hears. The run
    completed and the three files are signed and on disk, so what a red step here
    says is *the page was refused*, not *the run failed* — and no rate decided it,
    which is the invariant `scripts/bench.py` keeps (ADR-0065 §4).
    """
    key = generate()
    monkeypatch.setenv(SIGNING_KEY_VARIABLE, encoded_private(key))
    monkeypatch.setattr(headless_agent, "AGENT", RecordingAgent())
    leaked = next(one for one in admitted_library(CASES_DIR) if one.payload).payload[0]
    monkeypatch.setattr(bench, "job_summary", lambda *_, **__: leaked)
    published = tmp_path / "artefact"
    page = tmp_path / "summary.md"
    reference = "backend.tests.headless_agent:AGENT"
    document = tmp_path / "agentaudit-attestation.md"
    document.write_text(ATTESTATION.replace(TARGET, reference), encoding="utf-8")

    code = bench.main(
        [
            "--identity",
            "octocat",
            "--attestation-file",
            str(document),
            "--out",
            str(published),
            "--deterministic-only",
            "--max-calls",
            "100000",
            "--callback",
            reference,
            "--summary",
            str(page),
        ]
    )

    assert code == bench.EXIT_DISCLOSED
    assert (published / "report.sig").exists(), "the run's artefact is untouched"
    assert not page.exists(), "nothing was written to the page"
