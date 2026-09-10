# ADAPTIVE_ON_TARGET and the single-model bar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A route the adaptive attacker finds against a user's target enters the library on the single-model bar of ADR-0003, while a route found against the three reference agents keeps the cross-model bar of ADR-0012 — and `/pending-routes` therefore measures on one declared reference model instead of two.

**Architecture:** A fifth `DiscoveredBy` member carries the distinction. It is declared by whoever builds an `AttackableTarget` and threaded down to `proposed_from`, which today hardcodes `DiscoveredBy.ADAPTIVE` for every route whatever it was found against. `bar_for` gains a branch, and the invariant is then carried by the type: nothing downstream re-decides which bar applies. The pending-routes surface drops its second pass because after the mapping change every proposal it sees faces a one-model bar.

**Tech Stack:** Python 3.12, `uv`, pytest, mypy (strict), Ruff; React + TypeScript + Vitest for the console.

**Spec:** [docs/adr/0107-a-route-found-against-a-customers-target-faces-the-single-model-bar.md](../../adr/0107-a-route-found-against-a-customers-target-faces-the-single-model-bar.md) — the accepted decision this plan implements. Read it first; its four numbered decisions map to Tasks 1-6 and its Consequences list is what Task 7 has to write down.

## Global Constraints

- **No adaptive result may write into a scored rate** (ADR-0010). Nothing in this plan touches `Attempt`, a rate, or a denominator. An `AdaptiveEpisode` is not an `Attempt`; if a signature starts wanting both, stop.
- **Drive every new test red once before committing.** Break the thing it guards on purpose, confirm it fails *for the right reason* — not by import error or typo — then revert. Every task below has an explicit "verify it fails" step and an expected failure message; a step that fails with `ImportError` or `AttributeError` when the plan says `AssertionError` has not been driven red.
- **Never merge on red CI.** Report back instead.
- **A decision belongs in an ADR; its local consequence belongs in a docstring.** ADR-0107 is already written and accepted — do not extend it, and do not append to ADR-0012 or ADR-0003. Docstrings link to ADR-0107 and state the local consequence only.
- **Do not run `pytest` while a gate run or a pending-routes run is in flight.** The case-library lease makes `test_gate`, `test_multi_model` and `test_api_gate_runs` fail spuriously.
- Commands: `uv run pytest -q`, `uv run mypy`, `uv run ruff check .`, `uv run ruff format .`. Frontend: `cd frontend && npm test`.
- The parameter and field name is `discovered_by` everywhere it appears — one name, so a reader can grep the whole thread.
- No enum member is inserted above an existing one. `DiscoveredBy` members print in declaration order in the provenance census (`admission.LibraryProvenance.stated`), and reordering that line breaks a comparison readers make across two gate runs.

---

### Task 1: The fifth provenance and its bar

**Files:**
- Modify: `backend/bench/library.py:246-291` (the `DiscoveredBy` enum), `backend/bench/library.py:2845-2872` (`bar_for`)
- Test: `backend/tests/test_admission.py`

**Interfaces:**
- Consumes: nothing — this is the first task.
- Produces: `DiscoveredBy.ADAPTIVE_ON_TARGET` (value `"adaptive_on_target"`), and `bar_for(DiscoveredBy.ADAPTIVE_ON_TARGET) is AdmissionBar.SINGLE_MODEL`. Every later task imports the member from `backend.bench.library`; `admission.bar_for` remains the public name for the function.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_admission.py`, directly after `test_a_retrieved_case_faces_the_single_model_bar_for_a_reason_of_its_own` (which ends at line 160):

```python
def test_a_route_found_against_a_target_faces_the_single_model_bar() -> None:
    # The fifth provenance, and the branch is its own rather than joined to the
    # three that share its answer. ADR-0012's bar answers a defect in one loop:
    # the attacker discovers on the three reference agents and the gate admits by
    # testing separation of those same three. A route found against a user's
    # target never ran in that loop — CONTEXT.md is explicit that a reference
    # agent is not a target — so the selection pressure the second bar counters is
    # not acting on it (ADR-0107).
    assert bar_for(DiscoveredBy.ADAPTIVE_ON_TARGET) is AdmissionBar.SINGLE_MODEL

    # And the narrowing is asserted from the other side: a route found against the
    # reference agents keeps the second bar, because there the argument is intact.
    assert bar_for(DiscoveredBy.ADAPTIVE) is AdmissionBar.CROSS_MODEL
```

`bar_for`, `AdmissionBar` and `DiscoveredBy` are already imported at the top of that file (lines 32 and 40ff) — add no imports.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/test_admission.py::test_a_route_found_against_a_target_faces_the_single_model_bar -q`

Expected: FAIL with `AttributeError: ADAPTIVE_ON_TARGET`. This one is an attribute error by construction — the member is the thing under test — so it is the right failure. The *red drive that matters* for this task is Step 6.

- [ ] **Step 3: Add the enum member**

In `backend/bench/library.py`, append to `DiscoveredBy` **after** `RETRIEVED` (which ends at line 291), and add the pointer paragraph to `ADAPTIVE`:

```python
    ADAPTIVE_ON_TARGET = "adaptive_on_target"
    """Found by the adaptive attacker against a **target** — a user's own agent.

    Last in the set, on `RETRIEVED`'s terms: the provenance census prints in this
    order and a member inserted above one already counted reorders a line readers
    of two gate runs compare (`admission.LibraryProvenance.stated`).

    Distinct from `ADAPTIVE` because the two were found in different loops and only
    one of them is the loop ADR-0012's bar was written about, so it faces the
    single-model rule of ADR-0003
    ([ADR-0107](../../docs/adr/0107-a-route-found-against-a-customers-target-faces-the-single-model-bar.md)).
    CONTEXT.md is what keeps the two names apart: a **target** is an agent belonging
    to a user, and a **reference agent** is test equipment that never reaches one.
    """
```

And amend `ADAPTIVE`'s docstring (line 267-269) so it says which loop it now means:

```python
    ADAPTIVE = "adaptive"
    """Found by the adaptive attacker against the three **reference agents**, and
    promoted through `propose_case`. Faces the second bar, because discovery and
    admission ran on the same set (ADR-0012). A route the same attacker found
    against a user's target is `ADAPTIVE_ON_TARGET` and faces the first
    (ADR-0107)."""
```

- [ ] **Step 4: Add the `bar_for` branch**

In `backend/bench/library.py`, inside `bar_for`'s `match`, add a branch of its own **after** the `RETRIEVED` branch (which ends at line 2872):

```python
        case DiscoveredBy.ADAPTIVE_ON_TARGET:
            # The same answer on a fourth reason, and its own branch rather than
            # joined above because it is a fourth reason and not a fourth name for
            # one of the three. The three above were fitted to nothing this bench
            # measures; this one was fitted to a target, which is not the thing it
            # is graded against — so discovery and admission did not run on one
            # set and ADR-0012's defect is not present. ADR-0107 decides it and
            # records what is given up: model-dependence is no longer caught at
            # admission for this population, only by the retirement signal.
            return AdmissionBar.SINGLE_MODEL
```

Also update the `DiscoveredBy` docstring's own summary of the mapping (lines 256-261), which currently says `ADAPTIVE` faces the cross-model bar without naming the fifth member:

```python
    The member is not decoration. `AUTHORED`, `USER_GAP` and `RETRIEVED` face the
    single-model bar of ADR-0003, and so does `ADAPTIVE_ON_TARGET` on a reason of
    its own (ADR-0107); `ADAPTIVE` faces the cross-model bar of ADR-0012, because
    the attacker discovers on the same three agents the gate admits against and a
    route fitted to that set has to prove itself on a model it was not fitted to.
    The mapping lives in `backend/bench/admission.py` and is applied to the record
    here by `Case.__post_init__`.
```

- [ ] **Step 5: Run the test and the census tests**

Run: `uv run pytest backend/tests/test_admission.py backend/tests/test_promotion.py -q`

Expected: the new test PASSES. `test_promotion.py` may now FAIL at `LibraryProvenance.__post_init__` with `the live census names no count for ['adaptive_on_target']` — its mappings at lines 245-260 are built by hand. That refusal is the type doing its job. Fix those mappings by adding `DiscoveredBy.ADAPTIVE_ON_TARGET: 0` to each hand-built census; do not weaken `__post_init__`.

- [ ] **Step 6: Drive the new test red for the right reason**

Temporarily change the new `bar_for` branch to `return AdmissionBar.CROSS_MODEL`.

Run: `uv run pytest backend/tests/test_admission.py::test_a_route_found_against_a_target_faces_the_single_model_bar -q`

Expected: FAIL with `AssertionError` on the first assert — **not** an `AttributeError` or an import error. Then revert the branch to `SINGLE_MODEL` and re-run to confirm PASS.

- [ ] **Step 7: Typecheck, lint, commit**

```bash
uv run mypy && uv run ruff check . && uv run ruff format --check .
git add backend/bench/library.py backend/tests/test_admission.py backend/tests/test_promotion.py
git commit -m "A route found against a target is its own provenance, on its own bar

ADR-0107 §1 and §2. \`bar_for\` gains a fourth reason for the same answer
rather than a fourth name for one of the three, and the census refuses a
mapping that leaves the new member out.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `proposed_from` is told what the route was found against

**Files:**
- Modify: `backend/bench/adaptive/proposal.py:128-142` (signature), `:210` (the hardcoded provenance), `:189-196` (the `not_tested` sentence)
- Test: `backend/tests/test_promotion.py`

**Interfaces:**
- Consumes: `DiscoveredBy.ADAPTIVE_ON_TARGET` from Task 1.
- Produces: `proposed_from(objective, target, family, payload, description, broken, discovered_by, today=None) -> ProposedRoute` — `discovered_by: DiscoveredBy` is keyword-or-positional but **required, with no default**, placed after `broken` and before `today`. It raises `ValueError` for any member that is not one of the two adaptive ones.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_promotion.py`. The existing `proposed_from` call sites in that file show how an objective and target are built — reuse whichever helper they use rather than inventing one:

```python
def test_a_proposal_records_what_the_route_was_found_against() -> None:
    # The provenance is the caller's declaration and not this function's guess:
    # `TargetConfig` describes a target and a reference agent alike and holds no
    # field that tells them apart, so a bar derived from it would move when
    # somebody renamed a fixture (ADR-0107 §3).
    against_a_target = proposed_from(
        objective=AN_OBJECTIVE,
        target=A_TARGET,
        family=Family.DATA_LEAKAGE,
        payload="the probe that worked",
        description="what the attacker did",
        broken=True,
        discovered_by=DiscoveredBy.ADAPTIVE_ON_TARGET,
    )
    assert against_a_target.case.discovered_by is DiscoveredBy.ADAPTIVE_ON_TARGET
    assert bar_for(against_a_target.case.discovered_by) is AdmissionBar.SINGLE_MODEL

    against_the_agents = proposed_from(
        objective=AN_OBJECTIVE,
        target=A_TARGET,
        family=Family.DATA_LEAKAGE,
        payload="the probe that worked",
        description="what the attacker did",
        broken=True,
        discovered_by=DiscoveredBy.ADAPTIVE,
    )
    assert against_the_agents.case.discovered_by is DiscoveredBy.ADAPTIVE
    assert bar_for(against_the_agents.case.discovered_by) is AdmissionBar.CROSS_MODEL


def test_a_proposal_refuses_a_provenance_the_attacker_cannot_have_found() -> None:
    # An authored case was written by hand and a retrieved one came out of a
    # published corpus. Neither is a thing this function can produce, and a
    # proposal carrying one would enter the library on a bar its provenance is a
    # lie about.
    for member in (
        DiscoveredBy.AUTHORED,
        DiscoveredBy.USER_GAP,
        DiscoveredBy.RETRIEVED,
    ):
        with pytest.raises(ValueError, match="the adaptive attacker"):
            proposed_from(
                objective=AN_OBJECTIVE,
                target=A_TARGET,
                family=Family.DATA_LEAKAGE,
                payload="the probe that worked",
                description="what the attacker did",
                broken=True,
                discovered_by=member,
            )
```

Replace `AN_OBJECTIVE` and `A_TARGET` with the file's own fixtures. Import `bar_for` and `AdmissionBar` from `backend.bench.admission` and `DiscoveredBy` from `backend.bench.library` if the file does not already.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest backend/tests/test_promotion.py -q -k "found_against or cannot_have_found"`

Expected: FAIL with `TypeError: proposed_from() got an unexpected keyword argument 'discovered_by'`.

- [ ] **Step 3: Add the required parameter and the refusal**

In `backend/bench/adaptive/proposal.py`, change the signature (line 128):

```python
def proposed_from(
    objective: Case,
    target: TargetConfig,
    family: AnyFamily,
    payload: str,
    description: str,
    broken: bool,
    discovered_by: DiscoveredBy,
    today: date | None = None,
) -> ProposedRoute:
```

Add to the docstring, after the `broken` paragraph:

```
    `discovered_by` says which loop this route was found in, and it is required for
    the reason `broken` is: it is a fact the record cannot be made honestly without.
    It decides the admission bar — `ADAPTIVE` against the three reference agents
    keeps ADR-0012's cross-model bar, `ADAPTIVE_ON_TARGET` against a user's own
    agent faces ADR-0003's single-model one — and it is the caller's declaration
    rather than a reading of `target`, which describes both kinds alike
    ([ADR-0107](../../../docs/adr/0107-a-route-found-against-a-customers-target-faces-the-single-model-bar.md)
    §3).
```

Add the refusal beside the other three, immediately before the `if not broken:` guard:

```python
    if discovered_by not in FOUND_BY_THE_ATTACKER:
        raise ValueError(
            f"a route proposed here is recorded as {discovered_by}, which is not a "
            "provenance the adaptive attacker can have found. An authored case was "
            "written by hand and a retrieved one came out of a published corpus, so "
            "a proposal carrying either would enter the library under a bar its own "
            "provenance is a lie about (ADR-0107)"
        )
```

and declare the closed pair at module level, beside the other two payload sets:

```python
FOUND_BY_THE_ATTACKER: frozenset[DiscoveredBy] = frozenset(
    {DiscoveredBy.ADAPTIVE, DiscoveredBy.ADAPTIVE_ON_TARGET}
)
"""The two provenances a proposal may carry, as a set rather than a pair of names.

Held here so that a sixth `DiscoveredBy` member is a decision somebody makes about
this set rather than a value that flows through by default. Which of the two a route
gets is the caller's declaration and never this module's guess (ADR-0107 §3).
"""
```

Then replace line 210's hardcoded value with the argument:

```text
            discovered_by=discovered_by,
```

- [ ] **Step 4: Fix the `not_tested` sentence**

Line 189-196 states the coverage claim as "until it has cleared the cross-model admission bar", which is now true of only one of the two. Make it name the bar the record actually faces:

```text
            external_id=ExternalId(
                identifier=objective.external_id.identifier,
                not_tested=(
                    "A route the adaptive attacker found. It makes no coverage "
                    f"claim until it has cleared the {bar_for(discovered_by)} "
                    "admission bar"
                ),
            ),
```

Import `bar_for` from `backend.bench.library` (it is defined there; `admission.bar_for` is the re-export for callers outside that module, and this module already imports from `library`).

- [ ] **Step 5: Run the tests**

Run: `uv run pytest backend/tests/test_promotion.py -q`

Expected: the two new tests PASS. Other tests in the file that call `proposed_from` will FAIL with `TypeError: missing 1 required positional argument: 'discovered_by'` — that is the required-argument design working. Fix each by passing `discovered_by=DiscoveredBy.ADAPTIVE`, which preserves what those tests were asserting.

- [ ] **Step 6: Drive the refusal red for the right reason**

Temporarily change `FOUND_BY_THE_ATTACKER` to `frozenset(DiscoveredBy)`.

Run: `uv run pytest backend/tests/test_promotion.py::test_a_proposal_refuses_a_provenance_the_attacker_cannot_have_found -q`

Expected: FAIL with `DID NOT RAISE <class 'ValueError'>` — not an import error. Revert and confirm PASS.

- [ ] **Step 7: Typecheck, lint, commit**

```bash
uv run mypy && uv run ruff check . && uv run ruff format --check .
git add backend/bench/adaptive/proposal.py backend/tests/test_promotion.py
git commit -m "A proposal is told which loop found it, and refuses a provenance it cannot have

ADR-0107 §3. Required with no default, on \`broken\`'s terms: a fact the
record cannot be made honestly without. The coverage sentence names the bar
the record actually faces rather than the cross-model one.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `AttackableTarget` carries it and the episode threads it down

**Files:**
- Modify: `backend/bench/adaptive/layer.py:72-97` (`AttackableTarget`), `:209-245` (`_open_episode`), `backend/bench/adaptive/attacker.py:195-245` (`run_episode` and `_Episode.__init__`), `:562-580` (`_propose`)
- Test: `backend/tests/test_adaptive_attacker.py`

**Interfaces:**
- Consumes: `proposed_from(..., discovered_by=...)` from Task 2.
- Produces: `AttackableTarget(target, canary, discovered_by, withdrawn=frozenset())` — `discovered_by: DiscoveredBy` is required, positioned third, before the defaulted `withdrawn`. `run_episode(..., discovered_by: DiscoveredBy, ...)` keyword-only, required. `_Episode.__init__` takes it and stores it as `self.discovered_by`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_adaptive_attacker.py`. Reuse the file's existing scripted-attacker fixtures — the one that drives an episode to a confirmed break and files a route:

```python
def test_an_episode_files_its_route_under_the_provenance_its_target_declared() -> None:
    # The thread ADR-0107 §3 asserts: the declaration is made where the target is
    # built and reaches the record without any step in between deciding it again.
    # Asserted on both members, because a thread that carried a constant would
    # pass a test that only ever looked at one.
    for declared in (DiscoveredBy.ADAPTIVE, DiscoveredBy.ADAPTIVE_ON_TARGET):
        episode = run_episode(
            target=A_BREAKABLE_TARGET,
            objective=AN_OBJECTIVE_IT_BREAKS,
            run_state=RunState(budget=A_BUDGET),
            attacker=an_attacker_that_files_its_break(),
            blinding=Blinding.NONE,
            discovered_by=declared,
        )
        assert episode.proposals, "the scripted attacker files a route on the break"
        for proposal in episode.proposals:
            assert proposal.case.discovered_by is declared
```

Replace the fixture names with the file's own. If the file's helper builds an `AttackableTarget` rather than calling `run_episode` directly, assert through `run_adaptive_layer` instead and pass `discovered_by` on the `AttackableTarget`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/test_adaptive_attacker.py -q -k provenance_its_target_declared`

Expected: FAIL with `TypeError: run_episode() got an unexpected keyword argument 'discovered_by'`.

- [ ] **Step 3: Add the field to `AttackableTarget`**

In `backend/bench/adaptive/layer.py`, add after `canary` (line 83) and before `withdrawn`:

```python
    discovered_by: DiscoveredBy
    """What a route found against this target is filed as, and so which bar it faces.

    Carried on the target rather than passed per episode, because it is a property
    of *what is being attacked* and not of one episode against it — and required
    with no default, so a caller that has not said which loop it is running cannot
    get the weaker bar by omission (ADR-0107 §3). `TargetConfig` deliberately does
    not tell a reference agent from a user's agent, so this cannot be derived from
    the field beside it.
    """
```

Import `DiscoveredBy` from `backend.bench.library`.

- [ ] **Step 4: Thread it through the episode**

`_open_episode` (layer.py:209) gains nothing new — it already holds `entry: AttackableTarget`. Pass the value down at the `run_episode` call (line 234):

```python
            episode = run_episode(
                target=entry.target,
                objective=Objective(family=family, case=objective, canary=entry.canary),
                run_state=run_state,
                # The target's own declaration, carried and not re-decided here: one
                # place says which loop this is, and every route the episode files
                # reads it from there (ADR-0107 §3).
                discovered_by=entry.discovered_by,
                attacker=attacker,
                ...
```

In `backend/bench/adaptive/attacker.py`, add the keyword-only required parameter to `run_episode` (after `blinding`, line 200) and to `_Episode.__init__` (after `blinding`, line 257), store it as `self.discovered_by = discovered_by` beside the other assignments (around line 267), pass it through the `_Episode(...)` construction, and use it at `_propose`'s `proposed_from` call (line 564):

```text
                broken=self.broken,
                discovered_by=self.discovered_by,
```

- [ ] **Step 5: Run the test**

Run: `uv run pytest backend/tests/test_adaptive_attacker.py backend/tests/test_promotion.py -q`

Expected: the new test PASSES. Every other construction of `AttackableTarget` or call of `run_episode` in the test suite FAILS with a missing-argument `TypeError`. Fix each with `discovered_by=DiscoveredBy.ADAPTIVE` — those tests are all about the reference-agent loop, so that preserves what they assert. `backend/tests/test_adaptive_on_the_elective_tier.py` builds its own `AttackableTarget`; it is in this list.

- [ ] **Step 6: Drive the thread red for the right reason**

Temporarily hardcode `discovered_by=DiscoveredBy.ADAPTIVE` at the `proposed_from` call in `_propose`, ignoring `self.discovered_by`.

Run: `uv run pytest backend/tests/test_adaptive_attacker.py -q -k provenance_its_target_declared`

Expected: FAIL with `AssertionError` on the `ADAPTIVE_ON_TARGET` half of the loop — proving the test reads the thread and not a constant. Revert and confirm PASS.

- [ ] **Step 7: Typecheck, lint, commit**

```bash
uv run mypy && uv run ruff check . && uv run ruff format --check .
git add backend/bench/adaptive/layer.py backend/bench/adaptive/attacker.py backend/tests/
git commit -m "The target declares which loop it is, and the episode carries it to the record

ADR-0107 §3. One declaration on \`AttackableTarget\`, threaded to
\`proposed_from\` with no step in between deciding it again.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Every run declares what it attacks

**Files:**
- Modify: `backend/bench/calibration.py:776` (`run_calibration` signature), `:964` (the `AttackableTarget` construction)
- Modify — reference agents, pass `DiscoveredBy.ADAPTIVE`: `backend/api/gate_runs.py:398`, `backend/api/pending_routes.py:888`, `scripts/gate.py:400`, `scripts/admit.py:369`, `scripts/swap.py:511`, `scripts/calibrate.py:221`, `scripts/attack.py:183`
- Modify — a user's target, pass `DiscoveredBy.ADAPTIVE_ON_TARGET`: `backend/api/runs.py:787`, `scripts/bench.py:572`, `scripts/probe_target.py:381`
- Test: `backend/tests/test_api_runs.py`, `backend/tests/test_multi_model.py`

**Interfaces:**
- Consumes: `AttackableTarget(..., discovered_by=...)` from Task 3.
- Produces: `run_calibration(..., discovered_by: DiscoveredBy, ...)` keyword-only and required. No caller may omit it; mypy strict is the enforcement.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_api_runs.py` — a customer run's route files under the target member, which is the whole point of the task:

```python
def test_a_customer_runs_route_is_filed_as_found_against_a_target() -> None:
    # `POST /runs` attacks somebody's own agent. A route found there faces the
    # single-model bar, and the declaration is made at this call site rather than
    # inferred downstream (ADR-0107 §3, §4).
    source = Path(runs.__file__).read_text()
    assert "discovered_by=DiscoveredBy.ADAPTIVE_ON_TARGET" in source

    # And the reference-agent surfaces keep the other member, so the narrowing did
    # not leak into the loop ADR-0012 was written about.
    for module in (gate_runs, pending_routes):
        assert (
            "discovered_by=DiscoveredBy.ADAPTIVE" in Path(module.__file__).read_text()
        )
```

A source assertion is the honest test here: the alternative is a live adaptive run against a real target, and this repository does not spend a provider call to assert a constant. Pair it with the behavioural test already written in Task 3, which proves the thread the constant feeds.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/test_api_runs.py -q -k found_against_a_target`

Expected: FAIL with `AssertionError` — the string is absent from `runs.py`.

- [ ] **Step 3: Add the required parameter to `run_calibration`**

In `backend/bench/calibration.py`, add to the signature (line 776) as keyword-only and required, and document it:

```
    `discovered_by` is what a route this run's adaptive layer files is recorded as,
    and so which admission bar it will face. Required and keyword-only, because the
    two callers it separates are the whole of ADR-0107: a surface attacking the
    three reference agents declares `ADAPTIVE` and one attacking a user's agent
    declares `ADAPTIVE_ON_TARGET`. It is not derived from the targets, which
    describe both kinds alike.
```

Pass it into the construction at line 964:

```python
                    AttackableTarget(
                        target=completed.target,
                        canary=completed.registration.nonce,
                        discovered_by=discovered_by,
                        withdrawn=frozenset(completed.not_measurable),
                    )
```

- [ ] **Step 4: Fix every call site**

Add `discovered_by=DiscoveredBy.ADAPTIVE` at the seven reference-agent sites and `discovered_by=DiscoveredBy.ADAPTIVE_ON_TARGET` at the three target sites, exactly as listed under **Files** above. At `scripts/attack.py:183` the construction is a direct `AttackableTarget`, not a `run_calibration` call — it attacks the reference agents (its own module docstring: "against the reference agents"), so it takes `DiscoveredBy.ADAPTIVE`.

Run `uv run mypy` after this step and before the tests: a missed call site is a strict-mode error naming the file and line, which is faster than a test failure.

- [ ] **Step 5: Run the suite**

Run: `uv run pytest -q` (confirm no gate run or pending-routes run is in flight first)

Expected: the new test PASSES and the suite is green.

- [ ] **Step 6: Drive it red for the right reason**

Temporarily change `runs.py`'s value to `DiscoveredBy.ADAPTIVE`.

Run: `uv run pytest backend/tests/test_api_runs.py -q -k found_against_a_target`

Expected: FAIL with `AssertionError` on the first assert. Revert and confirm PASS.

- [ ] **Step 7: Typecheck, lint, commit**

```bash
uv run mypy && uv run ruff check . && uv run ruff format --check .
git add -A
git commit -m "Every run says which loop it is running

ADR-0107 §3. Required and keyword-only on \`run_calibration\`, so the ten
call sites are a list mypy keeps rather than a convention: seven reference-agent
surfaces declare ADAPTIVE, three target surfaces declare ADAPTIVE_ON_TARGET.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5a: The routes already in the queue are re-stamped

**Files:**
- Create: `scripts/restamp_filed_routes.py`
- Test: `backend/tests/test_pending.py`

**Interfaces:**
- Consumes: `DiscoveredBy.ADAPTIVE_ON_TARGET` from Task 1.
- Produces: nothing importable. A one-shot script, run once against `pending/routes.sqlite`, and a validation.md line recording that it ran.

**Why this is a task and not a footnote.** `PendingRoutes.file` stores the whole drafted `Case` as a TOML record (`pending.py:216`, `:277`), so `discovered_by` is persisted as a string. The live queue holds **three** rows — `data_leakage-77663dfb1f9ba666`, `scope_creep-e14f521b37ec13e7`, `halt_defeat-df377d79ca7b492a` — and every one reads `discovered_by = "adaptive"`. After Task 5 the surface serves one model, so a row still stamped `adaptive` faces the cross-model bar against a one-model reading and returns `not read on enough models` on every run, for ever. This is not a cosmetic migration; skipping it makes the surface permanently unable to decide anything already in it.

It is a rewrite rather than a schema migration: `store.SCHEMA` is `SqliteStore.MIGRATIONS`, the vendored store's own list, and this project does not add to it.

It is a script rather than a translation at read time. A reader that silently mapped a stored `adaptive` to `ADAPTIVE_ON_TARGET` would be a record saying one thing and the surface acting on another — the failure ADR-0032 §4 refuses when it re-measures rather than reconciles. The rewrite happens once, visibly, and is recorded.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_pending.py`:

```python
def test_a_route_filed_before_the_narrowing_is_restamped_not_reinterpreted() -> None:
    # Every row in this queue was filed by a customer run — that is the only writer
    # (docs/specs/pending-routes.md §5) — so the new provenance is a constant and
    # not a judgement. Asserted on the record rather than on a reading, because a
    # reader that translated on the way out would leave the stored record saying
    # one thing while the surface acted on another (ADR-0032 §4).
    queue = PendingRoutes(path=tmp_queue)
    queue.file(a_proposal_stamped(DiscoveredBy.ADAPTIVE), criterion="whatever")

    restamped = restamp(queue)

    assert restamped == 1
    filed = queue.filed(the_route_key)
    assert filed is not None
    assert filed.draft.discovered_by is DiscoveredBy.ADAPTIVE_ON_TARGET


def test_restamping_is_idempotent_and_leaves_the_rest_of_the_draft_alone() -> None:
    # Run twice on purpose: a one-shot script that cannot be re-run safely is one
    # nobody can confirm the result of.
    queue = PendingRoutes(path=tmp_queue)
    queue.file(a_proposal_stamped(DiscoveredBy.ADAPTIVE), criterion="whatever")
    before = queue.filed(the_route_key)
    assert before is not None

    assert restamp(queue) == 1
    assert restamp(queue) == 0

    after = queue.filed(the_route_key)
    assert after is not None
    assert after.draft == replace(
        before.draft, discovered_by=DiscoveredBy.ADAPTIVE_ON_TARGET
    )
```

Substitute the file's own fixtures for `tmp_queue`, `a_proposal_stamped` and `the_route_key`. The second test's `replace` assertion is the load-bearing one: it proves the rewrite touched one field and nothing else — a TOML round-trip that dropped a payload or a precondition would pass the first test and fail this one.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest backend/tests/test_pending.py -q -k restamp`

Expected: FAIL with `NameError: name 'restamp' is not defined` (or an `ImportError` on the new module).

- [ ] **Step 3: Write the script**

Create `scripts/restamp_filed_routes.py`:

```python
"""Re-stamps routes filed before ADR-0107 as found against a target.

    uv run python -m scripts.restamp_filed_routes --dry-run
    uv run python -m scripts.restamp_filed_routes

**A one-shot, and the constant it applies is licensed by one fact**: a customer run
is the only writer of this queue (`docs/specs/pending-routes.md` §5), so every route
in it was found against somebody's own agent and none was found against the three
reference agents. That is what makes `ADAPTIVE -> ADAPTIVE_ON_TARGET` a rewrite and
not a guess about each row.

**Why a script and not a translation on the way out.** A reader that mapped the old
value as it loaded would leave the stored record saying `adaptive` while the surface
decided it on the single-model bar, which is the disagreement between a record and a
decision that ADR-0032 §4 re-measures rather than reconciles. This changes the
record, once, and prints what it changed.

Idempotent: a row already carrying the new member is counted and not rewritten, so
the script can be re-run to confirm its own result.
"""
```

The body reads every filed record, rewrites the draft of each `AwaitingDecision` whose `draft.discovered_by is DiscoveredBy.ADAPTIVE` via `dataclasses.replace`, re-files it under the same `RouteKey`, and returns the count. Expose the work as `restamp(queue: PendingRoutes) -> int` so the test calls it without a subprocess; `main` parses `--dry-run` and prints one line per row plus a total. A `Decided` record has no draft and is skipped — say so in a comment, because a reader will ask.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest backend/tests/test_pending.py -q`

Expected: both new tests PASS and the file's existing tests stay green.

- [ ] **Step 5: Drive it red for the right reason**

Temporarily change the script's guard to rewrite unconditionally (drop the `is DiscoveredBy.ADAPTIVE` check).

Run: `uv run pytest backend/tests/test_pending.py -q -k restamp`

Expected: the idempotency test FAILS with `AssertionError: 1 != 0` on the second `restamp` call — not an import error. Revert and confirm PASS.

- [ ] **Step 6: Run it against the live queue**

```bash
uv run python -m scripts.restamp_filed_routes --dry-run
```

Expected: three rows named — `data_leakage-77663dfb1f9ba666`, `scope_creep-e14f521b37ec13e7`, `halt_defeat-df377d79ca7b492a`. Confirm the count is 3, then run without `--dry-run` and re-run to confirm it reports 0. Record the three keys and the date in Task 7's validation entry.

Do this **after** Task 1 has landed and **before** Task 5 reaches an operator, or the surface will serve one model to rows that still demand two.

- [ ] **Step 7: Typecheck, lint, commit**

```bash
uv run mypy && uv run ruff check . && uv run ruff format --check .
git add scripts/restamp_filed_routes.py backend/tests/test_pending.py
git commit -m "Routes filed before the narrowing are re-stamped, once and visibly

ADR-0107's last consequence. A customer run is the only writer of this
queue, so the new provenance is a constant rather than a judgement — but it
is a rewrite of the record and not a translation on the way out, because a
record and a decision that disagree is what ADR-0032 §4 refuses.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: `/pending-routes` measures on one declared reference model

**Files:**
- Modify: `backend/api/app.py:5795-5830` (`deployed_pending_routes`)
- Modify: `backend/api/pending_routes.py:553-584` (`_budget`), `:586-597` (`_planned_attempts`)
- Test: `backend/tests/test_api_pending_routes.py`

**Interfaces:**
- Consumes: `bar_for(DiscoveredBy.ADAPTIVE_ON_TARGET) is AdmissionBar.SINGLE_MODEL` from Task 1, which is what makes the second pass unspendable.
- Produces: `PendingRouteBench.models` holds exactly one model where it held exactly two. `_planned_attempts(cases, targets)` keeps its signature; the caller stops multiplying by the model count.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_api_pending_routes.py`:

```python
def test_the_surface_decides_a_route_on_one_declared_reference_model() -> None:
    # After ADR-0107 §2 every proposal this surface sees faces a one-model bar, so
    # a second pass buys nothing it can spend. A deployment declaring one reference
    # model decides routes; before this it refused, because a bar met on one model
    # was not the bar.
    bench = deployed_pending_routes(
        A_CONFIG_DECLARING_ONE_REFERENCE_MODEL, A_GATE_RUN_BENCH
    )
    assert len(bench.models) == 1
    assert bench.models == (
        A_CONFIG_DECLARING_ONE_REFERENCE_MODEL.report.models.calibration,
    )


def test_the_estimate_counts_one_pass_and_not_two() -> None:
    # The figure the operator confirms is what the run spends. Two passes declared
    # against a one-model bar would be a confirmation for calls nothing makes.
    estimate = _planned_attempts(cases=1, targets=3)
    assert estimate == DECLARED_RULE.attempts_per_case * 3
```

Replace the fixture names with the file's own; `A_GATE_RUN_BENCH` is whatever that file already passes as the `gate_runs` argument.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest backend/tests/test_api_pending_routes.py -q -k "one_declared_reference_model or one_pass_and_not_two"`

Expected: the first FAILS with `AssertionError: 0 != 1` — `deployed_pending_routes` returns `()` for a one-model deployment today, via `models if len(models) == 2 else ()`.

- [ ] **Step 3: Require one model instead of two**

In `backend/api/app.py`, replace the two-or-none guard in `deployed_pending_routes`:

```python
    declared = config.report.models.calibration
    return PendingRouteBench(
        library=gate_runs.library,
        agents=agents,
        # One, and never a pair. Every route this surface decides was found against
        # a customer's target, so after ADR-0107 §2 it faces the single-model bar
        # and a second pass is a call the decision cannot spend. The second model is
        # still declared and still required by `scripts/swap.py`, which measures a
        # *pair* by definition (#15) — this surface simply stops reading it.
        models=() if declared == UNDECLARED_MODEL else (declared,),
    )
```

Rewrite the paragraph in its docstring that says "The two models are two declarations, and the second is this surface's alone" so it states what is true now: this surface reads `REFERENCE_MODEL_ENV` and no longer reads `SECOND_REFERENCE_MODEL_ENV`, and ADR-0107 §4 is why. Delete the `SECOND_REFERENCE_MODEL_ENV` import from `app.py` if nothing else there uses it — `uv run ruff check .` will say.

- [ ] **Step 4: Stop counting two passes**

In `backend/api/pending_routes.py`, `_budget` (line 578) currently declares `targets=tuple(targets) * len(self._bench.models)`. With one model the multiplication is by one and the line is now a lie about why it is there, so make it read what it means:

```python
        return RunBudget.declare(
            cases=[record.draft for record in routes],
            # The three agents once, because the pass is once: one model after
            # ADR-0107 §4, and a figure multiplied by a model count that is always
            # one is arithmetic a reader has to check to find out it changes nothing.
            targets=tuple(targets),
            rule=DECLARED_RULE,
            ...
```

`_planned_attempts` keeps `cases * DECLARED_RULE.attempts_per_case * targets` — its `targets` is already the agent count, not the model count. Check its call site at line 890 (`_planned_attempts(len(cases), len(served.targets))`) and confirm nothing there multiplies by models; if it does, remove that factor.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest backend/tests/test_api_pending_routes.py backend/tests/test_multi_model.py -q`

Expected: both new tests PASS. `test_multi_model.py` asserts the swap's two-model behaviour and must stay green untouched — if it fails, the change leaked out of this surface and into `cross_model_bar`, which this task does not modify. Tests asserting the old two-or-none refusal will fail; those assertions invert, and the one asserting the *partial-reading* refusal (`docs/specs/pending-routes.md:107` — one model read, the other unreachable) no longer describes a reachable state on this surface and comes out with a note pointing at ADR-0107 §4.

- [ ] **Step 6: Drive it red for the right reason**

Temporarily restore `models if len(models) == 2 else ()`.

Run: `uv run pytest backend/tests/test_api_pending_routes.py -q -k one_declared_reference_model`

Expected: FAIL with `AssertionError` comparing 0 to 1. Revert and confirm PASS.

- [ ] **Step 7: Typecheck, lint, commit**

```bash
uv run mypy && uv run ruff check . && uv run ruff format --check .
git add backend/api/app.py backend/api/pending_routes.py backend/tests/
git commit -m "Deciding a route reads one declared reference model

ADR-0107 §4. Every route this surface decides faces a one-model bar, so the
second pass is a call the decision cannot spend and the estimate stops
declaring it. The swap still measures a pair.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: The screen stops promising a bucket that cannot move

**Files:**
- Modify: `frontend/src/console/pending.ts` — lines 18, 29, 192, 204-208, 307, 315, 377, 393, 458, 543-547, 581
- Test: `frontend/src/console/pending.test.ts`

**Interfaces:**
- Consumes: the one-model `PendingRouteBench` from Task 5 — the API now serves one entry where the reading expected two.
- Produces: no type changes. `models: string[]` stays a list; it now holds one entry, and the prose stops saying "two".

- [ ] **Step 1: Write the failing test**

Add to `frontend/src/console/pending.test.ts`:

```typescript
it('states one pass over the three agents, and no second model', () => {
  const blocks = pendingRoutesScreen(aQueueWithOneRoute())
  const prose = JSON.stringify(blocks)

  expect(prose).not.toMatch(/two models/i)
  expect(prose).not.toMatch(/both models/i)
  // The rejection bucket ADR-0012 called a finding cannot fill on this surface any
  // more: a route is read on one model, so 'separated on one model and not on
  // another' is a line that can only ever read zero here (ADR-0107).
  expect(prose).not.toMatch(/separated on one model and not on another/i)
})

it('draws one progress bar, because there is one pass', () => {
  const reading = measurementProgress(aMeasurementUnderway())
  expect(reading.bars).toHaveLength(1)
})
```

Replace the fixture names with the file's own, and `measurementProgress` / `.bars` with whatever the per-model bar work on `per-model-progress-bar` actually named (that branch is merged under this one; read `pending.ts:543-547` for the real names).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- pending`

Expected: FAIL — the first on the `two models` match, the second with `expected length 1, received 2`.

- [ ] **Step 3: Rewrite the prose**

Work through the eleven sites listed under **Files**. Each says "two models", "both models", or "on two models each"; each becomes one pass over the three reference agents. Specifically:

- Line 18's ADR-0012 link becomes an ADR-0107 link, since ADR-0107 is now what decides this surface's bar.
- Lines 29, 307, 315, 377, 393: "three reference agents on two models" → "the three reference agents", and line 315's "on both models" → "once".
- Line 192's sentence about a zero in the cross-model bucket comes out: it is a line that can only read zero here.
- Lines 543-547 (the per-model bar) reduce to one bar. Keep the paragraph's argument for *why* a bar exists at all — the action is minutes long and "how far in" is a fact about the pass — and drop the clause about walking two models strictly one at a time.
- Line 581's "inference budget on two models" → "inference budget".

- [ ] **Step 4: Run the tests**

Run: `cd frontend && npm test -- pending`

Expected: both new tests PASS, and the file's existing tests that assert the two-model prose now fail. Invert those assertions; do not delete a test that was checking the screen says what the bar is.

- [ ] **Step 5: Drive it red for the right reason**

Temporarily restore the words "on two models" in one of the statement constants.

Run: `cd frontend && npm test -- pending`

Expected: FAIL with the `not.toMatch(/two models/i)` assertion, naming that string. Revert and confirm PASS.

- [ ] **Step 6: Commit**

```bash
cd frontend && npm test && npx tsc --noEmit
cd .. && git add frontend/src/console/pending.ts frontend/src/console/pending.test.ts
git commit -m "The queue says one pass, and drops a bucket that cannot move

ADR-0107 §4. One bar, because there is one pass; and the cross-model
rejection line comes off a surface where it can only ever read zero.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: The records say what changed

**Files:**
- Modify: `docs/specs/pending-routes.md` — §5, §37, §41, §107, §113
- Modify: `CONTEXT.md` — the **Route** and **Adaptive finding** entries
- Modify: `docs/validation.md` — a new dated entry
- Test: none. This task's deliverable is prose, and the check is that no source file still describes the old behaviour.

**Interfaces:**
- Consumes: everything above. Written last so it describes what was built rather than what was planned.
- Produces: nothing code reads.

- [ ] **Step 1: Amend the pending-routes spec**

The five sites, each stating what is now true:

- §5 and §37: "measure on two models" → one declared reference model, with an ADR-0107 link.
- §41: the claim "nothing about the bar changes here" was true when written and is now false. Replace it with what did change and why the code path is still one: `cross_model_bar` still serves both surfaces and still takes N models; what moved is which bar a proposal's provenance selects.
- §107: the partial-reading refusal ("one model read, the other unreachable") is no longer a reachable state on this surface. Say so and point at ADR-0107 §4; keep the assertion for the swap.
- §113: this is the line that reserved the question — "that is a question for an ADR of its own and not a value to tune here." Replace it with a pointer to ADR-0107, which answered it. Leave the rest of the non-goal (`D >= 0.4`, Wilson 90%, three agents) exactly as it stands: none of that moved.

- [ ] **Step 2: Amend CONTEXT.md**

`DiscoveredBy` is now five members and two of them are adaptive, so the vocabulary has to distinguish them or the terms stop being load-bearing arithmetic. Add to the **Route** or **Adaptive finding** entry — whichever already carries the provenance language — a sentence naming both members and the bar each faces, in the file's own `_Avoid_` style where it applies.

- [ ] **Step 3: Add the validation entry**

Append a dated section to `docs/validation.md` following the file's existing format. It records, as a change to the instrument rather than a measurement:

- the date (2026-09-10) and that ADR-0107 narrowed ADR-0012 §1;
- that the provenance census now reports five members, so a reader comparing this gate run's provenance block to an earlier one sees the split appear;
- that no case in the library changed — all 21 are `authored` under `single_model`, and no adaptive case has ever been admitted, so there is no admission to re-decide;
- what is now *not* measured: model-dependence at admission for target-discovered routes, with the retirement-rate signal named as the remaining control.

State plainly that this entry is a record of a decision and not a reading: nothing here was measured.

- [ ] **Step 4: Check no source still describes the old behaviour**

Run:

```bash
grep -rn "two models\|both models\|two underlying models" \
  backend/ frontend/src/ scripts/ docs/specs/ CONTEXT.md \
  --include=*.py --include=*.ts --include=*.tsx --include=*.md
```

Every surviving hit must be about `scripts/swap.py`, `cross_model_bar`'s own N-model loop, or ADR-0012/ADR-0107 themselves — all of which are still correct. Anything about `/pending-routes` is a miss from Task 5 or 6.

- [ ] **Step 5: Full green, then commit**

```bash
uv run pytest -q && uv run mypy && uv run ruff check . && uv run ruff format --check .
cd frontend && npm test && npx tsc --noEmit && cd ..
git add -A
git commit -m "The records say a target-discovered route faces one model

ADR-0107, written down where a reader meets it: the spec's reserved
non-goal is answered, CONTEXT.md tells the two adaptive provenances apart,
and validation.md records a decision that measured nothing.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage.** ADR-0107 §1 → Task 1 (member, declared last). §2 → Task 1 (`bar_for` branch, own reason). §3 → Tasks 2, 3, 4 (`proposed_from` required arg; `AttackableTarget` field; ten call sites). §4 → Task 5 (one declared model, estimate) and Task 6 (the screen). Consequences 1, 4, 5 → Task 7's validation entry. Consequence 3 (the bucket reads zero here, still fills from the swap) → Task 6 Step 3 and Task 7 §41. Consequence 6 (the `pending/routes.sqlite` backfill) → **gap, addressed below.**

**The backfill — resolved, and it is Task 5a.** ADR-0107's last consequence reserved this. Checked rather than left to the implementer: `PendingRoutes.file` stores the whole drafted `Case` as a TOML record (`pending.py:216`, `:277`), so the provenance is persisted, and the live queue holds three rows all reading `discovered_by = "adaptive"`. It is not a schema migration — `store.SCHEMA` is the vendored `SqliteStore.MIGRATIONS` and this project does not add to it — so it is a one-shot rewrite with its own tests. Task 5a must land after Task 1 and before Task 5 reaches an operator; skipping it leaves the surface permanently unable to decide the three routes already filed in it.

**The memory does not need one.** `decided.criterion_of` excludes `discovered_by` by name — "does not change what the three reference agents would return" — so nothing in `decisions/routes.sqlite` is keyed on the provenance and no stored measurement is invalidated by this change. Task 7's validation entry should say this explicitly, because a reader who knows the queue needed a rewrite will ask whether the memory did too.

**Placeholder scan.** Fixture names are deliberately left as named placeholders (`AN_OBJECTIVE`, `A_BREAKABLE_TARGET`, `A_CONFIG_DECLARING_ONE_REFERENCE_MODEL`) with an instruction to substitute the file's own, because inventing fixtures that duplicate existing ones is worse than naming the substitution. Every other step carries the actual code or the actual command.

**Type consistency.** `discovered_by: DiscoveredBy` is the name and type in all four signatures it reaches — `proposed_from`, `AttackableTarget`, `run_episode`, `run_calibration` — and `FOUND_BY_THE_ATTACKER` is the only new module-level name. `bar_for` is imported from `backend.bench.library` inside that package and from `backend.bench.admission` outside it, matching the existing convention.

**Ordering.** Tasks 1-4 are strictly sequential (each consumes the previous signature). Task 5a depends only on Task 1 and must precede Task 5. Task 5 depends on Task 1 and 5a. Task 6 depends on Task 5. Task 7 depends on all of them. Tasks 5 and 2-4 could run in parallel, but the shared `uv run mypy` gate makes that a false economy.
