/**
 * The bench's HTTP surface as this app is allowed to see it.
 *
 * One module per API area since #14 — `nonces`, `runs`, `attempts`, `report`,
 * `gateruns`, `pendingroutes`, `settings`, `artefacts`, over the shared `contracts`
 * and the two
 * fetch primitives in `http` — and this file is the surface they are read through.
 * Every screen imports `../api/bench`, and the split deliberately did not move that:
 * an area module is where a wire shape is *defined*, and this is where the app is
 * allowed to see it.
 *
 * **The field names are the backend's own, `snake_case` and all**, because the
 * request body is a contract with `backend/api/app.py` rather than a shape this app
 * is free to choose. A camel-cased mirror would be one rename away from posting a
 * body the API refuses, and the refusal would arrive as a `422` nobody could read.
 * That rule survives the split unchanged and `contracts.ts` says it again, because
 * the contracts module is where a new wire shape now gets written.
 *
 * **Nothing here throws for a refusal.** A registration the bench refuses is a step
 * the operator has to complete rather than an error the app fell over on (ADR-0007
 * calls it the authorisation guard for exactly that reason), so `startRun` returns
 * one of three outcomes and every one of them carries the sentence the bench wrote.
 * What *is* thrown is a fetch that never reached the bench at all — see
 * `unreachable` in `runs.ts`.
 *
 * `http.ts` is not re-exported here. Its two functions are how the area modules talk
 * to the bench, not something a screen may reach for: a screen that fetched a path
 * of its own would be a route this file does not list.
 */

export * from './contracts'
export * from './nonces'
export * from './ruleOfTwo'
export * from './runs'
export * from './attempts'
export * from './report'
export * from './gateruns'
export * from './pendingroutes'
export * from './settings'
export * from './artefacts'
