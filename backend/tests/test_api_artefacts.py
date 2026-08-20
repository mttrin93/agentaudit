"""The list of signed artefacts, and the six ways it could quietly stop being one.

`GET /artefacts` is the answer to *which of these can I send a customer*. It is a
read over artefacts that already exist, and the thing that makes it worth serving is
the answer that says **do not send this one yet** — so every claim below is about a
row still telling the truth when one of its three results did not hold.

**Three results, always three.** A row carrying the signature alone would let its
reader infer re-derivability from integrity, which is the one inference ADR-0017
exists to prevent. Asserted over rows whose results disagree with each other, because
three results on a row where everything held is the case that cannot fail.

**The two claims stay two.** Integrity is over the whole document and
re-derivability is over the **scored layer alone**; the adaptive layer is recorded and
not reproducible (ADR-0010). One sentence carrying both would be the conflation, and
one claim carried without the other would be the same failure by omission.

**A failure is named by its own outcome.** *Signed by a key you did not pin* is not
*this document was altered* and neither is *the rendering does not match its digest*:
they send a reader to three different places. Asserted by putting three artefacts
that fail differently on one list and requiring three different names.

**The check is the bench's own and every row says so.** A sender's word for their own
document is the thing a signature exists to replace, so `checked_by` travels on each
row and the recipient's command travels on the list.

**Three files, under the names a verifier already knows.** Asserted by fetching the
paths the row advertises and reading the filename each one arrives under: a file
served as `artefact-7f3c.json` is portable evidence a recipient's tooling cannot find.

**Nothing is computed and nothing is summarised.** The row and the list have their
field sets asserted exactly — a total is not absent because nobody printed it, it is
absent because there is no field for it — and the only integer anywhere on the list is
the artefact version.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import datetime
from typing import Any, cast

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from backend.api.app import (
    ARTEFACTS_ROUTE,
    ArtefactFile,
    ArtefactList,
    ArtefactRow,
    artefacts_response,
    create_app,
    report_paths,
)
from backend.api.report import VERIFY_COMMAND, ReportConfig, Unsigned
from backend.api.runs import BenchConfig, RunRecord, RunStatus, plan_for
from backend.bench.library import Case, LibraryVersion
from backend.bench.payload import ARTEFACT, ARTEFACT_VERSION
from backend.bench.rendering import REPORT_MARKDOWN, REPORT_PAYLOAD
from backend.bench.signing import (
    SIGNATURE_FILE,
    SignedArtefact,
    fingerprint,
    generate,
    public_key,
    signed,
)
from backend.bench.verification import (
    BindingOutcome,
    ReDerivationOutcome,
    SignatureOutcome,
)
from backend.graph.runstate import RunState
from backend.tests.conftest import BENCH_ATTESTATION, a_budget, a_target, some_cases
from backend.tests.test_api_report import completed
from backend.tests.test_payload import FORBIDDEN_IN_A_KEY, a_payload

THE_THREE_FILENAMES = [REPORT_PAYLOAD, REPORT_MARKDOWN, SIGNATURE_FILE]
"""What a verifier reads out of a directory, in the order it reads them.

The constants rather than the strings, so that a filename renamed in `rendering.py`
or `signing.py` moves this expectation with it — and `test_verify.py` is where those
names are pinned to `report.json`, `report.md` and `report.sig`.
"""


def a_record(name: str, artefact: SignedArtefact | Unsigned) -> RunRecord:
    """A run on the record holding that artefact, or holding the absence of one.

    Built by hand rather than run, because what is under test here is what the list
    makes of an artefact whose verification does *not* hold — and a run cannot be
    asked to produce a signature under somebody else's key. The artefacts themselves
    are real: signed by `signing.signed` over a real payload, and then damaged one
    field at a time.
    """
    plan = plan_for(BenchConfig(cases=some_cases(3)), note_planted=True)
    budget = a_budget(cases=18, targets=1)
    return RunRecord(
        run_id=f"run-{name}",
        target=a_target(name=name),
        attestation=BENCH_ATTESTATION,
        nonce="nonce",
        plan=plan,
        budget=budget,
        run_state=RunState(budget=budget, library=LibraryVersion.of(plan.cases)),
        presented=budget.as_payload(),
        status=RunStatus.COMPLETED,
        report=artefact,
    )


def three_artefacts(
    key: Ed25519PrivateKey, other: Ed25519PrivateKey
) -> list[RunRecord]:
    """Three signed artefacts that fail three different checks, and one that does not.

    One verifies. One is signed by a key the recipient did not pin — the outcome that
    makes this list worth serving, because the document was not altered and no
    recipient can check it. One's rendered document was edited after it was bound, so
    the signature is still this key's over these bytes and the Markdown beside them is
    no longer the document a machine verified. Three failures a single cross would
    show identically.
    """
    artefact = signed(a_payload(), key)
    return [
        a_record("verifies", artefact),
        a_record("signed-by-another-key", signed(a_payload(), other)),
        a_record(
            "rendering-edited",
            replace(
                artefact, rendering=f"{artefact.rendering}\n\nedited after signing"
            ),
        ),
    ]


def test_the_route_lists_a_signed_artefact_with_its_three_files_and_three_results(
    leakage_case: Case,
) -> None:
    """One real run's artefact, listed: what it is of, its files, its reading.

    The whole flow rather than a record built by hand, because what is under test is
    the artefact a *run* produced and what the routes serving it say about themselves.
    """
    key = generate()
    with completed([leakage_case], key, pinned=key.public_key()) as served:
        body = _listed(served.client)
        [row] = body["artefacts"]
        fetched = {
            file["filename"]: served.client.get(file["path"]) for file in row["files"]
        }
        target_url = served.record.target.url
        text = served.client.get(ARTEFACTS_ROUTE).text

    assert row["run_id"] == served.run_id
    assert row["target"] == served.record.target.name
    assert datetime.fromisoformat(row["recorded_at"]).tzinfo is not None

    # The three files, in the order a verifier reads them, at the paths that serve
    # them — and each one arrives under the name `scripts/verify.py` looks for, which
    # is the whole of what makes the directory a recipient saves verifiable.
    assert [file["filename"] for file in row["files"]] == THE_THREE_FILENAMES
    assert [file["path"] for file in row["files"]] == list(
        report_paths(served.run_id)[:3]
    )
    for filename, response in fetched.items():
        assert response.status_code == 200, filename
        assert f'filename="{filename}"' in response.headers["content-disposition"]

    # All three results, by name, and the artefact they are of.
    verification = row["verification"]
    assert verification["artefact"] == ARTEFACT
    assert verification["signature"]["outcome"] == SignatureOutcome.VALID.value
    assert verification["binding"]["outcome"] == BindingOutcome.MATCHES.value
    assert verification["arithmetic"]["outcome"] == ReDerivationOutcome.AGREES.value

    # The endpoint that answers jailbreak payloads is nowhere on a list somebody
    # screenshots, and the command a recipient runs is on it (ADR-0008).
    assert target_url not in text
    assert body["verify_command"] == VERIFY_COMMAND
    assert body["verify_command"].startswith("uv run python -m scripts.verify")


def test_the_reading_on_a_row_is_the_one_the_verification_route_serves(
    leakage_case: Case,
) -> None:
    """One definition of verifying, reached two ways.

    Field for field the same reading, because a second implementation behind the list
    would be a second definition of *verifying* — and the two would only have to
    disagree once for an engineer to send a customer an artefact a screen called
    checkable.
    """
    key = generate()
    with completed([leakage_case], key, pinned=key.public_key()) as served:
        [row] = _listed(served.client)["artefacts"]
        reading = served.fetch("/verification").json()

    assert row["verification"] == reading


def test_a_failing_result_is_named_by_its_own_outcome_and_not_by_a_shared_mark() -> (
    None
):
    """Three artefacts failing three different checks, named three different ways.

    This is the claim the list exists for. *Signed by a key you did not pin* is not
    tampering: the document arrived exactly as it left and no recipient pinning the
    published key can check it, and an engineer told only *did not verify* would go
    looking for a transport fault instead of asking whose key signed their evidence.
    The edited rendering is the third fact — a valid signature over bytes whose human
    view was changed afterwards — and one cross would show all three identically.
    """
    key, other = generate(), generate()
    body = artefacts_response(
        three_artefacts(key, other),
        ReportConfig(signing_key=key, pinned=key.public_key()),
    ).model_dump(mode="json")

    rows = {row["target"]: row["verification"] for row in body["artefacts"]}
    assert list(rows) == ["verifies", "signed-by-another-key", "rendering-edited"]

    held = rows["verifies"]
    assert held["signature"]["outcome"] == SignatureOutcome.VALID.value
    assert held["verified"] is True

    # The key nobody pinned, named as itself — with both fingerprints, so the reader
    # sees which key they are missing rather than that something about it is wrong.
    unpinned = rows["signed-by-another-key"]
    assert unpinned["signature"]["outcome"] == SignatureOutcome.ANOTHER_KEY.value
    assert fingerprint(other.public_key()) in unpinned["signature"]["statement"]
    assert fingerprint(key.public_key()) in unpinned["signature"]["statement"]

    # The document a human reads, no longer the one a machine verified — and the
    # signature over the payload still valid, which is exactly why this is its own
    # result rather than a footnote on the first.
    altered = rows["rendering-edited"]
    assert altered["binding"]["outcome"] == BindingOutcome.ALTERED.value
    assert altered["signature"]["outcome"] == SignatureOutcome.VALID.value

    # Three failures, three names, and no two rows reporting one as the other.
    named = {
        (row["signature"]["outcome"], row["binding"]["outcome"])
        for row in rows.values()
    }
    assert len(named) == 3


def test_all_three_results_are_on_every_row_even_where_one_of_them_failed() -> None:
    """No row shows two results, and there is no field that shows one instead.

    Asserted over the failing rows rather than the passing one, because the row that
    verifies is the case that cannot go wrong: a screen tempted to draw one mark
    draws it where something failed.
    """
    key, other = generate(), generate()
    body = artefacts_response(
        three_artefacts(key, other),
        ReportConfig(signing_key=key, pinned=key.public_key()),
    ).model_dump(mode="json")

    assert len(body["artefacts"]) == 3
    for row in body["artefacts"]:
        verification = row["verification"]
        for result in ("signature", "binding", "arithmetic"):
            assert set(verification[result]) == {"outcome", "statement"}
            assert verification[result]["outcome"]
            assert verification[result]["statement"]
        # And the two properties that are not one: nothing contradicted with one
        # result never established is a third answer, and a single flag could not
        # carry it.
        assert isinstance(verification["verified"], bool)
        assert isinstance(verification["contradicted"], bool)


def test_the_two_claims_are_two_statements_and_the_second_is_the_scored_layer_only(
    leakage_case: Case,
) -> None:
    """Integrity over the whole document; re-derivability over the scored layer.

    Two sentences and never one. The second is the reason the first is not enough:
    a valid signature over the adaptive section is a claim about its bytes and never
    about its figures, so re-derivability may not be widened to cover it (ADR-0010).
    """
    key = generate()
    with completed([leakage_case], key, pinned=key.public_key()) as served:
        [row] = _listed(served.client)["artefacts"]

    verification = row["verification"]
    integrity, re_derivability = (
        verification["integrity"],
        verification["re_derivability"],
    )

    assert "Integrity, for the whole document" in integrity
    assert "Re-derivability, for the scored layer only" in re_derivability
    assert "recorded and not reproducible" in re_derivability

    # Two fields, and neither is the other or a container for it: a row carrying one
    # sentence would be the conflation whatever that sentence said.
    assert integrity != re_derivability
    assert integrity not in re_derivability
    assert re_derivability not in integrity

    # And the bench says the check is its own, on the row rather than once at the top,
    # because what circulates is a row.
    assert "by the bench that produced the artefact" in verification["checked_by"]
    assert "scripts.verify" in verification["checked_by"]


def test_a_completed_run_with_no_signed_artefact_is_not_a_row(
    leakage_case: Case,
) -> None:
    """A run that finished on a bench with no key produced no artefact to list.

    Not an empty row and not a row with a reading of nothing: *never signed* is a
    fact about the run, and it is stated by name on that run's own report route and
    on the list of runs. A row here would be a document a reader could go looking
    for.
    """
    with completed([leakage_case], None) as served:
        body = _listed(served.client)
        assert served.record.status is RunStatus.COMPLETED
        refusal = served.fetch("/verification").json()["detail"]

    assert body["artefacts"] == []
    assert refusal["outcome"] == "never_signed"
    # And the list says which fact an absent artefact is, so a reader looking for a
    # run they know completed is not left to conclude the list dropped it.
    assert "never_signed" in body["statement"]


def test_a_run_with_no_artefact_is_skipped_without_disturbing_the_rows_around_it() -> (
    None
):
    """The rows are the artefacts, in the order the records arrived.

    The order is the record's — most recently recorded first, as `BenchRuns.records`
    decided — and it is not re-sorted here: a screen that sorted the rows again would
    be a second opinion on which artefact is the most recent one.
    """
    key = generate()
    artefact = signed(a_payload(), key)
    records = [
        a_record("first", artefact),
        a_record("no-artefact", Unsigned()),
        a_record("second", artefact),
    ]

    listed = artefacts_response(records, ReportConfig(pinned=key.public_key()))

    assert [row.target for row in listed.artefacts] == ["first", "second"]


def test_nothing_on_this_list_is_a_figure_a_mark_or_a_summary_of_the_rows() -> None:
    """No count, no total, no tick, and nowhere for one to be printed.

    The structural half is the one that matters: a mark over the three results is not
    absent because nobody drew it, it is absent because the row has no field for it.
    The scan is the second half — the only integer anywhere on this list is the
    artefact version, so no rate, no band, no count of artefacts and no figure over
    them has arrived under a name nobody read.
    """
    key, other = generate(), generate()
    body = artefacts_response(
        three_artefacts(key, other),
        ReportConfig(signing_key=key, pinned=key.public_key()),
    ).model_dump(mode="json")

    assert set(ArtefactRow.model_fields) == {
        "run_id",
        "target",
        "recorded_at",
        "files",
        "verification",
    }
    assert set(ArtefactList.model_fields) == {
        "artefacts",
        "statement",
        "verify_command",
    }
    assert set(ArtefactFile.model_fields) == {"filename", "path", "holds"}

    # Nothing named for a figure over more than one family, and nothing named for a
    # mark: a `status`, a `severity` or an `icon` beside a target's name is the badge
    # this project refuses (ADR-0005, D3, D12).
    for key_name in _keys(body):
        assert not [word for word in FORBIDDEN_IN_A_KEY if word in key_name], key_name
        assert not [
            word
            for word in ("severity", "badge", "tick", "icon", "colour", "color")
            if word in key_name
        ], f"{key_name} reads as a mark rather than as a result"

    # And no target passes or fails anything: an artefact is a document about a
    # target, and a target has rates, intervals and bands (ADR-0018).
    for row in body["artefacts"]:
        for sentence in _sentences(row):
            for verdict in (f"{row['target']} passed", f"{row['target']} failed"):
                assert verdict not in sentence, verdict

    assert _numbers(body) == {ARTEFACT_VERSION}


def test_a_bench_that_has_produced_no_artefacts_answers_with_no_rows() -> None:
    """An empty list is a `200` with nothing on it, and never a refusal.

    A fresh deployment has produced nothing, and an engineer opening the console for
    the first time is in exactly that state.
    """
    client = TestClient(create_app(BenchConfig(cases=[], report=ReportConfig())))
    response = client.get(ARTEFACTS_ROUTE)

    assert response.status_code == 200
    assert response.json()["artefacts"] == []
    assert response.json()["verify_command"] == VERIFY_COMMAND


def test_the_default_reading_is_run_against_the_key_a_recipient_pins() -> None:
    """A bench that pinned nothing is read against the committed key, not its own.

    The default is the key whose fingerprint the README publishes, because a bench
    verifying its own artefacts against its own signing key would report *valid* on
    every report it ever produced — including the ones no recipient can check.
    """
    key = generate()
    body = artefacts_response(
        [a_record("signed-by-a-key-nobody-published", signed(a_payload(), key))],
        # The bench's own signing key, and no pinned key: the reading has to be run
        # against the committed one anyway, which is what makes this row say *no
        # recipient can check this* rather than *valid*.
        ReportConfig(signing_key=key),
    ).model_dump(mode="json")

    [row] = body["artefacts"]
    signature = row["verification"]["signature"]
    assert signature["outcome"] == SignatureOutcome.ANOTHER_KEY.value
    assert fingerprint(public_key()) in signature["statement"]
    assert fingerprint(key.public_key()) in signature["statement"]


def _listed(client: TestClient) -> dict[str, Any]:
    response = client.get(ARTEFACTS_ROUTE)
    assert response.status_code == 200
    return cast(dict[str, Any], response.json())


def _sentences(node: Any) -> Iterator[str]:
    """Every string anywhere in the response, however deeply nested."""
    if isinstance(node, dict):
        for value in node.values():
            yield from _sentences(value)
    elif isinstance(node, list):
        for value in node:
            yield from _sentences(value)
    elif isinstance(node, str):
        yield node


def _keys(node: Any) -> Iterator[str]:
    """Every key anywhere in the served document, however deeply nested."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield str(key)
            yield from _keys(value)
    elif isinstance(node, list):
        for value in node:
            yield from _keys(value)


def _numbers(node: Any) -> set[int]:
    """Every integer anywhere in a response, timestamps excluded.

    `recorded_at` is dropped because it is digits around a decimal point and nothing
    else: a scan that read the clock would fail on the second it ran rather than on a
    figure anybody printed.
    """
    if isinstance(node, bool):
        return set()
    if isinstance(node, int):
        return {node}
    if isinstance(node, dict):
        return set().union(
            *(_numbers(value) for key, value in node.items() if key != "recorded_at"),
            set(),
        )
    if isinstance(node, list):
        return set().union(*(_numbers(value) for value in node), set())
    return set()
