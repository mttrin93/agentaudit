---
status: accepted
---

# OWASP 2026 IDs as secondary labels, never as identity

Portability is this project's thesis, but a private six-family taxonomy is legible only to its author, and the reader after [ADR-0001](./0001-procurement-not-regulator-is-the-buyer.md) is a procurement or insurer analyst who recognises `LLM01` and does not recognise `wrongful_commitment`. Inventing a seventh private taxonomy is the problem the mission statement complains about. No harmonised standard is cited in the Official Journal, so no attack list carries Article 40 presumption of conformity — but OWASP GenAI LLM Top 10 2026 and OWASP Top 10 for Agentic Applications 2026 are published with stable identifiers.

**Decision.** Every attack family carries an OWASP 2026 identifier as a *secondary* label. The wording is fixed and load-bearing: a family **tests one case within** LLM01; it **is not** LLM01. An OWASP entry is a risk category; a family is an executable test with a success condition. Carrying the identifier must never imply the two are the same object.

## Consequences

- **Coverage limits, per family:** which case inside that identifier is tested, and which is not.
- **Coverage limits, per report:** which OWASP 2026 agentic categories are not tested at all. This uses the public list as a coverage checklist rather than only as a label. It is free, and it is the first thing a security analyst looks for.
- Gaps are **listed, not closed.** New families to cover them are P2 at the earliest.
- OWASP identifiers are the primary external reference because they are published and stable. prEN 18229-2 (accuracy and robustness) and prEN 18282 (cybersecurity for AI systems) are at Enquiry stage, so clause numbers move between drafts: any citation carries the draft date and is marked provisional. A stale clause number inside a signed report is worse than no reference at all.
- Four of six families are re-labellings of published categories; only halt defeat and disclosure denial have no OWASP home. The project's originality therefore does **not** live in the mapping. It lives in the gate, the admission and retirement lifecycle, the declared discrimination score, and the multi-model validity check. The borrowed categories are a feature: the labels become recognisable while the measurement stays ours.
