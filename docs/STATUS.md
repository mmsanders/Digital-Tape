# STATUS

**Updated:** 2026-08-31 · **Phase:** 0 (format freeze) · **Updated by:** Software Lead

---

## What changed since last time

First entry. Two of the charter's first five actions are done.

**WP-01 — repository scaffolded** per Charter §03: directory tree, `CLAUDE.md` carrying the
twelve guardrails verbatim, and the four `docs/` files. Each stream directory carries its own
README with packages, dependencies, done-when, and rejected-on-sight list, so a sub-agent
dropped into one subtree can state the constraints without reading the whole repo.

**WP-04 — CI stood up on the empty engine.** Five gates, all failing, which is the acceptance
criterion. Build at `-Werror`; allocation audit by undefined-symbol reference; recursion audit
by call-graph cycle detection over the archive; static RAM budget against 200 KB; golden-suite
runner. `./tools/ci/all.sh` runs everything locally exactly as CI runs it.

Each audit was verified against deliberately violating code, not just against emptiness —
a gate that only fails on an empty repo proves nothing. Two real defects were found and fixed
in the process: unrelocated external calls in an unlinked archive read as self-recursion, and
tail-call recursion compiles to `jmp` and bypassed the call-graph walk entirely.

Nothing in `engine/` is implemented.

## In flight

| Work | Owner | State |
|---|---|---|
| WP-01 repo scaffold | Software Lead | **Done**, pending PM review |
| WP-02 `spec/tapefs-v1.md` | Software Lead | **Blocked** — see below |
| WP-03 `spec/engine-api.md` | Software Lead | **Blocked** — see below |
| WP-04 CI on empty engine | Software Lead | **Done** — 5/5 gates red, as specified |

## Blocked

**WP-02 and WP-03 are blocked on the plan document (Rev B).** The charter directs both specs
to be written "to byte-exact detail" and notes that *the plan document has the numbers*. That
document has not reached this repo. The charter's guardrails constrain the design heavily but
do not supply region sizes, chunk map entry layout, preroll cache size, or the per-call memory
budget. Writing those numbers by inference and freezing them at the Phase 0 gate is the single
most expensive mistake available right now, so this is a hard stop rather than a best guess.

**Requested from the PM:** Plan Rev B, or the subset covering WP-02/WP-03 numbers.

**One spec question is already open** and does not need the plan document to answer: does the
200 KB static budget in guardrail 08 mean `.data + .bss` (RAM), or total static footprint
including `.rodata`? CI currently enforces the former. See DECISIONS.md ADR-006 — it is
trivial to change today and expensive once the engine is written against the looser reading.

## Acceptance criteria flipped to passing

None. No Verification Lead is assigned yet, so nothing can be independently signed off —
including WP-01 and WP-04 above, which are the Software Lead's own claims about its own work.

## What will hurt in three weeks

- **No Verification Lead.** Charter §01 makes this a peer role reporting to the PM, and §09
  action 04 wants CI failing on an empty engine *before* implementation. Both need that agent
  to exist. Every day Stream 1 starts before Stream 2 does is a day the golden fixtures get
  written by someone who has already seen the implementation.
- **The format freeze is the long pole.** Action 05 is the only item in the first five that
  waits on Michael, and everything downstream of `spec/` waits on it.
- **CI is red on purpose and will stay red for weeks.** That is WP-04's acceptance criterion,
  but a permanently-red pipeline stops being read. The risk is that the first genuine failure
  arrives and nobody notices, because red is the background. Worth revisiting once WP-06 lands
  and the build gate can go green independently of the fixtures.
