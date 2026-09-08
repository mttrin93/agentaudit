---
status: accepted
---

# The seed is per library directory, and a requested elective family with no case is stated

[ADR-0035](./0035-the-elective-family-tier-is-never-gate-deciding.md) put the elective
tier in a subdirectory of the case library, and `library.ELECTIVE_DIRECTORY` records
why: `load_library` globs `*.toml` and does not recurse, so a run that asks for
nothing from the tier loads exactly the cases it always loaded and its
`LibraryVersion` digest does not move. Asking for an elective family is *a caller
reaching for a second directory*.

`seeded_library` never reached the second directory. It copies `seed.glob("*.toml")`
— the top level only, file by file, so that what lands is case records and nothing
else — and a mounted volume therefore held the six's library and no elective one. The
consequence is that the tier was **reachable in a terminal run off the image and
unreachable on every deployment with a volume**: the console offered the three
families, an operator could request all three, `admitted_elective` globbed a
directory that did not exist, and the run attempted nothing.

That defect survived because nothing printed it. A run that requested three elective
families and measured none of them produced an empty `measured.elective`, an empty
`measured.elective_not_measurable`, and a `requested_stated` sentence saying *what
each of them measured against this target is reported above with its interval and its
band* — above which there was nothing. The tier had five kinds of nothing and no word
for *you asked, and there was no case to attempt*.

## Decision

1. **Each directory of the library is seeded when it holds no record of its own.**
   `seeded_library`'s three states — no mount, an empty mount, a mount with records —
   are read **per directory** rather than per mount: the top level is seeded when it
   holds no `*.toml`, and the elective subdirectory is seeded when *it* holds none.
   The two are independent because they are two libraries, loaded by two calls, and a
   single gate over the top level is what left the tier empty.

   This also repairs a volume that predates the tier, which is every volume in
   existence: it has top-level records, so the top level is left exactly as it is, and
   it has no subdirectory, so the tier's records land. Nothing is ever written over —
   the decay series a retirement is re-derived from is the one thing here that cannot
   be recomputed, and an accumulated elective directory is as untouchable as an
   accumulated top level.

2. **A directory is created only when there is something to put in it.** A deployment
   whose image ships no elective directory gets no empty one. An empty directory and
   a directory of records are the same answer to `load_library` and a different
   answer to a person reading the volume, and the second reader is the one who has to
   diagnose this class of fault.

3. **A requested elective family with no case is a sixth kind of nothing, and it is
   derived rather than supplied.** `TargetResult.requested_and_unanswered` is
   *requested* minus the two answers the tier has — a rate in `measured.elective`, a
   reason in `measured.elective_not_measurable` — and `payload.RequestedAndUnanswered`
   serialises it beside `not_requested` in the document's elective block. Derived, in
   the discipline `NotRequested.over` and `MeasuredSection.unfit_to_report` already
   follow: a document that had to be *told* which requests went unanswered is one
   where forgetting prints nothing, and forgetting is precisely how this defect lived.

4. **The sentence names the library and not the target.** *Not measurable* sends an
   operator to look at their own agent, and there is nothing there to find: the same
   request against a library that holds the tier's cases would have been attempted. So
   the line says the case library the run was made against holds none for this family,
   that this is not a rate of zero and not a reading about the target, and that the
   library's version is in the provenance block — which is what lets a reader say
   *which* library this was true of.

5. **The live run screen reads the tier in a second list, and draws it only when it
   was asked for.** `RunProgress` gains `elective_families`, an
   `ElectiveFamilyRun` list keyed on `ElectiveFamily` — a second model and not
   `FamilyRun`, so the two lists have nowhere to meet and no row of one can arrive
   where the other's arithmetic is (ADR-0035 §2, ADR-0088 §2). The screen draws them
   under two headings of their own, and `RunPlan` carries the selection the plan was
   built from, so a requested family the library holds no case in gets a row rather
   than being inferred out of existence by the cases that survived.

   **Rows for the requested families only**, which is where this parts from the six.
   Six rows are drawn whether or not a family has started, because one of the six
   missing while the run is on another reads as a family this run is not doing; an
   elective family nobody asked for is not part of the run at all, and three lines of
   *not asked for* under a person's own bars say nothing about where their run has got
   to. The document is what has to account for every family, and it does — decisions 3
   and 4. A block drawn only when there is something in it is the same rule the run
   screen already applies to its transport outcome and its episode.

   `no_case` carries the reason on the row, in a second wording: decision 4's sentence
   points a recipient at the provenance block, and a person watching their own run has
   no document in front of them yet.

6. **The artefact version does not move.** This is a key added beside existing keys,
   carrying no figure and nothing for a verifier to re-derive — the case ADR-0044 §8
   and ADR-0070 both declined to move the version for, and not the case ADR-0088 §7
   moved it for, which was a change in *what the measured section is keyed on*. A
   version-1-shaped verifier reading a version-2 document re-derives every figure it
   knows about and misses nothing here, because there is no arithmetic in this block.

## Considered options

**Copying the library as a tree.** Rejected: `seeded_library` copies file by file so
that what lands is case records and nothing else — no lease left by a previous run, no
document, nothing this bench did not write. A tree copy would seed whatever the image
happened to hold beside the records, and the reason for the file-by-file loop is
exactly that.

**Seeding both directories only when the whole mount is empty.** Rejected on decision
1, and it is the shape that would have looked like the smaller change. Every existing
volume has top-level records, so the tier would stay empty on precisely the
deployments that already ran — the ones where an operator has requested the tier and
got silence.

**Refusing the request instead: a `422` when a requested elective family has no case
in the library.** Rejected, and it was tempting because it makes the state
unreachable. But the run is not the wrong thing to do — the six are still measured, and
the artefact is still evidence about the target — and a bench that refused would take
the whole reading away over a gap in its own library. It also puts the refusal at the
route, where the library the run will actually be planned against is not yet known to
be short. Stating it keeps the run and names the gap.

**Reusing `NotMeasurable` with a new member.** Rejected on decision 4. That
enumeration is *why this target could not answer* — a precondition this bench checked
against this endpoint. A family with no case is unanswered against every target in the
world, and filing it there would tell every recipient that their agent was the reason.

**Reusing `DeclaredGap`.** Rejected for the mirror reason: a declared gap is something
only the caller knows — no adjudicator, an unplanted note, a family switched off
(ADR-0075). Here the caller asked *for* the family. Nothing was declared away.

**Drawing three *not asked for* rows on the run screen, as the report draws them.**
Rejected on decision 5. The two surfaces answer two questions: the document accounts
for every family the bench holds, because a recipient cannot ask it anything; the live
screen says where *this* run has got to, and a family nobody requested has nowhere to
have got to.

**Printing nothing when the list is empty.** Rejected on the rule every absence on
this page already follows: a reader who cannot tell *every request was attempted* from
*this document predates the check* is the reader the empty answers exist for. The
block prints its own empty sentence.

## Consequences

- A deployed bench can measure the elective tier for the first time. On a volume that
  already holds the six's library, the tier's records land at the next boot without
  touching anything the volume has accumulated.
- The document gains one key inside its `elective` block and one list in section 4.
  The golden rendering digest moves — `test_rendering.GOLDEN_ONE_FAMILY`, its
  nineteenth move, with the reason written beside it — and the artefact version does
  not.
- A run that asks for a family whose cases the library does not hold now says so in
  the signed artefact, so this class of defect cannot recur silently: the next
  incomplete library announces itself in the report rather than in an operator's
  screenshot.
- The run screen answers for the tier while the run goes: two more columns under the
  six, drawn only for a run that asked. `GET /runs/{id}` gains one key, defaulted to
  an empty list, so a caller reading a run made before the tier could be requested
  gets the same answer as one that requested nothing — which is the same answer.
- `RunPlan` gains the selection it was planned from. It is the declared input the plan
  is a consequence of, and carrying it there is what lets a *requested and unplanned*
  family be named at all: the cases that survived cannot say which families were asked
  for, only which were attemptable.
