"""What a gate run leaves behind, on the way out and under the same lease.

Split out of `gate_runs.py`, and it is a module rather than a private function
because it is the only place in this package that *writes* to the case library. The
three writes are one critical section — the readings, then this run's own record as
fields, then the gate citation that names it — and separating them from the service
that decides makes the critical section something a reader can see the whole of.

A console gate run has no dated Markdown document for its record to sit beside,
which is what
[ADR-0021](../../docs/adr/0021-the-console-may-start-a-gate-run.md) recorded as *the
two entry points leave different traces*. So the record goes into the library as
fields and the citation points at it there, so that the bench cites the gate run it
just made rather than whatever a deployment declared
([ADR-0023](../../docs/adr/0023-a-gate-run-updates-the-citation-it-earned.md)).

**The citation reaches `ReportConfig.gate` through `Cites` and through nothing
else**: a `GateCitation` in, nothing out, and no decision or record crossing in
either direction. `cite` is called here and nowhere else on this side, which is why
this is the module a test that substitutes it patches.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from backend.api.gate_run_equipment import ServedAgents
from backend.api.gate_run_state import Cites, GateRunRecord, WrittenBack
from backend.api.run_config import BenchConfig
from backend.bench.calibration import CalibrationResult
from backend.bench.cited import cite
from backend.bench.gate import GateResult
from backend.bench.gate_record import (
    record_named,
    recorded_gate_run,
    write_the_record,
)
from backend.bench.retirement import RetirementDecision, readings_of, store


def _write_back(
    record: GateRunRecord,
    result: CalibrationResult,
    gate: GateResult,
    served: ServedAgents,
    config: BenchConfig,
    cites: Cites | None,
) -> WrittenBack:
    """Append this run's `D` to every case record it read, and retire what retires.

    After the decision and never before it: what a case scored is stored whatever
    the gate answered, and the rule that retires one is read over two runs rather
    than over this one. Written to the case records by the run that measured them, so
    the series a retirement is re-derived from is the case's own — and written under
    the lease this gate run has held since before it read them.

    The models are read off the record that declares them (`DeclaredModels`) rather
    than named here: a reading stored under a model identifier this module invented
    would be a decay series about a pair of models nobody declared (ADR-0012).

    **Three writes, one critical section.** The readings, then this run's own record
    as fields, then the citation that names it — all inside the lease this gate run
    has held since before it read the library, so no second gate run can slip between
    the readings and the citation that claims them (ADR-0021 condition 5, ADR-0023).
    The order is the argument: a citation is a claim about a library at a version, and
    the version it claims is the one the readings were just stored against.

    **This is where a console gate run's figures become durable.** The record goes
    into the library and the citation points at it there, which is where a
    command-line run puts its record too: the citation carries the file name and every
    reader resolves it against the library, so the library is the only directory a
    cited record is reachable from (ADR-0023, amended — the command line wrote it
    beside its document until then, and every judged rate was withheld for it). That
    closes ADR-0021's own complaint that the two entry points leave different traces —
    the trace is now the same record in the same kind of place, and what a console run
    still lacks is the dated document.

    **The in-process citation is the last thing and it is optional.** `cites` is the
    one edge back onto the bench a run is measured with, and a registry wired to none
    still leaves the library citing this gate run for the next process to read: the
    difference between the two entry points is a restart, not a citation.
    """
    # One clock for the whole write-back: the date on every reading and the stamp on
    # the record are the same moment, so a run that crossed midnight between them
    # cannot store a series dated one day and a record dated the next.
    stamped = datetime.now(tz=UTC)
    runs = {run.target.name: run for run in result.target_runs}
    history = readings_of(
        record.cases,
        hardened=runs[served.hardened],
        weak=runs[served.weak],
        trivial=runs[served.trivial],
        model=config.report.models.calibration,
        # Whether the run measured the field, from the equipment that served the
        # agents rather than from the declared string: a reading taken on a stub
        # fixture is stored, marked, and retires nothing (ADR-0022).
        measured_the_field=served.measured_the_field,
        ran_on=stamped.date(),
        # The families the gate did not decide on. A reading from one is stored and
        # the rule is not applied to it: retirement declines on a family the bench
        # cannot vouch for (ADR-0016).
        excluded=gate.decision.excluded_families,
        adjudicator=config.report.models.adjudicating,
    )
    decisions: Sequence[RetirementDecision] = store(
        record.library, history, config.rule
    )
    recorded = recorded_gate_run(
        gate,
        decided_at=stamped.isoformat(),
        # No prose to point at: this entry point leaves the record and no document
        # (ADR-0021), and the absence is typed rather than written as a sentence in a
        # field a reader would follow as a path (ADR-0023).
        document=None,
        record=record_named(stamped),
        # The instrument the κ figures on this record were measured on, so a target
        # report can reuse them only where it adjudicates with the same model
        # (`cited.the_reliability`, ADR-0004).
        adjudicating_model=config.report.models.adjudicating,
    )
    write_the_record(recorded, record.library)
    replaced = cite(recorded, record.library)
    if cites is not None:
        cites(replaced.now)
    return WrittenBack(
        library=record.library,
        readings=len(history.readings),
        unread=history.unread,
        retired=tuple(decision.case_id for decision in decisions if decision.retires),
        record=recorded.record,
        cited=replaced.stated(),
    )
