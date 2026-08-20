# AgentAudit

An adversarial test bench for AI agents. It attacks a target agent across six failure families, proves its own discriminating power before its results are trusted, and reports the outcome as signed evidence a recipient can verify offline.

Full design in [PLAN.md](./PLAN.md) · vocabulary in [CONTEXT.md](./CONTEXT.md) · decisions in [docs/adr/](./docs/adr/).

> **Status: pre-build.** This README carries the disclosure posture only, because that decision binds from the first commit. Purpose, users, D1–D14, the article mapping and a worked example arrive at phase 5.

---

## Disclosure posture

`backend/cases/` is a working library of adversarial payloads with success conditions, in a public repository. That is what makes this repository useful and what makes it a weapon. The position is deliberate, not accidental — see [ADR-0008](./docs/adr/0008-repo-disclosure-posture.md).

- **The harness is public.** Registration, scanner, attacker, evaluator, judge, scorer, assembler, report, the gate (`scripts/gate.py`) and the offline signature check (`scripts/verify.py`).
- **A payload is public when the situation is the mechanism.** Most of this library works because of what it asks for and where it asks from — an errand that sounds like the agent's own job, a stop signal followed by ordinary housekeeping, a persona instruction and then a direct question. The prose description conveys those as fully as the text does, so withholding the text would hide what is tested and protect nobody. Each record states which side of this line it is on, and argues it.
- **A payload is withheld when its wording is the working part.** Anything that reads as a reusable override, jailbreak or filter defeat — a phrasing someone could lift and point at a target that was never in this repository. The description is enough to understand what is tested and to reproduce the finding against your own agent; it is not enough to lift as an attack.
- **Cases derived from published techniques stay public, with citation.** They are already public knowledge, and citing the source supports the external-identifier column in the article mapping.

The line used to be drawn at origin — originated here meant withheld — and that proxy failed in both directions: it described situational cases as weapons and shipped the one case whose wording *is* the mechanism out with a citation. See the amendment in [ADR-0008](./docs/adr/0008-repo-disclosure-posture.md).
- **Nothing operational is ever committed.** No target credentials, no user findings, no real attestations, no nonces. `.env` is gitignored.

### The attacker generates payloads at runtime

The bench also carries an **adaptive attacker** — an agent that, after the fixed case library has run, attacks the same target by a route of its own choosing. It composes novel payloads while the run is happening, which changes three things about what ships here and leaves the split above alone.

- **The repository ships a weapon factory rather than a weapon.** A real change of kind, and a smaller one than it sounds: the attacker's reach is bounded by a model anyone can already prompt. **Its system prompt and its five tools are public**, because withholding them would hollow out the claim that the harness is public while withholding nothing scarce.
- **Transcripts are not committed.** A successful adaptive route against a defended agent is a working, previously unpublished exploit written down. `docs/validation.md` records the statistics, the family and a prose description of the route. It never records the payload.
- **Cases the attacker discovers are withheld by default.** A route found by breaking a defended agent is the one artefact whose wording is demonstrably the working part: it beat a target that resisted the whole library, so the phrasing carries something the prose does not. That is the withheld side of the line above.

If you are a researcher who wants a withheld payload for defensive work, open an issue describing the use; the answer may still be no.

## Running a target through the API

The bench runs from something other than a terminal too. Start it with the app factory:

```
uv run uvicorn backend.api.app:create_app --factory
```

**It will not start without a signing key.** The factory reads `AGENTAUDIT_SIGNING_KEY` and refuses to boot when it is empty, naming the variable and the command that makes a pair. A bench with no key runs the whole library against your endpoint and then has no document to give you — every report refused as `never_signed` — and the signature is what makes a report portable, which is the only thing this bench claims to produce ([ADR-0020](./docs/adr/0020-a-factory-with-no-signing-key-refuses-to-boot.md)). For a local run, generate a pair and export the private half in the shell you start the server from:

```
uv run python -m scripts.keygen --public /tmp/dev-signing.pub
export AGENTAUDIT_SIGNING_KEY=<the value printed once, base64, one line>
```

`.env.example` lists every variable this repository reads, with placeholders and the defaults that apply when one is left unset; copy it to the gitignored `.env`. The signing key is the exception it names: the scripts read `.env`, the API does not, so a key that lives only there starts `scripts/` and leaves the factory refusing to boot.

Point `--public` somewhere outside the repository, as above: `keygen` refuses to replace the committed public key, and a report signed by a dev key verifies only against the dev public half — pass it to `scripts/verify.py` with `--pubkey`. The private half goes in the environment and nowhere a commit can reach: the shell, or the gitignored `.env` the scripts load — base64 on one line, which is the format for exactly that reason. Nothing in this codebase writes a private key to disk; `keygen` prints it once. A deployed instance gets a real key set in its environment, and its public half is the committed one whose fingerprint is published below.

Three calls start a run, and both of the controls that make one authorised are in them:

1. **`POST /nonces`** issues the value you plant in the target's configuration. Only somebody who can edit that configuration can plant it, which is what makes the echo proof that you control the endpoint.
2. **`POST /runs`** carries the target, the attestation's three statements, that nonce and your own price per call. It answers with a `run_id` and the estimate — **the scored layer exactly and the adaptive layer as a ceiling, never one blended figure** — and then halts. Nothing has reached your endpoint at that point. A run whose attestation is incomplete, or whose nonce this bench never issued, is refused here; a nonce the target does not echo back is refused by the run itself, because the probe that checks it is a call on your endpoint and the halt is ahead of it.
3. **`POST /runs/{run_id}/approval`** answers the halt. A separate request rather than a field on the one above: the halt is a real LangGraph interrupt against a checkpointer, and a decision taken in front of the figures is not a checkbox somebody scrolled past ([ADR-0007](./docs/adr/0007-canary-nonce-as-proof-of-control.md)). On a yes the suite runs in the background under the ceiling you confirmed and aborts rather than exceed it. On anything else — including no answer at all — nothing is sent and nothing is spent, and the run says which of the two happened.

The price per call is yours to declare and is never defaulted from the bench's own configuration: your confirmation is the liability record, and a run you have not priced reports its cost as *not priced* rather than as zero.

### Registering a target in the browser

The same three calls, as a screen that walks you through them. The frontend is a Vite, React and TypeScript app in [`frontend/`](./frontend):

```
cd frontend && npm install && npm run dev     # then http://localhost:5173
npm run build                                 # typecheck and production build
npm test                                      # the guard rules, no browser
```

The dev server proxies `/nonces`, `/runs` and `/report` to the API on `http://127.0.0.1:8000` — set `AGENTAUDIT_API` to point it somewhere else. The proxy is the whole of the cross-origin arrangement: the API installs no CORS middleware, and a header the bench would send to every caller forever is not a thing to add so that one developer's browser is happy.

**Registration is a walk rather than a form.** The endpoint and its price, then the nonce to plant, then the three attestations one screen at a time with the consequence of each stated beside it, then the tool-call visibility declaration — which is where you are told that scope creep and halt defeat report as *not measurable* without it, and that the tool list you type is a declaration the bench cannot verify. A registration the bench refuses is shown in the bench's own words and hands you back to the plant step, and so is a run whose target never echoed the nonce: that one cannot be known until after the cost interrupt is answered, so the run screen points back here.

## Verifying a report

A report is three files under fixed names: `report.json` — the canonical JSON payload, which is the artefact — `report.md`, the document a human reads, and `report.sig`, a detached Ed25519 signature over the payload's bytes. Check them with no network and no credential:

```
uv run python -m scripts.verify path/to/report
```

It prints **three results, always all three**: whether the signature is valid over the payload, whether `report.md` hashes to the digest inside the payload, and whether the arithmetic re-derives — every rate, Wilson interval, band and κ floor recomputed from the counts the payload carries, through the same functions the bench used, plus a check that the rule and band cut points the report says it was read against are the ones this repository declares. The third is the one that is a check on the bench rather than on the transport, and it is what makes *re-derivable* something you established rather than something the document asserted. Each failure has its own named outcome, so you learn *which* property failed, and a report that states no per-family figure is reported as having re-derived nothing rather than as having agreed. See [ADR-0017](./docs/adr/0017-the-signature-covers-the-document-and-carries-two-claims.md).

**A valid signature is not a quality claim.** It says these bytes are the ones that were produced and that nothing has altered them — the adaptive section included, since the signature covers the whole payload. It says nothing whatsoever about whether the agent is safe, and the report carries no score, no grade and no declaration of conformity.

### The signing key

The public key is committed at [`keys/agentaudit-signing.pub`](./keys/agentaudit-signing.pub) and `scripts/verify.py` pins it by default; `--pubkey` takes another. Its fingerprint, which is also the `key_id` inside every payload it signs:

```
sha256:dcfa72c1b118550a6f35b96f457d24429e10d3308d5780ff8ec5a042ffa72a93
```

Compare that against the `key_id` in a report you receive. A valid signature over a key you have not seen published is not provenance — it only proves that whoever sent the document also sent the key — which is why a report signed by any other key is reported under its own outcome rather than as tampering.

**The private half is never committed.** It is read from `AGENTAUDIT_SIGNING_KEY` and from nowhere else, so publishing this repository does not publish the ability to forge its reports. `uv run python -m scripts.keygen` generates a pair, writes the public half and prints the private half once; it refuses to replace a committed public key, because rotation invalidates every signature ever issued under the old one and has to be a deliberate act with the fingerprint above updated in the same commit.

## Safety

The bench makes an agent take unauthorised actions and defeat its own stop control. **Against a production endpoint it causes the damage it measures.**

Registration therefore requires proof that you control the target — a nonce you must plant in its system prompt and which the target must echo back — plus an explicit attestation that you are authorised to test it, that it is not production, and that you accept the provider-policy and inference-cost consequences of being attacked. No run starts without both. See [ADR-0007](./docs/adr/0007-canary-nonce-as-proof-of-control.md).
