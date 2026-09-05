"""The three sections built from what the run *declared*: what was measured, how the
run was made, and the controls that authorised it.

Annex IV points 1, 2 and 4. What these three have in common, and what makes them one
module, is that every figure in them was declared before the run rather than measured
by it — the target's identity, the library version, the models, the attestation, the
halt. A reader checking *whether this run was authorised and against what* reads these
sections and this module.

**Two of the document's three claims live here** — `INTEGRITY_CLAIM` and
`RE_DERIVABILITY_CLAIM` — because the general description is where a reader is told
what the signature covers and what it does not. The third,
`NOT_A_CLAIM_OF_CONFORMITY`, is in `_layout.py` because point 9 says it again.

**`FORMAT_UNVALIDATED` is here for the same reason it exists**: ADR-0001 records the
report format as an open question no procurement reader has been asked, and the
dishonest form of that is silence.

Every definition moved verbatim out of `rendering.py`; no byte of the document
changed (ADR-0017).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.bench.rendering._layout import (
    NOT_A_CLAIM_OF_CONFORMITY,
    Section,
    _listed,
)
from backend.bench.reproducibility import Reproducibility

FORMAT_UNVALIDATED = (
    "**The format of this report has never been validated against a real "
    "procurement reader.** Its section order is the Act's own technical-"
    "documentation order (Annex IV), which is a defensible default and not a "
    "finding: ADR-0001 records that the format is a question for the readers this "
    "document is shaped for, and none has been asked. A reader who needs it in "
    "another shape — a questionnaire template, SOC 2, ISO 42001 — is reading "
    "something this bench has not done, and not a claim about what they should "
    "expect. The same "
    "statement is recorded in `docs/validation.md`."
)
"""The label ADR-0001 requires, in the document rather than only in the repository.

Stated because the alternative is silence, and silence is indistinguishable from
having asked a reader and been told this shape was right.
"""

"""ADR-0017's first claim, printed beside the second and never alone.

*This reached you unaltered*, stated for the whole artefact including the adaptive
section, because a security report with an unprotected region would be a worse
artefact for a strictly worse reason. It deliberately does not say the document **is**
signed: an unsigned run must be impossible to present as signed, so this paragraph
describes what the binding makes checkable and `verify.py` is what answers whether it
checks out.
"""


INTEGRITY_CLAIM = (
    "**Integrity, for the whole document.** The canonical JSON payload beside this "
    "file carries this document's sha256 in `rendered_sha256`, so the two travel as "
    "one artefact: alter a byte of either and they no longer agree. A signature over "
    "that payload therefore covers this document whole, the adaptive section "
    "included — no region of it is left unprotected (ADR-0017). Whether these bytes "
    "*are* signed, and by which key, is a property of the payload beside them and is "
    "answered by `scripts/verify.py`, not by this sentence."
)

"""ADR-0017's second claim, and the reason the first one is not enough on its own.

A valid signature over `A_break = +0.25` invites the reading that the figure is
reproducible, and it is not: the same declared configuration produced +0.00 and +0.25
on two certified runs a day apart. So the scope of re-derivability is stated in the
document rather than left to be inferred from the presence of a signature.
"""


RE_DERIVABILITY_CLAIM = (
    "**Re-derivability, for the scored layer only.** Every figure in the scored "
    "sections follows from the recorded attempts, the case records and the rule "
    "printed below, so a reader holding those recomputes it without this bench. The "
    "adaptive layer is **recorded and not reproducible**: re-run it and the attacker "
    "takes a different path. Both claims are printed together, because a document "
    "stating one of them alone would be claiming the stochastic half was reproducible "
    "by omission (ADR-0010, ADR-0017)."
)

"""What this document refuses to be, printed in section 1 and again in section 8.

Twice on purpose, and not by an accident of reuse: a reader who arrives looking for a
badge turns to the declaration-of-conformity section, and a refusal placed only in an
introduction they skipped would tell them nothing. The most likely way this report
fails is by reading like a grade, and no one sentence is the safeguard — the safeguard
is that the page never makes a single figure easy to construct.
"""


def _general_description(body: Mapping[str, Any]) -> Section:
    """What this document is about, the headline finding, and the two claims.

    The declared-and-defeated join is the headline because it is the strongest
    finding the bench can produce: a control the operator declared and the bench
    empirically broke. It is a status and a case id rather than a figure, which is
    why it can sit above the measurements without becoming a summary of them.
    """
    provenance = body["provenance"]
    attestation = provenance["attestation"]
    return Section(
        point=1,
        title="The target, and the headline finding",
        body=(
            f"- **Target**: `{body['target']}`",
            f"- **Attested by**: {attestation['identity']}, "
            f"recorded {attestation['recorded_at']}",
            "- **One run, in two layers**: the recorded library at the declared "
            "attempts per case, then one adaptive attacker. Only the first is scored.",
            "",
            "### The headline finding — declared, and defeated",
            "",
            *_headline(body["declared"]),
            "",
            "### The two claims this document carries",
            "",
            f"- {INTEGRITY_CLAIM}",
            f"- {RE_DERIVABILITY_CLAIM}",
            "",
            "### What this document is not",
            "",
            NOT_A_CLAIM_OF_CONFORMITY,
            "",
            "### The shape of this document",
            "",
            FORMAT_UNVALIDATED,
        ),
    )


CONTROL_PROVED = (
    "- **Control of the endpoint**: proved. The target echoed the registration "
    "nonce, a value only somebody who can edit its configuration could have "
    "planted, so the first statement above was checked and not only made "
    "(ADR-0007)."
)


CONTROL_DECLARED = (
    "- **Control of the endpoint**: declared, and not proved. This run was started "
    "with the nonce echo waived, so the first statement above stands on the "
    "attester's word alone and nothing here checked it. Read the figures below as "
    "measurements of an endpoint whose ownership this document does not establish "
    "(ADR-0007, as amended)."
)


def _control(proved: bool) -> str:
    """The line that says what the attestation is worth on this run.

    Two whole sentences rather than a flag, and the declared one says what a reader
    should do about it. A document that printed `control_proved: false` and left it
    there would be telling a recipient a fact whose consequence they have to work out
    while holding a report about somebody else's agent.
    """
    return CONTROL_PROVED if proved else CONTROL_DECLARED


def _headline(declared: Mapping[str, Any]) -> tuple[str, ...]:
    """The controls this target declared and the bench broke, or the stated absence.

    An empty join is an answer and not a blank: a target whose declarations all held
    is reported as having held them, and one that declared nothing has nothing to be
    caught over-declaring.
    """
    defeated = [
        control
        for control in declared["controls"]
        if control["control"] in declared["defeated"]
    ]
    if not defeated:
        if not declared["controls"]:
            return (
                "This target declared no controls, so there is no declaration for "
                "these attempts to have broken. An absence on the operator's side, "
                "and not a finding about the agent.",
            )
        return (
            "**No control this target declared was defeated by these attempts.** "
            "Not evidence that the controls exist, only that these attempts did not "
            "get past them — the per-control rows in section 3 say which was which.",
        )
    return tuple(
        f"- **Declared, and defeated:** {control['stated']}." for control in defeated
    )


def _how_the_run_was_made(body: Mapping[str, Any]) -> Section:
    """Provenance: who attested, on which models, against which library, at what cost.

    The bench's gate **result** is cited here and in no other section (ADR-0018).
    This is the part of a document that says *how this was made*, which is where a
    reader looks for the ruler's certification — not in the section carrying what the
    ruler measured.
    """
    provenance = body["provenance"]
    attestation = provenance["attestation"]
    models = provenance["models"]
    selection = provenance["selection"]
    rule = provenance["rule"]
    return Section(
        point=2,
        title="How this run was made, and by what instruments",
        body=(
            "### The attestation this run required",
            "",
            f"- **Identity**: {attestation['identity']}",
            f"- **Recorded at**: {attestation['recorded_at']}",
            f"- **Endpoint**: `sha256:{attestation['endpoint_sha256']}` — the "
            "endpoint travels as a hash. A live URL that answers jailbreak payloads "
            "is not a thing to write into a document that leaves the building "
            "(ADR-0008).",
            "",
            "The three statements this run could not start without, as recorded:",
            "",
            *(f"- Attested — {wording}." for wording in attestation["statements"]),
            "",
            _control(attestation["control_proved"]),
            "",
            "### The four declared models",
            "",
            f"- **{models['calibration']}** — the model the bench's own calibration "
            "equipment ran on, and so the model its gate citation was earned on.",
            f"- **{models['adjudicating']}** — the instrument that decided the judged "
            "families, and the one κ is measured on.",
            # The fourth, and the reason section 3b is not an unattributed page: the
            # instrument that wrote the prose is named beside the three that
            # calibrate, decide and attack (ADR-0070 §5). Never κ's subject, and the
            # line says so — κ is a figure about the adjudicator above it, and no
            # figure anywhere in this document is read off this one.
            f"- **{models['narrative']}** — the model the judge and the remediation "
            "tool ran on, which is to say the model that wrote every sentence in "
            "section 3b. It decides nothing: no rate, band, interval or "
            "discrimination score reads a word it wrote, and it carries no "
            "reliability figure of its own.",
            f"- **{models['attacking']}** — the adaptive layer's model, and the "
            "adaptive layer's only. It decides nothing that is scored.",
            f"  - Sampling: {models['attacking_temperature_stated']}.",
            # Both declared inputs of the one instrument, under it and never folded
            # into a single line: two runs of one model at one temperature and
            # different reasoning effort are two different instruments (#5).
            f"  - Reasoning: {models['attacking_reasoning_effort_stated']}.",
            "",
            "### The library these attempts came from",
            "",
            f"- {provenance['library']['stated']}",
            "",
            # Beside the library version and never anywhere else, because the two are
            # one condition: section 4 says the figures are comparable only at equal
            # library version and **equal selection**, and until #79 this document
            # carried the first half of that and left the second to be trusted
            # (ADR-0058). The layers are named because a layer switched off is why a
            # construction is missing, and the sentence is the payload's own — a
            # renderer that reworded it would be a second wording of a claim about
            # what may be done with these figures.
            "### The constructions this run sent",
            "",
            *(f"- **{layer}**" for layer in selection["layers"]),
            "",
            f"{selection['stated']}",
            "",
            "### What this run spent, per layer",
            "",
            *(
                f"- **{layer} layer**: {calls} calls on the wire"
                for layer, calls in provenance["calls_spent"].items()
            ),
            "- Reported per layer and never as one figure: a blended number hides "
            "which half of the run spent the operator's budget.",
            "",
            # The cleanup, printed whichever way it went. A run that planted nothing
            # says so, and a run whose teardown failed says which namespace and what
            # the error was — the run's figures are unaffected either way, and the
            # only person who can act on a store this bench wrote into is the operator
            # who is told about it (ADR-0063 §3).
            "### What this run planted, and whether it took it back out",
            "",
            # What was planted and how good the evidence is that it landed, ahead of
            # what became of it. On an endpoint run this is the sentence that says
            # the bench planted nothing, so the strongest claim the block can make is
            # not one a target that is a URL ever prints (ADR-0064 §5).
            f"- {provenance['planting']['stated']}",
            f"- {provenance['teardown']['stated']}",
            "",
            "### The rule these figures were measured under",
            "",
            f"- **{rule['attempts_per_case']} attempts per case** — the denominator "
            "behind each rate is printed beside it in section 4.",
            # The sentence beside the number, nested under it the way the attacker's
            # two sampling settings are: the value alone cannot say whether it is the
            # published denominator, and a run at another one is not a gate result and
            # says so here rather than only on the screen that offered the setting
            # (ADR-0025, ADR-0027).
            f"  - {rule['attempts_per_case_stated']}.",
            f"- **Wilson interval at {rule['interval_confidence']:.0%}** around every "
            "rate.",
            f"- **κ floor of {rule['kappa_floor']:.2f}** — a judged family whose "
            "adjudicator reads below it is not published, and section 4 says which.",
            "- Only the part of the declared rule that decided the figures below "
            "appears here. The rest of it decides the bench's own gate, over three "
            "agents of known construction, and has no definition for one target "
            "(ADR-0018).",
            "",
            "### The bench's own gate, cited as provenance",
            "",
            f"> {provenance['gate']['stated']}",
        ),
    )


PUBLISHED_RULE_OF_TWO = (
    "The published rule says an agent should not, in one session and without human "
    "supervision, hold more than two of — processes untrusted input, reaches private "
    "data or sensitive systems, changes state or communicates outward. **Nothing was "
    "sent to establish any of this.** It is read off the operator's own registration "
    "and reported against the rule, so it is a declaration on the same footing as the "
    "controls above and not a finding: no attempt was made against it, no verdict "
    "lies behind it, and no rate, band or discrimination score anywhere in this "
    "document is a function of it (ADR-0005, ADR-0038)."
)
"""What the rule is, and what reading it off a declaration does and does not buy.

Printed above the line rather than folded into it, because the reader arrives here
from a join whose every row points at a verdict. A shape named without that paragraph
reads as the next finding down the page, and the one standing that matters — all
three, unsupervised — is the one that reads most like a finding.

Its counterpart in the artefact is `scanner.NOT_A_MEASUREMENT`, which every reading
carries: the sentence travels with the fact, the way `NotMeasurable.stated` does, so
a consumer that never renders this page still gets it. The two are not one constant
because this module reads the serialised document and never the records behind it,
and they say different things — this one states the rule, that one states what
reading it off a declaration is worth.
"""


def _controls(declared: Mapping[str, Any]) -> Section:
    """The declared-and-defeated join in full: what was claimed, and what held.

    Statuses and case ids, and no count of either. A number in this section would be
    a measurement inside the declared half, and the first thing anyone would do with
    two of them is compare two targets on it.

    **3a since ADR-0070**, because Annex IV point 3 now holds two sections: this one
    is the join per *control*, and `_findings` is the same material per *failure* —
    why each break happened and what to change. Two labelled sections under one point
    is the shape point 5 already has, and it is the honest alternative to one section
    carrying two reproducibility labels (`_layout.Section.part`).
    """
    return Section(
        point=3,
        part="a",
        title="The controls this target declared, and what the attacks made of them",
        reproducibility=Reproducibility(declared["reproducibility"]),
        body=(
            "The scan reads what the operator declared. A declared control can still "
            "be broken, and that is what the attempts are for — this section is the "
            "join, and every row points at a verdict rather than at a figure.",
            "",
            "### Declared",
            "",
            *_listed(
                (f"- {control['stated']}" for control in declared["controls"]),
                "- Nothing was declared, so nothing here was examined.",
            ),
            "",
            "### Not declared",
            "",
            *_listed(
                (f"- {absent['stated']}" for absent in declared["absent"]),
                "- The checklist asks about no control this target left undeclared.",
            ),
            "",
            "### The Agents Rule of Two, as this target declares itself",
            "",
            PUBLISHED_RULE_OF_TWO,
            "",
            f"- {declared['rule_of_two']['stated']}.",
        ),
    )
