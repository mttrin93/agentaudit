"""The two servers one browser walkthrough needs, and the environment it needs them in.

Started by Playwright as a `webServer` and killed by it at the end of the run. It
serves the bench's own API on a fixed port — the port `playwright.config.ts` points
the Vite dev server's proxy at — and one set of reference agents on an ephemeral one,
then writes what the test cannot know in advance to `served.json` beside this file: the
endpoint to type into the registration form, the route to plant the nonce on, and the
key the report it produces will verify against.

**The environment is emptied before the factory reads it, and that is the whole point
of this file.** `create_app` points the process at whatever trace sink the environment
declares and builds whatever models it names, and this repository's `.env` declares a
real sink and three real models. A walkthrough started from an engineer's own shell
would publish prompts and replies to that sink and could spend on that provider. So
every variable the factory reads is deleted here before it is called, and the one that
is set is a signing key generated in this process: no endpoint, no API key, no model
slug, and a bench that declares no models runs the deterministic stand-in attacker and
attempts no judged case (`app.deployed_models`, `adaptive/scripted.py`).

**The pair is generated per run, and the private half is written nowhere.** It exists
in this process's environment for as long as the process does and in no file, which is
the posture ADR-0020 asks for. The public half is written — `scripts.verify` pins a key
file and the walkthrough's last leg runs it — and it is written beside this harness and
deleted when it stops. `signing.generate` is reached directly rather than through
`scripts/keygen`, whose other two jobs are writing the *committed* public half and
refusing to replace it: no path in this file names
`keys/agentaudit-signing.pub`, and none can be pointed at it by editing an argument.

**Nothing here is reachable from the bench.** It is test equipment under
`frontend/e2e/`, it is imported by no module of `backend/` or `scripts/`, and the run
it makes possible goes through the same routes an operator's run goes through: there is
no shortcut past the attestation, the nonce echo or the approval interrupt, and the run
is shortened only by the two declared-input routes the console already writes to
(ADR-0025).
"""

import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path

PUBLIC_KEY = Path(__file__).resolve().parent / "dev-signing.pub"
"""Where the public half of the walkthrough's key pair is written, for one run.

The pair is generated in this process and the private half stays in this process's
environment. The public half has to reach a second process — `scripts.verify` is how a
recipient checks an artefact, and it pins a key file — so it is written here, next to
the walkthrough that reads it, and deleted when the harness stops.

**Never `keys/agentaudit-signing.pub`.** That file is the published key whose
fingerprint the README carries, every signature ever issued under it verifies against
it, and `scripts/keygen` refuses to replace it. Nothing in this file names it: the pair
is reached through `signing.generate` rather than through the script, so a path in this
harness cannot be pointed at the committed key by editing an argument.
"""

REPOSITORY = Path(__file__).resolve().parents[2]
"""The repository root, put on the import path below.

A script run as `python frontend/e2e/harness.py` gets its own directory as `sys.path[0]`
and not the working directory, so `import backend` fails however sensible the working
directory is. The suite never meets this because pytest reads `pythonpath = ["."]` out
of `pyproject.toml`; a script has no such file to read, and a green local run on a
machine whose virtualenv happens to hold the project is not evidence that a fresh
checkout works — CI's first run of this job proved that by failing on this line.

Inserted rather than appended, and at import rather than inside `main`, so the path is
in place before any import statement in this file can run.
"""

sys.path.insert(0, str(REPOSITORY))

SERVED = Path(__file__).resolve().parent / "served.json"
"""Where the reference agents' address is left for the test to read.

A file rather than a port agreed in advance, because `serving.serve` binds an
ephemeral port and a walkthrough that pinned one would fail on a machine already
using it. Written after the agents are up, so a test that reads it reads a live
address.
"""

API_PORT_VARIABLE = "AGENTAUDIT_E2E_API_PORT"
"""The port the API is served on, set by `playwright.config.ts`.

Fixed rather than ephemeral because a second process needs it before this one starts:
the Vite dev server proxies the bench's six prefixes to it, and its configuration is
read at startup.
"""

FACTORY_VARIABLES = (
    "AGENTAUDIT_TRACE_ENDPOINT",
    "AGENTAUDIT_TRACE_API_KEY",
    "AGENTAUDIT_TRACE_PROJECT",
    "AGENTAUDIT_TRACE_SAMPLE",
    "AGENTAUDIT_REFERENCE_MODEL",
    "AGENTAUDIT_ADJUDICATOR_MODEL",
    "AGENTAUDIT_ATTACKER_MODEL",
    "AGENTAUDIT_ATTACKER_REASONING_EFFORT",
    "AGENTAUDIT_TURNS_PER_EPISODE",
    "OPENROUTER_API_KEY",
    "OPENROUTER_BASE_URL",
    "AGENTAUDIT_ISSUER_JWT_KEY",
    "AGENTAUDIT_ISSUER_SECRET_KEY",
)
"""Every variable this walkthrough refuses to inherit, deleted before the factory runs.

The four trace variables are the sink; the four model variables are what would be
called; the two OpenRouter ones are the credential a call would be billed against;
the two issuer ones are the door, which this walkthrough declares off below — deleted
as well as declared off so that an engineer with a real issuer exported does not have
a browser run that could reach it. The doored path puts those two back, and puts back
only what `DOOR_JWT_KEY_VARIABLE` and its companion were exported with: an operator
asking for a doored walkthrough is a variable that exists for nothing else, never an
inherited one.
Deleted rather than overridden with something harmless, because a harmless value is
still a value the factory reads and reports, and the run is supposed to describe a
bench that declared none of them.

The langchain switches are not listed: `observability.INHERITED_TRACING_VARIABLES`
holds those and `create_app` turns them off itself (ADR-0026). One module knows what
is on the far end of a sink and this is not it.
"""

STUB_MODEL = "stub:obedient"
"""The model the reference agents are served on. No network and no provider.

`obedient` hands its whole configuration to anyone who writes to it, so the nonce
planted in it comes back on the registration probe and comes back again to the
data-leakage payloads. Deterministic in both places, which is what a walkthrough that
must not race a model needs.
"""

AUTH_TOKEN = "walkthrough-auth-token"
"""What the served agents expect in `Authorization: Bearer …`, and so what the form is
filled in with. A credential for a process this file started, and it is typed into the
browser: a walkthrough that left the field empty would not exercise the one field on
that form that carries somebody's secret."""

DOOR_JWT_KEY_VARIABLE = "AGENTAUDIT_E2E_ISSUER_JWT_KEY"
"""The issuer's public key, in PEM, that turns this walkthrough's door on.

**Its own variable and never `AGENTAUDIT_ISSUER_JWT_KEY`.** That one is deleted above
with the rest of the factory's environment, and deliberately: an engineer with a real
issuer exported must not get a browser run that reaches it by accident. The doored
walkthrough is therefore something an operator asks for, in a variable that exists for
no other purpose, and the deleted name is set from it below — so the factory reads what
it always reads and the opt-in is visible in one grep.

Absent is the path every clone and every CI run takes: `NO_DOOR`, and a console with no
publishable key — ADR-0125, which decides that the doored suite is opt-in and that an
absent test user is a printed skip. `docs/deployment.md` lists the four variables.
"""

DOOR_SECRET_KEY_VARIABLE = "AGENTAUDIT_E2E_ISSUER_SECRET_KEY"
"""The issuer's secret key, optional beside the PEM.

A session token is checked offline against the PEM and needs nothing here (ADR-0116
§4). It is the machine credential that is checked at the issuer (ADR-0124), so a
walkthrough that means to exercise one exports this as well; a walkthrough that only
signs a person in does not.
"""


def declared_door(environment: Mapping[str, str]) -> dict[str, str] | None:
    """What this walkthrough serves: the deployed factory's own reading, or nothing.

    Answers the environment the harness was started with, and answers it as the
    variables `backend/identity.py` reads rather than as a flag — so the doored run is
    the deployed reading of the factory and not a third configuration of it.

    **Blank is unset**, as it is in `identity.declared_issuer` and for its reason: a
    variable cleared by whatever set it has declared nothing.

    **The PEM alone is a door and the secret key alone is not.** Verification here is
    offline or it is not this bench: a run given only the secret key would call the
    issuer on every request the console's two-second poll makes, which is a bench the
    deployment is not. So that reading is `None` — no door, and the walkthrough says
    which one it served.
    """
    jwt_key = environment.get(DOOR_JWT_KEY_VARIABLE, "").strip()
    if not jwt_key:
        return None
    declared = {"AGENTAUDIT_ISSUER_JWT_KEY": jwt_key}
    secret_key = environment.get(DOOR_SECRET_KEY_VARIABLE, "").strip()
    if secret_key:
        declared["AGENTAUDIT_ISSUER_SECRET_KEY"] = secret_key
    return declared


AGENT = "trivial"
"""Which of the three agents is registered: the one with no defences.

The walkthrough is about the console's path and not about a defence, and `trivial` is
the agent whose verdicts are settled by the payload rather than by a control — so the
report the last leg opens has a finding in it every time.
"""


def main() -> int:
    """Serve the agents, serve the bench, and block until Playwright kills us."""
    port = os.environ.get(API_PORT_VARIABLE, "").strip()
    if not port:
        print(f"{API_PORT_VARIABLE} is not set: playwright.config.ts sets it")
        return 2

    # The imports come first and the environment is emptied after them, and that
    # order is load-bearing. Importing `backend.api.app` reaches `deepeval`, which
    # calls `load_dotenv()` on import: this repository's `.env` — the real sink and
    # the three real models — is in `os.environ` by the time the import statement
    # returns, whatever the shell held before it. Emptying first and importing
    # second would put every one of them back.
    import uvicorn

    from backend.api.app import NO_DOOR, create_app
    from backend.bench.signing import (
        SIGNING_KEY_VARIABLE,
        encoded_private,
        generate,
        public_pem,
    )
    from backend.observability import trace_config
    from backend.targets.reference.model import ModelConfig
    from backend.targets.reference.server import ReferenceConfig, create_reference_app
    from backend.targets.reference.serving import serve

    # Read before the deletion below empties it, and applied after — so the two
    # issuer variables the factory reads are the ones this file put there and never
    # ones a shell happened to hold (`DOOR_JWT_KEY_VARIABLE`).
    door = declared_door(os.environ)

    for variable in FACTORY_VARIABLES:
        os.environ.pop(variable, None)
    os.environ.update(door or {})

    # Asked of the module that owns the answer rather than inferred from the list
    # above. A sink variable renamed or added would leave this walkthrough exporting
    # spans to somebody's real project and nothing would say so, so the harness
    # refuses to serve instead of trusting its own list (ADR-0026).
    if trace_config() is not None:
        print(
            "this environment still declares a trace sink after "
            f"{', '.join(FACTORY_VARIABLES)} were removed. A browser walkthrough "
            "must not publish prompts and replies to a real project: refusing to "
            "serve until observability.trace_config reads nothing"
        )
        return 2

    key = generate()
    os.environ[SIGNING_KEY_VARIABLE] = encoded_private(key)
    PUBLIC_KEY.write_bytes(public_pem(key.public_key()))

    agents = create_reference_app(
        ReferenceConfig(model=ModelConfig.parse(STUB_MODEL), auth_token=AUTH_TOKEN)
    )
    with serve(agents) as base_url:
        SERVED.write_text(
            json.dumps(
                {
                    "target_url": f"{base_url}/reference/{AGENT}/messages",
                    "plant_url": f"{base_url}/reference/{AGENT}/nonce",
                    "auth_token": AUTH_TOKEN,
                    "name": AGENT,
                    "pubkey": str(PUBLIC_KEY),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        # One line, so that a webServer Playwright is still waiting on can be told
        # apart from one that failed before it bound. A CI run of this job timed out
        # on a silent wait, which is the failure this print is for.
        # Which of the two benches this is, in the line an operator reads: a doored
        # run that quietly served an open bench would pass every assertion the
        # issuerless suite makes and prove nothing about the door.
        served_as = "a door" if door is not None else "no door"
        print(
            f"reference agents at {base_url}; the bench on port {port} with "
            f"{served_as}",
            flush=True,
        )
        try:
            uvicorn.run(
                # The door, declared off — unless an operator exported an issuer,
                # in which case nothing is declared and the factory reads its own
                # environment like a deployment does. A deployed factory refuses to
                # boot without an issuer (`app.NO_ISSUER_NO_BOOT`), and the
                # issuerless walkthrough has none: it runs in CI on a fork, against
                # agents it started itself, with a browser that has no account to
                # sign in to. Declared rather than defaulted, which is the whole of
                # the distinction — nothing here falls into an open bench, this file
                # asks for one, and the doored path asks for the other by exporting
                # a key rather than by editing this line.
                create_app() if door is not None else create_app(verifier=NO_DOOR),
                host="127.0.0.1",
                port=int(port),
                log_level="warning",
            )
        finally:
            SERVED.unlink(missing_ok=True)
            PUBLIC_KEY.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
