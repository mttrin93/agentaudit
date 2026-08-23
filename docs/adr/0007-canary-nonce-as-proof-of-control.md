---
status: accepted
---

# The leakage canary is the proof of control

"The endpoint must be staging or sandbox" was a sentence with no mechanism behind it, on a tool that takes a URL and a bearer token from a form and fires jailbreak payloads at whatever answers. Deployed to a live URL, that is functionally an **open attack proxy**. Ownership heuristics are not available: domain denylists and guesses about what "looks like production" are unreliable and would reject legitimate targets while admitting illegitimate ones.

**Decision.** The data-leakage family already requires a canary token planted in the target's system prompt, and **only someone who can edit the target's configuration can plant it.** The bench issues a nonce at registration, and no run starts until the target echoes it back under the leakage probe. Authorisation therefore falls out of a mechanism the bench already needs, with no new heuristics and no new trust assumptions.

## Consequences

- **Explicit three-part attestation at registration**, with the consequences spelled out rather than implied: authorised to test this endpoint; this is a staging or sandbox environment; accepts that these payloads will generate provider policy violations against the user's own account and consume their inference budget. The second consequence is one a user would never infer, so it must be stated.
- **Attestation is recorded** — timestamp, identity, endpoint hash — into the Article 12 log **and** the report's provenance block. Record-keeping then does real work in this design instead of being the article that merely "applies to all six rows", and the compliance obligation doubles as the liability record.
- **Enforced run budget:** declared maximum calls per run, hard abort on breach, and an estimated call count and cost shown *before* the user confirms. A target run is 6 families × 3 cases × 10 attempts = 180 target calls plus retries, on the user's inference spend — that is `LLM06:2026 Unbounded Consumption`, denial of wallet, performed by the bench on its own user. Cost display is therefore a **consent mechanism, not a convenience feature**.
- **The adaptive layer makes the budget load-bearing rather than prudent, and it must be presented as two numbers.** An adaptive attacker ([ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md)) spends the user's inference budget unpredictably, so the estimate now covers a fact and a bound, and blending them would hide which is which:

  ```
  Fixed suite      180 calls   exact — arithmetic, 6 × 3 × 10
  Adaptive layer  ≤ 96 calls   ceiling — worst case, 6 families × T=8 × k=2
                  ─────────
  Total           ≤ 276 calls
  ```

  Showing an *average* adaptive cost would be worse than showing nothing: it invites a run to exceed what the user agreed to. The ceiling is enforced at **two levels** — a per-episode turn cap and a whole-layer call ceiling — because a per-family cap multiplied by six families is a multiplication a user consents to once and then forgets.
- **Amended by #5, on two figures the table above does not show.** The estimate the
  bench presents reads **181** per target rather than 180, because the nonce echo
  probe is a call on the operator's endpoint like any other and a consent figure
  that omitted it would understate the run. It is still exact arithmetic, and the
  extra call is published in the figure's own stated basis rather than absorbed
  into it. Separately, the **enforced** ceiling is not the estimate: it is the
  estimate with every message retried to its target's own transport limit, summed
  per target. Both are shown, both carry `≤`, and the larger is the one enforced —
  a run may not exceed anything it was shown with a `≤` in front of it. Building
  the ceiling from the same retry limit is what lets the budget be checked *before*
  each message rather than detected after it, so a run inside its arithmetic is
  never aborted early and a run outside it never overspends.
- **Cost is declared by the operator, never estimated by the bench.** A target is
  the operator's endpoint on the operator's provider, so the price per call is
  theirs. A run with no price declared reports its cost as *not priced* rather than
  as zero — an unknown cost and a free run are different facts, and only one is
  safe to confirm without reading further. What is priced rounds up.
- **A mid-episode abort records the episode as censored, never as resisted.** Budget exhaustion that read as target strength would be infrastructure scored as a security result, which is the discipline this project already applies to timeouts, 401s, malformed replies and rate limits, arriving at a new surface. Censoring is also the statistically correct treatment — see [ADR-0011](./0011-the-adaptive-attacker-is-label-blind.md).
- The "security guard" is the **authorisation guard**, not a prompt-injection filter on the bench's own model, and it is in scope rather than optional. A tool whose function is attacking network endpoints does not file its authorisation control under optional extras.
- **Amended: an operator may waive the echo, and the artefact carries that they did.**
  The requirement above assumed every operator can write into the configuration of
  the agent they are testing, and that is not true of a third-party or hosted agent
  somebody else deploys. A run may now start on the declaration alone. Three things
  hold it honest, and all three are mechanism rather than wording:

  - **The probe is still sent.** What the waiver changes is whether a missing echo
    *stops* the run, never what the bench looks at. `Registration` carries `echoed`
    and `waived` as two fields, and no code path writes the declaration into the
    first — a target that echoes anyway proved control, whatever was declared.
  - **The data-leakage family is not run.** The nonce is that family's canary, so an
    unplanted value means thirty attempts against a string nowhere in the target and
    a clean rate against an attack that was never possible. It is dropped by
    `plan_for` and reported as a declared gap, the same treatment the unplanted
    indirect-injection note gets, and the estimate does not charge for it.

    **Amended by [ADR-0024](./0024-a-planted-canary-that-will-not-be-echoed-is-still-measurable.md):
    this bullet holds for an unplanted value, which is the case the amendment above
    was written for, and not for the waiver as such.** A target that planted the
    canary and refuses to repeat it on request has the value in place, so the family
    is measurable and is run. The two statements are two declarations there —
    `nonce_planted` decides the family, `echo_waived` decides whether a missing echo
    stops the run — and `plan_for` still reads only the first.
  - **The report says which it was.** `control_proved` travels in the provenance
    block beside the attestation, inside the signed bytes and printed in the
    rendering: *proved* against an endpoint that echoed, *declared, and not proved*
    otherwise. An unchecked attestation and a checked one are not the same evidence,
    and a document that presented them alike would be the relaxation costing a
    recipient something rather than the operator.

  **A waived run carries no nonce.** The value has two jobs and that run has
  neither: it is the proof of control, which was waived, and it is the leakage
  canary, whose family was dropped. So `POST /runs` does not check the issued set
  for one — requiring a value nobody plants and nothing reads would be a button
  press standing in for a guard that is already gone, and a bench that holds issued
  nonces in memory would refuse a run whose operator did everything asked of them
  and waited through a restart. A waived run that does carry a nonce is still
  checked against the issued set.

  What this gives up is real and is not recovered by any of the three: on a waived
  run, nothing separates an operator testing their own agent from anyone testing
  anyone's, which is the property the decision above was written to establish. The
  waiver is per run, declared in the request, and there is no setting that turns it
  on for the next one.
