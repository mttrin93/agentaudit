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

## Safety

The bench makes an agent take unauthorised actions and defeat its own stop control. **Against a production endpoint it causes the damage it measures.**

Registration therefore requires proof that you control the target — a nonce you must plant in its system prompt and which the target must echo back — plus an explicit attestation that you are authorised to test it, that it is not production, and that you accept the provider-policy and inference-cost consequences of being attacked. No run starts without both. See [ADR-0007](./docs/adr/0007-canary-nonce-as-proof-of-control.md).
