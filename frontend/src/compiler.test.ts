/**
 * That the React Compiler is compiling this app, and not merely switched on.
 *
 * `vite.config.ts` says `compiler: true`, and that sentence is worth nothing on its
 * own. The compiler decides per function whether it can compile at all, and where it
 * cannot it **skips that function and emits a note** — the build stays green, the
 * bundle stays correct, and the optimisation silently is not there. Enabling it and
 * never looking is the failure mode where a switch is flipped and nothing happens.
 *
 * So this reads the compiler itself. `oxc-transform-react` is the same transform
 * `@vitejs/plugin-react` runs in the build — the Rust port, not the Babel plugin;
 * this plugin version carries no `babel` option — and it is called here with the
 * same `reactCompiler` configuration the build gives it, which is the default one.
 * Every `.tsx` this app ships goes through it and two things are asserted:
 *
 * - **the plugin would hand the file over.** The plugin skips a file whose text
 *   contains no component-shaped or hook-shaped name at all, before the compiler ever
 *   sees it, so a file that fails that filter is not compiled no matter how healthy it
 *   is. The filter is the plugin's own private constant, so it is **read back out of
 *   the plugin's shipped source** rather than copied: a copy would go stale in the
 *   direction that matters, staying green while a filter that had grown stricter
 *   quietly skipped files.
 * - **the compiler compiled it, and said nothing.** Compiled means the output reaches
 *   the memoisation cache in `react/compiler-runtime`: no cache, no compilation. Said
 *   nothing means no diagnostic at all — a diagnostic here is a skipped function, and
 *   the last one on this app skipped the whole of `RegisterScreen` over a `finally`
 *   clause four lines long.
 *
 * The roster is globbed rather than listed, so a screen added next year is covered by
 * this test on the day it lands rather than on the day somebody remembers.
 *
 * **Two of the three seams here are contracts and one is codegen.** `TransformResult`
 * — `fatal`, `errors`, and the `react/compiler-runtime` entry point — is published API
 * and will not move under a patch. The shape the compiler *emits* for a stable value,
 * asserted in the second block below, is not: it is the compiler's own output, and a
 * version of it that keys or hoists differently would fail these three tests without
 * anything about this app having changed. That is why `oxc-transform-react` is pinned
 * to an exact version in `package.json`. If these three fail and nothing here moved,
 * read the pin before reading the screens.
 *
 * **`main.tsx` is the one file with nothing in it to compile**, and it is asserted in
 * that direction so that the sweep above cannot pass by exempting files. It mounts the
 * router and declares no component and no hook, so there is nothing to memoise. This
 * much is a house rule rather than anything the compiler requires: a cache appearing
 * there means the file has grown a component, and the answer is to move that component
 * into a screen. If it ever genuinely belongs here, move the file into
 * `NOTHING_TO_COMPILE`'s place deliberately — that is the point of the failure.
 */

import { transformSync } from 'oxc-transform-react'
import { describe, expect, it } from 'vitest'

import plugin from '../node_modules/@vitejs/plugin-react/dist/index.js?raw'
import config from '../vite.config.ts?raw'

/**
 * The text filter `@vitejs/plugin-react` applies before it calls the compiler, lifted
 * out of the plugin's own shipped source. A file whose source does not match is never
 * offered to the compiler at all.
 *
 * Read rather than copied, and read by matching the declaration rather than by
 * importing it, because the plugin does not export it. Both halves fail loudly: a
 * plugin that renames or reshapes the constant fails `theFilter` below, and a plugin
 * that changes what the constant *says* changes what this test enforces, which is the
 * whole point.
 */
function theFilter(): RegExp {
  const declared = /const defaultCodeFilter = \/(.*)\/([a-z]*);/.exec(plugin)
  if (declared === null) {
    throw new Error('@vitejs/plugin-react no longer declares `defaultCodeFilter`')
  }
  // Rebuilt from the body and the flags rather than evaluated: a test that runs a
  // string out of `node_modules` as code is a worse thing than the drift it guards.
  const [, body, flags] = declared
  return new RegExp(body as string, flags)
}

/** The import the compiler adds to a file it compiled, and adds to nothing else. */
const CACHE = 'react/compiler-runtime'

/** The one file with nothing in it to compile. */
const NOTHING_TO_COMPILE = 'main.tsx'

const sources = import.meta.glob<string>('./**/*.tsx', {
  query: '?raw',
  import: 'default',
  eager: true,
})

/**
 * The hooks, which are `.ts` because they hold no JSX, read separately from the sweep.
 *
 * The sweep above is over `.tsx` on purpose: it asserts that every file this app
 * *renders* is compiled, and `NOTHING_TO_COMPILE` below is what stops it passing by
 * exemption. A glob over `.ts` as well would pull in every pure-logic module in the
 * app, none of which has anything to compile, and that assertion would have to go.
 *
 * But a hook is exactly where a memoisation lives, so the roster further down has to
 * be able to reach one. #14 moved `readTheBench` out of `GateScreen.tsx` and into
 * `useGateRun.ts`, and this is how the roster still finds it. Named rather than
 * globbed, so a hook added without a memoisation to assert is not silently swept in.
 */
const hooks = import.meta.glob<string>('./**/use*.ts', {
  query: '?raw',
  import: 'default',
  eager: true,
})

/**
 * What the compiler made of one file: its diagnostics, whether it cached anything, and
 * the code it emitted.
 *
 * The one place in this file that names the compiler's configuration, so that every
 * assertion below is about the same compiler the build runs. `reactCompiler: {}` is
 * what `@vitejs/plugin-react` passes for `compiler: true` — the default options.
 */
function compile(path: string, source: string) {
  const result = transformSync(path, source, { lang: 'tsx', reactCompiler: {} })
  return {
    fatal: result.fatal,
    said: result.errors.map((error) => `${path}: ${error.message}`),
    cached: result.code.includes(CACHE),
    code: result.code,
  }
}

describe('the React Compiler', () => {
  it('is enabled in the build this test compiles for', () => {
    // Asserted against the config's own text: this whole file is a statement about
    // the build, and it would be a statement about nothing if the build had the
    // compiler off. The option is the plugin's own, which is why there is no
    // `babel-plugin-react-compiler` to look for here.
    expect(config).toContain('react({ compiler: true })')
  })

  it('is given every .tsx this app ships', () => {
    const offered = theFilter()
    // The app is eleven `.tsx` files as this is written. Asserted as a floor rather
    // than a count, because a screen arriving should not fail this — but a glob that
    // matched nothing would let every assertion below pass by vacuum, and a glob that
    // had quietly stopped seeing most of the app would too.
    expect(Object.keys(sources).length).toBeGreaterThanOrEqual(11)
    for (const [path, source] of Object.entries(sources)) {
      expect(offered.test(source), `${path} is filtered out before the compiler`).toBe(
        true,
      )
    }
    // The negative half. Without it the assertion above passes for any filter loose
    // enough, including one that matches everything, and it would then be saying
    // nothing at all.
    expect(offered.test('export const bit = <p>a</p>\n')).toBe(false)
  })

  it('compiles every one of them, and reports nothing about any of them', () => {
    const skipped: string[] = []
    const said: string[] = []
    for (const [path, source] of Object.entries(sources)) {
      if (path.endsWith(NOTHING_TO_COMPILE)) {
        continue
      }
      const outcome = compile(path, source)
      said.push(...outcome.said)
      if (outcome.fatal || !outcome.cached) {
        skipped.push(path)
      }
    }
    // Both listed rather than counted: the point of a failure here is which file.
    expect(said).toEqual([])
    expect(skipped).toEqual([])
  })

  it('finds nothing to compile in the file that mounts the app', () => {
    const source = sources[`./${NOTHING_TO_COMPILE}`]
    expect(source).toBeDefined()
    expect(compile(NOTHING_TO_COMPILE, source as string).cached).toBe(false)
  })
})

describe('the three memoisations the screens keep', () => {
  /**
   * Each of the three is named in a `useEffect` dependency array or handed down as a
   * prop, and in two of the three the effect starts a two-second poll against a
   * running bench. What is asserted is the consequence — that the identity is stable
   * across a render — and the compiler has two ways of delivering it:
   *
   * - **keyed.** The value sits in a cache slot and every consumer compares against
   *   it (`$[n] !== read`), so the effect re-runs when it changes and at no other
   *   time. This is what happens where the value closes over something.
   * - **hoisted.** Where the value closes over nothing at all, the compiler lifts the
   *   function out of the component to module scope, which is stability by
   *   construction rather than by cache.
   *
   * **Each site declares which one it gets, and gets asserted on that one.** The
   * reason is that each call site's comment makes the specific claim, and a test that
   * accepted either would let a site quietly change shape and leave its comment
   * describing a screen that no longer exists. A screen the compiler skipped delivers
   * neither shape, which is the other way this fails.
   */
  const kept: readonly {
    path: string
    held: string
    shape: 'keyed' | 'hoisted'
    what: string
  }[] = [
    {
      path: './run/RunScreen.tsx',
      held: 'read',
      shape: 'keyed',
      what: 'the run progress poll',
    },
    {
      path: './console/useGateRun.ts',
      held: 'readTheBench',
      shape: 'hoisted',
      what: 'the gate run poll',
    },
    {
      path: './register/RegisterScreen.tsx',
      held: 'declare',
      shape: 'keyed',
      what: "the registration form's steps",
    },
  ]

  // Matched to a word boundary in both shapes. A substring match would accept
  // `!== readNow` as evidence about `read`, which is the one rename these tests exist
  // to notice — and it did, until it was driven red.
  const shapes = {
    keyed: (held: string) => new RegExp(`!== ${held}\\b`),
    hoisted: (held: string) => new RegExp(`const ${held} = _temp\\b`),
  } as const

  for (const { path, held, shape, what } of kept) {
    it(`holds ${what} ${shape} on \`${held}\``, () => {
      const source = sources[path] ?? hooks[path]
      expect(source).toBeDefined()
      const compiled = compile(path, source as string)
      expect(compiled.said).toEqual([])
      expect(
        shapes[shape](held).test(compiled.code),
        `${held} is not ${shape} in the compiler's output`,
      ).toBe(true)
    })
  }
})
