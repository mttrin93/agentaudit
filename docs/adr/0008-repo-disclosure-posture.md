---
status: accepted
amended_by: 0047-a-retrieved-case-cites-its-row-and-a-person-signs-for-its-family.md
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

**Amended: the operator's own console may show the route text of their own run.**
The paragraph above is about what this repository ships, and it was read as though it
were also about what a running bench may ever display. Those are two questions. An
operator whose agent was broken in ten turns is told by the report that it was broken
in ten turns, and nothing further; the probes are the whole of what they need in order
to fix it, they are already in the process's memory, and withholding them from that
operator protects nobody — the route was taken against *their* endpoint, by an
attacker *they* paid for, at their own instruction. So `GET /runs/{id}/episodes`
serves the probes of one live run's episodes, in the order they were sent, and the
console draws them under the adaptive section of the report screen.

**This is not the disclosure this ADR refuses, and the difference is four mechanisms
rather than an assurance.** It does not commit: nothing writes a transcript to a
file, and `backend/cases/` is exactly what it was. It does not sign: the payload
carries each episode's family, outcome, turn count and prose, `ReportedEpisode` has
no field a probe could be written into, and that response is built from
`AdaptiveEpisode.transcripts`, which the assembler never sees — so the split is
carried by the types rather than by a reviewer's care. It does not circulate: the
signed artefact is the document that reaches a customer, and this is a read served to
the operator out of their own process. And it dies with the process: the episodes
live on `RunState`, so a restart leaves every earlier run answering that this bench
never started it. What ships in a public repository is unchanged by this amendment.

**What is given up is a screenshot, and it is a real thing to give up.** A page
showing the probes that beat a defended agent is a copy of a working, previously
unpublished exploit, and it can be pasted anywhere. None of the four mechanisms
survives leaving the screen: they bound where the text is *held*, never where it is
*taken*. So the response and the block both state what they are — read from this
process's memory, not part of the signed artefact, committed nowhere, and gone once
the process stops — and the operator who copies it is the one carrying it. That is a
trade this posture makes for an operator reading their own agent's route, and it is
not one it would make for a document that travels.

**Every adaptive-promoted case is withheld by default**, and this needs no new rule — though the amendment above changes which rule it falls under. It is not that a discovered case is originated here; origin no longer decides anything. It is that a route the attacker found by breaking a defended agent is the one artefact whose *wording* is demonstrably the working part: it defeated a target that resisted the library, so the phrasing carries something the prose does not. That is the withheld side of the amended line, and adaptive cases sit on it by their nature rather than by their provenance. The `discovered_by` field of [ADR-0012](./0012-adaptive-discovered-cases-face-a-cross-model-admission-bar.md) makes the classification mechanical rather than a judgement call at commit time.

## Amendment: a payload already published under a licence ships with its citation and that licence's notice

The amended line above is **transferability**, and the library it governed held one
payload that was published elsewhere first: `data-leakage-001`, which ships committed
*with its citation*, on the sentence "republishing what is already published protects
nobody". #62's group grows four families out of a **corpus** of 33,416
published human/LLM interactions
([ADR-0045](./0045-the-corpus-is-a-search-surface-and-never-a-library.md)), so that one
case's situation becomes the ordinary one, and the posture has to say what it decides
before a retrieved payload is written rather than after.

**Read literally, the transferability test forbids these payloads.** An Aegis injection
row is a phrasing that transfers to a target outside this repository, and most of them
read as exactly the reusable override the test names. Read for its reason, it permits
them: what makes publishing a payload irreversible is that *this repository would be the
first to publish it*, and a corpus row was published by somebody else, ungated, under
CC BY 4.0, at a revision this repository records the SHA-256 of. The letter and the
reason point opposite ways, so this decides rather than assumes.

**Amended decision.** A payload that was **already published under a licence that
permits redistribution** ships committed, with three things beside it and refused
without them: the publisher's own row under a pinned revision, the licence it was
published under, and the notice that licence asks to travel with the use. That is
`library.RetrievedFrom`, and the argument is
[ADR-0047](./0047-a-retrieved-case-cites-its-row-and-a-person-signs-for-its-family.md)
decision 3. The citation is not a courtesy here: it is what distinguishes *the 33,417th
copy of a public string* from *a phrasing this repository put into the world*, and a
record that carries the text without it is the second thing wearing the first thing's
clothes.

**Three things this does not change, and the third is the one to say plainly.** It does
not touch transcripts, which are still never committed. It does not touch
adaptive-promoted cases, which are still withheld by default and are the artefact this
posture exists for — a route that beat a defended agent is the case where wording
demonstrably is the mechanism, and nothing published it first. And **it is not a blanket
permission for the corpus.** The classification stays per case, stated in the record's
header with its argument, exactly as the amendment above requires: *already published*
is a strong argument and it is made about one payload at a time, by whoever writes the
record, and refused case by case where it does not hold. A bulk import of a hundred
overrides under one appeal to this paragraph is the thing the per-case rule exists to
prevent, and it would also be the sampled slice of a corpus that ADR-0045 rejects on
this ADR's own authority.
