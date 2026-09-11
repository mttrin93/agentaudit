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

It rewrites records and not a column, because there is no column: `PendingRoutes.file`
stores the whole drafted `Case` as the TOML record `entry.case_record` writes, so
`discovered_by` is a line inside a text field that only a reader of the draft can
reach. That it is not a schema migration either is `store.SCHEMA`'s doing — the
vendored `SqliteStore.MIGRATIONS`, which this project does not add to.

Idempotent: a row already carrying the new member is skipped and not rewritten, so
the script can be re-run to confirm its own result, and a second run reports zero.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import replace

from backend.bench.library import DiscoveredBy
from backend.bench.pending import PENDING_ROUTES, AwaitingDecision, PendingRoutes


def restamp(queue: PendingRoutes) -> int:
    """Rewrite every route still stamped `ADAPTIVE`, and say how many there were.

    Exposed as a function over a `PendingRoutes` rather than done inside `main`, so
    that the test drives the rewrite itself rather than a subprocess and can read
    the record back out of the store afterwards.

    The write goes through the store under the record's own key rather than through
    `file`, which takes a `ProposedRoute` this script does not have and would mint a
    fresh `filed_on`. One field moves and every other is carried across by
    `dataclasses.replace`, which is what the second test asserts.
    """
    stale = restampable(queue)
    for record in stale:
        restamped = replace(
            record,
            draft=replace(record.draft, discovered_by=DiscoveredBy.ADAPTIVE_ON_TARGET),
        )
        queue.store.put(
            queue.namespace, restamped.route.filed_under, restamped.stored()
        )
    return len(stale)


def restampable(queue: PendingRoutes) -> tuple[AwaitingDecision, ...]:
    """The records `restamp` would rewrite — the selection, in one place.

    Read by `restamp` and by `--dry-run` both, so the rows the dry run names are the
    rows the real run writes by construction rather than by two predicates agreeing.

    A `Decided` record is not among them, and a reader will ask why: it has no
    `draft` — the payload and the case it drafted went with the decision
    (ADR-0104 §4) — so there is no stored provenance on it to re-stamp, and the bar
    it faced was applied while it was still pending.
    """
    return tuple(
        record
        for record in queue.queue()
        if isinstance(record, AwaitingDecision)
        and record.draft.discovered_by is DiscoveredBy.ADAPTIVE
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="name the routes that would be re-stamped and write nothing",
    )
    args = parser.parse_args(argv)

    queue = PENDING_ROUTES
    stale = restampable(queue)
    for record in stale:
        print(f"  {record.route.filed_under}: adaptive -> adaptive_on_target")

    if args.dry_run:
        print(f"{len(stale)} would be re-stamped ({queue.store.path})")
        return 0

    print(f"{restamp(queue)} re-stamped ({queue.store.path})")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
