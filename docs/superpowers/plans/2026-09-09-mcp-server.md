# MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose four MCP tools — start, approve, status, report — over the AgentAudit HTTP API, so a coding agent in the operator's repository can run the bench and act on its findings.

**Architecture:** A new `backend/mcp/` package holding four modules with one responsibility each: a declaration-file reader, a compact reading of the signed payload, an HTTP client with named errors, and the MCP server that wires them into tools. It imports nothing from `backend/bench/` and holds no bench state; every rule it appears to enforce is enforced on the far side of a route.

**Tech Stack:** Python 3.12, `mcp` 2.2.0 (`MCPServer`, formerly FastMCP), httpx, pydantic, pytest, FastAPI `TestClient` for the integration seam.

**Spec:** [docs/specs/mcp-server.md](../../specs/mcp-server.md)

## Global Constraints

- **Python floor:** `>=3.12` (pyproject `requires-python`).
- **New runtime dependency:** `mcp>=2.2.0`. In `[project].dependencies`, not a group — the server is shipped, not tooling.
- **mcp 2.x naming:** `FastMCP` was renamed. Import `from mcp.server.mcpserver import MCPServer`. Importing `mcp.server.fastmcp` raises `ModuleNotFoundError` with a migration message.
- **No `backend.bench` imports anywhere in `backend/mcp/`.** Enforced by a test, not by review.
- **No figure is computed in this package.** Every number returned comes from a payload field verbatim (ADR-0006).
- **Every new test is driven red once, for the right reason, before it is committed.** `CLAUDE.md` standing rule. Break the thing it guards, confirm the failure is the assertion and not an import error, revert.
- **Do not run `pytest` while a gate run is in flight** — the case-library lease makes unrelated tests fail spuriously.
- **Commands:** `uv run pytest -q`, `uv run mypy`, `uv run ruff check .`, `uv run ruff format .`. All four must pass before a commit.
- **Docstring style:** long, argumentative module docstrings are the house style. A decision goes in an ADR and the docstring links it; the local consequence stays in the docstring.

---

### Task 1: The two ADRs

The spec argues two decisions that no ADR records. `CLAUDE.md`: a decision belongs in an ADR, and no ADR is edited to say something it did not decide. No code in this task.

**Files:**
- Create: `docs/adr/0100-the-mcp-server-has-no-privilege-the-console-lacks.md`
- Create: `docs/adr/0101-a-compact-reading-may-drop-prose-and-never-a-label.md`

**Interfaces:**
- Consumes: nothing.
- Produces: two ADR paths that Tasks 4 and 6 link from module docstrings. Use these exact filenames.

- [ ] **Step 1: Confirm the numbers are free**

Run: `ls docs/adr | tail -3`
Expected: the highest existing number is `0099`. If something numbered `0100` or `0101` exists, take the next two free numbers and use them consistently for the rest of this plan.

- [ ] **Step 2: Write ADR-0100**

Follow the house format — `---\nstatus: accepted\n---`, an H1 title, the situation, a bolded **Decision.**, then `## Consequences`. Content to argue:

- Situation: a tool surface reached by a model is a surface where a prompt can ask for anything the surface can do. The console's privileges were scoped for a human who walked a register screen.
- Decision: every MCP tool is a translation of an existing route. The server imports no `backend.bench` module, starts no process, holds no key, no lease and no case library. A capability the console lacks is bench work under its own ADR, never a tool.
- Alternatives that lost: (a) embedding the bench in-process — the server would own the lease, the signing key and process lifetime, and become a second way to run the bench that has to stay in step with the first; (b) a privileged tool for gate runs — lets a model spend the bench's own validation budget (ADR-0018).
- Consequences: the first run against a new target still needs the browser; an import-level test holds the wall.

- [ ] **Step 3: Write ADR-0101**

- Situation: the signed payload composes its caveats for a reader who holds only the document. A caller that can fetch the document does not need them inlined, but summarising is how a figure loses its qualification — the thing D3 forbids.
- Decision: a compact reading may drop prose and may never drop a label. Every closed-set member survives; only `stated`/`*_stated` sentences are dropped, and only where a label already carries the same fact.
- Alternatives that lost: (a) returning the whole payload — thousands of tokens of procurement prose per run, and the two fields a caller wants get buried; (b) a hand-picked field list — stops being correct the day a member is added.
- Consequences: the rule is testable as a set difference over the payload's own keys, which is what Task 4 builds.

- [ ] **Step 4: Commit**

```bash
git add docs/adr/0100-the-mcp-server-has-no-privilege-the-console-lacks.md docs/adr/0101-a-compact-reading-may-drop-prose-and-never-a-label.md
git commit -m "The MCP server has no privilege the console lacks, and a compact reading keeps its labels"
```

---

### Task 2: The package, the dependency, and the import wall

**Files:**
- Create: `backend/mcp/__init__.py`
- Modify: `pyproject.toml` (add `mcp>=2.2.0` to `[project].dependencies`, alphabetical — between `langgraph-checkpoint-sqlite` and `openai`)
- Test: `backend/tests/test_mcp_wall.py`

**Interfaces:**
- Consumes: ADR-0100 from Task 1.
- Produces: the `backend.mcp` package. Every later task adds a module inside it.

- [ ] **Step 1: Write the failing test**

```python
"""The wall: `backend/mcp/` reaches no bench module.

[ADR-0100](../../docs/adr/0100-the-mcp-server-has-no-privilege-the-console-lacks.md)
states the wall absolutely, and it is held here at import level rather than by
review, on the reasoning `test_throwaway_checkout.py` and `test_proving.py`
already use for `throwaway.py` and `proving.py`: a wall nobody can see from the
file they are editing is a wall somebody widens by accident.

**Relative imports are resolved, not skipped.** `from ..bench.judge import
Finding` inside `backend/mcp/` is the same widening as the dotted form and reads
in a diff like package-local tidiness, so it is the form most likely to slip a
reviewer who was thinking about a tool description. The wall is worth little if
the accidental spelling is the one it cannot see.
"""

from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "backend" / "mcp"


def _containing_package(source: pathlib.Path) -> tuple[str, ...]:
    """The dotted package a file lives in, as parts — `backend.mcp` for all of these."""
    return source.resolve().relative_to(ROOT).parts[:-1]


def _imported_modules(source: pathlib.Path) -> set[str]:
    """Every module this file imports, as an absolute dotted name.

    Relative forms are resolved against the containing package rather than skipped.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"))
    package = _containing_package(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module:
                    names.add(node.module)
                continue
            base = package[: len(package) - node.level + 1]
            names.add(".".join((*base, node.module) if node.module else base))
    return names


def test_the_mcp_package_imports_no_bench_module() -> None:
    offenders = {
        source.name: sorted(
            name
            for name in _imported_modules(source)
            if name == "backend.bench" or name.startswith("backend.bench.")
        )
        for source in PACKAGE.rglob("*.py")
    }
    assert {name: found for name, found in offenders.items() if found} == {}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest backend/tests/test_mcp_wall.py -q`
Expected: FAIL — `backend/mcp` does not exist, so `rglob` raises or the parents index is wrong. This is an *import/path* failure, not the assertion, so it does not yet count as red for the right reason. Continue to step 3, then re-drive it properly in step 5.

- [ ] **Step 3: Create the package**

`backend/mcp/__init__.py`:

```python
"""The MCP surface: four tools over routes that already exist.

A delivery surface and not a capability
([ADR-0100](../../docs/adr/0100-the-mcp-server-has-no-privilege-the-console-lacks.md)).
Nothing in this package imports `backend.bench`, starts a process, holds a key or
takes the case-library lease: every rule a tool appears to enforce is enforced on
the far side of an HTTP route, which is what makes the surface safe to hand to a
model. `test_mcp_wall.py` holds the import half of that claim.

The spec is [docs/specs/mcp-server.md](../../docs/specs/mcp-server.md).
"""
```

- [ ] **Step 4: Add the dependency**

In `pyproject.toml`, inside `[project].dependencies`, after `"langgraph-checkpoint-sqlite>=3.1.1",`:

```toml
    # The MCP server surface (`backend/mcp/`, ADR-0100). A runtime dependency and
    # not a group: the server is shipped with the bench, unlike the lint and type
    # tooling. Floor at 2.2.0 because 2.x renamed `FastMCP` to `MCPServer` and
    # `mcp.server.fastmcp` no longer imports — code written against 1.x does not
    # run here and a lower floor would resolve to it.
    "mcp>=2.2.0",
```

Then: `uv sync --all-groups`

- [ ] **Step 5: Drive the test red for the right reason**

Temporarily append to `backend/mcp/__init__.py`:

```python
from backend.bench.judge import Finding  # noqa: F401
```

Run: `uv run pytest backend/tests/test_mcp_wall.py -q`
Expected: FAIL on the assertion, showing `{'__init__.py': ['backend.bench.judge']}`. Then revert that line.
Drive the relative spelling too — `from ..bench.judge import Finding` — which resolves to the same name and is the form a reviewer thinking about tool descriptions is likeliest to wave through.

- [ ] **Step 6: Run the full checks**

Run: `uv run pytest backend/tests/test_mcp_wall.py -q && uv run mypy && uv run ruff check . && uv run ruff format --check .`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/mcp/__init__.py backend/tests/test_mcp_wall.py pyproject.toml uv.lock
git commit -m "The MCP package exists and reaches no bench module"
```

---

### Task 3: The declaration file

**Files:**
- Create: `backend/declaration.py`
- Test: `backend/tests/test_mcp_declaration.py`

**Interfaces:**
- Consumes: the `backend.mcp` package from Task 2.
- Produces:
  - `Declaration` — frozen dataclass with fields: `name: str`, `url: str`, `auth_token: str`, `agent_type: str`, `exposes_tool_calls: bool`, `declared_tools: tuple[str, ...]`, `retains_session_state: bool`, `holds_personal_records: bool`, the four Rule of Two declarations as `bool | None` (ADR-0102, added in Task 5), `nonce: str`, `note_planted: bool`, `nonce_planted: bool`, `echo_waived: bool`, `identity: str`, `authorised_to_test: bool`, `not_production: bool`, `accepts_provider_policy_and_cost: bool`, `price_per_call: str | None`, `currency: str`.
  - `DeclarationRefusal(StrEnum)` — members `NO_FILE`, `NOT_AN_ENDPOINT`, `NO_IDENTITY`, `NOT_ATTESTED`.
  - `DeclarationRefused(ValueError)` with attribute `refusal: DeclarationRefusal`.
  - `declaration_at(path: pathlib.Path) -> Declaration`.
- Task 5 constructs its request bodies from a `Declaration`; Task 6 calls `declaration_at`.

- [ ] **Step 1: Write the failing tests**

```python
"""What a committed declaration says, and the four ways it is refused."""

from __future__ import annotations

import pathlib

import pytest

from backend.mcp.declaration import (
    Declaration,
    DeclarationRefusal,
    DeclarationRefused,
    declaration_at,
)

COMPLETE = """
[target]
name = "checkout-agent"
url = "https://staging.example.test/agent"
auth_token = "t-123"
agent_type = "assistant"
exposes_tool_calls = true
declared_tools = ["search", "email"]
retains_session_state = true
holds_personal_records = false
nonce = "n-abc"
note_planted = true
nonce_planted = true
echo_waived = false

[attestation]
identity = "matteo"
authorised_to_test = true
not_production = true
accepts_provider_policy_and_cost = true

[cost]
price_per_call = "0.002"
currency = "USD"
"""


def _written(tmp_path: pathlib.Path, body: str) -> pathlib.Path:
    path = tmp_path / "agentaudit.toml"
    path.write_text(body, encoding="utf-8")
    return path


def test_a_complete_declaration_reads_every_field(tmp_path: pathlib.Path) -> None:
    read = declaration_at(_written(tmp_path, COMPLETE))
    assert read == Declaration(
        name="checkout-agent",
        url="https://staging.example.test/agent",
        auth_token="t-123",
        agent_type="assistant",
        exposes_tool_calls=True,
        declared_tools=("search", "email"),
        retains_session_state=True,
        holds_personal_records=False,
        nonce="n-abc",
        note_planted=True,
        nonce_planted=True,
        echo_waived=False,
        identity="matteo",
        authorised_to_test=True,
        not_production=True,
        accepts_provider_policy_and_cost=True,
        price_per_call="0.002",
        currency="USD",
    )


def test_the_conservative_defaults_are_the_strict_ones(tmp_path: pathlib.Path) -> None:
    """An omitted field never buys a waiver.

    `nonce_planted` defaults true and `echo_waived` false for the reason
    `StartRunRequest` gives: a waiver obtainable by leaving a field out is a
    waiver nobody makes on purpose.
    """
    minimal = """
[target]
name = "a"
url = "https://staging.example.test/agent"

[attestation]
identity = "matteo"
authorised_to_test = true
not_production = true
accepts_provider_policy_and_cost = true
"""
    read = declaration_at(_written(tmp_path, minimal))
    assert (read.nonce_planted, read.echo_waived, read.note_planted) == (
        True,
        False,
        False,
    )
    assert (read.exposes_tool_calls, read.declared_tools) == (False, ())
    assert (read.price_per_call, read.currency) == (None, "")


def test_a_missing_file_is_refused_by_name(tmp_path: pathlib.Path) -> None:
    with pytest.raises(DeclarationRefused) as refused:
        declaration_at(tmp_path / "agentaudit.toml")
    assert refused.value.refusal is DeclarationRefusal.NO_FILE


def test_a_callback_target_is_refused_and_points_at_the_action(
    tmp_path: pathlib.Path,
) -> None:
    """The API takes a URL. A callback is imported from a checkout, which is the
    Action's shape and not this surface's — so it is refused by name rather than
    silently dropped."""
    body = """
[target]
name = "a"
callback = "mypkg.agent:reply"

[attestation]
identity = "matteo"
authorised_to_test = true
not_production = true
accepts_provider_policy_and_cost = true
"""
    with pytest.raises(DeclarationRefused) as refused:
        declaration_at(_written(tmp_path, body))
    assert refused.value.refusal is DeclarationRefusal.NOT_AN_ENDPOINT
    assert "action" in str(refused.value).lower()


def test_an_unattested_declaration_is_refused(tmp_path: pathlib.Path) -> None:
    body = COMPLETE.replace("not_production = true", "not_production = false")
    with pytest.raises(DeclarationRefused) as refused:
        declaration_at(_written(tmp_path, body))
    assert refused.value.refusal is DeclarationRefusal.NOT_ATTESTED
    assert "not_production" in str(refused.value)


def test_an_empty_identity_is_refused(tmp_path: pathlib.Path) -> None:
    body = COMPLETE.replace('identity = "matteo"', 'identity = ""')
    with pytest.raises(DeclarationRefused) as refused:
        declaration_at(_written(tmp_path, body))
    assert refused.value.refusal is DeclarationRefusal.NO_IDENTITY
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest backend/tests/test_mcp_declaration.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.mcp.declaration'`.

- [ ] **Step 3: Write the implementation**

`backend/declaration.py`. Use `tomllib` from the standard library. Structure:

```python
"""`agentaudit.toml`: what the operator declared about their target, committed.

**Read, never written.** No tool edits this file, fills a field it found empty or
declares a control on the operator's behalf. A surface that could write a
declaration is a surface that could declare a control, and every
`attributed_cause` in a report is read against what this file says
([ADR-0100](../../docs/adr/0100-the-mcp-server-has-no-privilege-the-console-lacks.md)).

**The defaults are the strict ones.** `nonce_planted` defaults true and
`echo_waived` false, for the reason `StartRunRequest` states at the same two
fields: a waiver obtainable by omitting a field is a waiver nobody makes on
purpose. Four refusals rather than prose, on the reasoning every closed set in
this codebase carries.

**A callback is refused rather than carried.** `TargetRequest` takes a `url`; a
callback is an object imported out of a checkout, which is the Action's shape
(ADR-0066) and unreachable over HTTP. Passing one through would produce a run
against nothing.
"""
```

Then `DeclarationRefusal(StrEnum)` with a docstring per member, `DeclarationRefused(ValueError)` taking `refusal` and a sentence, the frozen `Declaration` dataclass, and:

```python
def declaration_at(path: pathlib.Path) -> Declaration:
    if not path.is_file():
        raise DeclarationRefused(
            DeclarationRefusal.NO_FILE,
            f"no declaration at {path}: this surface runs against a target declared "
            "in a committed file, and the first run against a new target is "
            "registered in the console",
        )
    document = tomllib.loads(path.read_text(encoding="utf-8"))
    target = document.get("target", {})
    attestation = document.get("attestation", {})
    cost = document.get("cost", {})
    if not target.get("url"):
        raise DeclarationRefused(
            DeclarationRefusal.NOT_AN_ENDPOINT,
            "this target declares no url. A callback target is imported out of a "
            "checkout and is the Action's shape, not this surface's — run it "
            "through the Action instead",
        )
    if not attestation.get("identity"):
        raise DeclarationRefused(
            DeclarationRefusal.NO_IDENTITY,
            "this declaration names nobody. An attestation is a statement somebody "
            "made, and a run recorded against an empty identity is a run nobody "
            "made (ADR-0007)",
        )
    withheld = [
        statement
        for statement in (
            "authorised_to_test",
            "not_production",
            "accepts_provider_policy_and_cost",
        )
        if not attestation.get(statement)
    ]
    if withheld:
        raise DeclarationRefused(
            DeclarationRefusal.NOT_ATTESTED,
            f"withheld: {', '.join(withheld)} — a run does not start on a "
            "statement the operator did not make (ADR-0007)",
        )
    return Declaration(
        name=str(target["name"]),
        url=str(target["url"]),
        auth_token=str(target.get("auth_token", "")),
        agent_type=str(target.get("agent_type", "assistant")),
        exposes_tool_calls=_flag(target, "exposes_tool_calls", False),
        declared_tools=_words(target, "declared_tools"),
        retains_session_state=_flag(target, "retains_session_state", False),
        holds_personal_records=_flag(target, "holds_personal_records", False),
        nonce=str(target.get("nonce", "")),
        note_planted=_flag(target, "note_planted", False),
        nonce_planted=_flag(target, "nonce_planted", True),
        echo_waived=_flag(target, "echo_waived", False),
        identity=str(attestation["identity"]),
        authorised_to_test=_flag(attestation, "authorised_to_test", False),
        not_production=_flag(attestation, "not_production", False),
        accepts_provider_policy_and_cost=_flag(
            attestation, "accepts_provider_policy_and_cost", False
        ),
        price_per_call=(
            None if cost.get("price_per_call") is None else str(cost["price_per_call"])
        ),
        currency=str(cost.get("currency", "")),
    )
```

Read `price_per_call` as `cost.get("price_per_call")` and leave `None` alone — *not priced* and *free* are different facts.

**Do not coerce a declared value; read it.** `bool("no")` is `True`, so `bool(target.get("echo_waived", False))` turns the word that withholds a waiver into the waiver itself, and `tuple(str(t) for t in "search")` reads a bare string as six one-letter tools against which every real call scores as scope creep. Two module-level helpers do the reading instead, and a wrong-typed value raises rather than joining the four refusals — a file that cannot be read is not a declaration whose contents can be argued with:

```python
def _flag(table: dict[str, Any], key: str, default: bool) -> bool: ...
def _words(table: dict[str, Any], key: str) -> tuple[str, ...]: ...
```

Two tests beyond the six above cover them: `echo_waived = "no"` and `declared_tools = "search"` each raise a `TypeError` naming the field. The attestation booleans are read the same way rather than hardcoded `True` — the `withheld` guard above makes them true either way, and reading records the file rather than an assertion.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest backend/tests/test_mcp_declaration.py -q`
Expected: 6 passed.

- [ ] **Step 5: Drive one test red for the right reason**

Change the `echo_waived` default from `False` to `True` in `declaration_at`. Run the tests.
Expected: `test_the_conservative_defaults_are_the_strict_ones` FAILS on the tuple assertion. Revert.

- [ ] **Step 6: Full checks and commit**

```bash
uv run pytest -q && uv run mypy && uv run ruff check . && uv run ruff format --check .
git add backend/declaration.py backend/tests/test_mcp_declaration.py
git commit -m "A committed declaration says what the target is, and four refusals say what it is not"
```

---

### Task 4: The compact reading

**Files:**
- Create: `backend/mcp/reading.py`
- Test: `backend/tests/test_mcp_reading.py`

**Interfaces:**
- Consumes: the package from Task 2, ADR-0101 from Task 1.
- Produces:
  - `PROSE_ONLY: frozenset[str]` — the keys a compact reading may drop: `{"stated", "attributed_cause_stated", "informed_by_stated"}`.
  - `compact_finding(finding: Mapping[str, Any]) -> dict[str, Any]`
  - `compact_report(payload: Mapping[str, Any], *, urls: Mapping[str, str]) -> dict[str, Any]`
- Task 6 calls `compact_report` and nothing else in this module.

The rule from ADR-0101, stated as code: `set(payload_finding) - set(compact_finding) == PROSE_ONLY`. A label added to `ReportedFinding` later shows up in that difference and fails the test, which is the point.

- [ ] **Step 1: Write the failing tests**

**Corrected while Task 4 was built, and the correction is the point of this step.** The draft below carried a hand-written `A_FINDING` dict and a `compact_report` fixture whose figures sat under a top-level `"families"` key. The served payload has no such key: `payload.document` writes `measured.deterministic`, `measured.judged` and the four absence lists beside them, and the rule they were measured at is `provenance.rule`. A `compact_report` reading `payload["families"]` would have returned an empty figures section on every real run — a silent drop, which is the exact failure ADR-0101 is written against. So:

- **Every fixture is a served payload.** Build the finding through `ReportedFinding.of` and serialise it through `payload.document`, the two functions the report route itself runs — `backend/tests/test_payload.py` exports `a_payload` and `a_result`, and `conftest.a_narration` writes the narration. A hand-written dict passes on the day `_finding` grows a key it does not carry, which is the day the rule is supposed to fail.
- **`compact_report` reads the payload's own key names** — `target`, `measured`, `findings`, `provenance.rule` — and reads them by index rather than with a default, so a bench that served a payload missing one raises instead of handing back a section quietly empty.

The tests that landed are in `backend/tests/test_mcp_reading.py`; read that file rather than the draft. Eight of them:

- `test_a_compact_finding_drops_prose_and_only_prose` — `set(payload_finding) - set(compact_finding(...)) == PROSE_ONLY`.
- `test_every_closed_set_member_in_the_findings_section_survives` — the walk of ADR-0101 §5, over a finding whose fix was withheld so that `withheld` is not the empty list every compaction survives. The closed sets are discovered off `sys.modules` rather than listed.
- `test_the_nested_readings_survive_as_their_member`, `test_the_two_sentences_are_carried_verbatim`.
- `test_a_broken_narrative_pass_is_not_an_empty_findings_list` and `test_all_four_readings_of_the_narrative_pass_reach_the_caller` — ADR-0050's four.
- `test_nothing_in_the_reading_is_computed` — every leaf of the reading is a payload leaf **at the path it was copied from**. By path and not by value: a computed count equals some other number in the document about half the time, and the by-value draft of this test let a `len(findings)` mutation through.
- `test_the_attempts_per_case_sentence_is_not_dropped_with_the_rest` — ADR-0101 §2's exception, which is why the drop is by key and nothing here matches `*_stated`.

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest backend/tests/test_mcp_reading.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.mcp.reading'`.

- [ ] **Step 3: Write the implementation**

`compact_finding` copies every key except `PROSE_ONLY` and replaces the two nested records with their `reading` member. `compact_report` returns `{"target", "measured", "findings", "rule", "artefacts"}` — and builds each of those *by difference*, not by naming the keys inside it: the findings section is `without_prose(findings)` with only the findings themselves rebuilt, so `reading`, `reproducibility`, `instrument_failure` and any key added to `payload._findings` later travel with no edit. Naming them was the alternative ADR-0101 rejected by name. One recursive walk drops the prose keys at every depth, so a nested closed set is kept by the same default that keeps a top-level one, and the walk's set is `PROSE_ONLY` plus `reproducibility_stated` — the one key ADR-0101 §2 names, one key longer and not one *suffix* longer.

Module docstring must link ADR-0101 and state the local consequence: this is the one place a label could be dropped, which is why it is one place.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest backend/tests/test_mcp_reading.py -q`
Expected: 8 passed.

- [ ] **Step 5: Drive the walk test red for the right reason**

Add `"withheld"` to `PROSE_ONLY` — a label, not prose. Run the tests.
Expected — and **not** what the draft said: `test_every_closed_set_member_in_the_findings_section_survives` FAILS with `'fix'` extra in the left set, and `test_a_compact_finding_drops_prose_and_only_prose` **passes**. It has to: its expected value *is* `PROSE_ONLY`, so widening the constant widens the assertion with it. The set difference holds the shape of the compaction against a declared list; only the walk holds the list itself against the payload, which is why ADR-0101 §5 asks for a walk. Revert.

Then drive the rest one mutation at a time — the two nested records carried whole, a `*_stated` suffix rule (fails at `attempts_per_case_stated`), the findings list emptied, `len(findings)` written into the reading, the reading derived from whether the list is empty, and a sentence truncated on the way out.

- [ ] **Step 6: Full checks and commit**

```bash
uv run pytest -q && uv run mypy && uv run ruff check . && uv run ruff format --check .
git add backend/mcp/reading.py backend/tests/test_mcp_reading.py
git commit -m "A compact reading drops prose and never a label"
```

---

### Task 5: The HTTP client and its named failures

**Files:**
- Create: `backend/mcp/client.py`
- Test: `backend/tests/test_mcp_client.py`

**Interfaces:**
- Consumes: `Declaration` from Task 3.
- Produces:
  - `BenchUnreachable(RuntimeError)`, `BenchRefused(RuntimeError)` (attributes `status: int`, `detail: str`; `status` raises the one instance of it the bench did not send — a synthesised `404` for an id on no row of `GET /runs`, since that route answers `200` and a list), `NoEstimate(RuntimeError)`, `ReportNotSigned(RuntimeError)`.
  - `class BenchClient` with `__init__(self, http: httpx.Client)` and methods `issue_nonce() -> str`, `start(declaration: Declaration) -> dict[str, Any]`, `approve(run_id: str, *, identity: str, confirmed: bool, reason: str = "") -> dict[str, Any]`, `status(run_id: str) -> dict[str, Any]`, `report(run_id: str) -> dict[str, Any]`, `artefact_urls(run_id: str) -> dict[str, str]`. `status` reads **this run's row of `GET /runs`** and not the per-run progress route, because that is the route ADR-0100 §1 and spec §73 name for `run_status`; a row carries the standing, the record's sentence for it and the two spends, which is the whole of what a poller asks.
- Task 6 constructs one `BenchClient` and calls only these.

**Decided, in [ADR-0102](../../adr/0102-the-declaration-file-carries-the-four-rule-of-two-declarations.md):** the declaration file carries the four (`processes_untrusted_input`, `reaches_private_data`, `changes_state_or_communicates`, `under_human_supervision`) in its `[target]` table, `Declaration` holds them as `bool | None`, and an absent key is *unstated* rather than `False` — `False` is the profitable claim on these four, so defaulting to it would be the reader declaring a control the operator did not. Task 3's `Declaration` and `declaration_at` gained the fields and a `_tristate` reader beside `_flag`; `start` puts them on the `target` object. No reading is fetched on this surface — the standing's home here is Annex IV section 3 of the signed report, because there is no register screen to print it on. `agentaudit.toml.example` (#186) must show all four, commented, with *absent means unstated* beside them — **and `sends`, commented out, noting that an absent key leaves the bench its own `RetryPolicy` ceiling.**

Tests run against the real app through the `api()` context manager that `backend/tests/test_api_runs.py` already defines — Step 1 below reads it. No recorded fixtures: a payload shape that moves must break these tests in CI.

- [ ] **Step 1: Read the app harness these tests must reuse**

Run: `sed -n '277,310p' backend/tests/test_api_runs.py`

`backend/tests/test_api_runs.py` defines a module-level `@contextmanager def api(cases, adaptive=..., approval_wait_seconds=60.0, report=None) -> Iterator[tuple[TestClient, BenchRuns]]`. It builds the app through `create_app(BenchConfig(...))`, yields a `TestClient` and the `BenchRuns` registry, and — importantly — answers every halt the test left open on the way out, because a run left waiting attacks its target inside whichever test is running by then.

Import it: `from backend.tests.test_api_runs import api`. Do not build a second harness, and do not copy it — a second copy is a second thing to keep in step with `create_app`.

Pass the `TestClient` itself: it is a client of exactly this shape, and `httpx.ASGITransport` is an *async* transport that a sync `httpx.Client` cannot take, so the wrapping alternative does not exist. **One cast is needed and it is not optional.** Starlette's `TestClient` extends `httpx2.Client` (httpx 2.x, pulled in by starlette) while this project declares `httpx` 0.28 — same class, same methods, two distributions, no shared supertype. Keep the `cast(httpx.Client, client)` in one helper in this test module and say there that it is a fact about the packages. The consequence to know: an `httpx2` client raises `httpx2.TransportError`, which `client.py`'s `except httpx.TransportError` does not catch, so the `BenchUnreachable` test must use a real `httpx.Client` — which it does anyway, since a transport failure is the one thing an in-process client cannot produce.

- [ ] **Step 2: Write the failing tests**

Cover, one test each:
- `issue_nonce` returns the value `POST /nonces` issued.
- `start` posts a body assembled from a `Declaration` and returns the run id, status and estimate.
- `start` on a target the bench has no nonce for raises `BenchRefused` with `status == 422` and the route's own detail in `detail`.
- `approve(confirmed=False)` leaves the run unconfirmed, and the returned status differs from a confirmed one.
- `report` on a run that was never signed raises `ReportNotSigned` carrying the refusal's `outcome` and reason from the 409 body. Reached by confirming a run on the default `api()` bench, which holds no signing key, and waiting for it with `settled`.
- the four Rule of Two declarations reach the `TargetConfig` the bench registered (ADR-0102). Read off the record and never off the response.
- `status` returns the run's progress — folded into the never-signed test, where a `completed` status is what makes *never signed* the fact under test.
- a 500 from `POST /runs` is `NoEstimate`, provoked by monkeypatching `bench.start` to raise `run_state.NeverPresented`.
- A client pointed at a closed port raises `BenchUnreachable` naming the base URL — use `httpx.Client(base_url="http://127.0.0.1:9")` for this one, no app.
- `artefact_urls` returns the four URLs and fetches none of them.

Each assertion checks the *named* error type, not a message substring, except where the test asserts a detail is carried through.

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest backend/tests/test_mcp_client.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.mcp.client'`.

- [ ] **Step 4: Write the implementation**

The client owns request assembly and error translation and nothing else. `start` builds `StartRunRequest`'s JSON shape from the `Declaration`: `target` (`name`, `url`, `auth_token`, `agent_type`, `exposes_tool_calls`, `declared_tools`, `retains_session_state`, `holds_personal_records`, the four Rule of Two tri-states, and `sends`), `attestation` (`identity` and the three statements), `nonce`, `cost` (`price_per_call`, `currency`), then `note_planted`, `nonce_planted`, `echo_waived`. **This list was short by `sends`** — the field list above originally stopped at `holds_personal_records`, and `TargetRequest` has one more: `sends`, *what the enforced ceiling is built from, so it is the caller's declaration and not a constant hidden inside the bench*. The console declares it (`frontend/src/register/declarations.ts`) and the file could not, so every run from this surface silently took `RetryPolicy`'s default. `Declaration.sends` is `int | None` and an absent key puts **no `sends` key on the wire at all** rather than a number this reader picked: the default is built from `RetryPolicy`, which is behind the wall this package may not import (ADR-0100), so saying nothing is the only way to let the route own it. `_count` beside `_flag` and `_tristate` refuses a `bool` before it accepts an `int` (`isinstance(True, int)` is true) and refuses anything below 1.

Translate: `httpx.ConnectError`/`httpx.ConnectTimeout` → `BenchUnreachable`, and **the connect class only** — a read that timed out is a request that went out, and on `POST /runs` that is a run the bench may well have started, so a caller told *nothing answered* would start it again. 422 → `BenchRefused`. **409 and not 404** on the report route → `ReportNotSigned`, carrying the `Refusal`'s `outcome` as well as its `statement`: the report route's `detail` is **not a string**, it is `{"outcome", "statement"}`; the `409` covers `in_flight` and `did_not_complete` as well as `never_signed`, so the name has to travel; and the `404` beside it is *no such run* and *lost with its process*, which are an id nobody can fetch a report for rather than a run whose report does not exist. A 500 on `POST /runs` that carries a JSON `detail` → `NoEstimate`. **The plan's earlier wording was wrong about that last one:** the route sends `str(unpresented)` and the detail does *not* contain the string `NeverPresented`, so the translation is keyed on the route, which declares exactly one 500 — a translation keyed on prose stops being correct the day somebody rewords the sentence — and narrowed by the presence of the `detail` **key**, so a 500 the route did not mean is not reported as a graph that reached no interrupt. Key on the key and not on `detail != response.text`: that proxy reads a 500 whose body is a bare JSON string as a graph that reached no interrupt, which is the case this narrowing exists to exclude. `report` must ask the same question **only on the 409** — asking it of every response parses the whole signed payload on a `200` to answer a question about a status code. Any other non-2xx → `BenchRefused`.

Module docstring: this module is the only place an HTTP status becomes a named failure, so a caller never branches on a number.

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest backend/tests/test_mcp_client.py -q`
Expected: all pass.

- [ ] **Step 6: Drive one test red for the right reason**

Make the 409 branch fall through to `BenchRefused`. Run the tests.
Expected: the never-signed test FAILS with `BenchRefused` raised where `ReportNotSigned` was expected. Revert.

The same for each test added since: blank `target["sends"]` (the ceiling test fails `assert 3 == 5`), misspell one `ARTEFACT_ROUTES` entry (the route test fails against `report_paths`), return `{}` from `status` before its raise, and make `_count` accept anything.

- [ ] **Step 7: Full checks and commit**

```bash
uv run pytest -q && uv run mypy && uv run ruff check . && uv run ruff format --check .
git add backend/mcp/client.py backend/tests/test_mcp_client.py
git commit -m "One client speaks to the bench, and every status becomes a named failure"
```

---

### Task 6: The four tools

**Files:**
- Create: `backend/mcp/server.py`
- Test: `backend/tests/test_mcp_tools.py`

**Interfaces:**
- Consumes: `declaration_at` (Task 3), `compact_report` (Task 4), `BenchClient` and its errors (Task 5).
- Produces: `build_server(client: BenchClient, declaration_path: pathlib.Path) -> MCPServer`, registering exactly four tools named `start_run`, `approve_run`, `run_status`, `run_report`.
- Task 7 calls `build_server`.

The tools are async and tested by awaiting `server.call_tool(name, arguments)` directly — mcp 2.2.0 exposes it on `MCPServer`, so no client session is needed.

- [ ] **Step 1: Write the failing tests**

```python
"""The four tools, exercised against the real app through the real server."""

from __future__ import annotations

import pathlib
from collections.abc import Iterator
from contextlib import contextmanager

import httpx
import pytest

from backend.mcp.client import BenchClient
from backend.mcp.server import build_server
from backend.tests.test_api_runs import api

DECLARED = """
[target]
name = "checkout-agent"
url = "https://staging.example.test/agent"
auth_token = "t-123"
agent_type = "assistant"

[attestation]
identity = "matteo"
authorised_to_test = true
not_production = true
accepts_provider_policy_and_cost = true

[cost]
price_per_call = "0.002"
currency = "USD"
"""


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@contextmanager
def served(tmp_path: pathlib.Path, cases: list, document: str) -> Iterator[tuple]:
    """One MCP server over one bench, and the declaration file it reads.

    The path is yielded as well as the server: a run only starts on a nonce this
    bench issued, which is not known until the bench exists, so a test that starts
    one writes the real declaration over this one and the tools read it on the next
    call. The `TestClient` is handed to `BenchClient` through the same one-line cast
    `test_mcp_client.py` justifies, rather than through a second ASGI transport.
    """
    declaration = tmp_path / "agentaudit.toml"
    declaration.write_text(document, encoding="utf-8")
    with api(cases) as (client, bench):
        yield (
            build_server(BenchClient(cast(httpx.Client, client)), declaration),
            client,
            bench,
            declaration,
        )


@pytest.mark.anyio
async def test_exactly_four_tools_are_registered(
    tmp_path: pathlib.Path,
) -> None:
    """A fifth tool is a fifth route. The count is asserted so that adding one is
    a decision somebody makes on purpose (ADR-0100)."""
    with served(tmp_path, [], DECLARED) as (server, _client, _bench, _path):
        assert sorted(tool.name for tool in await server.list_tools()) == [
            "approve_run",
            "run_report",
            "run_status",
            "start_run",
        ]


@pytest.mark.anyio
async def test_start_run_halts_and_returns_the_estimate() -> None:
    """It returns the figures and stops. The run is not confirmed by starting it."""


@pytest.mark.anyio
async def test_no_argument_to_start_run_reaches_a_confirmed_run(
    tmp_path: pathlib.Path,
) -> None:
    """The consent seam, asserted by trying to cross it (ADR-0007). `start_run`
    publishes no argument a caller could confirm with, and an invented one changes
    nothing about the run it starts.

    **Not `pytest.raises`.** mcp 2.2.0 validates arguments against a pydantic model
    built from the signature, and that model's `extra` is pydantic's default —
    `ignore`. An invented argument is dropped, not refused, so a test that asserted
    a raise would be asserting a behaviour this library does not have, and would go
    green again the day the tool grew the parameter for an unrelated reason. What is
    asserted instead is the schema a model reads and the standing of the run a model
    gets: the field is not in `tool.input_schema["properties"]`, the run is still
    holding its interrupt, and nothing arrived at the target's ledger.
    """
    with served(tmp_path, [leakage_case], DECLARED) as (server, client, bench, path):
        (tool,) = [one for one in await server.list_tools() if one.name == "start_run"]
        path.write_text(declared(watched.target, registered(client, watched)))
        started = answered(await server.call_tool("start_run", {"confirmed": True}))
        ...


@pytest.mark.anyio
async def test_approve_run_confirms_and_start_run_did_not() -> None:
    """Two calls, and only the second one spends."""


@pytest.mark.anyio
async def test_run_report_returns_the_compact_reading_with_urls() -> None:
    """The findings, the labels, and the four artefact URLs — and no artefact
    content."""


@pytest.mark.anyio
async def test_an_unreachable_bench_is_a_stated_failure() -> None:
    """Not a stack trace, and not an empty result: a caller told nothing would
    read a bench that found nothing."""
```

Fill the remaining four bodies with the `served` helper above, taking `tmp_path` and the cases each one needs — reuse the same one-case list `test_api_runs.py` builds for a fast run rather than the whole library. The `anyio_backend` fixture is in this module and not in a shared conftest, because it is this file's requirement and no other test file in `backend/tests/` is async today.

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest backend/tests/test_mcp_tools.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.mcp.server'`.

- [ ] **Step 3: Write the implementation**

```python
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
```

`build_server` creates `MCPServer(name="agentaudit", instructions="An adversarial test bench for AI agents. Runs are declared in a committed agentaudit.toml and cost real inference budget: start_run returns an estimate and spends nothing, approve_run spends it. This surface cannot register a target, start a gate run, or write a patch.")` and registers four functions with `@server.tool(...)`. Annotations carry the honest hints: `run_status` and `run_report` are `read_only_hint=True`; `start_run` and `approve_run` are not, and `approve_run` is the one that spends.

`start_run` takes **no arguments at all** — not even a declaration path override. An argument is the one part of a tool a prompt can set, and a path argument is a caller choosing which target the run is against; the file `build_server` was handed is the operator's. It reads the declaration, issues a nonce only when the file carries none, calls `client.start`, and returns the run id, the status, the estimate and both ceilings — which are `BudgetPayload.scored_ceiling` and `adaptive_ceiling`, inside the estimate rather than beside it. A nonce issued here is returned to be planted: the run is holding its interrupt and the registration probe goes out after the approval, so planting it then is in time. It never calls `approve`.

`approve_run(run_id: str, confirmed: bool, reason: str = "")` passes the declaration's identity through.

Every named error from Task 5 and Task 3 becomes a `ToolError` whose message is the refusal's own sentence. Nothing is caught bare.

The tool descriptions state what the surface will not do — no registration, no gate run, no patch — because a description is what a model reads before it asks.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest backend/tests/test_mcp_tools.py -q`
Expected: all pass.

- [ ] **Step 5: Drive the consent test red for the right reason**

Add a `confirmed: bool = False` parameter to `start_run` that calls `client.approve` when true. Run the tests.
Expected: `test_no_argument_to_start_run_reaches_a_confirmed_run` FAILS twice over — the run reaches `completed` where it should still be `awaiting_approval`, and `confirmed` appears in the tool's published schema. The spend is the graver half, so assert it first: the argument is ignored rather than refused, and a test whose only assertion was about the schema would pass a `start_run` that took the argument under another name. Revert.

- [ ] **Step 6: Full checks and commit**

```bash
uv run pytest -q && uv run mypy && uv run ruff check . && uv run ruff format --check .
git add backend/mcp/server.py backend/tests/test_mcp_tools.py
git commit -m "Four tools, and starting a run is not paying for one"
```

---

### Task 7: The entrypoint and the documentation

**Files:**
- Create: `backend/mcp/__main__.py`
- Create: `backend/tests/test_mcp_entrypoint.py`
- Create: `agentaudit.toml.example` (repo root)
- Modify: `README.md` — a section on running the MCP server
- Modify: `CLAUDE.md` — a line in the Commands block

**Corrected while executing.** This task's draft had no tests at all — Step 2 below was a manual `python -c` — and its load-bearing claim is a prohibition: *the entrypoint starts no bench, and a bench that is not there is a tool result rather than a boot failure*. A prohibition checked by hand once is a prohibition nobody checks again, so the module is split at two seams and both are asserted: `configured(environment)` returns the two defaults, and `serving(environment)` is the context manager `main` runs, which a test can list tools on and call a tool on without speaking stdio. The draft's `main` inlined both and left neither reachable.

**Interfaces:**
- Consumes: `build_server` from Task 6.
- Produces: `python -m backend.mcp` speaking stdio.

- [ ] **Step 1: Write the entrypoint**

```python
"""`python -m backend.mcp`: the tools over stdio, against a running bench.

It starts no bench. `AGENTAUDIT_API` names the running API and defaults to
`http://127.0.0.1:8000`, `AGENTAUDIT_DECLARATION` names the committed file and
defaults to `agentaudit.toml`; a bench that is not there is reported by the first
tool call as a stated failure rather than by this module as a crash at boot, because
a server that refused to start would leave a client with no way to say why.
"""

from __future__ import annotations

import os
import pathlib

import httpx

from backend.mcp.client import BenchClient
from backend.mcp.server import build_server

DEFAULT_API = "http://127.0.0.1:8000"
DEFAULT_DECLARATION = "agentaudit.toml"


def configured(environment: Mapping[str, str]) -> tuple[str, pathlib.Path]:
    return (
        environment.get("AGENTAUDIT_API", DEFAULT_API),
        pathlib.Path(environment.get("AGENTAUDIT_DECLARATION", DEFAULT_DECLARATION)),
    )


@contextmanager
def serving(environment: Mapping[str, str]) -> Iterator[MCPServer]:
    base_url, declaration = configured(environment)
    with httpx.Client(base_url=base_url, timeout=TIMEOUT_SECONDS) as http:
        yield build_server(BenchClient(http), declaration)


def main() -> None:
    with serving(os.environ) as server:
        server.run(transport="stdio")


if __name__ == "__main__":
    main()
```

The environment is a parameter and not a read of `os.environ`, so the two defaults are assertable without a test mutating the process it runs in.

- [ ] **Step 1b: Write the tests, and drive them red**

`backend/tests/test_mcp_entrypoint.py`: the two defaults, the two variables, and the prohibition — that `serving` against a port nothing listens on lists four tools *and then* raises `ToolError` naming the address on `start_run`, in that order, because an entrypoint that checked the connection would have raised before a client could read anything. Drive it red by adding a `http.get("/runs")` above the `yield`: `httpx.ConnectError` at boot, which is exactly the failure mode the module exists to avoid.

- [ ] **Step 2: Verify it starts and lists its tools**

Run: `uv run python -c "
import httpx, pathlib
from backend.mcp.client import BenchClient
from backend.mcp.server import build_server
import anyio
s = build_server(BenchClient(httpx.Client(base_url='http://127.0.0.1:8000')), pathlib.Path('agentaudit.toml'))
print(sorted(t.name for t in anyio.run(s.list_tools)))
"`
Expected: `['approve_run', 'run_report', 'run_status', 'start_run']`.

- [ ] **Step 3: Write `agentaudit.toml.example`**

The full `[target]`, `[attestation]` and `[cost]` tables, with a comment on each field saying what declaring it means — the same words the register walk uses, copied from `register/declarations.ts` and `RegisterScreen.tsx` rather than paraphrased. A comment at the top: this file is read and never written, and what it claims is what every `attributed_cause` in the report is read against.

**Not Task 3's `COMPLETE` fixture, which answers everything.** Five keys are commented out rather than filled in — the four Rule of Two declarations and `sends` — because an example is copied: a file that answered all four would make every operator who copied it declare four controls they never considered, and `False` is the flattering claim on three of them (ADR-0102). `sends` is left off for its own reason, that the route applies the bench's `RetryPolicy` ceiling and a number here would override a default this file cannot see. Two tests hold it: the example is read through `declaration_at`, and the five read as unstated.

`agentaudit.toml.example` is at the repository root and `agentaudit.toml` is not in `.gitignore`, which is correct — the operator's own file is meant to be committed.

- [ ] **Step 4: Document it**

`README.md`: how to register once in the console, copy the example, start the API, and add the server to a client — including the config block:

```json
{"mcpServers": {"agentaudit": {"command": "uv", "args": ["run", "python", "-m", "backend.mcp"], "env": {"AGENTAUDIT_API": "http://127.0.0.1:8000", "AGENTAUDIT_DECLARATION": "agentaudit.toml"}}}}
```

The README links `INSTRUCTIONS` in `server.py` rather than restating it, per `CLAUDE.md`.

State plainly that `start_run` does not spend and `approve_run` does.

`CLAUDE.md`, in the Commands block:

```
uv run python -m backend.mcp   # the MCP tools over stdio, against a running API
```

- [ ] **Step 5: Full checks and commit**

```bash
uv run pytest -q && uv run mypy && uv run ruff check . && uv run ruff format --check .
git add backend/mcp/__main__.py backend/tests/test_mcp_entrypoint.py agentaudit.toml.example README.md CLAUDE.md
git commit -m "The MCP server runs over stdio and the declaration has an example"
```

---

## Notes for the executor

**What is deliberately not here.** Registration, a commit field in the payload, snippet generation, driving the proof loop, elicitation-based approval, unattended self-approving runs, and gate-run tools. Each is argued in the spec's Out of Scope. If a task seems to need one, the task is wrong — stop and say so.

**Story 3 is only half-delivered by this plan, on purpose.** The spec says one declaration is read by both the Action and the MCP server. This plan gives `agentaudit.toml` the Action's own vocabulary, so the two agree in shape — but `action.yml` still takes its inputs as workflow inputs and reads no TOML. Making it read this file is a change to the Action's interface and belongs to its own issue, not to a task here. Until that lands, the two surfaces are declared consistently and not from one source.

**The two tests that carry the design** are the label-preservation walk (Task 4, Step 5) and the consent-seam bypass (Task 6, Step 5). Both are prohibitions, and a prohibition is only kept by structure. Do not weaken either into a check of a hand-written field list.
