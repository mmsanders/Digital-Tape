# STATUS

**Updated:** 2026-08-31 · **Phase:** 0 (format freeze) · **Updated by:** Software Lead

---

## What changed since last time

First entry. Repository scaffolded per Charter §03: directory tree, `CLAUDE.md` carrying the
twelve guardrails verbatim, and the four `docs/` files. Nothing is implemented.

## In flight

| Work | Owner | State |
|---|---|---|
| WP-01 repo scaffold | Software Lead | **Done**, pending PM review |
| WP-02 `spec/tapefs-v1.md` | Software Lead | **Blocked** — see below |
| WP-03 `spec/engine-api.md` | Software Lead | **Blocked** — see below |
| WP-04 CI on empty engine | Software Lead | Not started; follows WP-03 |

## Blocked

**WP-02 and WP-03 are blocked on the plan document (Rev B).** The charter directs both specs
to be written "to byte-exact detail" and notes that *the plan document has the numbers*. That
document has not reached this repo. The charter's guardrails constrain the design heavily but
do not supply region sizes, chunk map entry layout, preroll cache size, or the per-call memory
budget. Writing those numbers by inference and freezing them at the Phase 0 gate is the single
most expensive mistake available right now, so this is a hard stop rather than a best guess.

**Requested from the PM:** Plan Rev B, or the subset covering WP-02/WP-03 numbers.

## Acceptance criteria flipped to passing

None. No Verification Lead is assigned yet; nothing can be independently signed off.

## What will hurt in three weeks

- **No Verification Lead.** Charter §01 makes this a peer role reporting to the PM, and §09
  action 04 wants CI failing on an empty engine *before* implementation. Both need that agent
  to exist. Every day Stream 1 starts before Stream 2 does is a day the golden fixtures get
  written by someone who has already seen the implementation.
- **The format freeze is the long pole.** Action 05 is the only item in the first five that
  waits on Michael, and everything downstream of `spec/` waits on it.
