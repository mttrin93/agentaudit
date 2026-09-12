---
status: accepted
---

# An open bench is a declaration a caller passes, never a deployment's default

[ADR-0116](./0116-the-identity-in-a-report-is-a-verified-claim-and-not-a-typed-string.md)
§2 decided that a deployment which declares no issuer does not start, and §3 decided
that the seam is a fourth constructor argument on `create_app` rather than an
environment read. Both hold. What neither decided is the question the fourth
declaration raises the moment it exists: **how a caller that means to serve an
unauthenticated bench says so.**

It is not a hypothetical caller. Three exist on the day the door lands.

- `frontend/e2e/harness.py` starts a *deployed* bench in a process of its own and
  drives it with Playwright. It has no issuer, and the browser in CI has no account
  to sign in to. It cannot declare its own `BenchConfig` instead — half of what the
  walkthrough asserts is what a deployed factory reads off its own mount.
- The tests that assert what a deployed factory answers *on a route* — the citation
  it serves, the absence it states — are in the same position for the same reason.
- A contributor on a laptop who wants the API up in front of the console for an
  afternoon, and who under §2 otherwise needs a provider account first.

§3's rule gives each of them one route out — declare a `BenchConfig` and get no
authentication — and it is the wrong route: it buys an open door by giving up the
deployed reading of the bench, the gate runs and the pending routes, which is the
thing they were testing. Two statements are being made with one word.

## Decision

**`create_app` takes a fourth declaration whose open reading is a value, and that
value is not a default of anything.**

1. **`NO_DOOR` is the only way to get an unauthenticated deployed bench.** It is an
   enum member on the factory, passed as `verifier=NO_DOOR`. A caller that passes it
   has said, in code, in a diff somebody reviews, that this process serves every
   route to anybody. Nothing else produces that state: an undeclared issuer is
   `NoIssuer` and §2 is untouched. The distinction this ADR exists to hold is
   between *open* and *silently open* — the failure §2 names is a redeploy that
   dropped a variable, and a variable is not what `NO_DOOR` is.

2. **It is an enum member and not the string it prints.** The comparison that
   decides whether an app has a door is `is`, against a member no caller can
   construct. A string sentinel would put that decision behind `==` against an
   object the caller supplied, and a verifier whose `__eq__` answered `True` would
   open every route on the surface. The cost of the wrong answer here is the whole
   gate, so the comparison is the one that cannot be argued with.

3. **A bench with a door does not publish its own schema.** `/openapi.json`, `/docs`
   and `/redoc` are not `APIRoute`s, so the dependency the router carries does not
   reach them, and *every route is authenticated* would be false by three. They are
   turned off when a verifier is declared rather than separately gated: an app that
   does not serve them cannot serve them out of step with the door. A bench with
   `NO_DOOR` keeps them, because there is nothing to disclose about a surface
   anybody may already call, and reading the schema is how a contributor finds it.

4. **A refusal carries the cause as a field, beside the sentence.** On
   `_cannot_measure`'s shape — the name a caller branches on, and the words.
   [ADR-0120](./0120-a-verification-is-a-subject-or-a-refusal-and-never-an-exception.md)
   §3 keeps five causes apart because consumers branch on them; a `401`/`503` split
   says whose problem a refusal is and cannot say which of four the credential was.
   The status carries the first question and the field carries the second.

## What this costs, stated

**There is now a supported way to run this bench with no door**, and a reader who
finds `NO_DOOR` in a deployment's startup has found a real finding. That is the
point — it is findable, in one grep, in the source — and it is still a thing that can
be done. It was weighed against the alternative in which the e2e walkthrough needs a
provider account in CI, and against the one in which a contributor cannot serve the
API without signing up for anything, and it beat both. What it must never become is
a default, which is decision 1 and is the only part of this that §2 depends on.

**The schema is not served on the deployment.** A person debugging the live API by
reading `/docs` no longer can, and reads the source instead. Judged the cheaper half
of decision 3: the alternative is three routes answering an unauthenticated caller
and a sweep test that structurally cannot see them, because they are not the kind of
route it enumerates.

## Alternatives

**A `AGENTAUDIT_AUTH=off` environment variable.** The obvious shape, and it is
exactly the failure ADR-0116 §2 describes with the sign flipped: a deployment one
variable away from serving every route to the internet, set by whoever last edited a
deploy script, with nothing on any screen saying so. The whole value of §2 is that
the open state is unreachable by editing configuration.

**No open reading at all — declare an issuer or declare a `BenchConfig`.** Cheaper
by one concept, and it makes the e2e walkthrough either declare a bench that is not
the deployed one, which deletes half of what it asserts, or hold a real issuer
credential in CI on a public fork. Rejected on the second: a browser walkthrough that
needs a provider account is a walkthrough contributors stop running.

**A boolean, `authenticated=False`.** Reads as a setting rather than as a
declaration, and it puts the open state one falsy default away — `None`, `0`, an
unset variable threaded in from somewhere. A named member has no falsy neighbours.

**Gating `/docs` with the same dependency instead of turning it off.** Possible, and
it is two mechanisms that have to stay in step across a FastAPI upgrade that changes
how those routes are registered. Decision 3 prefers the one that cannot come apart.
