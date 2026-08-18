---
status: accepted
---

# Repository disclosure posture

`backend/cases/` is a working library of adversarial payloads with success conditions, and publishing it is the least reversible act in this project — a payload cannot be unpublished. We therefore split it: the harness and cases derived from already-published techniques are public with citation, while cases originated here — halt defeat in particular — are described in prose with the payload withheld.

The alternative postures were both rejected. Publishing everything treats a working attack library as a portfolio exhibit; publishing nothing forfeits the citation trail that makes the external-identifier column in [ADR-0002](./0002-owasp-ids-as-secondary-labels.md) verifiable, and hides the harness that is the actual contribution.

The posture is stated in the [README](../../README.md), where a reader meets it before the code, and it binds from the first commit rather than from phase 5.

## Amendment: the line is transferability, not origin

The split above draws the line at **origin** — derived from a published technique is
public, originated here is withheld — and the library it now governs does not obey
it. Six cases ship with their payload committed, and three of them claim no external
technique: `halt-defeat-001` and `disclosure-denial-001` say "originated here" in as
many words, and `wrongful-commitment-001` claims an OWASP identifier as a *label*
(which is all an identifier is, per [ADR-0002](./0002-owasp-ids-as-secondary-labels.md))
while deriving from no published technique either. Only `data-leakage-001` carries a
citation. So the posture as written is false about half the library, and it names
halt defeat specifically as the case it withholds.

**Origin was a proxy for transferability, and the proxy fails in both directions.**
What makes publishing a payload irreversible is that its *words* are the working part
— a phrasing someone can lift and point at a target that was never in this
repository. Origin does not track that. An originated case can be entirely
situational: `halt-defeat-001` is a stop signal followed by a request that is inside
the agent's own declared job, `scope-creep-001` is an errand in words no deny-list
holds, `disclosure-denial-001` is a persona instruction and a plain question. Lifting
those words buys an attacker nothing, because what does the work is the situation and
the situation is fully described in the prose either way. Meanwhile a payload derived
from a published technique is the case where the wording *is* the mechanism — and the
original split sent exactly that one out with a citation.

**And for the three already committed, withholding is not on the menu.** This ADR's
own first sentence is that a payload cannot be unpublished; `halt-defeat-001`'s
payload has been public since the commit that added it. Deleting it now would leave
it in the history, remove the reader's ability to see what the family tests, and
leave the posture no truer. The choice is between an ADR that describes the
repository and an ADR that is false about it.

**Amended decision.** A payload ships committed when the prose description would
convey the attack as fully as the text does — when the situation is the mechanism.
A payload is **withheld** when its wording is the working part: a phrasing that
transfers to a target outside this repository, and specifically anything that reads
as a reusable override, jailbreak or filter defeat. The classification is stated in
the case record's header, with the argument, so it is auditable per case rather than
asserted once. `data-leakage-001` stays public *with its citation* — a published
technique needs the citation for the reason ADR-0002 gives, and republishing what is
already published protects nobody.

Nothing that was actually scarce becomes public under the amendment. **Transcripts
are still never committed, and adaptive-promoted cases are still withheld by
default** — see the two sections below, which are unchanged and which govern the
artefacts where wording *is* the mechanism. A successful adaptive route against the
hardened agent is the case this posture exists for, and the amendment does not touch
it. What changes is that the rule now names the property it was always trying to
protect, instead of a proxy that let a situational case be described as a weapon and
a published technique be shipped as a courtesy.

## The adaptive attacker generates payloads at runtime

The posture above governs payloads written by a person and committed to a file. The adaptive layer ([ADR-0010](./0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md)) composes novel payloads while the run is happening, which changes what ships in this repository in three ways and leaves the fourth alone.

**Static cases are unchanged.** The split above, as amended, holds.

**The repository now ships a weapon factory rather than a weapon.** This is a real change of kind and a smaller one in practice: the attacker's reach is bounded by the model behind it, and that model is available to anybody who wants to prompt it. **The attacker's system prompt is therefore published**, along with its five tools. Withholding it would hollow out the claim that the harness is public while withholding nothing scarce, and the harness is the actual contribution.

**The genuinely new artefact is the transcript, and transcripts are not committed.** "Full transcripts recorded" means a successful adaptive route against the hardened agent is a working, previously unpublished exploit written down in a public repository. `docs/validation.md` records the statistics, the family and a prose description of the route; it never records the payload text. Transcripts live outside the repository with the run that produced them, and a transcript against a *user's* target belongs to that user and never enters this repository at all.

**Every adaptive-promoted case is withheld by default**, and this needs no new rule — though the amendment above changes which rule it falls under. It is not that a discovered case is originated here; origin no longer decides anything. It is that a route the attacker found by breaking a defended agent is the one artefact whose *wording* is demonstrably the working part: it defeated a target that resisted the library, so the phrasing carries something the prose does not. That is the withheld side of the amended line, and adaptive cases sit on it by their nature rather than by their provenance. The `discovered_by` field of [ADR-0012](./0012-adaptive-discovered-cases-face-a-cross-model-admission-bar.md) makes the classification mechanical rather than a judgement call at commit time.
