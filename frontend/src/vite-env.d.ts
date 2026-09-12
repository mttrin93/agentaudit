/// <reference types="vite/client" />

/**
 * The one variable this app reads out of its build environment, declared.
 *
 * **It is inlined at build time and not read at run time.** Vite substitutes the
 * literal into the bundle, so setting it on a server after a deploy does nothing at
 * all: the build is the moment it is decided, and a deployment whose console has no
 * sign-in is a deployment that was built without it.
 *
 * Optional, because a clone with no issuer account is a supported reading and
 * `console/door.ts` says what it means. Declared here rather than left to the
 * fallback index signature so that it is one name with one type — and so that
 * `import.meta.env` answers `string | undefined` rather than `any` where it is read.
 */
interface ImportMetaEnv {
  readonly VITE_CLERK_PUBLISHABLE_KEY?: string
}
