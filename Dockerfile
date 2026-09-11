# The image a deployed bench runs in: the dependencies from the lock file, the
# backend package, and nothing else.
#
# `pyproject.toml` declares no `[build-system]`, so this is a uv *virtual* project:
# `uv sync` installs the dependencies and does not install `agentaudit` itself.
# `backend` is therefore imported off the working directory, which is why WORKDIR is
# set before the source is copied and why the source lands at /app/backend rather
# than in site-packages.
#
# **The five SQLite stores live beside the code, inside this image.** `runs/`,
# `checkpoints/`, `precedent/`, `decisions/` and `pending/` are each
# `Path(__file__).resolve().parents[2] / …` and every one of their docstrings
# refuses an environment override, so on a deployment they are written into the
# container's own filesystem — writable, per-instance, and gone when the instance
# is. That is a property of the deployment and not of the bench: the README records
# it, and the case library is the one store that is meant to outlive a redeploy,
# which is why that one is a mount point (`gate_run_equipment.DEPLOYED_LIBRARY`) and
# not a directory in here.

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# The dependency layer, on its own so that editing a module does not re-resolve it.
# `--locked` is CI's flag: the lock file is the authority and a resolution that
# wanted to move it fails the build instead of moving it silently.
#
# `--no-dev` drops mypy, ruff, pytest and pre-commit. The `corpus` extra is left out
# by saying nothing about it — an extra is not installed by default, which is the
# whole reason ADR-0045 made it one: 80 transitive packages and 331 MB for a
# build-time instrument that no run, no route and no test opens.
#
# README.md is copied with them because `pyproject.toml` names it as the readme and
# uv reads the field before it reads anything else.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project

# The backend, and only the backend. `backend/cases/` is the admitted library this
# bench falls back to when no volume is mounted, `backend/goldset/` is the
# hand-labelled reference a judged family's kappa is measured against, and
# `backend/targets/reference/` is the test equipment a gate run serves on loopback —
# all three are read out of the image and all three have to be in it.
COPY backend ./backend

# The committed public half of the signing key. Not a secret and not optional: it is
# the key a recipient pins, and the bench reads it to state its own fingerprints and
# to run a recipient's checks over an artefact it just produced
# (`signing.PUBLIC_KEY_PATH`). The private half is never in here — it arrives as
# AGENTAUDIT_SIGNING_KEY or the factory refuses to boot (ADR-0020).
COPY keys ./keys

# Cloud Run injects PORT and a deployment that also set it would be declaring a
# number the platform is about to contradict. The shell form is deliberate: the
# variable has to expand.
#
# One worker, because a run is a thread in this process and its record is a dict in
# this process (`backend/api/runs.py`) — a second worker would be a second bench
# answering for the first one's halts.
ENV PORT=8080
CMD exec uv run --no-sync uvicorn backend.api.app:create_app --factory --host 0.0.0.0 --port ${PORT} --workers 1
