# AgentAudit

An adversarial test bench for AI agents. It attacks a target agent across six failure families, proves its own discriminating power before its results are trusted, and reports the outcome as signed evidence a recipient can verify offline.

Full design in [PLAN.md](./PLAN.md) · vocabulary in [CONTEXT.md](./CONTEXT.md) · decisions in [docs/adr/](./docs/adr/).

> **Status: pre-build.** This README carries the disclosure posture only, because that decision binds from the first commit. Purpose, users, D1–D14, the article mapping and a worked example arrive at phase 5.

---

## Disclosure posture

`backend/cases/` is a working library of adversarial payloads with success conditions, in a public repository. That is what makes this repository useful and what makes it a weapon. The position is deliberate, not accidental — see [ADR-0008](./docs/adr/0008-repo-disclosure-posture.md).

- **The harness is public.** Registration, scanner, attacker, evaluator, judge, scorer, assembler, report, the gate (`scripts/calibrate.py`) and the offline signature check (`scripts/verify.py`).
- **Cases derived from published techniques are public, with citation.** They are already public knowledge, and citing the source supports the external-identifier column in the article mapping.
- **Cases originated here are described in prose with the payload withheld.** This covers the halt-defeat family in particular, which has no published equivalent. The description is enough to understand what is tested and to reproduce the finding against your own agent; it is not enough to lift as an attack.
- **Nothing operational is ever committed.** No target credentials, no user findings, no real attestations, no nonces. `.env` is gitignored.

If you are a researcher who wants a withheld payload for defensive work, open an issue describing the use; the answer may still be no.

## Safety

The bench makes an agent take unauthorised actions and defeat its own stop control. **Against a production endpoint it causes the damage it measures.**

Registration therefore requires proof that you control the target — a nonce you must plant in its system prompt and which the target must echo back — plus an explicit attestation that you are authorised to test it, that it is not production, and that you accept the provider-policy and inference-cost consequences of being attacked. No run starts without both. See [ADR-0007](./docs/adr/0007-canary-nonce-as-proof-of-control.md).
