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
- The "security guard" is the **authorisation guard**, not a prompt-injection filter on the bench's own model, and it is in scope rather than optional. A tool whose function is attacking network endpoints does not file its authorisation control under optional extras.
