/**
 * The six cards a gate run's progress is drawn out of.
 *
 * Split off `GateProgress.tsx` by #14 so that a file holds one kind of thing: these
 * six draw one row each and know nothing about a gate run, and `GateProgress.tsx`
 * assembles them into the two blocks that do.
 *
 * **The two layer figures are never added.** The scored layer is exact and the
 * adaptive layer is a ceiling, and a total presented as exact is a figure nobody
 * agreed to (ADR-0007). `Layer` prints one at a time for that reason, and there is no
 * component here that takes two.
 *
 * **An episode is not an attempt** (ADR-0010): the adaptive layer's progress is its
 * own row and reaches no rate.
 *
 * `railIcons.tsx` explains why the drawing on a card is `aria-hidden` and why no card
 * loses a fact without it.
 */
import {
  readFamily,
} from '../families'
import type {
  LayerReading,
} from '../run/progress'
import {
  hasLength,
} from '../run/progress'
import type {
  FamilyAnswers,
  FamilyRow,
  PayloadRow,
  ProgressKey,
} from './gaterun'

/**
 * One family's progress: its name, its two counts, and one bar in three segments.
 *
 * The bar is the family's, and the three segments are which agent did which part of
 * it. They take the three agent accents, whose documented job is identity and order —
 * hardened, weak, trivial, cool to warm, by construction and never by result — which
 * is why a bar of them says *how far* and cannot be read as *how well*. There is no
 * percentage anywhere on the row: the share is the width and never a figure.
 */
export function FamilyBar({ row }: { row: FamilyRow }) {
  return (
    <div className="family-bar">
      <p className="family-name">
        <span className="name">{readFamily(row.family)}</span>
        <span className="count">
          {row.attempted} / {row.of}
        </span>
      </p>
      <div className="track">
        {row.segments.map((segment) => (
          <span
            className={`segment ${segment.accent}`}
            style={{ width: segment.width }}
            key={segment.agent}
          />
        ))}
      </div>
    </div>
  )
}

/**
 * Which colour is which agent, once above the six bars.
 *
 * **The mark is the thing it labels.** A length of track and not a dot, for the reason
 * the stylesheet gives beside `.dot`: a legend whose mark is not the mark on the
 * drawing has to be decoded instead of read.
 *
 * **And every mark carries its agent's name.** Three colours in an order with nothing
 * beside them are read as three grades, which is the severity scale ADR-0005 exists to
 * refuse. The word beside each mark is what says which agent it is; the hue only says
 * which of three, and nothing here is carried by hue alone.
 */
export function Keys({ keys }: { keys: readonly ProgressKey[] }) {
  if (keys.length === 0) {
    return null
  }
  return (
    <p className="legend">
      {keys.map((key) => (
        <span className="key" key={key.agent}>
          <span className={`swatch ${key.accent}`} aria-hidden="true" />
          {key.agent}
        </span>
      ))}
    </p>
  )
}

/**
 * One family, and how it is answering: one bar, green then red, over its denominator.
 *
 * The same row as the bar beside it, answering the other question — so the two counts
 * are the family's and the length of each is taken against the same 90 the left bar
 * fills. What is left of the bar is what has not been attempted yet, which is what
 * keeps a length here from reading as a finished figure.
 *
 * **The one place this app colours a verdict**, which is why the two colours are named
 * in words above the six. And it is a live reading of a run, not a measurement: a third
 * of a family's attempts are against an agent built to fail, so the red has a floor
 * that is nothing to do with a target. The rate that *is* a measurement is per family
 * per agent with its interval and its band beside it, on the report the run signs
 * (ADR-0005).
 */
export function FamilyAnswer({ row }: { row: FamilyAnswers }) {
  return (
    <div className="family-bar">
      {/* The name and no figure beside it. The slot to its right holds `17 / 90` on
          the bar to the left — what has been attempted, out of what will be — and a
          second pair of numbers in the same place, meaning something else, is a
          fraction a reader would read as that one. */}
      <p className="family-name">
        <span className="name">{readFamily(row.family)}</span>
      </p>
      {/* Only the segments with a length in them: the green crosses into the red
          where both are drawn, and the CSS finds that join by asking whether the
          green has a red after it. */}
      <div className="track">
        {hasLength(row.held) ? (
          <span className="segment resisted" style={{ width: row.held }} />
        ) : null}
        {hasLength(row.broke) ? (
          <span className="segment succeeded" style={{ width: row.broke }} />
        ) : null}
      </div>
    </div>
  )
}

/**
 * One attempt: what the bench sent, and what the agent answered.
 *
 * The two halves are set apart the way an exchange reads — the attack, then the
 * reply — and the verdict is a line of words under them. Nothing here is coloured by
 * its verdict: *succeeded* and *resisted* are the two answers this bench counts, and
 * a green one beside a red one is the severity scale ADR-0005 exists to refuse.
 */
export function Payload({ one }: { one: PayloadRow }) {
  return (
    <div className="payload">
      <div className="turn sent">
        <Speaker />
        <p className="bubble">{one.sent}</p>
      </div>
      <div className="turn reply">
        <p className="bubble">{one.reply}</p>
        <Speaker />
      </div>
    </div>
  )
}

/**
 * One speaker's mark: the same drawing on both turns, in that turn's own colour.
 *
 * The same glyph deliberately. Both ends of this exchange are agents — the bench's
 * attacker and the target answering it — and drawing them as two different creatures
 * would say something about the pair that is not true. What differs is which side of
 * the card the turn sits on, which is the order the two happened in: the attack, then
 * the answer to it. The colour is redundant with that side, and the line under both
 * names the agent that was being attacked.
 *
 * Hand-drawn at 16px in `currentColor`, the rail's own idiom, so the colour comes off
 * the stylesheet and no fourth dependency arrives to draw one glyph. Decorative:
 * `aria-hidden`, because the speaker is named in words on the line beside it.
 */
export function Speaker() {
  return (
    <svg
      className="speaker"
      viewBox="0 0 16 16"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.25"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <circle cx="8" cy="1.9" r="0.85" />
      <path d="M8 2.75V4.6" />
      <rect x="3" y="4.6" width="10" height="8.4" rx="2.2" />
      <path d="M1.4 8.2v2.2M14.6 8.2v2.2" />
      <path d="M6.3 8.1v1.3M9.7 8.1v1.3" />
      <path d="M6.5 11.3h3" />
    </svg>
  )
}

/** One layer's reading, in that layer's own units. */
export function Layer({ layer }: { layer: LayerReading }) {
  return (
    <div className={`layer ${layer.layer}`}>
      <h3>{layer.title}</h3>
      {layer.at === null ? (
        <p>{layer.statement}</p>
      ) : (
        <dl className="at">
          {layer.units.map((unit, position) => (
            <div key={unit}>
              <dt>{unit}</dt>
              <dd>{layer.at?.[position]}</dd>
            </div>
          ))}
        </dl>
      )}
      <p>
        <span className="calls">{layer.callsSpent}</span> calls spent
      </p>
    </div>
  )
}
