---
status: accepted
---

# Repository disclosure posture

`backend/cases/` is a working library of adversarial payloads with success conditions, and publishing it is the least reversible act in this project — a payload cannot be unpublished. We therefore split it: the harness and cases derived from already-published techniques are public with citation, while cases originated here — halt defeat in particular — are described in prose with the payload withheld.

The alternative postures were both rejected. Publishing everything treats a working attack library as a portfolio exhibit; publishing nothing forfeits the citation trail that makes the external-identifier column in [ADR-0002](./0002-owasp-ids-as-secondary-labels.md) verifiable, and hides the harness that is the actual contribution.

The posture is stated in the [README](../../README.md), where a reader meets it before the code, and it binds from the first commit rather than from phase 5.

## The adaptive attacker generates payloads at runtime

The posture above governs payloads written by a person and committed to a file. The adaptive layer ([ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md)) composes novel payloads while the run is happening, which changes what ships in this repository in three ways and leaves the fourth alone.

**Static cases are unchanged.** The split above holds exactly as written.

**The repository now ships a weapon factory rather than a weapon.** This is a real change of kind and a smaller one in practice: the attacker's reach is bounded by the model behind it, and that model is available to anybody who wants to prompt it. **The attacker's system prompt is therefore published**, along with its five tools. Withholding it would hollow out the claim that the harness is public while withholding nothing scarce, and the harness is the actual contribution.

**The genuinely new artefact is the transcript, and transcripts are not committed.** "Full transcripts recorded" means a successful adaptive route against the hardened agent is a working, previously unpublished exploit written down in a public repository. `docs/validation.md` records the statistics, the family and a prose description of the route; it never records the payload text. Transcripts live outside the repository with the run that produced them, and a transcript against a *user's* target belongs to that user and never enters this repository at all.

**Every adaptive-promoted case is withheld by default**, and this needs no new rule. A case discovered by the attacker is by definition originated here, and the split above already says originated cases ship as prose with the payload withheld. The `discovered_by` field of [ADR-0012](./0012-adaptive-discovered-cases-face-a-cross-model-admission-bar.md) makes the classification mechanical rather than a judgement call at commit time.
