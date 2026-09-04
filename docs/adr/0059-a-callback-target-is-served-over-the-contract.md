---
status: accepted
---

# A callback target is served over the contract, and no in-process branch is added

A target is a URL and `send_message` is the only path to one. Group J (#81) adds a
second *way in* for somebody whose agent is a Python function rather than a deployed
endpoint, and the question that arrives with it is whether the bench grows a second
path in as well.

**Decision.** `backend/bench/shim.py` **serves** the callback. `serve_callback` wraps
it in a FastAPI app on an ephemeral loopback port, generates the bearer token, and
yields a `TargetConfig` describing that endpoint. `contract.py` is untouched: no
`callback` field, no dispatch, and nothing anywhere in the bench knows whether a
target it is measuring is a URL somebody deployed or a function somebody wrote.

## 1. What the rejected design gives up

Design B is cheaper by every measure a diff can see: a `callback` field on
`TargetConfig` and a branch at the top of `send_message`, no thread and no port. It
was rejected because it produces **two `send_message`s** — the one the gate measured
over HTTP, and the one a user's callback run takes — and every property the bench
pays for in that one path is untested on the second:

- **`RetryPolicy`, and sends counted apart from attempts.** A retry is not an
  attempt, because if it were, an endpoint having a bad minute would read as an agent
  that defended itself. That arithmetic lives in the loop inside `send_message`.
- **The named `TargetFailure`s, raised as `TargetUnreachable` rather than scored.**
  Six named outcomes and one sentence — `NOT_A_SECURITY_RESULT` — attached to all of
  them, none of which a branch above the loop ever reaches.
- **`DEFAULT_TIMEOUT` and its relationship to the two waits inside it.** Sixty
  seconds is the outer wait of a chain of three, held apart deliberately
  (`contract.DEFAULT_TIMEOUT`). A callback invoked in-process has no wait at all, so
  a callback that hangs hangs the run.

A callback that raised would have to acquire its own vocabulary for all of that, in a
branch, beside the one that has it — and the branch would be the path *no gate run
ever exercises*, which is the thing the module docstring of `contract.py` refuses:
*"there is deliberately no in-process branch for the reference agents: they are
reached over this same path, so the gate exercises the code a user's run exercises."*

Serving costs a thread and a port. The spec already accepts that cost for the
reference agents — *"calibration needs a server fixture and runs slower than an
in-process equivalent"* (`backend/targets/reference/serving.py`) — and
`serve_callback` is built on the same `serving.serve`.

**Two tests hold the property, and both were driven red by actually writing design B.**
`test_the_contract_knows_nothing_about_a_callback` reads `contract.py`'s source, on
`test_transport.py`'s reasoning that this regression is reachable by a *name* rather
than by an argument, and additionally asserts that no field of `TargetConfig` is
callable-typed — there is nowhere for a branch to sit. The discriminating one is
`test_a_shim_target_is_unreachable_once_its_server_is_gone`: after the context
manager exits, a send to the same `TargetConfig` must raise
`TargetFailure.UNREACHABLE`. Under design B it would still get a reply, because a
branch does not need the port. Design B fails ten of the fifteen tests in
`backend/tests/test_callback_shim.py`.

## 2. What is served, in security terms

This endpoint exists to be sent jailbreak payloads, so its shape is small and none of
it is configurable:

- **Loopback only.** `serve_callback` passes no host to `serving.serve`, and there is
  no host parameter, so a user's function cannot be published to a network by passing
  an argument. The port is ephemeral and belongs to the `with` block.
- **One route.** `POST /messages`, and nothing else. `server.py`'s
  `PUT /reference/{agent}/nonce` is test equipment for agents this repository ships;
  a user's callback gets nothing like it. The planting hooks of #85–#87 are a
  **pre-run step**, off this surface rather than a route on it, precisely so that no
  route exists by which a plant could become an attempt.
- **The token is generated, not accepted.** `secrets.token_urlsafe(32)` per served
  callback, compared with `secrets.compare_digest`, absent from every reply — and
  there is **no `auth_token` parameter**, so a caller cannot serve a callback under a
  token they chose, reused across runs, or committed to a repository. A test asserts
  the parameter's absence, because adding one is the obvious convenience and it is the
  whole of the property.
- **The message is data.** It is handed to the callback as a `str`. This module does
  not interpret it, template it, or evaluate it.
- **A raise says nothing.** The reply body is the fixed string `CALLBACK_RAISED`. The
  exception and its traceback go to the module logger, where they are the operator's
  own to read. A traceback crossing the socket — a file path, a credential in a repr,
  the system prompt — would be a disclosure the bench *caused* rather than one it
  measured. The test for this reads the body off the wire and not off the exception,
  because `TargetUnreachable` carries no body and asserting against it would pass
  whatever the endpoint said.
- **`_create_callback_app` is private.** A public app builder taking a token would
  put the choice the bullet above removes one import away, and `serving.serve` is
  right there. The claim above is about the module, not only about one function.
- **The request body is validated by the contract's own model.** `MessageRequest`,
  `MessageReply`, `ToolTracePayload` and `ToolCallPayload` are imported from
  `server.py` rather than restated, so a shim target cannot drift off the one contract
  the bench speaks — the reasoning `backend/tests/flaky_target.py` is built on,
  applied to a surface a user reaches.

## 3. An exception from the callback is a transport failure, named

A raise becomes HTTP 500. That status is in `contract.TRANSIENT_STATUSES`, so the
retry policy sees it: a callback that falls over once is retried like any other bad
minute, and the sends it cost are recorded on `Transcript.sends` against **one**
attempt. A callback that falls over on every send exhausts the policy and stops the
run as `TargetFailure.UNAVAILABLE`, with no attempt recorded — never a verdict.

**Zero attempts is asserted from the callback's own side**, because a run that raised
returns no result to count them from: an attempt is one execution of one case, so a
run with none is a run in which no case payload ever went out. The test records every
message the callback saw and asserts it saw the registration echo probe three times
and nothing from the case. Driven red by letting registration complete, at which
point the payload appears in that list.

**An agent that crashed did not defend itself.** The alternative was answering a raise
with something the bench could read, and every version of that is worse in the one
direction a bench must never fail in: an empty reply scores as *resisted*, so a
crashing callback would report as a well-defended agent. Both halves are held by
tests, and the red drive for them was exactly that mistake — answering a raise with
`{"reply": ""}` — which moves the sends count to 1 and turns the named failure into a
clean run.

## 4. `exposes_tool_calls` is derived from the callback, not declared to the shim

Every other target's `exposes_tool_calls` is the operator's word about a URL the bench
cannot see inside, and the bench finds out it was wrong on the first reply —
`NotMeasurable.TRACE_DECLARED_BUT_ABSENT`. **On this surface the bench built the
endpoint, so it is the one target property that can be checked before a single
message is sent**, and taking a declaration for it anyway would be throwing that
away.

**The derivation is the callback's return annotation, read exactly:**
`exposes_tool_calls_of` resolves it and asks whether it *is* `Turn`. A union, an
unannotated function, a lambda and an annotation that cannot be resolved from the
callback's own module all read as no visibility — the conservative direction, and the
default the field already has.

**Enforcement runs in one direction, and the asymmetry is the decision.**

- A callback annotated `-> Turn` that answers with a bare string raises
  `CallbackBreachedItsAnnotation`, which becomes a 500 and so a named transport
  failure. This is the direction that would otherwise reproduce
  `TRACE_DECLARED_BUT_ABSENT` here, so a shim target that declares visibility never
  emits a traceless reply and that reason is **unreachable** on this surface rather
  than merely unlikely.
- A trace from a callback registered *without* visibility is **dropped, with a
  warning logged**. The two families that read a trace were withdrawn before anything
  was sent, so nobody is waiting for it; passing it through would measure a family
  the registration withdrew, and refusing it would end a run over evidence nobody was
  going to read. The warning is there because the operator is the only person who can
  turn this into a measurement — annotate the callback `-> Turn` — and they can only
  do that if they are told.

**`Callback` is a union of two protocols, and not one protocol returning
`str | Turn`.** #82 writes the required signature as
`__call__(message, session_id) -> str | Turn`, and that union is exactly what this
decision reads, so a *single* callback annotated with it would be declaring a
visibility it has only sometimes. The first draft of this module took that reading —
"the annotation mentions `Turn`" — and it built a trap: a callback written with the
protocol's own signature derived visibility and then ended the run the first time it
answered in text, which is the common case §5 exists to protect. `TextCallback` and
`TracingCallback` move the failure from a turn later to the call site, where `mypy`
reports it: a function returning `str | Turn` satisfies neither, and a test asserts
that `mypy` says so.

**Two rejected alternatives.** An `exposes_tool_calls` *argument* to `serve_callback`
is one line shorter and is a declaration — the operator saying what their function
does, on the single surface where the bench can read the function. A **setup-time
probe** — calling the callback once with a synthetic message and looking at what came
back — was the other, and it lost because it calls a user's agent with a message the
operator did not authorise and charges them for it, off every counter. Reading an
annotation is unusual for this codebase and is admitted as such; what buys it is that
it is checked by `mypy` in the user's own repository, costs no call against their
agent, and is available before anything is sent.

## 5. A trace absent and a trace empty stay two answers

`Turn.tool_trace` is **required**, which is the whole reason `Turn` exists beside a
bare `str`. A callback with no visibility says so by returning a string, and the shim
never invents an empty trace on its behalf.

On the wire that distinction survives as an **absent key** versus `{"calls": []}`, held
by `response_model_exclude_none=True` on the route. Both readings are already in the
bench — `Transcript.tool_trace` answers `None` for the first, which makes two families
*not measurable*, and an empty `ToolTrace` for the second, which is a measured
*resisted* — so the shim's job is only to not collapse them. It would have collapsed
them by default: FastAPI serialises the optional field as `tool_trace: null`, and the
red drive for this was removing that one keyword.

## 6. What is deliberately not here

No planting hook, no `teardown()`, and no run-scoped namespace: those are #84 through
#87, and each is a decision of its own. No optional hooks of any kind, so `Callback`
requires exactly `__call__(message, session_id)` and is a `Protocol` rather than a base
class — nothing about a user's agent should have to inherit from this bench to be
measured by it.

**A known cost, stated rather than discovered.** `serve_callback` forwards the
operator's declarations one keyword at a time, so a new declaration on `TargetConfig`
is an edit here as well. The alternative — taking a template `TargetConfig` and
`replace()`-ing the three the shim owns — makes a caller pass a `url` and an
`auth_token` that are about to be thrown away, which is worse at the one seam whose
whole purpose is that a user needs no endpoint. #84 revisits it if the hook set makes
the signature worse.

`serve_callback` forwards the operator's declarations — `declared_tools`,
`declared_controls`, `retains_session_state`, `holds_personal_records` and the four
the Agents Rule of Two is read over — untouched, because those are statements about
the agent wherever it lives. The three the shim decides for itself are `url`,
`auth_token` and `exposes_tool_calls`, and there is no parameter for any of them.

Nothing here writes into a scored rate. A shim target is measured by the code a URL
target is measured by, which is the point of the decision above and the reason this
group can claim its results are about a user's run.
