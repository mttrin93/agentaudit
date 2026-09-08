/**
 * The console's front door: what this instrument is, and the three things it does.
 *
 * The root used to redirect to the registration form, which asked an engineer for
 * an endpoint before telling them what would be done to it. This screen says what
 * the bench is in one paragraph, offers the three errands the console exists for —
 * register a target, run the gate, check an artefact — and then lists what this
 * bench has already done.
 *
 * **The cards carry no figure, and none of them starts anything from here.** Each
 * is a name, what that screen does, and a link to it. A gate run attacks all three
 * reference agents, spends about 830 calls and writes back to the case library; it
 * is started on the gate screen, where the rule, the write-back and the two figures
 * are on the page beside it (ADR-0021). An operation with three attestation
 * statements and a spend in front of it does not belong on the screen somebody
 * lands on.
 *
 * **The bench's own gate citation is not on this screen any more, and this screen
 * reads no route for it.** It used to be here, drawn so that an absence was as
 * visible as a pass; it is on the gate screen, in that same idiom, beside the rule
 * it was decided under and the document it wrote. A citation read apart from its
 * rule is an outcome a reader cannot check, and the front door's answer about
 * validation is now that there is a gate and one link to it. The cost is real and
 * it is the one to watch: a bench that has never passed its gate no longer says so
 * on the screen an engineer lands on.
 *
 * **The runs on the record** are read from `GET /runs`, so that a run whose URL
 * nobody kept is still reachable. Each row carries calls spent in two columns — the
 * scored layer's and the adaptive layer's — set side by side in two hues and
 * **never added into a third figure**: the two are enforced against two separate
 * ceilings, and a single number would say what a run cost without saying which half
 * of it cost that (ADR-0007, ADR-0010). There is no totals row on this screen and
 * the view model has no field for one.
 *
 * **The last region is the nine families**, one to a row: what the failure *is*, the
 * agent doing the thing, then the OWASP entries it claims and the EU AI Act articles it
 * bears, with no figure anywhere in it. An operator meets `indirect prompt injection` on
 * four screens before anything on any of them says what one is, and this is where it is
 * said. The six and the elective three are one undifferentiated table
 * ([ADR-0091](../../../docs/adr/0091-the-console-draws-the-nine-families-as-one-list.md));
 * what stays split is the pair of arrays the switches write to.
 *
 * **Where the security questionnaire was.** That region answered a questionnaire out of
 * the most recent signed report — a family per question, its rate over that family's
 * own denominator, its interval and confidence — and it is the block this project
 * points at, against the displaced default of a questionnaire filled in from
 * recollection for a reader who cannot check a line of it (ADR-0001). It is off this
 * screen and not out of the bench: `questionnaire.ts` still builds it, its tests still
 * hold every claim in it, and a rate with its interval beside it is what the report
 * screen is for. This screen now reads exactly one route, `GET /runs`.
 *
 * The view models are `landing.ts` and `runs.ts`, and they are where the wording
 * lives; this file is markup and is driven by hand, as every screen in this app is.
 */

import { useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { readFamily, readName } from '../families'
import {
  benchArtefacts,
  benchRuns,
  benchSettings,
  coverFamilies,
  selectConstructions,
  type ArtefactList,
  type FamilyCovered,
  type RunList,
} from '../api/bench'
import {
  selectionReading,
  WHAT_THIS_CONSOLE_DOES,
  WHAT_THIS_INSTRUMENT_IS,
  type ConsoleDoes,
  type SelectionReading,
  familyRows,
} from './landing'
import {
  runsReading,
  type AdaptiveColumn,
  type RunsReading,
  type ScoredColumn,
} from './runs'
import { artefactsReading, type ArtefactsReading } from './artefacts'
import { useArrivalFocus, useScreenTitle } from './announce'
import { THE_BENCH } from './rail'

/** What the second region is holding: the runs, or why it could not read them. */
interface HeldRuns {
  list: RunList | null
  unavailable: string
}

const NO_LIST_YET: HeldRuns = { list: null, unavailable: '' }

/** What the artefacts region is holding: the list, or why it could not read it. */
interface HeldArtefacts {
  list: ArtefactList | null
  unavailable: string
}

const NO_ARTEFACTS_LIST_YET: HeldArtefacts = { list: null, unavailable: '' }

export function LandingScreen() {
  const [runs, setRuns] = useState<HeldRuns>(NO_LIST_YET)
  const [signed, setSigned] = useState<HeldArtefacts>(NO_ARTEFACTS_LIST_YET)
  /*
   * Which families the next run covers, on its own state like the two above.
   *
   * `null` until the bench answers, and the switches are drawn from the bench's answer
   * rather than from a local copy — so what a reader sees is what the next run will do
   * and not what this screen last sent. A refusal leaves the switches where they were
   * and says why: the bench refuses a change while a run is going, which is a state to
   * wait out rather than an error to work around.
   */
  const [families, setFamilies] = useState<FamilyCovered[] | null>(null)
  /*
   * The tier's switches, beside the six's state.
   *
   * Two pieces of state and one table: `familyRows` joins them for drawing, and the
   * screen shows no mark saying which row came from which
   * ([ADR-0091](../../../docs/adr/0091-the-console-draws-the-nine-families-as-one-list.md)).
   * They stay two here because `ElectiveFamily` is a closed set of its own, the route
   * answers with two arrays, and a moved switch has to be written back into the one it
   * came from (ADR-0015, ADR-0035).
   */
  const [elective, setElective] = useState<FamilyCovered[] | null>(null)
  const [refused, setRefused] = useState('')
  /*
   * What the next run sends, on its own state and its own refusal beside the families'.
   *
   * Two states rather than one, because they are two writes: a bench refusing to
   * narrow the constructions while a run is going has not refused to switch a family
   * off, and one alert standing for both would tell an operator that a change they did
   * not make was rejected.
   *
   * `null` until the bench answers, and the switches are drawn from its answer rather
   * than from a local copy — so what a reader sees is what the next run will send.
   */
  const [sends, setSends] = useState<SelectionReading | null>(null)
  const [refusedSelection, setRefusedSelection] = useState('')

  useEffect(() => {
    let current = true
    const read = async () => {
      try {
        const list = await benchRuns()
        if (current) {
          setRuns({ list, unavailable: '' })
        }
      } catch (unknown: unknown) {
        if (current) {
          setRuns({ list: null, unavailable: `${unknown}` })
        }
      }
    }
    void read()
    return () => {
      current = false
    }
  }, [])

  /*
   * The artefacts, on their own state and deliberately not on the runs' state.
   *
   * A list of runs an operator can navigate by is worth having whether or not the
   * artefacts could be read, and one failure state across the two would take the list
   * down with them — the same reason the questionnaire that used to be here held its
   * own.
   */
  useEffect(() => {
    let current = true
    const read = async () => {
      try {
        const list = await benchArtefacts()
        if (current) {
          setSigned({ list, unavailable: '' })
        }
      } catch (unknown: unknown) {
        if (current) {
          setSigned({ list: null, unavailable: `${unknown}` })
        }
      }
    }
    void read()
    return () => {
      current = false
    }
  }, [])

  useEffect(() => {
    let current = true
    const read = async () => {
      try {
        const bench = await benchSettings()
        if (current) {
          setFamilies(bench.tuning.families)
          setElective(bench.tuning.elective_families)
          setSends(selectionReading(bench.tuning))
        }
      } catch {
        // The switches simply do not draw. A families block that reported a failed
        // settings read would be this section explaining somebody else's problem.
        if (current) {
          setFamilies(null)
          setElective(null)
          setSends(null)
        }
      }
    }
    void read()
    return () => {
      current = false
    }
  }, [])

  /*
   * One switch moved, and both lists sent.
   *
   * The tier and the six are one statement about what the next run covers, so the
   * request carries both every time: a call that sent only the list the operator
   * touched would clear the other one, because this `PUT` is the whole statement
   * (ADR-0088 §8). Which list the switch was in decides which one is recomputed, and
   * the two arrays never merge — the six are the gate's denominator and the tier is a
   * second closed set (ADR-0015, ADR-0035).
   */
  const cover = async (family: string, on: boolean, tier: 'six' | 'elective') => {
    const held = (rows: FamilyCovered[] | null, mine: boolean) =>
      (rows ?? [])
        .filter((one) => (mine && one.family === family ? on : one.covered))
        .map((one) => one.family)
    setRefused('')
    try {
      const bench = await coverFamilies(
        held(families, tier === 'six'),
        held(elective, tier === 'elective'),
      )
      setFamilies(bench.tuning.families)
      setElective(bench.tuning.elective_families)
    } catch (refusal: unknown) {
      setRefused(`${refusal}`)
    }
  }

  /*
   * One switch moved, and both lists sent: the pair is one statement about what the
   * next run sends, and the answer is the whole reading back rather than an
   * acknowledgement.
   *
   * Two handlers rather than one taking *which kind of switch this was*: exactly one
   * of the two is ever the thing that moved, and a single function would say so with a
   * pair of nullable arguments only one of which is ever set. What they share is the
   * request and its refusal, which is `sent`.
   *
   * A selection under which nothing would be scored is refused by the bench rather
   * than widened here — a run that measures nothing still spends a registration probe
   * per target — so the switches stay where they were and the refusal says why.
   */
  const switches = sends?.layers ?? []
  const sent = async (
    layers: string[],
    transforms: string[],
    schedules: string[],
  ) => {
    setRefusedSelection('')
    try {
      const bench = await selectConstructions(layers, transforms, schedules)
      setSends(selectionReading(bench.tuning))
    } catch (refusal: unknown) {
      setRefusedSelection(`${refusal}`)
    }
  }

  /** Every schedule left where the operator put it, for the two writes that are not
      about them. Read off the switches rather than remembered, on `held`'s terms. */
  const scheduled = () =>
    switches
      .flatMap((one) => one.schedules)
      .filter((one) => one.selected)
      .map((one) => one.schedule)

  /** One layer switched, and every construction left where the operator put it. */
  const selectLayer = (layer: string, on: boolean) =>
    sent(
      switches
        .filter((one) => (one.layer === layer ? on : one.runs))
        .map((one) => one.layer),
      switches
        .flatMap((one) => one.constructions)
        .filter((one) => one.sent)
        .map((one) => one.transform),
      scheduled(),
    )

  /** One construction switched, and every layer left where the operator put it. */
  const selectConstruction = (transform: string, on: boolean) =>
    sent(
      switches.filter((one) => one.runs).map((one) => one.layer),
      switches
        .flatMap((one) => one.constructions)
        .filter((one) => (one.transform === transform ? on : one.sent))
        .map((one) => one.transform),
      scheduled(),
    )

  /**
   * One schedule switched, and everything else left where the operator put it.
   *
   * A third handler on the two above's reasoning — exactly one of the three switches
   * is ever the thing that moved — and the one whose answer is not a narrower run:
   * ticking the second schedule opens a second episode set per family, so the bench
   * answers with a doubled adaptive ceiling and the next run is priced against it. The
   * last schedule cannot be unticked: the bench refuses a layer running under none,
   * because that is what the layer's own switch says, and the refusal arrives in the
   * bench's own sentence above the boxes (ADR-0096).
   */
  const selectSchedule = (schedule: string, on: boolean) =>
    sent(
      switches.filter((one) => one.runs).map((one) => one.layer),
      switches
        .flatMap((one) => one.constructions)
        .filter((one) => one.sent)
        .map((one) => one.transform),
      switches
        .flatMap((one) => one.schedules)
        .filter((one) => (one.schedule === schedule ? on : one.selected))
        .map((one) => one.schedule),
    )

  useScreenTitle(THE_BENCH)
  const heading = useArrivalFocus(THE_BENCH)
  return (
    <main className="screen">
      <header>
        <h1 ref={heading} tabIndex={-1}>
          AgentAudit: an adversarial bench
        </h1>
      </header>

      <section>
        <h2>The instrument</h2>
        <p>{WHAT_THIS_INSTRUMENT_IS}</p>
      </section>

      <section>
        <h2>What this console does</h2>
        <div className="does">
          {WHAT_THIS_CONSOLE_DOES.map((card) => (
            <Card card={card} key={card.path} />
          ))}
        </div>
      </section>

      <section>
        {/*
          The heading and then the runs.

          Two paragraphs stood here. One said what the two columns are and why they are
          never added — which the rows say by being two columns with two headings and no
          third; the reason they are not added is `runs.ts`'s to hold, and it holds it
          where the columns are built. The other pointed at the signed artefacts screen,
          which is a row in the rail on the left of this page and a card two sections
          above it.
        */}
        <h2>Your runs</h2>

        {/* Polite, and so is the artefacts block below it: both are what this screen
            found when it read the record on arrival, and neither answers a press. The
            two blocks further down that look identical to these are assertive, because
            those two *are* answers to a tick (ADR-0080). */}
        {runs.unavailable ? (
          <div className="citation uncited" role="status">
            <h3>This bench did not answer for its runs</h3>
            <p>{runs.unavailable}</p>
            <p className="aside">
              Not the same fact as a bench with no runs on the record: what is
              unknown here is what it would have listed, so nothing below should be
              read as <em>none</em>.
            </p>
          </div>
        ) : runs.list === null ? (
          <p className="aside">Reading the runs on the record…</p>
        ) : (
          <Runs reading={runsReading(runs.list)} />
        )}
      </section>

      <section>
        {/*
          The artefacts, in the shape the runs above them are in.

          A summary and not the artefacts screen: the target, when the run went on the
          record, the one line naming how its three checks settled, and the two links a
          reader wants — the report a recipient may already hold, and the run it came
          from. The three results one by one, the two claims and the three files a
          verifier saves are on the signed artefacts screen, which is a rail row and a
          card at the top of this page.
        */}
        <h2>Your artefacts</h2>

        {signed.unavailable ? (
          <div className="citation uncited" role="status">
            <h3>This bench did not answer for its artefacts</h3>
            <p>{signed.unavailable}</p>
            <p className="aside">
              Not the same fact as a bench that has signed nothing: what is unknown
              here is what it would have listed, so nothing below should be read as{' '}
              <em>none</em>.
            </p>
          </div>
        ) : signed.list === null ? (
          <p className="aside">Reading the artefacts on the record…</p>
        ) : (
          <Artefacts reading={artefactsReading(signed.list)} />
        )}
      </section>

      {/*
        The nine families, one to a row, where the questionnaire region was.

        That region answered a questionnaire out of the most recent signed report — a
        family per question, its rate over its own denominator, its interval and its
        confidence — and it was the block this project points at. It is gone from this
        screen and not from the bench: `questionnaire.ts` still builds it and its tests
        still hold every claim about it, and the report screen is where a reader meets a
        rate with its interval beside it.

        What is here instead is what this page was missing: an operator meets
        `indirect prompt injection` on four screens before anything says what one is.
        Nine sentences, no figure in any of them, and the names read as words — and
        beside each, the published entries it claims and the articles it bears.
      */}
      {/* No form on this screen or the one below it, and that is the decision rather
          than the omission (#120). Every input here is a tick that writes on change:
          there is no text field for implicit submission to serve, and nothing is
          waiting to be sent, so a form would add a submit that submits what is
          already stored. The screens that got one are the ones with a field to
          finish — `RegisterScreen`, `SettingsScreen`, `GateAttestation`. */}
      <section>
        <h2>The families</h2>
        {/* Assertive (ADR-0080): an operator moved a family's switch and the bench
            would not move it. The switch has gone back to where it was, so this
            sentence is the only thing that says the press did nothing. */}
        {refused ? (
          <div className="citation uncited" role="alert">
            <h3>Nothing was changed</h3>
            <p>{refused}</p>
          </div>
        ) : null}
        {/*
          One family to a box, one box to a row.

          The boxes are the idiom every other block on this page is made of — paper, a
          hairline, the same radius — and they were two to a row before, which read as
          a grid of cards and buried the question the block exists to answer: which of
          these will the next run cover. One to a row answers it down a single column.

          Four things in each box: the switch with the family's name, what the failure
          is in a sentence, the OWASP entries it claims and the EU AI Act articles it
          bears. The labels sit in a footer rather than in columns of their own, so a
          box stays a box and the two published claims read as what they are — what
          this family is *read onto*, under the sentence saying what it is.

          **Nine boxes and not six and three.** The six and the elective tier are drawn
          in one list with nothing marking them apart
          ([ADR-0091](../../../docs/adr/0091-the-console-draws-the-nine-families-as-one-list.md)).
          What that decision moved is the presentation and nothing else: the two arrays
          are still two, `PUT /bench/settings/families` still takes them as one
          statement of two lists, the tier still defaults off and still decides no gate,
          and a family left unticked is still stated on the report as *not requested*
          rather than as a rate of zero (ADR-0015, ADR-0035, ADR-0088).

          No figure in any box. Not a rate, not an interval, not a band, not a `D`: an
          article number and an entry's edition year are the only digits here.
        */}
        <dl className="said families">
          {familyRows(families, elective).map((one) => (
            <div key={one.family}>
              <dt>
                {/*
                  The tick box first and the name after it, which is the order a reader
                  scans: the question this block answers is *which of these will run*,
                  and a control at the end of the line is one the eye finds last. A
                  checkbox, so a keyboard lands on it and a screen reader reads it as
                  what it is, with the family's own name as its label.

                  Switching one off is not measuring it at zero: the bench drops that
                  family's cases and its report states the family as *not run*. A
                  family that was not asked is not a family that held.
                */}
                <FamilyTick
                  rows={one.tier === 'six' ? families : elective}
                  family={one.family}
                  fallback={one.tier === 'six'}
                  unread={
                    // The settings could not be read, so the box draws the default the
                    // next run would use — filled for the six, empty for the three. It
                    // says *this switch is on* and never *this family is elective*:
                    // the two words the label used to differ by named the tier out
                    // loud, which is the one thing a row may not do (ADR-0091). The
                    // state still differs, because it differs — a family drawn ticked
                    // that the next run will not attack is a lie about the run, and
                    // the normal path shows the same difference just as plainly.
                    <span
                      className={one.tier === 'six' ? 'tick on' : 'tick'}
                      role="img"
                      aria-label={
                        one.tier === 'six' ? 'on by default' : 'off by default'
                      }
                    />
                  }
                  onMove={(on) => void cover(one.family, on, one.tier)}
                />
                {readFamily(one.family)}
              </dt>
              <dd>{one.says}</dd>
              {/*
                What the family is read onto, under what it is.

                Each list labelled, because `ASI01:2026` and `15` are not self-naming
                and a reader who has not met the agentic list needs the word. An empty
                list draws nothing at all — not a dash, which would read as *not looked
                up*: data leakage claims none of the agentic entries, and halt defeat
                and disclosure denial none of the LLM ones, and those are refusals
                `labels.py` argues for rather than gaps.
              */}
              <dd className="claims">
                {one.owasp.length > 0 ? (
                  <span>
                    <span className="of">OWASP</span>
                    {one.owasp.map((entry) => (
                      <code key={entry}>{entry}</code>
                    ))}
                  </span>
                ) : null}
                {one.articles.length > 0 ? (
                  <span>
                    <span className="of">EU AI Act</span>
                    {one.articles.map((article) => (
                      <code key={article}>{article}</code>
                    ))}
                  </span>
                ) : null}
              </dd>
            </div>
          ))}
        </dl>
      </section>

      {/*
        How a run attacks, under the families it attacks them about.

        The same switches in the same idiom, one level down: the families say *which
        failures are asked about* and these say *how they are attacked*. Three layers,
        and the constructions each one schedules nested under it, because the operator's
        question is answered by the layers — do I want the encodings, the ladders, or
        the agent — and the list inside is the finer grain.

        **One layer to a box, one box to a row**, which is the families block's own
        shape read one level down. Three boxes in an auto-fit grid came out as unequal
        columns — one tall with the encodings, one short with the ladders, one all but
        empty — and read as a set of cards rather than as the question the block asks:
        which of the three will the next run send. One to a row answers it down a
        single column, and the constructions wrap into as many columns as the box is
        wide instead of into one tall stack.

        The constructions sit in a footer under the layer's sentence, behind the word
        for what they are, exactly as a family's published claims do: a box holds one
        subject, and these are the finer grain of the switch above them rather than a
        second block.

        The adaptive layer holds no construction — what it would hold are the two loops
        the bench's closed set of constructions deliberately does not name — and it
        holds **its two schedules** instead, in the footer the constructions would have
        been in and behind the word for what they are. Both ticked is two episode sets
        per family rather than one wider search, which is why the sentence about what
        the tick costs is printed under them: the second schedule doubles the turns the
        next run may put on the operator's own endpoint, and that is a figure they
        confirm rather than discover (ADR-0057, ADR-0096). A layer whose footer holds
        neither says so rather than ending early.

        No figure in any of it. The two sentences the route serves beside these
        switches — what switching a construction off does, and what a run made now
        would carry into its provenance — are both written for a reader holding a
        document, and neither is printed here: what an operator on this screen is
        answering is which of the three the next run will send, and the boxes answer
        it. The artefact still states both, in the artefact.
      */}
      {sends === null ? null : (
        <section>
          <h2>How a run attacks</h2>
          {/* Assertive, on the same terms as the families block above (ADR-0080):
              this is the answer to a layer's own switch. */}
          {refusedSelection ? (
            <div className="citation uncited" role="alert">
              <h3>Nothing was changed</h3>
              <p>{refusedSelection}</p>
            </div>
          ) : null}
          <dl className="said layers">
            {sends.layers.map((layer) => (
              <div key={layer.layer}>
                <dt>
                  <input
                    className="tick"
                    type="checkbox"
                    checked={layer.runs}
                    aria-label={readName(layer.layer)}
                    onChange={(event) =>
                      void selectLayer(layer.layer, event.target.checked)
                    }
                  />
                  {readName(layer.layer)}
                </dt>
                <dd>{layer.sends}</dd>
                <dd className="sends">
                  {layer.constructions.length === 0 &&
                  layer.schedules.length === 0 ? (
                    <span className="none">
                      Nothing to choose inside this layer — the switch above is the
                      whole of it.
                    </span>
                  ) : null}
                  {layer.constructions.length === 0 ? null : (
                    <>
                      <span className="of">Constructions</span>
                      <ul className="sent">
                        {layer.constructions.map((one) => (
                          <li key={one.transform}>
                            <label>
                              <input
                                className="tick"
                                type="checkbox"
                                checked={one.sent}
                                onChange={(event) =>
                                  void selectConstruction(
                                    one.transform,
                                    event.target.checked,
                                  )
                                }
                              />
                              {readName(one.transform)}
                            </label>
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                  {/*
                    The adaptive layer's own two switches, in the footer its
                    constructions would have been in and behind the word for what they
                    are. Drawn wherever the wire says a schedule belongs, which is that
                    layer, so this markup names no layer.

                    **The one sentence this block prints**, and it is here rather than
                    under the heading because it is what *this* tick costs: both
                    schedules is a second episode set per family, so the layer's
                    ceiling doubles and the doubling reaches the figure the operator
                    confirms before a run starts. The two document sentences the route
                    serves are still not printed anywhere on this screen (ADR-0096).
                  */}
                  {layer.schedules.length === 0 ? null : (
                    <>
                      <span className="of">Schedules</span>
                      <ul className="sent">
                        {layer.schedules.map((one) => (
                          <li key={one.schedule}>
                            <label>
                              <input
                                className="tick"
                                type="checkbox"
                                checked={one.selected}
                                onChange={(event) =>
                                  void selectSchedule(
                                    one.schedule,
                                    event.target.checked,
                                  )
                                }
                              />
                              {readName(one.schedule)}
                            </label>
                          </li>
                        ))}
                      </ul>
                      <span className="aside">{sends.schedulesCost}</span>
                    </>
                  )}
                </dd>
              </div>
            ))}
          </dl>
        </section>
      )}
    </main>
  )
}

/**
 * The artefacts on the record, or the stated fact that there are none.
 *
 * One line per artefact: the name the operator gave the target, and the id they will
 * quote when they send it. These are the same runs the table above lists, seen from the
 * other end — one that finished and was signed — and the line is a link, so everything
 * else about an artefact is one click away rather than printed here.
 *
 * The name links to the report and there is no second link to the run. Both screens
 * are reachable from either, the run is named on the report, and a row with two links
 * makes a reader choose between them before they have read anything.
 *
 * The order is the route's, most recent first, and nothing is filtered: an artefact
 * whose signature did not verify is the one an engineer most needs to see, so it is on
 * the list. How it settled is not on the line — the three results are on the screen the
 * name links to, all three named, on every artefact.
 */
/**
 * One family's switch, for either of the two closed sets this screen offers.
 *
 * One control and two lists, which is the split ADR-0035 asks for read at the right
 * level: what may never be merged is the **arrays** — the six are the denominator the
 * gate is decided over and the tier is a second closed set — and a tick box is a tick
 * box. The caller says which array it is reading and what the switch means when it is
 * moved, and nothing here knows about either tier.
 *
 * `fallback` is what a family the bench did not name is drawn as, and it differs by
 * tier because the two defaults differ: every one of the six is covered unless it was
 * switched off, and no elective family is requested unless it was asked for.
 *
 * `unread` is what is drawn when the settings could not be read at all — a state
 * distinct from *off*, so it is a caller's node rather than a blank: the six draw the
 * switch they are on by default, and the tier draws the one it is off by default.
 */
function FamilyTick({
  rows,
  family,
  fallback,
  unread,
  onMove,
}: {
  rows: FamilyCovered[] | null
  family: string
  fallback: boolean
  unread: ReactNode
  onMove: (on: boolean) => void
}) {
  if (rows === null) {
    return unread
  }
  return (
    <input
      className="tick"
      type="checkbox"
      checked={rows.find((held) => held.family === family)?.covered ?? fallback}
      aria-label={readFamily(family)}
      onChange={(event) => onMove(event.target.checked)}
    />
  )
}

function Artefacts({ reading }: { reading: ArtefactsReading }) {
  if (!reading.listed) {
    return (
      <div className="citation uncited">
        <h3>No signed artefact on the record</h3>
      </div>
    )
  }
  return (
    <ol className="signed">
      {reading.artefacts.map((artefact) => (
        <li key={artefact.id}>
          <Link to={artefact.reportPath}>{artefact.target}</Link>
          {/*
            No word for how it settled, on any line.

            A word here was one outcome out of three, on the lines that did not verify,
            with nothing said on the ones that did — a reader had to know that silence
            meant *verified* to read the list at all, which is an inference off a screen
            and not off a check. The three results are named individually on the
            artefact's own screen, verified ones included (ADR-0017), and that screen is
            one click along the name at the head of this line. `settledInAWord` is still
            built and still tested; no screen prints it.
          */}
          <code>{artefact.id}</code>
        </li>
      ))}
    </ol>
  )
}

/**
 * The runs on the record, or the stated fact that there are none.
 *
 * A table now, where this was a list of blocks. The list was chosen so that there
 * would be nowhere to put a total — a table of two numeric columns has a foot, and a
 * foot is where somebody adds an adaptive figure to a scored one against two ceilings
 * that are enforced separately (ADR-0007, ADR-0010). The invariant did not move to the
 * layout: it is carried by the two column *types*, which cannot be handed to one
 * another and so cannot be reduced, and by `runs.ts` adding, averaging and counting
 * nothing. What this markup owes that decision is one thing — **there is no `tfoot`
 * here, and a row of sums is not a row this component knows how to draw.**
 *
 * No caption under the rows. The record's sentence about the two columns — they are
 * not added, there is no total, no average and no figure spanning two runs — is four
 * clauses saying what the screen already shows by having two headed columns and no
 * third. `RunsReading.statement` is still built and still tested.
 *
 * **A zero keeps its meaning from the standing beside it.** The per-layer sentences —
 * *nothing: this layer put no call on the operator's endpoint* — do not fit a cell, and
 * the standing column is what now distinguishes a run nobody answered from a cheap one:
 * `Unanswered`, `Declined` and `Failed` say why a row spent nothing. The sentences are
 * still built and still tested in `runs.ts`; nothing on this screen prints them, and
 * the run's own screen says the same thing in its own words off `progress.ts`.
 */
function Runs({ reading }: { reading: RunsReading }) {
  // With no runs, the heading and nothing under it — and no head of a table drawn over
  // nothing. It carried the record's own sentence — nothing registered in this process,
  // a fact about the bench and not about any target, register one and it appears here —
  // which is three clauses under a heading that says the whole of it.
  // `RunsReading.statement` is still built and still tested.
  if (!reading.listed) {
    return (
      <div className="citation uncited">
        <h3>No runs on the record</h3>
      </div>
    )
  }
  return (
    <div className="ledger-wrap">
      <table className="ledger">
        <thead>
          <tr>
            <th scope="col">Target</th>
            <th scope="col">Standing</th>
            <th scope="col">Recorded</th>
            {/*
              The two spend columns are headed in the two accents, and the words say
              which layer each is: colour carries identity here and never a judgement,
              and it is redundant with the heading so nothing is read off hue alone.
            */}
            <th scope="col" className="calls-cell scored">
              Scored calls
            </th>
            <th scope="col" className="calls-cell adaptive">
              Adaptive calls
            </th>
          </tr>
        </thead>
        <tbody>
          {reading.runs.map((run) => (
            <tr key={run.id}>
              {/*
                The target is the row's header and the link back to the run: an operator
                who did not keep the URL finds it here, under the name they gave the
                endpoint and never the endpoint.
              */}
              <th scope="row">
                <Link to={run.path}>{run.target}</Link>
              </th>
              <td>{run.standing}</td>
              {/*
                A date and a clock time in UTC, with the zone written out — read in the
                reader's locale it would name a different instant from the one the bench
                quotes back. `runs.recordedIn` is where the digits are chosen.
              */}
              <td className="recorded">{run.recordedAt}</td>
              <Calls column={run.scored} />
              <Calls column={run.adaptive} />
            </tr>
          ))}
        </tbody>
        {/* No `tfoot`. See the note above this component: that absence is the point. */}
      </table>
    </div>
  )
}

/**
 * One layer's calls, in its own hue, right-aligned against the next row's.
 *
 * The union rather than one shared column type, so that this component is the only
 * place in the app that has seen both — and all it does with them is draw them apart.
 * The accent is a class name and the colour is the stylesheet's, and the column it sits
 * under names the layer in words, so the distinction survives a reader who cannot see
 * the two hues apart.
 */
function Calls({ column }: { column: ScoredColumn | AdaptiveColumn }) {
  return <td className={`calls-cell ${column.accent}`}>{column.calls}</td>
}

/**
 * One errand, with the control that starts it.
 *
 * A `Link` and not a `button`, styled as the control it is: it navigates, and a
 * button that navigates is a control a keyboard and a screen reader are told the
 * wrong thing about.
 *
 * All three take the same treatment. The filled one used to be the lead card's alone,
 * which left the other two outlined in the same hairline every block on the page is
 * edged with — three doors, one of them drawn as a door. `lead` still says which errand
 * comes first, and the order of the cards is where a reader sees it.
 */
function Card({ card }: { card: ConsoleDoes }) {
  return (
    <div className="card">
      <h3>{card.name}</h3>
      <p>{card.does}</p>
      <Link className="act" to={card.path}>
        {card.act}
      </Link>
    </div>
  )
}
