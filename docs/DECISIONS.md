# DECISIONS

Append-only. Newest at the bottom. Never edit or delete an entry — supersede it with a new one.

Every entry carries four fields. The fourth is the one that gets skipped and the one that
matters most nine months from now.

**Format:** `## ADR-NNN — title` / **Date** / **Decision** / **Rationale** / **Cost to reverse**

---

## ADR-001 — One monorepo, not four

**Date:** 2026-08-31 · **Decided by:** PM (Software Charter §03)

**Decision.** `github.com/mmsanders/Digital-Tape` holds everything including hardware.

**Rationale.** The engine and its three consumers change together constantly in the early
phases. Separate repos would buy independent versioning nobody needs at the cost of version
skew nobody wants. Atomic cross-cutting commits are worth more than clean module boundaries
in the URL.

**Cost to reverse.** Moderate and rising. Splitting later means untangling shared CI, the FFI
build, and cross-references in `spec/`. Cheap through Phase 1; expensive once firmware and
host both consume the engine in anger.

---

## ADR-002 — Repository is public

**Date:** 2026-08-31 · **Decided by:** PM (Software Charter §03), verified by Software Lead

**Decision.** The repo is public. `docs/STATUS.md` is readable from
`raw.githubusercontent.com` without authentication.

**Rationale.** There is no first-party GitHub connector on the PM's account, so the PM cannot
authenticate into a private repo. Public means live project state at the start of every PM
session — no relaying, no stale summaries, no Michael pasting digests by hand. There is
nothing in a family cassette player worth keeping secret.

**Cost to reverse.** Low technically (flip the setting), but forks and clones taken while
public cannot be recalled. Decide before there is anything sensitive; there is no plan for
there ever to be.

---

## ADR-003 — Verification is a peer role, not a report

**Date:** 2026-08-31 · **Decided by:** PM (Software Charter §01)

**Decision.** The Verification Lead owns `tests/` outright and reports to the PM, not to the
Software Lead.

**Rationale.** The crash-injection harness exists to prove that a child yanking a cartridge
mid-write cannot destroy the music they love. If the agent whose code is under test also
manages the agent writing the tests, that harness will quietly get weaker every time it is
inconvenient.

**Cost to reverse.** Low to reverse, high to undo the consequences. Collapsing the roles saves
one session per cycle and forfeits the one guarantee this project cannot compromise on. The
damage would not be visible until a cartridge is corrupted in the field.

---

## ADR-004 — Code-defined CAD, not GUI CAD

**Date:** 2026-08-31 · **Decided by:** PM (Software Charter §08)

**Decision.** Enclosure, button mechanism and cartridge shell in CadQuery or OpenSCAD; boards
in KiCad. Everything hardware is text and therefore source.

**Rationale.** An agent can iterate, diff, parameterise and regenerate a family of variants
from one changed number. "Print six variants of the latch bar with hook depths from 0.8 to
1.8 mm" is a for-loop, not six modelling sessions — Michael carries one plate to the library
and comes back with the answer instead of one data point. Michael does not model, so a GUI
tool's cost buys nothing.

**Cost to reverse.** High after the first enclosure spin. Parametric intent does not survive
export to a GUI tool; the sweep capability is lost outright.
