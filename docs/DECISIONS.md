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


---

## ADR-009 — Verification Lead is ChatGPT, with no repository access

**Date:** 2026-08-31 · **Decided by:** PM (Software Charter, revision of 31 Aug)

**Decision.** Stream 2 moves from a Claude Code instance to ChatGPT. Its scope gains adversarial
spec review. It has no repository access: it receives `spec/` as text and returns findings and
test source, which the Software Lead lands and runs. Three seam rules govern the exchange —
recorded verbatim in `CLAUDE.md` §2.

**Rationale (the PM's).** An independent verifier is worth most when it does not share the
implementer's priors. A verifier built on the same model as the implementer will tend to find the
same things obvious, and the things it finds obvious are exactly the things nobody checks.

**Cost to reverse.** Low as a swap, high in what it would quietly undo. Moving Stream 2 back to a
Claude instance would restore repository access and remove the relay described below — a real
convenience — while giving up the shared-priors argument that is the entire reason for the
change. The tell that it has been reversed in spirit rather than by decision would be tests that
stop surprising anyone.

**Consequence not yet resolved.** The charter does not say who carries text across the seam. That
is the highest-frequency interaction in the project and it now has a human-shaped gap in the
middle of it. Raised in `docs/REVIEW/software-lead.md` §3.1.

---

## ADR-010 — Spec authorship is the PM's; the Software Lead lands text mechanically

**Date:** 2026-09-01 · **Decided by:** PM (Decisions 001 §0)

**Decision.** The charter contradicted itself — §1 made `spec/` PM-owned, §9 told the Software
Lead to author WP-02 and WP-03. Settled: the PM authors, the Software Lead lands the text
mechanically and does not edit it. WP-02 and WP-03 close as PM-delivered.

**Rationale.** A spec authored by the implementer bends toward the implementation, and three
streams read it as truth. The same argument that makes the Verification Lead a different model.

**Cost to reverse.** Low mechanically, high in what it protects. The tell that it has been
reversed in practice rather than by decision is spec text that starts matching the code's
convenience — which is invisible until a stream implements against it and is surprised.

---

## ADR-011 — Two static budgets, both asserted

**Date:** 2026-09-01 · **Decided by:** PM (Decisions 001 §1), from issue #2

**Decision.** RAM 200 KiB (`.data` + `.bss` + the engine instance) and flash 32 KiB (`.rodata`).
Both printed on every CI run.

**Rationale.** My recommendation was "A now, C later", on the grounds that the flash number was
a guess until there was a board. The PM's counter is correct: the RT1062 carries external QSPI
flash in megabytes, and 32 KiB is generous for a CRC table (1 KiB, now measured at exactly that),
a fade curve and resampling coefficients combined. A generous ceiling that exists beats a precise
one that doesn't — and it closes the risk I raised myself, that a large constant table sails
through a RAM-only gate.

**Cost to reverse.** Trivial as numbers. Expensive as a habit: `.rodata` approaching 32 KiB is an
escalation, not a reason to raise the ceiling.

---

## ADR-012 — The on-card preroll region is deleted

**Date:** 2026-09-01 · **Decided by:** PM (Decisions 001 §2), from issue #3

**Decision.** The 512 KiB on-card preroll region is removed from the format, `preroll_frames`
leaves the superblock, and `tape_mount` gains an optional warm-start buffer — in practice the
caller's play ring.

**Rationale.** My analysis stopped one step early. I argued the buffer should be caller-owned;
the PM observed the on-card region cannot do its job at all. It lives on the cartridge, so it
cannot be read until the card is initialised — and card initialisation is precisely the
100–500 ms it existed to hide. Once the card is up, an ordinary indexed read is just as fast.

Instant-on comes from two places instead, neither a format feature: retaining the play ring
across sleep, and starting card init on the cartridge-detect switch rather than the play press,
so human hand-travel time hides the latency. Both are firmware behaviours.

**Cost to reverse.** Reinstating a region in a frozen format is a format revision. But the
region bought nothing, so there is nothing to reinstate it for.

---

## ADR-013 — An index entry describes a run, not a chunk

**Date:** 2026-09-01 · **Decided by:** PM (Decisions 001 §3), from issue #4

**Decision.** `entry := { first_chunk_id, start_frame, frame_count }` over *consecutive* chunk
ids, with `frame_count` allowed to exceed `CHUNK_FRAMES`.

**Rationale.** I offered "refuse the splice" or "grow the slot", and objected to growing the slot
myself because it moves the wall rather than removing it. The PM took neither and changed what an
entry means. A pristine 90-minute tape was burning 1,817 entries before a child had done
anything; it is now **one**. Headroom goes from 1.5× to roughly 4,000 splices after a re-spool,
and re-spool becomes genuinely restorative — which finally gives it a user-facing purpose instead
of being invisible housekeeping.

Critically, **the commit path does not change**. My objection to coalescing — that the commit
path is where "clever" is a liability and must stay simple enough to reason about under crash
injection — is respected completely. The only new arithmetic is that the allocator hands out
contiguous runs (natural for a bump allocator) and a mid-run splice splits an entry in two.

**Cost to reverse.** High after the freeze — it is the index format. Cheap now, and it removes a
wall rather than moving it.

---

## ADR-014 — Decidable CI gates replace disassembly parsing

**Date:** 2026-09-01 · **Decided by:** PM (Decisions 001 §4), from issues #11 and #12

**Decision.** Guardrail 09 is enforced by funnelling every indirect call through three
`static inline` wrappers in `engine/src/dev.h`, gated at the source, with a link-time backstop
against function addresses in data sections. Guardrail 08's recursion clause is replaced by a
max stack depth of **8 KiB**, measured from `-fstack-usage` and `-fcallgraph-info`.

**Rationale.** The invariant I wrote ("at most two indirect call sites") was not the invariant I
wanted (*every indirect call targets a `tape_dev` callback*), and no regex over disassembly can
decide the second. Likewise "no recursion" is a proxy for a bounded stack; measuring depth
directly subsumes it and yields a number worth reading in review.

`dev_write` asserts its function pointer is non-`NULL` in debug builds via `__builtin_trap` —
not `assert()`, which reaches libc file I/O that guardrail 08 forbids. In release it dereferences
and dies. Guardrail 06 wants a loud crash; a `NULL` check returning an error code quietly would
defeat it.

**Cost to reverse.** Low. But the gates are leaned on for nine months, and the source-level check
fails with a filename and a line number rather than a hex offset — which is the difference
between a gate people fix and a gate people disable.

---

## ADR-015 — Ports are outside the engine and outside its gates

**Date:** 2026-09-02 · **Decided by:** Software Lead

**Decision.** `engine/src` builds `libtape.a`, subject to every gate. `engine/port` builds
`libtape_port.a`, subject to none of them.

**Rationale.** The file-backed port is libc file I/O by definition, which guardrail 08 forbids
*in the engine*. That is not a conflict — it is the block-device boundary doing its job, and the
engine never learns a file exists. Keeping them in one archive would force a choice between a
gate that lies and a port that cannot exist.

**Cost to reverse.** Low now, and it gets harder to introduce later once the ports have grown.
The rule to keep: if a gate ever runs over the port archive and fails, the fix is the gate.
