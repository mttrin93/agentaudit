# AgentAudit

An adversarial test bench for AI agents. It attacks a target across six failure
families, proves its own discriminating power before its results are trusted, and
reports the outcome as signed evidence.

## Where things are written down

Do not restate these here — read them.

| For | Read |
| --- | --- |
| Vocabulary — target, case, attempt, family, verdict | [CONTEXT.md](./CONTEXT.md) |
| Decisions and why they were made | [docs/adr/](./docs/adr/) |
| Scope, phases, the Sprint line | [PLAN.md](./PLAN.md) |
| What the bench measures and what it has measured | [docs/validation.md](./docs/validation.md) |
| The build spec — the bench, through the gate | [docs/specs/pre-web-bench.md](./docs/specs/pre-web-bench.md) |
| The build spec — the signed report and its delivery | [docs/specs/signed-report-and-delivery.md](./docs/specs/signed-report-and-delivery.md) |
| The build spec — the elective family tier | [docs/specs/elective-family-tier.md](./docs/specs/elective-family-tier.md) |
| The build spec — the MCP server | [docs/specs/mcp-server.md](./docs/specs/mcp-server.md) |

Terms in CONTEXT.md are load-bearing arithmetic, not synonyms. An **attempt** is
the unit of the denominator; a turn is not an attempt.

## Commands

```
uv sync --all-groups          # install; add --locked to match CI exactly
uv sync --extra corpus        # only to build or query the corpus index (ADR-0045)
uv run pytest -q              # tests
uv run mypy                   # typecheck, strict
uv run ruff check .           # lint
uv run ruff format .          # format (CI runs --check)
uv run pre-commit install     # once per clone: run the two Ruff checks pre-commit
```

CI runs lint, format, typecheck and tests on every branch. The pre-commit hooks
are a local echo of CI's two Ruff steps and nothing more — they exist only on a
clone where `pre-commit install` has been run, and CI stays the authority.

## Standing rules

**No adaptive result may write into a scored rate.**
[ADR-0010](./docs/adr/0010-two-layers-in-one-run-the-adaptive-layer-is-never-scored.md).
An `AdaptiveEpisode` is not an `Attempt`. The adaptive layer reaches the scored
side through exactly one edge — `propose_case` into the admission gate, where a
declared threshold decides. Everything else it produces reports in its own
section. The invariant is carried by the type, so if you find yourself widening
a signature to accept both, stop.

**Drive every new test red once before committing.**
Break the thing it guards on purpose, confirm it fails *for the right reason* and
not by import error or typo, then revert. A test that has never failed is not
known to work.

**Never merge on red CI.** Report back instead.

**A decision belongs in an ADR; its local consequence belongs in a docstring.**
The prose in this codebase is an asset, and the long docstrings are the house
style — so this rule is about *where* a passage lives, never about deleting it.
Four cases, and only the first two move:

1. A decision, its alternatives, and why the alternatives lost → an ADR. The
   docstring keeps a one-line pointer to it and the local consequence.
2. A restatement of something already argued in an ADR, [PLAN.md](./PLAN.md),
   [CONTEXT.md](./CONTEXT.md) or the README → replaced by the link. This is the
   table above — *do not restate these here* — applied to source.
3. Why *this* code at *this* call site is shaped this way → stays. An ADR records
   a decision and deliberately not its consequence at line 200 of one module;
   moving that out makes both files worse.
4. A measurement that licenses a value → stays with the value. The κ readings
   on `completion.DEFAULT_ADJUDICATOR_MODEL`, `budget.NOT_PRICED`, the per-layer
   counters: the figure is a property of the literal it sits on, so filing it
   elsewhere loses the fact that editing the literal invalidates it.

Where prose moves, **both ends move in the same commit** — the ADR gains the
paragraph, the docstring gains the link — and **no ADR is edited to say something
it did not decide.** A decision no ADR records is a new ADR to propose, not a
paragraph appended to the nearest one.

**Blockers and dependencies live in GitHub**, in the native dependency and
sub-issue fields — not only as prose in an issue body. The issue list is the
signal for what is ready to start, and it is only a signal if it is machine-
readable. Keep the prose too; it says *why*.
