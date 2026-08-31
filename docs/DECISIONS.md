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

---

## ADR-005 — CI tooling lives in `tools/`, outside the Charter §03 tree

**Date:** 2026-08-31 · **Decided by:** Software Lead · **Flagged for PM review**

**Decision.** Gate scripts live in `tools/ci/`, with `.github/workflows/ci.yml` as a thin
caller. Charter §03 does not name either directory.

**Rationale.** Charter §09 action 04 requires CI, and it has to live somewhere. Putting the gates in
`tools/ci/` rather than inside the workflow means every gate runs locally exactly as it runs
in CI, so "works on my machine" and "works in CI" are the same claim. Putting them under
`engine/` would have been wrong — the golden-suite gate spans `tests/`, which belongs to the
Verification Lead.

This is the reversible path taken under the "never block a whole stream waiting on an answer"
rule. The PM may rename or relocate it.

**Cost to reverse.** Trivial now — a `git mv` and one path in the workflow. Rises once the
Hardware Lead adds KiCad ERC/DRC gates alongside these, which the charter anticipates.

---

## ADR-006 — Memory budget counts `.data + .bss`, not `.rodata`

**Date:** 2026-08-31 · **Decided by:** Software Lead · **NEEDS PM CONFIRMATION at WP-03**

**Decision.** The 200 KB static budget in guardrail 08 is enforced against `.data + .bss`.
`.rodata` is reported but not counted.

**Rationale.** On the target, `.rodata` lives in flash and `.data`/`.bss` consume RAM, and RAM
is the scarce resource the guardrail exists to protect. The charter says "static budget under
200 KB" without splitting them, so this is an interpretation, not a reading.

**It may be the wrong one.** If the intent was total static footprint, the gate is currently
too permissive and a large constant table would sail through. `spec/engine-api.md` (WP-03)
must state which, in bytes, per subsystem. Raised as a `pm-decision` issue.

**Cost to reverse.** Trivial today — one line in `tools/ci/audit-memory.sh`. Expensive once
the engine is written against the looser reading, because tightening it later means finding
RAM that was already spent.

---

## ADR-007 — Plan Rev B adopted as the numeric input to WP-02 and WP-03

**Date:** 2026-08-31 · **Decided by:** PM (Plan Rev B), checked by Software Lead

**Decision.** The format and API numbers in Plan Rev B §04 and §05 are the input to
`spec/tapefs-v1.md` and `spec/engine-api.md`. Adopted as given:

| Quantity | Value |
|---|---|
| Audio | 44.1 kHz / 16-bit stereo PCM, 176,400 B/s |
| 90-minute cartridge | 952,560,000 B (~953 MB), 1,817 chunks |
| Chunk | 512 KiB = 2.9722 s |
| Superblock | 4 KiB × 2, both ends of the partition |
| Preroll cache | 512 KiB (~2.97 s) |
| Index slots | 32 KiB × 4 — two double-buffered per side |
| Index entry | `{chunk_id, start_offset, length}`, 12 B |
| Side A store | 952 MB, immutable, below high-water mark |
| Partitioning | MBR: small FAT32 (README + label art) + raw TAPEFS |

**Rationale.** The numbers reconcile exactly and independently. The plan states the Side B map
is "about 22 KB"; 1,817 entries × 12 B = 21,804 B = 21.3 KiB. That arithmetic was not given in
the plan — it confirms the 12-byte entry width rather than assuming it, which is why the entry
layout can be specified byte-exact rather than guessed.

Checked and consistent: byte rate, tape size, chunk duration, chunk count, copy rate
(952.56 MB / 30 s = 31.8 MB/s), preroll duration.

**Two things the plan does not resolve.** Both raised rather than assumed — issues #3 and #4.
Neither blocks WP-02.

**Cost to reverse.** Rises sharply at the format freeze. Before the gate, changing a number is
an edit to one document. After it, it is a reflash of every cartridge ever written. Region
sizes will be parameterised from superblock fields specifically so that tape length can change
without a re-spec — see the open 90-minute question.

---

## ADR-008 — Region sizes are derived from superblock parameters, not hard-coded

**Date:** 2026-08-31 · **Decided by:** Software Lead

**Decision.** `spec/tapefs-v1.md` will state region *offsets and sizes as fields in the
superblock*, computed at format time from a stored tape length, rather than fixing 952 MB and
1,817 chunks as constants in the format.

**Rationale.** Plan §13 ask #02 puts the 90-vs-60-minute question to Michael and it is still
open. 60 minutes changes the Side A store from 952 MB to 635 MB. The plan already lists "format
params" and "region offsets" among the superblock's contents, so this is reading the plan
rather than extending it — but making it explicit means the answer arriving late costs a
format-time constant, not a spec revision and three streams re-reading it.

It also makes the engine's mount path honest: it reads where the regions are instead of
assuming, which is the same code either way.

**Cost to reverse.** Low, and it buys optionality that is expensive to add later. The cost paid
is a handful of extra superblock fields and a mount path that computes instead of assumes —
both of which the engine needs regardless.
