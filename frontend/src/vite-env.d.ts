/// <reference types="vite/client" />

/**
 * The one variable this app reads out of its build environment, declared.
 *
 * Optional, because a clone with no issuer account is a supported reading and
 * `console/door.ts` says what it means. Declared here rather than left to the
 * fallback index signature so that it is one name with one type — and so that
 * `import.meta.env` answers `string | undefined` rather than `any` where it is read.
 * It is inlined at build time and not read at run time, which
 * [the spec](../../docs/specs/the-authenticated-operator.md) and
 * `frontend/.env.example` both say the consequence of.
 */
interface ImportMetaEnv {
  readonly VITE_CLERK_PUBLISHABLE_KEY?: string
}
