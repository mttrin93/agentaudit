"""The bench over HTTP, where every status code becomes a name.

**This is the only place in the package a status code is read.** Four named failures
leave this module and no caller branches on a number, for the reason the API's own
`ReportRefusal` gives on the other side of the wire: the name is the field a caller
branches on and the sentence is the one a person reads, and a status code carries
neither. A `409` means one thing on the report route and something else on the
approval route, so a tool that matched on `409` would be a tool that had to know
which route it had called — and the caller here is a model, which is the reader least
able to hold that.

**It assembles a request body and translates an answer, and does nothing else.** No
retry, no polling loop, no state between calls, and no figure computed from anything
it reads: what comes back out is what came back in, keyed as the route keyed it
([ADR-0006](../../docs/adr/0006-every-figure-is-derived-from-the-record.md)). The
consent seam is the example that matters — `start` stops at the estimate and `approve`
is a second call — and it is held on the far side of the route rather than here
([ADR-0100](../../docs/adr/0100-the-mcp-server-has-no-privilege-the-console-lacks.md)).

**The routes are spelt here and held by tests against the real app.** Importing them
from `app.py` would pull the bench in behind them — that module's graph reaches the
scorer, the library and the signing key — so the paths below are written twice, once
in `app.py` and once here. What keeps the two in step is that
`test_mcp_client.py` runs against the app `create_app` builds, with no recorded
responses anywhere in it: a route that moves breaks this client in CI on the same
commit that moves it.

**The case-library lease is deliberately not translated.** `LibraryBusy` is answered
on one route, `api/gate_runs.py`'s, because the lease is a gate run's and never a
target run's — so no call on this client can meet it. A fifth name for a condition
this surface cannot reach would be a name nobody could ever act on.
"""

from __future__ import annotations

from typing import Any

import httpx

from backend.mcp.declaration import Declaration

NONCES_ROUTE = "/nonces"
RUNS_ROUTE = "/runs"
APPROVAL_ROUTE = "/runs/{run_id}/approval"
REPORT_ROUTE = "/report/{run_id}"

ARTEFACT_ROUTES = {
    "payload": REPORT_ROUTE,
    "rendering": f"{REPORT_ROUTE}/rendering",
    "signature": f"{REPORT_ROUTE}/signature",
    "verification": f"{REPORT_ROUTE}/verification",
}
"""Where one run's artefact is served, keyed as a caller would name the four files.

The three files that *are* the artefact and the verification that is a reading of
them, in `api/app.py:report_paths`'s order — a caller that saved the three under the
names they arrive with would still verify.
"""


class BenchUnreachable(RuntimeError):
    """Nothing answered at the base URL, so there is no status code to read.

    The likeliest failure on this surface and the one furthest from the bench: a
    caller reached for a tool against an API nobody started. It is named rather than
    left as a transport traceback because the remedy is a sentence — start the bench,
    or point at the one that is running — and because nothing in this package may
    start one itself (ADR-0100).
    """


class BenchRefused(RuntimeError):
    """The bench answered, and what it said was no.

    Carries the status and the route's own `detail`, because the detail is the only
    place the refusal says *which* thing was wrong. This is the general case and the
    three names below are the specific ones: a condition worth acting on differently
    gets its own type, and everything else arrives here with the bench's words intact
    rather than being sorted into a name this module invented for it.

    **`status` raises the one instance of this the bench did not send**, with a `404`
    nothing answered with, because an id that is on no row of `GET /runs` is a
    refusal only the reader of the list can notice — the route answered `200` and a
    list, and the absence is in it. It is this type rather than a fifth name because
    a caller acts on it exactly as it acts on the `404` the report route *does* send:
    there is no such run here, stop asking. `status` says so at the raise.
    """

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(f"the bench refused with {status}: {detail}")
        self.status = status
        self.detail = detail


class NoEstimate(RuntimeError):
    """The run reached no approval interrupt, so there is no estimate to confirm.

    Not a refusal and not a failure of the request: the body was accepted, nothing
    was sent to the target, and the graph did not get as far as presenting a cost.
    A caller that met this as `BenchRefused` would read it as a declaration it could
    fix by editing, and there is nothing in the declaration to fix.
    """


class ReportNotSigned(RuntimeError):
    """There is no signed artefact to fetch, and the bench named which fact that is.

    `outcome` is the refusal's own name — `never_signed`, `in_flight`,
    `did_not_complete`, `lost_with_its_process` — and the distinction it carries is
    the one `ReportRefusal` was written for: a run to ask again about and a run that
    will never have a report share this status code, and a caller that could not tell
    them apart would poll for the lifetime of the process.
    """

    def __init__(self, outcome: str, reason: str) -> None:
        super().__init__(f"{outcome}: {reason}")
        self.outcome = outcome
        self.reason = reason


def _parsed(response: httpx.Response) -> Any:
    """This response's body as JSON, or its text where it is not JSON at all."""
    try:
        return response.json()
    except ValueError:
        return response.text


def _raised_detail(response: httpx.Response) -> Any | None:
    """The `detail` one of this bench's own routes attached, or `None` for a body
    carrying none.

    The narrowing that tells a refusal this API raised from one that came from the
    framework or from something in front of it. `detail` is FastAPI's key for an
    `HTTPException` and nothing else on this wire writes it, so the *presence of the
    key* is the fact keyed on — never the sentence beside it, which a translation
    keyed on prose would stop being correct about the day somebody rewords it.
    """
    body = _parsed(response)
    if isinstance(body, dict) and "detail" in body:
        return body["detail"]
    return None


def _detail(response: httpx.Response) -> Any:
    """The route's `detail`, or the body it sent instead of one.

    A refusal this bench raised carries a `detail` — a sentence on most routes and a
    `Refusal` object on the report routes. Anything else came from the framework or
    from something in front of it, and is handed on as the text that arrived rather
    than as an empty string: a refusal nobody can read is worse than an ugly one.
    """
    raised = _raised_detail(response)
    return _parsed(response) if raised is None else raised


def _sentence(detail: Any) -> str:
    """That detail as the line a person reads, whichever shape it arrived in."""
    if isinstance(detail, dict) and "statement" in detail:
        return str(detail["statement"])
    return str(detail)


class BenchClient:
    """One conversation with a running bench, over a client the caller owns.

    Takes an `httpx.Client` rather than a base URL, so the process that decides where
    the bench is and how long to wait for it is the process that built the client —
    and so the tests can hand in the app itself. It closes nothing it did not open.
    """

    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """One call, with the transport's failure named before anything is read."""
        try:
            return self._http.request(method, path, **kwargs)
        except (httpx.ConnectError, httpx.ConnectTimeout) as unreachable:
            # The connect-class failures only, and the narrowness is deliberate. A
            # read that timed out is a request that went out, and on `POST /runs`
            # that is a run this bench may well have started: told *nothing
            # answered*, a caller's next move is to start it again. Those surface as
            # what they are rather than as a name that invites a second spend.
            raise BenchUnreachable(
                f"no bench answered at {self._http.base_url}: {unreachable}. This "
                "surface runs against an API somebody else started, and starts none "
                "of its own (ADR-0100)"
            ) from unreachable

    def _answered(self, response: httpx.Response, expected: int) -> dict[str, Any]:
        """That response's body, or the refusal it is instead.

        The one place a status code is compared on the way out, so that the four
        calls below read as *what I asked for* and none of them carries its own
        idea of what a no looks like.
        """
        if response.status_code != expected:
            raise BenchRefused(response.status_code, _sentence(_detail(response)))
        return dict(response.json())

    def issue_nonce(self) -> str:
        """A value for the operator to plant, and only the value.

        `POST /nonces` answers with the probe and the statement beside it, both of
        which are for the screen that shows an operator what to do. What a caller
        plants is one string.
        """
        issued = self._answered(
            self._request("POST", NONCES_ROUTE), httpx.codes.CREATED
        )
        return str(issued["nonce"])

    def start(self, declaration: Declaration) -> dict[str, Any]:
        """Register the target, present the estimate, and stop in front of it.

        The body is `StartRunRequest`'s and every field of it comes from the
        committed declaration — nothing is defaulted here, because a default applied
        on the way to the wire is a declaration this surface made rather than read
        (`declaration.py`). The run comes back holding its interrupt, which is
        before anything has been sent to the target.
        """
        response = self._request("POST", RUNS_ROUTE, json=_body(declaration))
        if response.status_code == httpx.codes.INTERNAL_SERVER_ERROR:
            raised = _raised_detail(response)
            if raised is not None:
                # A `detail` means this 500 is one the route raised, and
                # `NeverPresented` is the only one it raises. Keyed on the route
                # rather than on the sentence it wrote — a translation keyed on
                # prose stops being correct the day somebody rewords it — and
                # narrowed by the presence of a `detail` so that a 500 the route
                # did not mean, which arrives as the framework's own plain text or
                # as a body with no `detail` in it, is not reported as a graph that
                # reached no interrupt.
                raise NoEstimate(_sentence(raised))
        return self._answered(response, httpx.codes.ACCEPTED)

    def approve(
        self, run_id: str, *, identity: str, confirmed: bool, reason: str = ""
    ) -> dict[str, Any]:
        """Answer the halt. On a yes the suite runs; on anything else it does not.

        `confirmed` is keyword-only and has no default, which is the one argument on
        this client that must be written out at every call site: the yes is the whole
        of the consent seam, and a default would be one somebody could reach by
        omission.
        """
        return self._answered(
            self._request(
                "POST",
                APPROVAL_ROUTE.format(run_id=run_id),
                json={"confirmed": confirmed, "identity": identity, "reason": reason},
            ),
            httpx.codes.OK,
        )

    def status(self, run_id: str) -> dict[str, Any]:
        """Where this run has got to: its row of `GET /runs`, and no more than a row.

        The list route rather than the per-run progress route, because that is the
        route ADR-0100 §1 names for this tool — *`run_status` is this run's row of
        `GET /runs`* — and a row is what the question wants: the standing, the
        record's own sentence for it, and the two spends. The progress route serves
        a screen's worth of a run in flight, including the last exchange, and none
        of that is what a caller polling for *is it done* is asking.

        A read and never a wait: the suite is minutes long and the poll belongs to
        the caller, so this returns whatever is true now.
        """
        listed = self._answered(self._request("GET", RUNS_ROUTE), httpx.codes.OK)
        for row in listed["runs"]:
            if row["run_id"] == run_id:
                return dict(row)
        raise BenchRefused(
            int(httpx.codes.NOT_FOUND),
            f"no run {run_id} is on this bench's record. A run is on the list from "
            "the moment its attestation is taken, so an id that is not here was "
            "issued by a different bench or by a process that has ended",
        )

    def report(self, run_id: str) -> dict[str, Any]:
        """The signed payload, as the bytes that were signed, decoded.

        Decoded here and not re-encoded anywhere: what a caller reads figures out of
        is this document, and the bytes a recipient verifies stay on the route. A run
        with no artefact is `ReportNotSigned` and names which of the four facts it is.
        """
        response = self._request("GET", REPORT_ROUTE.format(run_id=run_id))
        # Read on the refusal and never on the way past it: on a `200` this body is
        # the signed payload, and parsing it here to ask whether it is a refusal
        # would decode the whole document twice to answer a question about a status.
        detail = (
            _raised_detail(response)
            if response.status_code == httpx.codes.CONFLICT
            else None
        )
        if isinstance(detail, dict):
            # The `409` and not the `404` beside it. Both carry a `Refusal`, but the
            # `404`s are *no such run* and *lost with its process* — an id nobody
            # can fetch a report for, which is a different thing from a run whose
            # report does not exist, and calling it *not signed* would say something
            # about a run this bench has no record of.
            raise ReportNotSigned(str(detail["outcome"]), _sentence(detail))
        return self._answered(response, httpx.codes.OK)

    def artefact_urls(self, run_id: str) -> dict[str, str]:
        """Where this run's artefact is served, and nothing fetched to find out.

        Nothing here asks the bench whether they exist, because the answer to that is
        `report` above and it has a name for every way it is no.
        """
        return {
            name: str(self._http.base_url.join(route.format(run_id=run_id)))
            for name, route in ARTEFACT_ROUTES.items()
        }


def _body(declaration: Declaration) -> dict[str, Any]:
    """`StartRunRequest`, as three objects and three flags.

    Flattened out of one record on the way in and expanded back into three tables on
    the way out, because a TOML file is three tables and a request body is three
    objects. Nothing is renamed in either direction: the file, this body and
    `TargetRequest` are one vocabulary, and a translation table between them would be
    the place a field quietly stopped arriving.
    """
    target: dict[str, Any] = {
        "name": declaration.name,
        "url": declaration.url,
        "auth_token": declaration.auth_token,
        "agent_type": declaration.agent_type,
        "exposes_tool_calls": declaration.exposes_tool_calls,
        "declared_tools": list(declaration.declared_tools),
        "retains_session_state": declaration.retains_session_state,
        "holds_personal_records": declaration.holds_personal_records,
        # `None` goes on the wire as `None`, because unstated is one of the
        # three answers and not the absence of one (ADR-0102).
        "processes_untrusted_input": declaration.processes_untrusted_input,
        "reaches_private_data": declaration.reaches_private_data,
        "changes_state_or_communicates": declaration.changes_state_or_communicates,
        "under_human_supervision": declaration.under_human_supervision,
    }
    if declaration.sends is not None:
        # Left off the body entirely where the file does not say, rather than sent
        # as a `None` the way the four above are. The difference is which end owns
        # the default: those four have none and unstated is an answer, while `sends`
        # has one that `TargetRequest` builds from `RetryPolicy` — behind the wall
        # this package may not import (ADR-0100) — so the key's absence is how the
        # route gets to apply it.
        target["sends"] = declaration.sends
    return {
        "target": target,
        "attestation": {
            "identity": declaration.identity,
            "authorised_to_test": declaration.authorised_to_test,
            "not_production": declaration.not_production,
            "accepts_provider_policy_and_cost": (
                declaration.accepts_provider_policy_and_cost
            ),
        },
        "nonce": declaration.nonce,
        "cost": {
            "price_per_call": declaration.price_per_call,
            "currency": declaration.currency,
        },
        "note_planted": declaration.note_planted,
        "nonce_planted": declaration.nonce_planted,
        "echo_waived": declaration.echo_waived,
    }
