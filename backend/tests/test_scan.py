"""The configuration scan, and the join that is the report's headline.

Four hazards, and every test here is one of them.

*A declaration could become a measurement.* The scan sends nothing, so the only
thing it can contribute is a claim. That is asserted at import level as well as
behaviourally, because the channel is reachable by a name rather than by an
argument — the same reason the adjudicator's blinding is checked that way.

*A target could improve its standing by declaring more controls.* This is the
defect ADR-0005 killed a composite score over, so it gets the test that runs the
same attempts against the same target twice with different declarations and
compares the measured section. Nothing about declaring may move a rate, an
interval, a band or a `D`.

*A defeat could rest on something a reader cannot check.* A defeat is a
deterministic verdict or it is not a defeat: the join filters on
`Attempt.verdict_class`, so a family attempted under adjudication leaves its
declared control untested rather than defeating it on an adjudicated verdict
(ADR-0004, spec: the join is computed against the attacker's deterministic
findings).

*A declared capability could be read off a measurement.* The Agents Rule of Two is
read from what the operator declares and from nothing else
([ADR-0038](../../docs/adr/0038-the-rule-of-two-is-a-declared-property.md)), and each
of its three properties has a family that is its near-neighbour — so the tests here
assert that the two enumerations share no member, that nothing in the reading can
hold a figure or a family, and that the scanner imports nothing that carries one. The
gaming direction is the mirror of the one above: a target would improve this property
by declaring **less**, and the answer is the same answer, so the same
declared-against-silent comparison is made over the capabilities.

The join itself is a pure function over recorded attempts, so it is driven
directly — seam two. The end-to-end cases at the foot of the file go through the
calibration entry point, because "the target declares a filter it does not have"
is a claim about a real run rather than about a data structure.
"""

import ast
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any, get_type_hints

import pytest

from backend.bench.assembler import (
    ControlStatus,
    ScannedControl,
    TargetResult,
    assemble,
    declared_and_defeated,
)
from backend.bench.calibration import PlantNonce, run_calibration
from backend.bench.contract import (
    AgentCapability,
    DeclaredControl,
    TargetConfig,
    Transcript,
)
from backend.bench.evaluator import Verdict
from backend.bench.library import Case, ElectiveFamily, Family, VerdictClass
from backend.bench.measurability import NotMeasurable
from backend.bench.rule import DECLARED_RULE
from backend.bench.scanner import (
    CONTROL_CHECKLIST,
    NOT_A_MEASUREMENT,
    NOTHING_DECLARED,
    RuleOfTwo,
    RuleOfTwoStanding,
    Scan,
    Supervision,
    family_claimed_by,
    scan,
)
from backend.bench.scorer import (
    FamilyOutcome,
    FamilyRates,
    GateDecision,
    GateOutcome,
    failure_rate,
    monotonicity,
)
from backend.graph.runstate import Attempt
from backend.tests.blind_target import blind_target
from backend.tests.conftest import (
    ADJUDICATING,
    BENCH_ATTESTATION,
    CONFIRMING,
    a_target,
    case_for,
    reference_target,
)

SCANNER_SOURCE = Path(__file__).resolve().parents[1] / "bench" / "scanner.py"

ALL_FOUR = tuple(DeclaredControl)
"""A target that claims every control the checklist asks about."""


# --- The scan reads declarations, and sends nothing --------------------------


def test_the_scan_reads_what_was_declared_and_lists_what_was_not() -> None:
    scanned = scan(
        a_target_declaring((DeclaredControl.OUTPUT_FILTER, DeclaredControl.INPUT_CHECK))
    )

    # Checklist order, not the order the operator happened to list them in, so two
    # targets' sections are read down the same column.
    assert scanned.declared == (
        DeclaredControl.INPUT_CHECK,
        DeclaredControl.OUTPUT_FILTER,
    )
    assert scanned.absent == (
        DeclaredControl.SCOPE_LIMIT,
        DeclaredControl.STOP_CONTROL,
    )

    # The two sides partition the checklist and overlap nowhere: a control the
    # scan reported in both would be a claim and an absence at once.
    assert set(scanned.declared) | set(scanned.absent) == set(CONTROL_CHECKLIST)
    assert not set(scanned.declared) & set(scanned.absent)


def test_a_target_that_declares_nothing_is_scanned_and_not_penalised() -> None:
    scanned = scan(a_target())

    assert scanned.declared == ()
    assert scanned.absent == CONTROL_CHECKLIST
    # Nothing is computed from an absence. The four families those controls would
    # have claimed are measured either way, and ADR-0005's rejected score is the
    # thing that deducted points here.
    assert declared_and_defeated(scanned, an_attempted_library()) == ()


def test_the_scan_sends_no_message_to_the_target_it_reads() -> None:
    # The url is unroutable, so a scan that tried to reach it would raise rather
    # than return. The scan is a pure function of the registration, which is what
    # lets it run before the approval interrupt without spending anything.
    unreachable = a_target_declaring(ALL_FOUR)
    assert unreachable.url.endswith(".invalid/messages")

    assert scan(unreachable).declared == ALL_FOUR


def test_the_scanner_imports_no_route_to_a_target() -> None:
    # Import-level, because the channel is reachable by a name rather than by an
    # argument. A scan that could send a message would be a measurement wearing a
    # declaration's name, and the headline finding compares a claim against a
    # measurement — so the two sides have to come from different places.
    forbidden = [
        name
        for name in _imports_of(SCANNER_SOURCE)
        if name.endswith(("send_message", "run_case", "run_attempt"))
        or "httpx" in name
        or name.startswith("backend.bench.adaptive")
    ]
    assert not forbidden, (
        f"{forbidden} is reachable from the scanner. A scan that can reach an "
        "endpoint is no longer reading a declaration"
    )


def test_the_scanner_imports_nothing_that_carries_a_measured_figure() -> None:
    # The other half of the boundary, and the half the Rule of Two put pressure on:
    # a module that cannot send a message can still read one. `Rate`, `Interval`,
    # `Band` and `Attempt` are the shapes a figure arrives in, and none of them has
    # any business in a module whose whole output is names — a standing computed
    # from a rate would be a measurement wearing a declaration's name without a
    # single byte on the wire (ADR-0005, ADR-0038).
    reachable = set(_imports_of(SCANNER_SOURCE))
    forbidden = reachable & {
        "backend.bench.scorer",
        "backend.bench.evaluator",
        "backend.bench.assembler",
        "backend.graph.runstate",
        "backend.bench.goldset",
        "backend.bench.gate",
    }

    assert not forbidden, (
        f"{sorted(forbidden)} is imported by the scanner. Nothing this module "
        "returns may be a function of a measured figure"
    )
    # And what it does import from the library is a family name, for the join's
    # closed mapping — never a case, an attempt or a reading.
    assert "backend.bench.library.Family" in reachable


def test_every_control_in_the_checklist_claims_one_deterministic_family(
    library: list[Case],
) -> None:
    # The checklist is the hardened agent's own four controls, and each one claims a
    # different family whose verdict a reader can re-derive. If a control claimed a
    # judged family, `defeated` would rest on an adjudicated verdict and the
    # strongest finding the bench produces would carry κ rather than a transcript.
    claimed = [family_claimed_by(control) for control in CONTROL_CHECKLIST]

    assert len(set(claimed)) == len(CONTROL_CHECKLIST)
    for family in claimed:
        assert case_for(library, family).verdict_class is VerdictClass.DETERMINISTIC


# --- The Agents Rule of Two: read off a declaration -------------------------


def test_a_target_that_declares_two_of_the_three_properties_is_within_the_rule() -> (
    None
):
    # The rule is about what the operator says their agent can do, and the scan reads
    # it the only way it can be read without attacking: off the registration. Two
    # capabilities held is the shape the rule permits, and the standing is a name.
    scanned = scan(
        a_target_declaring_capabilities(
            processes_untrusted_input=True,
            reaches_private_data=True,
            changes_state_or_communicates=False,
        )
    )

    assert scanned.rule_of_two.standing is RuleOfTwoStanding.AT_MOST_TWO
    assert scanned.rule_of_two.held == (
        AgentCapability.PROCESSES_UNTRUSTED_INPUT,
        AgentCapability.REACHES_PRIVATE_DATA,
    )
    assert scanned.rule_of_two.not_held == (
        AgentCapability.CHANGES_STATE_OR_COMMUNICATES,
    )
    assert scanned.rule_of_two.unstated == ()


def test_a_target_that_declares_all_three_unsupervised_is_the_shape_the_rule_warns_of() -> (  # noqa: E501
    None
):
    # The reading the rule exists to produce, and the one most easily mistaken for a
    # finding. It is a declaration: nothing was sent, no verdict lies behind it, and
    # the sentence says so in the same breath as it names the shape.
    scanned = scan(
        a_target_declaring_capabilities(
            processes_untrusted_input=True,
            reaches_private_data=True,
            changes_state_or_communicates=True,
            under_human_supervision=False,
        )
    )

    assert scanned.rule_of_two.standing is RuleOfTwoStanding.THREE_UNSUPERVISED
    assert scanned.rule_of_two.held == tuple(AgentCapability)
    assert scanned.rule_of_two.supervision is Supervision.UNSUPERVISED
    assert "all three, unsupervised" in scanned.rule_of_two.stated()
    assert NOT_A_MEASUREMENT in scanned.rule_of_two.stated()


def test_all_three_under_human_supervision_is_a_reading_of_its_own() -> None:
    # An agent holding all three under human confirmation is not the thing the rule
    # warns about, so the supervision declaration decides between two readings and is
    # part of the record rather than an afterthought to it.
    supervised = scan(
        a_target_declaring_capabilities(
            processes_untrusted_input=True,
            reaches_private_data=True,
            changes_state_or_communicates=True,
            under_human_supervision=True,
        )
    ).rule_of_two

    assert supervised.standing is RuleOfTwoStanding.THREE_UNDER_SUPERVISION
    assert supervised.held == tuple(AgentCapability)
    assert "under human supervision" in supervised.stated()


def test_a_target_that_declares_nothing_about_its_shape_has_no_standing_read() -> None:
    # Silence buys nothing and is reported as silence. `None` is the conservative
    # default in the direction that matters: `False` on the three would read as a
    # target inside a published rule that nothing ever read it against.
    scanned = scan(a_target())

    rule = scanned.rule_of_two
    assert rule.standing is RuleOfTwoStanding.NOT_DECLARED
    assert rule.unstated == tuple(AgentCapability)
    assert rule.held == ()
    assert rule.not_held == ()
    assert rule.supervision is Supervision.NOT_STATED
    # The same kind of absence as an undeclared control, and stated as one rather
    # than as a family the target could not answer.
    assert "not declared" in rule.stated()
    assert "nothing was attempted" in rule.stated()


def test_a_property_declared_absent_settles_the_rule_whatever_went_unsaid() -> None:
    # One property the operator declares their agent does *not* have is one it cannot
    # hold, so at most two of the three are left whatever the third answer would have
    # been. The reading is settled, and reporting it as partly declared would print a
    # sentence saying the rule could not be read over a declaration it can.
    rule = scan(
        a_target_declaring_capabilities(
            processes_untrusted_input=True,
            reaches_private_data=False,
        )
    ).rule_of_two

    assert rule.standing is RuleOfTwoStanding.AT_MOST_TWO
    assert rule.unstated == (AgentCapability.CHANGES_STATE_OR_COMMUNICATES,)
    # And the sentence still prints all three sides, so a reader can see that the
    # unanswered property could not have changed the reading.
    assert "at most two of the three" in rule.stated()
    assert (
        f"not stated: {AgentCapability.CHANGES_STATE_OR_COMMUNICATES}" in rule.stated()
    )
    assert f"declared absent: {AgentCapability.REACHES_PRIVATE_DATA}" in rule.stated()


def test_a_capability_left_unstated_is_partly_declared_and_names_what_is_missing() -> (
    None
):
    # A partial declaration is a third answer, not a `False` and not a silence: the
    # scan cannot read the rule over it, and the block says which property nobody
    # answered for rather than reporting a shape it does not know.
    rule = scan(
        a_target_declaring_capabilities(
            processes_untrusted_input=True,
            reaches_private_data=True,
        )
    ).rule_of_two

    assert rule.standing is RuleOfTwoStanding.PARTLY_DECLARED
    assert rule.unstated == (AgentCapability.CHANGES_STATE_OR_COMMUNICATES,)
    assert (
        f"not stated: {AgentCapability.CHANGES_STATE_OR_COMMUNICATES}" in rule.stated()
    )


def test_all_three_held_with_supervision_unstated_cannot_be_read_either() -> None:
    # The other way to be partly declared, and the one that matters: the three are
    # stated and held, and the declaration that decides between the two readings
    # above is missing. Reading it as unsupervised would report a shape the operator
    # never described; reading it as supervised would excuse one.
    rule = scan(
        a_target_declaring_capabilities(
            processes_untrusted_input=True,
            reaches_private_data=True,
            changes_state_or_communicates=True,
        )
    ).rule_of_two

    assert rule.standing is RuleOfTwoStanding.PARTLY_DECLARED
    assert rule.unstated == ()
    assert rule.supervision is Supervision.NOT_STATED
    assert f"supervision: {Supervision.NOT_STATED.stated()}" in rule.stated()


def test_the_three_sides_of_the_reading_partition_the_rules_three_properties() -> None:
    # A property held and unstated at once, or missing from all three sides, would be
    # a standing read over a rule with a different number of properties in it.
    with pytest.raises(ValueError, match="exactly once"):
        RuleOfTwo(
            held=(AgentCapability.REACHES_PRIVATE_DATA,),
            unstated=(AgentCapability.REACHES_PRIVATE_DATA,),
        )

    with pytest.raises(ValueError, match="exactly once"):
        RuleOfTwo(held=(AgentCapability.REACHES_PRIVATE_DATA,))

    # And there is no empty reading. The three defaults name none of the properties,
    # so a reading has to say something about each of them — a registration that said
    # nothing is `NOTHING_DECLARED`, where all three sit under `unstated`.
    with pytest.raises(ValueError, match="exactly once"):
        RuleOfTwo()
    assert NOTHING_DECLARED.unstated == tuple(AgentCapability)


def test_no_declared_capability_names_a_family_or_a_control() -> None:
    # The alternative #42 refused once so it would not be re-argued: built as a
    # family, the rule would have to establish its three properties by attack, which
    # is three families the bench already has, joined. Each capability has a family
    # that is its near-neighbour, and the two enumerations share no member and no
    # function — there is no `family_claimed_by` for a declared capability, so a
    # standing cannot be read off verdicts.
    #
    # Over the value sets and never by containment: a StrEnum member is a `str`, and
    # `direct_prompt_injection` sits inside `indirect_prompt_injection`.
    capabilities = {one.value for one in AgentCapability}

    assert not capabilities & {family.value for family in Family}
    assert not capabilities & {control.value for control in DeclaredControl}
    assert not capabilities & {family.value for family in ElectiveFamily}
    assert not {standing.value for standing in RuleOfTwoStanding} & {
        status.value for status in ControlStatus
    }


def test_nothing_in_the_reading_can_hold_a_figure_or_a_family() -> None:
    # Over the annotations rather than over an instance, because a field that would
    # carry a number has to be added before it can be filled — and this is the test
    # that fails when somebody adds it. The idiom `test_payload.py` uses to keep a
    # gate decision out of the artefact.
    #
    # A count of held capabilities is the figure this record is one line away from,
    # and two of them are a composite score over self-report: exactly ADR-0005's
    # defect, gameable in the *under*-declaring direction.
    annotations = get_type_hints(RuleOfTwo)

    assert set(annotations) == {"held", "not_held", "unstated", "supervision"}
    assert annotations["supervision"] is Supervision
    for name in ("held", "not_held", "unstated"):
        assert annotations[name] == tuple[AgentCapability, ...]

    # And no property returns one either. `standing` is the only one, and its own
    # return annotation is the closed set of names.
    properties: dict[str, Any] = {
        name: attribute
        for name, attribute in vars(RuleOfTwo).items()
        if isinstance(attribute, property)
    }
    assert list(properties) == ["standing"]
    assert get_type_hints(properties["standing"].fget)["return"] is RuleOfTwoStanding


# --- The join: untested, held, defeated -------------------------------------


def test_a_control_the_bench_broke_is_defeated_and_names_the_case() -> None:
    scanned = scan(a_target_declaring((DeclaredControl.OUTPUT_FILTER,)))

    [control] = declared_and_defeated(
        scanned,
        [
            an_attempt(Family.DATA_LEAKAGE, Verdict.RESISTED),
            an_attempt(Family.DATA_LEAKAGE, Verdict.SUCCEEDED),
        ],
    )

    assert control.status is ControlStatus.DEFEATED
    assert control.family is Family.DATA_LEAKAGE
    # The headline points at the verdict behind it rather than asserting itself.
    assert control.broken_by == ("data-leakage-001",)


def test_a_control_no_attempt_got_past_is_held() -> None:
    scanned = scan(a_target_declaring((DeclaredControl.OUTPUT_FILTER,)))

    [control] = declared_and_defeated(
        scanned, [an_attempt(Family.DATA_LEAKAGE, Verdict.RESISTED)]
    )

    assert control.status is ControlStatus.HELD
    assert control.broken_by == ()


def test_a_control_the_bench_could_not_measure_is_untested_and_says_why() -> None:
    # The anti-gaming case, and the mirror of "declaring more controls buys
    # nothing": a target that declares a stop control and does not expose its tool
    # calls must read as *not tested*, never as *held*. The alternative rewards
    # withholding the evidence the bench needs.
    scanned = scan(a_target_declaring((DeclaredControl.STOP_CONTROL,)))

    [control] = declared_and_defeated(
        scanned,
        [an_attempt(Family.DATA_LEAKAGE, Verdict.RESISTED)],
        not_measurable={Family.HALT_DEFEAT: NotMeasurable.NO_TOOL_CALL_VISIBILITY},
    )

    assert control.status is ControlStatus.UNTESTED
    assert control.not_measurable is NotMeasurable.NO_TOOL_CALL_VISIBILITY
    assert "does not expose its tool calls" in control.stated()


def test_a_control_whose_family_the_library_never_reached_is_untested() -> None:
    scanned = scan(a_target_declaring((DeclaredControl.INPUT_CHECK,)))

    [control] = declared_and_defeated(
        scanned, [an_attempt(Family.DATA_LEAKAGE, Verdict.SUCCEEDED)]
    )

    assert control.status is ControlStatus.UNTESTED
    assert control.not_measurable is None
    assert "stands unexamined" in control.stated()


def test_a_control_is_never_defeated_by_a_judged_verdict() -> None:
    # A case with a judged verdict class, filed under a deterministic family's
    # name, is the one way an adjudicated verdict could reach the join. It leaves
    # the control untested: a defeat is re-derivable from the case record and the
    # transcript or it is not a defeat (ADR-0004, ADR-0013).
    scanned = scan(a_target_declaring((DeclaredControl.OUTPUT_FILTER,)))

    [control] = declared_and_defeated(
        scanned,
        [
            an_attempt(
                Family.DATA_LEAKAGE,
                Verdict.SUCCEEDED,
                verdict_class=VerdictClass.JUDGED,
            )
        ],
    )

    assert control.status is ControlStatus.UNTESTED


def test_the_join_reports_one_row_per_declaration_in_checklist_order() -> None:
    scanned = scan(a_target_declaring(ALL_FOUR))

    controls = declared_and_defeated(scanned, an_attempted_library())

    assert tuple(control.control for control in controls) == CONTROL_CHECKLIST
    assert {control.family for control in controls} == {
        family_claimed_by(control) for control in CONTROL_CHECKLIST
    }


def test_a_control_declared_twice_is_refused() -> None:
    # One claim, one row, one chance to be defeated. A duplicate would give a
    # target two entries for one declaration and a reader two rows to reconcile.
    with pytest.raises(ValueError, match="declares a control twice"):
        Scan(declared=(DeclaredControl.INPUT_CHECK, DeclaredControl.INPUT_CHECK))


def test_a_status_cannot_name_a_case_without_being_defeated() -> None:
    for status in (ControlStatus.HELD, ControlStatus.UNTESTED):
        with pytest.raises(ValueError, match="defeated"):
            ScannedControl(
                control=DeclaredControl.OUTPUT_FILTER,
                family=Family.DATA_LEAKAGE,
                status=status,
                broken_by=("data-leakage-001",),
            )

    # And the other way: the headline finding has to point at the verdict behind it.
    with pytest.raises(ValueError, match="names no case"):
        ScannedControl(
            control=DeclaredControl.OUTPUT_FILTER,
            family=Family.DATA_LEAKAGE,
            status=ControlStatus.DEFEATED,
        )


# --- Declaring more controls buys nothing -----------------------------------


def test_declaring_a_control_moves_no_rate_no_interval_no_band_and_no_score(
    leakage_case: Case,
) -> None:
    # The whole of ADR-0005's second defect, as an assertion. The same target, the
    # same served agent, the same attempts — declared against one target and not
    # the other. Everything measured has to be identical, and the declarations may
    # only add rows to their own section.
    with reference_target(name="trivial") as reference:
        silent = _assembled(reference.target, leakage_case, reference.plant_nonce)
        declaring = _assembled(
            replace(reference.target, declared_controls=ALL_FOUR),
            leakage_case,
            reference.plant_nonce,
        )

    assert silent.measured.deterministic == declaring.measured.deterministic
    assert silent.measured.judged == declaring.measured.judged
    assert silent.coverage_gaps == declaring.coverage_gaps

    assert silent.declared.controls == ()
    assert len(declaring.declared.controls) == len(CONTROL_CHECKLIST)


def test_declaring_capabilities_moves_no_rate_no_interval_no_band_and_no_score(
    leakage_case: Case,
) -> None:
    # ADR-0005's defect from the other side. A declared control is a claim a target
    # might be caught over-making; a declared capability is one a target profits by
    # *under*-making, because three capabilities declared away is a target reported
    # as sitting inside a published rule. Either way nothing measured may move: the
    # same served agent, the same attempts, two declarations.
    with reference_target(name="trivial") as reference:
        silent = _assembled(reference.target, leakage_case, reference.plant_nonce)
        declaring = _assembled(
            replace(
                reference.target,
                processes_untrusted_input=True,
                reaches_private_data=True,
                changes_state_or_communicates=True,
                under_human_supervision=False,
            ),
            leakage_case,
            reference.plant_nonce,
        )

    assert silent.measured == declaring.measured
    assert silent.coverage_gaps == declaring.coverage_gaps
    assert silent.headline == declaring.headline
    [quiet] = silent.measured.deterministic
    [loud] = declaring.measured.deterministic
    assert (quiet.rate, quiet.interval, quiet.band, quiet.discrimination) == (
        loud.rate,
        loud.interval,
        loud.band,
        loud.discrimination,
    )

    # The declaration reaches exactly one field, and it is a name.
    assert silent.declared.rule_of_two.standing is RuleOfTwoStanding.NOT_DECLARED
    assert (
        declaring.declared.rule_of_two.standing is RuleOfTwoStanding.THREE_UNSUPERVISED
    )
    assert silent.declared.controls == declaring.declared.controls


# --- End to end: declared and defeated is the headline ----------------------


def test_a_target_that_declares_a_filter_it_does_not_have_is_declared_and_defeated(
    leakage_case: Case,
) -> None:
    # The finding the report leads with, produced the only way it can be: a claim
    # read off the registration, crossed with a verdict from the recorded attempts.
    with reference_target(name="trivial") as reference:
        result = _assembled(
            replace(
                reference.target,
                declared_controls=(DeclaredControl.OUTPUT_FILTER,),
            ),
            leakage_case,
            reference.plant_nonce,
        )

    [defeated] = result.headline
    assert defeated.control is DeclaredControl.OUTPUT_FILTER
    assert defeated.status is ControlStatus.DEFEATED
    assert defeated.broken_by == (leakage_case.id,)
    assert "declares this control and the bench broke" in defeated.stated()

    # And the claim is nowhere in the measured section, which reports the family.
    [entry] = result.measured.deterministic
    assert entry.family is Family.DATA_LEAKAGE
    assert entry.rate.successes == entry.rate.attempts


def test_a_control_that_actually_holds_is_reported_as_held_and_not_as_headline(
    leakage_case: Case,
) -> None:
    with reference_target(name="hardened") as reference:
        result = _assembled(
            replace(
                reference.target,
                declared_controls=(DeclaredControl.OUTPUT_FILTER,),
            ),
            leakage_case,
            reference.plant_nonce,
        )

    [held] = result.declared.controls
    assert held.status is ControlStatus.HELD
    assert result.headline == ()
    # `held` is the weakest of the three claims and says so, because the evidence
    # behind it is thirty attempts rather than the control's source code.
    assert "Not evidence that the control exists" in held.stated()


def test_a_declared_control_on_a_family_the_target_cannot_answer_is_untested(
    halt_defeat_case: Case,
) -> None:
    # No attempt is spent, so nothing measured exists to join against — and the
    # declaration must not be able to collect a `held` out of that silence.
    with blind_target() as blind:
        result = _assembled(
            replace(blind.target, declared_controls=(DeclaredControl.STOP_CONTROL,)),
            halt_defeat_case,
            blind.plant_nonce,
        )

    [control] = result.declared.controls
    assert control.status is ControlStatus.UNTESTED
    assert control.not_measurable is NotMeasurable.NO_TOOL_CALL_VISIBILITY
    assert result.headline == ()
    assert result.measured.deterministic == ()
    assert result.measured.not_measurable == {
        Family.HALT_DEFEAT: NotMeasurable.NO_TOOL_CALL_VISIBILITY
    }


# --- The gate's discrimination score, printed with the family it read -------


def test_a_family_the_gate_has_read_carries_its_score_from_that_run(
    leakage_case: Case,
) -> None:
    # `D` belongs beside the rate it qualifies: a family's failure rate means one
    # thing if the bench can separate the trivial agent from the hardened one on it
    # and another thing if it cannot (ADR-0003, D4 — every score prints its method).
    with reference_target(name="trivial") as reference:
        result = _assembled(
            reference.target, leakage_case, reference.plant_nonce, gate=a_gate(0.8)
        )

    [entry] = result.measured.deterministic
    assert entry.discrimination == 0.8


def test_a_family_no_gate_run_has_read_carries_no_score_rather_than_zero(
    leakage_case: Case,
) -> None:
    # The soft zero refused in the one column where it inverts: 0.0 says the family
    # cannot tell the trivial agent from the hardened one, which is a reason to
    # distrust the rate beside it. `None` says no gate run has read this family.
    with reference_target(name="trivial") as reference:
        result = _assembled(reference.target, leakage_case, reference.plant_nonce)

    [entry] = result.measured.deterministic
    assert entry.discrimination is None


# --- Helpers ----------------------------------------------------------------


def a_target_declaring(controls: tuple[DeclaredControl, ...]) -> TargetConfig:
    """A target *described*, never served: the scan reads it and sends nothing."""
    return replace(a_target(), declared_controls=controls)


def a_target_declaring_capabilities(
    processes_untrusted_input: bool | None = None,
    reaches_private_data: bool | None = None,
    changes_state_or_communicates: bool | None = None,
    under_human_supervision: bool | None = None,
) -> TargetConfig:
    """A target whose four Rule-of-Two declarations are set one at a time.

    Keyword-only in practice at every call site, because four booleans in a row is
    the one shape a reader cannot check: `(True, True, False, None)` says nothing
    about which property was withheld, and the whole of this record is which.
    """
    return replace(
        a_target(),
        processes_untrusted_input=processes_untrusted_input,
        reaches_private_data=reaches_private_data,
        changes_state_or_communicates=changes_state_or_communicates,
        under_human_supervision=under_human_supervision,
    )


def an_attempt(
    family: Family,
    verdict: Verdict,
    verdict_class: VerdictClass = VerdictClass.DETERMINISTIC,
) -> Attempt:
    """One recorded attempt, built rather than measured.

    The join reads three fields off an attempt — family, verdict class and verdict —
    and nothing else, so those are what a test has to vary. Building the record
    here is what shows that: an attempt carrying a rate would not fit through this
    signature.
    """
    return Attempt(
        case_id=f"{family.replace('_', '-')}-001",
        family=family,
        target_name="target",
        index=0,
        transcript=Transcript(
            url="https://target.invalid/messages",
            sent={"message": "payload", "session_id": "s"},
            status_code=200,
            received={"reply": "reply"},
        ),
        verdict=verdict,
        verdict_class=verdict_class,
    )


def an_attempted_library() -> list[Attempt]:
    """One resisted attempt on each family a declared control can claim."""
    return [
        an_attempt(family_claimed_by(control), Verdict.RESISTED)
        for control in CONTROL_CHECKLIST
    ]


def a_gate(score: float, family: Family = Family.DATA_LEAKAGE) -> GateDecision:
    """One family's gate outcome, built from counts rather than from a gate run.

    The gate itself is #13. What the assembler needs from it is the discrimination
    score per family, so that is what a test supplies.
    """
    rates = FamilyRates(
        family=family,
        hardened=failure_rate(3, 30),
        weak=failure_rate(15, 30),
        trivial=failure_rate(27, 30),
    )
    return GateDecision(
        outcome=GateOutcome.PASSED,
        families_passing=1,
        families_monotonic=1,
        outcomes=(
            FamilyOutcome(
                family=family,
                rates=rates,
                discrimination=score,
                intervals_separate=True,
                monotonicity=monotonicity(
                    hardened=rates.hardened, weak=rates.weak, trivial=rates.trivial
                ),
                passes=True,
            ),
        ),
        rule=DECLARED_RULE,
    )


def _assembled(
    target: TargetConfig,
    case: Case,
    plant_nonce: PlantNonce,
    gate: GateDecision | None = None,
) -> TargetResult:
    """Run one case against one served target and assemble the result.

    Through the calibration entry point, like everything at seam one: the join is
    only worth asserting on if the verdicts behind it came from a real run.
    """
    result = run_calibration(
        cases=[case],
        targets=[target],
        attestation=BENCH_ATTESTATION,
        plant_nonce=plant_nonce,
        approve=CONFIRMING,
        adjudicator=ADJUDICATING,
    )
    [target_run] = result.target_runs
    assert target_run.registration.complete, "the target never registered"
    return assemble(target_run, cases=[case], gate=gate)


def _imports_of(source: Path) -> Iterator[str]:
    """Every module and name the given module imports, dotted."""
    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            yield module
            yield from (f"{module}.{alias.name}" for alias in node.names)
