#!/usr/bin/env bash
#
# The pre-commit hooks' one entry point into Ruff.
#
# CI is the authority (`Never merge on red CI`); this is only a local echo of
# it, and an echo is worth having only if it cannot disagree. So the hook does
# not install a Ruff of its own: it calls the project's Ruff through
# `uv run --frozen`, which resolves the version `uv.lock` pins — the same
# version CI's `check` job gets from `uv sync --all-groups --locked`. There is
# no second pin to keep in step, and bumping Ruff in the lockfile moves the
# hook with it.
#
# `--frozen` also means a commit never rewrites `uv.lock` on its way past the
# hook, and it never runs a binary older than the lockfile: uv syncs the
# environment from the lock before running.
#
# The arguments are the Ruff invocation, passed through verbatim, so the
# command in `.pre-commit-config.yaml` reads the same as the one in
# `.github/workflows/ci.yml`.
set -uo pipefail

if ! command -v uv >/dev/null 2>&1; then
    echo "ruff-hook: uv is not on PATH, so there is no lockfile-pinned Ruff to run." >&2
    echo "ruff-hook: skipping — install uv and run 'uv sync --all-groups'." >&2
    echo "ruff-hook: CI runs 'ruff check .' and 'ruff format --check .' regardless." >&2
    exit 0
fi

exec uv run --frozen --group dev ruff "$@"
