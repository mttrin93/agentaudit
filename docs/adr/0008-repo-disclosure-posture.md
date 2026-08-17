---
status: accepted
---

# Repository disclosure posture

`backend/cases/` is a working library of adversarial payloads with success conditions, and publishing it is the least reversible act in this project — a payload cannot be unpublished. We therefore split it: the harness and cases derived from already-published techniques are public with citation, while cases originated here — halt defeat in particular — are described in prose with the payload withheld.

The alternative postures were both rejected. Publishing everything treats a working attack library as a portfolio exhibit; publishing nothing forfeits the citation trail that makes the external-identifier column in [ADR-0002](./0002-owasp-ids-as-secondary-labels.md) verifiable, and hides the harness that is the actual contribution.

The posture is stated in the [README](../../README.md), where a reader meets it before the code, and it binds from the first commit rather than from phase 5.
