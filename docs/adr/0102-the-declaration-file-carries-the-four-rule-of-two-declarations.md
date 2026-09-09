---
status: accepted
---

# The declaration file carries the four Rule of Two declarations, and an omitted key is unstated

[ADR-0038](./0038-the-rule-of-two-is-a-declared-property.md) decided that the Agents
Rule of Two is read over four declarations the operator makes and nothing derives, and
left open how an operator fills them in over the wire.
[ADR-0092](./0092-the-rule-of-two-is-declared-on-the-register-walk-and-the-reading-is-the-backends.md)
answered that for the console: the four are asked on the `tools` step of the register
walk, `TargetRequest` grew four `bool | None` fields, and `config()` passes them
through. The defect it fixed was stated plainly — *every target registered through the
API reads `not_declared` for ever, and the block prints, correctly, that nobody said
anything, because there is no way to say it.*

The MCP server is a third registration surface and it arrived after both records.
`POST /runs` takes the whole target on every start and there is no stored target to
reference, so what `backend/mcp/declaration.py` reads out of `agentaudit.toml` *is* the
registration. The file carried the endpoint, the agent type, the tool declarations, the
attestation and the price, and none of the four — so a run started from this surface
reproduced exactly the defect ADR-0092 had just closed, one surface over. This record
settles the question for the file rather than letting it be settled by omission.

## Decision

1. **`agentaudit.toml`'s `[target]` table carries the four, and `Declaration` carries
   them as `bool | None`.** `processes_untrusted_input`, `reaches_private_data`,
   `changes_state_or_communicates`, `under_human_supervision`, spelt exactly as
   `TargetRequest` spells them, because the file and the wire are one vocabulary with
   one meaning and renaming on the way through would make them two. The client puts
   them on the `target` object of `StartRunRequest`'s body beside the fields already
   there.

2. **The tri-state is *key absent*, `true`, `false` — and a key absent is `None`.**
   TOML has no radio group, but it has the one thing a checkbox lacks: a key that is
   not there. So the three states the field is typed for survive the file intact.
   This is the one field family on this surface whose default is *not* the strict
   direction, and that is the point rather than an exception to it: the strict
   direction for a declaration nobody made is to report that nobody made it.
   `False` is the **profitable** claim here — three capabilities declared away is a
   target reported as sitting inside a published rule that nothing ever read it
   against — which is the argument ADR-0038 decision 1 spends itself on, and
   defaulting an absent key to `False` in a file an agent can write a line into is
   that claim made by a tool on an operator's behalf.

3. **A value that is neither a boolean nor absent raises, and is not refused by
   name.** `_flag` already refuses to coerce, on the reasoning that `bool("no")` is
   `True` and the two-valued fields it guards are the ones where that direction buys
   a waiver. A tri-state reader has the same hazard with a third landing place —
   `"unstated"` would coerce to a held capability — so it raises for the same reason
   and by the same route: this is a file that cannot be read, not a declaration whose
   contents can be argued with, and `DeclarationRefusal` stays a closed set of four
   things an operator *said*.

4. **No reading is printed at declaration time on this surface, and the standing's
   home here is the signed report.** ADR-0092 decision 3 has the reading print on the
   register screen, and its argument is about *who is looking*: the operator is the
   one person who could act on a standing by changing what their agent is, and on
   that screen they are still answering. This surface has no screen and no moment of
   answering — the declaration is committed to a repository and reviewed in a pull
   request, possibly months before the run that reads it — so the reading has no
   *while they are still thinking about it* to arrive in. That leaves ADR-0092's own
   runner-up, which ADR-0038 decision 7 had already placed: Annex IV section 3 of the
   signed report, which needs no change and which now prints a standing other than
   `not_declared` for a run this surface started.

   The consequence is that `BenchClient` gains no `rule_of_two` method and the MCP
   server calls `POST /rule-of-two` from nowhere. A fifth route reached by no tool is
   a method with no caller, and `scanner.py` stays the sole author of the derivation
   either way.

## Considered options

**Leave the four off the file and let every run from this surface print
`not_declared`.** Rejected. It is ADR-0092's defect reintroduced on a new surface,
one release after it was closed, and the honest version of it would have to say that
an operator who declared all four in the console gets a different report from one who
declared all four in a file. The cost of carrying them is four keys and a reader.

**Ask the four as arguments to the `start_run` tool.** Rejected, and this is the
sharper alternative. It is where a chat surface's gravity points: the model has the
operator right there and could simply ask. But spec §31 already refuses that shape for
the rest of the declaration — *the alternative is a questionnaire answered in a chat
transcript, where a half-answer becomes a declared control the operator never meant to
claim* — and these four are the fields that argument was written about. A declaration
typed into a chat window in reply to a model's question is not reviewed, not committed,
and not attributable to anybody after the transcript is gone.
[ADR-0100](./0100-the-mcp-server-has-no-privilege-the-console-lacks.md) puts it the
other way round: the declaration file is read, never written, because a surface that
could write a declaration is a surface that could declare a control.

**Default an absent key to `False`, matching how `retains_session_state` and
`holds_personal_records` default on this surface.** Rejected on decision 2. Those two
are `bool` on `TargetRequest` and false is their *narrowing* direction — a capability
nobody claimed is one the run is not measured on (ADR-0041), so the default costs the
operator coverage. These four are `bool | None` and false is the *flattering*
direction: it costs the operator nothing and buys a standing. The two defaults look
alike and point opposite ways, which is why the field types differ (ADR-0093 argues
the same split at the same boundary).

**Carry `declared_controls` on the same commit.** Not reopened. ADR-0092 decision 8
priced it and declined it for the console, and nothing about a TOML file changes the
price: a declared control is joined against a verdict, that join is the report's
headline finding, and a field on the wire that no surface asks for properly is a wire
shape with no author.

## Consequences

- `Declaration` gains four `bool | None` fields and `declaration_at` gains a
  `_tristate` reader beside `_flag`. `backend/mcp/client.py` puts them on the `target`
  object it assembles, and a target started from this surface can reach Annex IV
  section 3 with a standing.
- `agentaudit.toml`'s documented shape grows four optional keys in `[target]`. The
  example file (#186) shows all four, commented, with the *absent means unstated*
  sentence beside them — an example that filled them in with `false` would be the
  profitable claim shipped as a template.
- The four are the first keys in that file whose omission is a *third* answer rather
  than a default, so the reader that reads them cannot be the reader that reads the
  rest, and the two sit beside each other saying why.
- `docs/validation.md`'s line under *what has never been validated* — that no real
  operator has ever declared any of this — is still true and is now true of three
  surfaces rather than two.
