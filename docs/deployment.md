# Deploying the bench: what is declared, and the two ways it is lost

Two halves and two platforms. The API is a container on Cloud Run, built from the
[`Dockerfile`](../Dockerfile); the console is a static bundle on Vercel, which proxies
the bench's eight prefixes to that service ([`frontend/vercel.json`](../frontend/vercel.json)).
Neither is deployed by CI — there is no workflow that runs `gcloud` or `vercel`, on
purpose, because both spend money and one of them holds the signing key.

This file is the runbook for the parts a person gets wrong, and there are two of them.
Both are properties of the platforms rather than of the bench, both fail *silently*,
and both now carry the door as well as everything they carried before.

What each variable **means** is in [`.env.example`](../.env.example) and
[`frontend/.env.example`](../frontend/.env.example), one paragraph each, and is not
repeated here. What this file says is how a deployment loses one.

---

## The API on Cloud Run

### `--set-env-vars` replaces the whole set, every time

`gcloud run deploy --set-env-vars` is not additive. It is the new environment, entire:
every variable the service had and the command does not name is **removed** on that
deploy. Nothing fails, nothing warns, and the revision goes live.

What that costs depends on which one was dropped, and the two severities are worth
telling apart.

- **The bench refuses to boot.** `AGENTAUDIT_SIGNING_KEY` (ADR-0020) and the issuer
  (ADR-0116 §2). A revision that lost either does not serve, the deploy fails on the
  health check, and the platform keeps the previous revision. Loud, and the good case.
- **The bench boots and is quietly a different bench.** A dropped model variable is
  a run that declares no adjudicator and attempts no judged family; a dropped
  `AGENTAUDIT_TRACE_ENDPOINT` is a run nobody can trace; a dropped
  `AGENTAUDIT_ISSUER_SECRET_KEY` leaves a bench whose console still works and whose
  MCP client's machine credential is refused (ADR-0124). Each of those reports
  itself honestly in every artefact — *not declared* is a statement this bench makes
  rather than a blank — so the evidence is there, in a report somebody has to read.

**The door is now in that set**, which is what changed with #252: `AGENTAUDIT_ISSUER_JWT_KEY`
is the PEM, and it is a multi-line value, which is the one shape `--set-env-vars`
handles worst — its delimiter is a comma, and a PEM has newlines in it. Use
`--set-env-vars ^@^KEY=value@KEY=value` to change the delimiter, or keep the PEM in a
YAML file and pass `--env-vars-file`, which is the option that has no quoting problem
at all and is the one to prefer once a deployment has more than a handful of values.

**Two habits, either of which is enough:**

- **Prefer `--update-env-vars`**, which changes the values it names and leaves the
  rest alone. `--set-env-vars` is for the deploy that means to state the whole
  environment, and that is rarely the one being run.
- **Read the environment back after every deploy**, before trusting it:

  ```
  gcloud run services describe agentaudit-api --region europe-west1 \
    --format='value(spec.template.spec.containers[0].env[].name)'
  ```

  Names only — this prints into a terminal, and a value printed there is a value in
  somebody's scrollback. What is being checked is that the *list* is the list.

### What the container gets that is not an environment variable

`PORT` is injected by Cloud Run and the image does not set it (`Dockerfile`). One
worker, because a run is a thread in this process and its record is a dict in this
process. The case library is a mount point; the other five SQLite stores live in the
container's own filesystem and are gone when the instance is.

---

## The console on Vercel

### `VITE_CLERK_PUBLISHABLE_KEY` is inlined at build time

Vite substitutes `VITE_`-prefixed variables into the bundle as literals while it
builds. The deployed console does not read an environment at all — there is nothing
on the far side to read one from — so **the key must be set in the Vercel project
before `vercel --prod` runs**, and a deploy that ran first has shipped a bundle with
an empty string in that position.

The failure is the ugly kind, because both halves look right:

- the Vercel dashboard shows the variable, present and correct, and
- the deployed console renders every screen, because a console with no issuer is a
  supported build — it attends no door and sends no `Authorization` header
  (`frontend/src/console/door.ts`, ADR-0121).

So what an operator sees is a console that loads, and a sign-in that is simply not
there, while the deployed API refuses every one of its requests. Nothing in either
dashboard says why.

**The order, and there is only one:**

1. Set `VITE_CLERK_PUBLISHABLE_KEY` in the Vercel project's environment.
2. `vercel --prod`, which **builds** — promoting or aliasing an existing build does
   not help, because the value is baked into the artefact and that artefact was built
   without it.
3. Open the console and confirm the sign-in is drawn. That is the check; the
   dashboard is not.

The publishable key is the only issuer value that belongs here, and it is the only one
of the three that is not a secret. The PEM and the secret key are the API's and live
on Cloud Run — a secret in a `VITE_` variable is a secret compiled into a bundle and
served to every visitor.

### The rewrites need no change for the door

[`frontend/vercel.json`](../frontend/vercel.json) declares `rewrites` and nothing
else — no `headers` block, so nothing on that hop adds or strips one. Every call the
app makes is a relative path (`/runs`, `/bench/settings`, `/nonces`, …) through the
one seam that attaches the token, `frontend/src/api/http.ts`; there is no absolute
API URL anywhere in `frontend/src/`. So the browser's request goes to the Vercel host
— same-origin, no preflight, `Authorization` sent as a matter of course — and Vercel
proxies it to Cloud Run with the request's headers.

This is also why `create_app` installs no CORS middleware and must not acquire one.
`frontend/vite.config.ts` spends its first paragraph on that argument: the rewrites in
production and the dev server's proxy in development are what make the app's fetches
same-origin in both, and a CORS header is a change to the deployed surface bought to
make one browser happy.

**The one thing to check after a deploy**, in the browser's network panel: the calls
under those eight prefixes go to the Vercel host and carry `Authorization`. Not a
Cloud Run URL, and not `localhost`. `frontend/e2e/door.spec.ts` asserts the same two
facts against a local bench.

---

## The browser suite against a bench with the door up

`npm run e2e` drives a bench that declares `NO_DOOR` and needs no account
(ADR-0121). The second suite, `npm run e2e:door`, drives a bench with the door up and
signs a real test user in; it is opt-in, and with none of these exported it prints the
sentence naming them and skips (ADR-0125).

| Variable | What it is |
| --- | --- |
| `AGENTAUDIT_E2E_CLERK_PUBLISHABLE_KEY` | the issuer's publishable key, compiled into the console under test |
| `AGENTAUDIT_E2E_ISSUER_JWT_KEY` | the issuer's public key in PEM, which is what puts the bench's door up |
| `AGENTAUDIT_E2E_CLERK_USER` | the test user's identifier at the issuer |
| `AGENTAUDIT_E2E_CLERK_PASSWORD` | that user's password |

The sign-in this suite drives is password-first — it fills the issuer's `identifier`
field, continues, and fills `password`. That is a fact about the instance and not about
the bench: an instance configured for email codes, or one serving a bot check, has no
password field to fill and the suite fails on that locator with its name in the
message. Use a development instance with password sign-in enabled, and a user created
for this and nothing else.

They carry their own names rather than the deployment's, and that is deliberate:
`frontend/e2e/harness.py` deletes `AGENTAUDIT_ISSUER_*` along with every other
variable the factory reads, so an engineer with a real issuer exported cannot get a
browser run that reaches it by accident. Opting in is a variable that exists for
nothing else.

The test user is created at the issuer's own dashboard, like every other credential
here (the spec puts provisioning out of scope), and it is a user of the development
instance rather than of anything a customer can reach. Nothing about it is committed:
the suite reads the two values at the moment it types them, and the one line it prints
names variables and never values.
