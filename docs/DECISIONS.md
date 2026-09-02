# DECISIONS

Append-only. Newest at the bottom. Never edit or delete an entry — supersede it with a new one.

Every entry carries four fields. The fourth is the one that gets skipped and the one that
matters most nine months from now.

**Format:** `## ADR-NNN — title` / **Date** / **Decision** / **Rationale** / **Cost to reverse**

**Numbering.** `ADR-0xx` is the shared sequence. **`ADR-1xx` is reserved for Hardware Lead
decisions.** Two leads appending numbers to one append-only file pick the same number and only
find out at merge — which already happened once: the Hardware Lead's first four decisions were
`ADR-010`–`013`, and so are four of the Software Lead's. A separate range removes the class of
problem rather than the instance. This is the reversible path taken under Charter §05; the PM
may collapse it back with one `sed`, and the Verification Lead should claim a range too.

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

---

## ADR-016 — The golden comparison has no tolerance, and none will be added

**Date:** 2026-09-02 · **Decided by:** Software Lead

**Decision.** `golden_diff` compares reference and actual WAVs byte for byte. No epsilon, no
per-case tolerance, no configuration knob for one.

**Rationale.** Contract 3 makes the golden fixtures the *definition* of correct behaviour and
requires firmware to be bit-identical at 1.0× playback. A tolerance would permit exactly the
divergence the suite exists to detect — a desktop/firmware mismatch would sit inside the
allowance and never fail. The moment a tolerance exists, the pressure on a hard failure is to
widen it rather than to find the bug, and `tests/` §6 already says relaxing a test is a finding
rather than a licence.

Failures instead get **information**: an audible difference WAV (silence where the outputs agree,
so you hear only what went wrong), the first differing frame with timestamp and channel, both
sample values and their delta, how many samples differ, and the peak absolute delta. That
distinguishes a click at a splice from an inverted channel from a one-frame offset — which is
what a person actually needs, and which a tolerance would have hidden rather than explained.

**Cost to reverse.** Adding a tolerance later is one parameter and would quietly void contract 3.
That asymmetry is the reason to refuse it now: the change is cheap and the loss is invisible.

---

## ADR-017 — WAV fixtures outside 44.1 kHz / 16-bit / stereo are rejected, not converted

**Date:** 2026-09-02 · **Decided by:** Software Lead

**Decision.** The fixture reader errors on any other rate, width or channel count.

**Rationale.** Guardrail 01 fixes the format and says every other design decision rests on byte
offset mapping linearly to time. A reader that resampled a 48 kHz fixture would make a
guardrail-01 violation pass its own test — the most expensive kind of convenience, because the
suite would then be certifying the thing it was built to prevent.

**Cost to reverse.** Trivial technically. The rule to keep is that a rejected fixture is a
question about the fixture, never a request for a converter.

---

## ADR-018 — C-60 is the standard cartridge

**Date:** 2026-09-02 · **Decided by:** Michael (Q-002), specified by PM (Decisions 003, tapefs §2)

**Decision.** `nominal_length_s` = 3600. 635 MB, 1 211 chunks, ~29 s copy on plain high-speed
4-bit. C-90 and C-120 are permitted by the format and copy more slowly; the label says what a
cartridge is.

**Rationale.** The 30-second copy no longer requires UHS-I at all. That removes the hardest
electrical risk on the board — 1.8 V switching, the voltage-switch sequence, tuned delay
lines — from the critical path for the headline requirement, and demotes SDR50 from
"must work" to optional upside.

**Cost to reverse.** A format-time constant, not a re-spec — which is exactly what ADR-008 was
for. Region sizes derive from `nominal_length_s` at format time, so changing the standard length
costs nothing already written.

---

## ADR-019 — Resume position is device-side, `(uuid, side)` → frames

**Date:** 2026-09-02 · **Decided by:** Michael (Q-004)

**Decision.** The player remembers the last 64 cartridges, keyed `(cartridge_uuid, side)`,
position in frames as u32. Checkpoint every 10 s and on every transport state change; resume
2 s early. LRU eviction. Promote clears `(uuid, A)`; reset B clears `(uuid, B)`.

**Rationale.** Forced: the source slot is read-only, so a cartridge played there has no writable
surface. Michael accepted the consequence explicitly — a tape resumes where *this player* left
it, not where the tape was last played — as a deliberate departure from the cassette metaphor
rather than a side effect.

Frames rather than bytes was the round-1 packet's recommendation, adopted: a `u32` of frames
has 12× headroom against the longest reachable timeline, where bytes would have had 3.0×.

**Cost to reverse.** Low while it is 64 entries in flash. It becomes expensive only if a second
consumer of the UUID appears, which `tapefs` §11 forbids by naming the position table as its
sole sanctioned consumer.

---

## ADR-020 — The record light shows Side B headroom

**Date:** 2026-09-02 · **Decided by:** Michael (Q-003)

**Decision.** Colour from `tape_status().entries_free` as a fraction of `TAPE_MAX_ENTRIES`:
green ≥ 25 % free, yellow < 25 %, red at 0. At red the record button does not hold — the
solenoid releases it. Off while not armed.

**Rationale.** My recommendation was the button refusing to hold, reusing an interlock the child
already knows. Michael took that and added warning before the wall, which is better: a rule you
meet without warning is a rule you experience as the device breaking. With run-length entries
(ADR-013) a child will realistically never reach red.

**Cost to reverse.** Low. `entries_free` is already in `tape_status`, and the thresholds are
firmware constants.

---

## ADR-021 — `spec/` has two tiers

**Date:** 2026-09-02 · **Decided by:** PM (Decisions 003)

**Decision.** `spec/` is PM-owned and frozen. `spec/hw/` is Hardware-Lead-owned and versioned,
with notification-not-approval on `board-rev-a.md`.

**Rationale.** The single-tier rule made every measurement a PM escalation, which would have
made the thermal budget stale by design — it has to track reality as boards are measured.

**Cost to reverse.** Low, but the tiers must stay legible: a document that moves tiers silently
is worse than either arrangement, because a reader cannot tell whose sign-off it carries.

---

## ADR-022 — Structural Rule 1: implementation waits on `main` for its tests

**Date:** 2026-09-02 · **Decided by:** PM (Decisions 003 §1b), proposed by Software Lead

**Decision.** Engine implementation stays on unmerged branches until the Verification Lead's
tests for that behaviour have landed on `main`, so `main` carries spec → tests → implementation
in that order.

**Rationale.** Rule 1 as originally written was discipline, and the charter's own reasoning
(guardrails 05 and 06) says discipline is the weak form. The PM's honest caveat is worth keeping
attached: branches on a public repo are still world-readable, so this makes the ordering
**auditable**, not the code unreadable. Combined with the verifier's standing instruction not to
open `engine/`, that is enough.

**Cost to reverse.** Low mechanically. What it would cost is the evidence: once implementation
merges ahead of tests, no later inspection can tell whether a test was written against the spec
or against the code.

---

## ADR-023 — Ports return their own codes, not `tape_result`

**Date:** 2026-09-02 · **Decided by:** Software Lead

**Decision.** Block-device callbacks return 0 on success and non-zero on failure, using
port-local codes in `engine/port/port.h`. They do not return `tape_result`.

**Rationale.** `spec/engine-api.md` §3 says exactly this, and the engine maps any non-zero to
`TAPE_ERR_IO`. My provisional header had ports returning engine error codes and had invented
`TAPE_ERR_RANGE` and `TAPE_ERR_NOT_IMPLEMENTED`, neither of which exists in DRAFT-3's enum.
Landing DRAFT-3 exposed both, which is the spec-upstream-of-code contract working.

**Cost to reverse.** Trivial now. The rule worth keeping: a port that needs a new *engine* error
code is a spec finding, not a header edit.

---

## ADR-024 — The engine holds no static buffers; all RAM is in the caller's instance

**Date:** 2026-09-02 · **Decided by:** Software Lead

**Decision.** No `static` mutable storage in `engine/src`. Index staging and the candidate index
live in `struct tape`, sized by `tape_instance_size()`.

**Rationale.** Found by the memory gate once it began counting `tape_instance_size()` per
`engine-api` §4: `.bss` was 98 KB of `static` buffers in the mount path. They were not
allocation, so they passed every other gate — but they are engine-owned RAM outside the caller's
instance, and worse, **they break reentrancy**. `tape_dup(src, dst)` mounts two cartridges at
once and would have had them overwrite each other's index.

That bug would not have appeared until duplicate was implemented, and it would have looked like
media corruption rather than a shared buffer.

**Cost to reverse.** Low now, and the gate keeps it reversed: RAM went from 197 KB (96 % of
budget, with the dominant term uncounted) to 148 KB (72 %), all of it in the instance.

---

## ADR-025 — One fault injector, and it is the Verification Lead's

**Date:** 2026-09-02 · **Decided by:** PM (Decisions 004 §4), from issue #16

**Decision.** `engine/port/dev_sim.c` loses its power-loss and torn-write modes and becomes a
pass-through that counts operations. All fault injection is
`tests/crash/fault_block_device.[ch]`, which models flush-required and write-through durability
as selectable modes.

**Rationale — and it generalises, which is why it is written at length.**

This is not a preference between two implementations. One of them is **structurally incapable of
detecting a whole class of bug.**

`tapefs` §8's entire safety argument is an *ordering over flushes* — chunks, flush, entries,
flush, header, flush — and §13 lists "a flush that returns success means data has reached media"
as an **assumption**, not a fact. A simulator in which every completed write is durable cannot
fail any test that depends on a flush having actually happened. It would report the commit
ordering as safe whether or not it was.

The proof is already on the record: the verifier found exactly that defect in DRAFT-1 by
reading — V-004, a commit protocol with no final flush. My simulator could never have caught it,
however many cases were run through it. Keeping both would have meant half the crash coverage
running against a model that cannot fail.

**The transferable rule:** a test double that can only produce outcomes the code already handles
is not coverage, it is decoration. Before adding a second convenient simulator, ask which class
of failure it is incapable of producing.

**Cost to reverse.** Low to re-add modes; high in what it would quietly cost. The tell that this
has been reversed in spirit is a crash suite that runs green faster than it used to.

---

## ADR-026 — Every gate must be proven able to go red

**Date:** 2026-09-02 · **Decided by:** PM (Decisions 004 §6), from the `.bss` finding

**Decision.** `tools/ci/verify-gates.sh` plants a real violation for each guardrail gate, asserts
it goes red, removes it, and asserts it goes green. It runs in CI. Adding a gate means adding its
red case.

**Rationale.** The allocation gate ran green for two rounds while 98 KB of `static` buffers sat
in `.bss`. It was asking *"is anything malloc'd?"* when guardrail 08's intent is *"does the
engine's RAM fit, and is it all in the caller's instance?"* Nothing was malloc'd. The gate was
simultaneously correct and useless, and nothing in a green run could have told anyone.

**A gate that measures the wrong quantity reads as green.** The remedy is not "write better
gates" — it is that a gate never observed failing has not been tested, and green from an
untested gate is indistinguishable from green from a broken one.

Verified: 11/11, including the `.bss` case that motivated it.

**Cost to reverse.** Trivial to delete, and its absence is invisible — which is the argument for
keeping it. The failure mode it prevents produced a reentrancy bug that would have surfaced as
media corruption months later.

## ADR-101 — Solenoid protection bounds duty cycle, not only pulse width

**Date:** 2026-09-02 · **Decided by:** Hardware Lead (Charter §05 — decide and log)

**Decision.** The solenoid gate carries three hardware protections, not one: a
non-retriggerable one-shot (`74HC221` class) capping on-time at 50 ms, an RC lockout enforcing
a minimum off-time, and a PPTC on the solenoid rail (hold ≈ 100 mA) as an average-current
backstop. Plus a flyback diode per coil and a gate pull-down.

**Rationale.** The Hardware Charter specifies a hardware one-shot and is right that it is not
a firmware responsibility. But a one-shot bounds how long a *single* assertion lasts and says
nothing about how often assertions may occur. Firmware stuck in a retrigger loop at 100 Hz
delivers a 50 ms pulse every 10 ms; the coil sees essentially its full 9 W continuously and the
one-shot fires correctly throughout. **The exact failure the charter describes — a stuck
firmware state cooking a coil built for 30 ms pulses — is reachable through a working
one-shot.** The PPTC closes that hole physically: no sequence of edges can defeat it, because
sustained conduction opens the circuit.

Cost over the charter's single one-shot: about fifteen cents.

**Cost to reverse.** Trivial before layout, expensive after. These are three small parts and a
rail; adding them post-layout means finding board area next to a switching node. Removing them
later is a schematic edit — but doing so re-opens a failure mode whose consequence is a burnt
part inside a sealed enclosure in a child's hands.

---

## ADR-102 — Charging is suspended for the duration of a copy

**Date:** 2026-09-02 · **Decided by:** Hardware Lead

**Decision.** The charger is inhibited while a copy is in progress, via a control line the
charger already has.

**Rationale.** `spec/hw/thermal-budget.md` §3 shows the copy is thermally free — 30 seconds
against a 621-second enclosure time constant raises the bulk temperature about half a kelvin.
The sustained case that governs is playback while charging, and at 35 °C ambient that lands
within 0.2 K of the 45 °C JEITA charge ceiling. Removing the highest-power mode from the
sustained set costs one control line and is imperceptible: nobody notices 30 seconds missing
from a 90-minute charge.

This is the cheapest thermal margin in the design, and it is available only because the copy is
required to be fast — guardrail 10 buys a thermal result as a side effect.

**Cost to reverse.** Near zero. One line in firmware and one net. Worth reversing only if
measurement shows the margin is larger than estimated, which WP-37 will say.

---

## ADR-103 — The bench build validates function, not copy time

**Date:** 2026-09-02 · **Decided by:** Hardware Lead

**Decision.** Card sustained-write characterisation runs on a PC with a rated reader, not on
the Teensy bench build. The bench build owns hot-swap detect, the LED row, the button matrix,
the interlock and the solenoid one-shot — everything in WP-18 and WP-20 except the throughput
number.

**Rationale.** The Teensy 4.1 has one 4-bit SDIO port. A second card hangs off SPI at roughly
10–20 MB/s, so a bench copy of a 90-minute cartridge takes 60–95 s regardless of how good the
cards are. That is a property of the bench platform, not a finding about the design, and a
criterion the platform cannot meet is a criterion that will be quietly relaxed.

Running the characterisation on a PC is also simply better: it is available the day the cards
arrive rather than after WP-17, and it removes our own untested driver from the measurement.

**Cost to reverse.** None — this is a routing decision about where a measurement happens.
The consequence to watch is WP-18's acceptance criteria, which currently read as though the
bench proves the copy time. Raised for the PM in `docs/REVIEW/hardware-lead.md`.

---

## ADR-104 — Print sweeps carry hidden controls and blind labels

**Date:** 2026-09-02 · **Decided by:** Hardware Lead

**Decision.** Every print-run packet embosses labels unrelated to the swept parameter, and
includes duplicate copies of one variant at spread bed positions, ranked blind alongside the
real variants. The mapping lives in the repository, never on the card.

**Rationale.** Two failure modes, both invisible without this. If the labels encode the
parameter, the ranker ranks by expectation rather than by feel — and Michael is the instrument,
so biasing him corrupts the only measurement we have. And a 0.3 mm step in hook depth is within
range of the variation a printer produces across its own bed, so without duplicates a scatter
is indistinguishable from a signal. The duplicates test the print and the ranker with the same
parts and no extra trip.

The counter-intuitive payoff: when the controls scatter, the correct next sweep is **coarser**,
not finer. Without controls the instinct after an inconclusive plate is to refine, which walks
further into the noise and costs another week.

**Cost to reverse.** Zero — it is a convention in `build_packet.py`, about twenty lines.
Abandoning it costs the ability to tell a result from noise, which is the whole reason the
library loop exists.

---

## ADR-105 — The cartridge's microSD is captive

**Date:** 2026-09-02 · **Decided by:** PM (Decisions 001 §2), raised by Hardware Lead (issue #6)

**Decision.** The microSD inside a cartridge is captive. `tapectl` and the GUI reach the card
**through the player over USB-C** — the production board exposes the device itself as the
cartridge. Removing the card is not a workflow the design supports.

Serviceable, **not** tool-free: an adult with a driver may open the shell to replace a failed
card. A curious six-year-old with a fingernail may not. **Where those two requirements fight,
the six-year-old wins.**

**Rationale.** A loose microSD in a child's hands is a lost microSD, and a shell that opens
becomes a container for something else and then a shell with nothing in it. The cartridge exists
so the storage is an object you can hold, label and pass around — it is the object, not a costume
around a memory card. It also settles the shell design in the direction the vision already
points, and removes an ESD path a child can touch.

**Cost to reverse.** High after WP-24. The shell, the sealing, the drop case and the carrier PCB
all follow from it. Reversing also strands the USB-C loading path in firmware and `host/` — which
is the cost this decision *adds*: a device path that is not in any work package today and needs
scoping. That obligation is recorded in `spec/hw/board-rev-a.md` §7.

---

## ADR-106 — `spec/hw/` is versioned, not frozen; limits stay upstream

**Date:** 2026-09-02 · **Decided by:** PM (Decisions 001 §3), raised by Hardware Lead (issue #7)

**Decision.** Two tiers. `spec/` stays PM-owned and frozen at the Phase 0 gate
(`tapefs-v1.md`, `engine-api.md`, `acceptance.md`). **`spec/hw/` is Hardware-Lead-owned and
versioned, with no PM gate** (`board-rev-a.md`, `thermal-budget.md`).

The obligation on `board-rev-a.md` is **notification, not approval**: any change to a pin, a
rail, or a timing constraint lands as a PR naming the Software Lead as reviewer, carrying a
`CHANGES` block listing exactly what moved. Firmware acknowledges by merging.
`thermal-budget.md` has no code consumer and needs no protocol at all.

**But limits move upstream.** The JEITA window, the solenoid on-time and duty ceilings, the
85 dB cap and the touch-temperature limit belong in `spec/acceptance.md`, PM-owned and frozen.
**Measurements live with the Hardware Lead; the numbers a unit must not exceed do not.**

**Rationale.** Both hardware documents are specified to change repeatedly after the freeze —
estimates become measurements, a revision moves a pin. Under a blanket freeze every thermocouple
reading is an escalation, which grinds or, far more likely, gets quietly ignored. That is the
"spec that drifts to describe whatever got built" failure arriving through the front door with
the rule's blessing. The cut is at the *consumer*, not the document: what needed protecting was
firmware's ability to trust a pin map, and notification protects that where a freeze could not.

**Cost to reverse.** Low — a directory move and a paragraph. The thing that would be expensive
to recover is the notification habit, which only works if it is never batched.

---

## ADR-107 — Hardware acceptance sign-off splits three ways by consequence

**Date:** 2026-09-02 · **Decided by:** PM (Decisions 001 §4), raised by Hardware Lead (issue #8)

**Decision.**

- **Criteria and paperwork → Verification Lead.** Its authority extends to reviewing whether a
  hardware acceptance test proves what it claims, **before** the test is run. It does not run the
  test and does not touch hardware.
- **Safety measurements → Michael witnesses.** WP-19's SPL check and WP-37's thermal run.
  Scheduled when he is around, not reported afterward.
- **Everything else → self-reported with data attached.** A chart and a raw log, not "passed".

Standing convention regardless: any result outside the first two categories is marked
**`SELF-REPORTED — no independent confirmation`**. Permanent practice, not a placeholder until
someone is assigned.

**Rationale.** ADR-003 says nobody grades their own homework, but the Verification Lead's scope
is `tests/` — golden fixtures, crash injection, fuzzing — and none of those tools touch a
thermocouple, an SPL meter or a latch counter. The failure mode with a self-designed hardware
test is almost always the **criterion**, not the measurement, which is why review lands before
the run rather than after it. The two witnessed tests are the only ones whose failure can hurt a
child; a second pair of eyes on an SPL meter is the entire mechanism.

**Cost to reverse.** Low to reverse, high to undo. Collapsing it saves a scheduling round and
forfeits the only independent check on the two safety criteria — and the damage would not be
visible until a unit is in a child's hands.

---

## ADR-108 — UHS-I bring-up is split at a testable gate

**Date:** 2026-09-02 · **Decided by:** PM (Decisions 001 §5), raised by Hardware Lead (issue #8)

**Decision.** Hardware Lead owns the bring-up procedure, the test points, the fallback strategy,
and delivering a board that passes an entry gate. Software Lead owns the driver, delay-line
tuning, and the throughput number. The gate:

> On rev A, an **unmodified reference driver** — NXP's SDK USDHC example — completes a 1 GB read
> and a 1 GB write on **each** slot at **SDR50** with **zero CRC retries**.

Fails the gate → hardware, and it is the Hardware Lead's call whether that is layout, power
integrity, or a respin. Passes and throughput still misses → software. Both remain jointly
accountable for the copy-time criterion.

**Rationale.** UHS-I bring-up is the hardest electrical thing on the board and the item most
likely to consume a spin, and it sits exactly between two owners. Without a gate, "is it the
layout or the tuning?" has no answer and both parties can point at the other while the schedule
burns. SDR50 rather than SDR104 because SDR104 depends on delay-line tuning, which is software's
half — **a gate that requires the other party's work to pass is not a gate.** SDR50 is also
sufficient for the requirement: the 90-minute copy needs 63% of a 50 MB/s bus.

**Cost to reverse.** Trivial as text, but it must exist **before fabrication** — written into
`spec/hw/board-rev-a.md` §5 while the board can still be changed to make the gate reachable.
Agreed after the first failure it is no longer a gate, it is an argument.

---

## ADR-109 — Tape length resolves on measurement, not argument

**Date:** 2026-09-02 · **Decided by:** PM (Decisions 001 §1), raised by Hardware Lead (issue #5)

**Decision.** Six candidate microSD SKUs are characterised under fixed conditions — card filled
to ~80%, transfer at least as long as a real copy, **worst-case windowed** write reported rather
than average. Then:

- **≥ 2 SKUs sustain ≥ 35 MB/s worst-case** (10% over the 31.75 MB/s requirement) → **90 minutes
  stands.**
- **Otherwise → 60 minutes becomes the standard tape.** 635 MB at 21.2 MB/s sits inside the V30
  floor with ~40% margin, and drops the bus requirement from SDR104 to SDR50 — retiring the
  highest-risk electrical work on the board as a side effect.

BOM discipline: **exact SKUs with revision, not model families**, recorded in
`spec/hw/board-rev-a.md` with the measured numbers and the date measured.

**Rationale.** On a UHS-I host there is no purchasable specification that guarantees the copy
target: V30's floor is 30 MB/s, below the requirement, and V60/V90 are UHS-II ratings that do
not apply when a card falls back to UHS-I. So the requirement is met by characterised models,
and a rule fixed in advance stops the decision being relitigated once someone has a number they
like. The test conditions each defeat a specific way a card looks faster than it is — an empty
card writes to clean blocks, a short transfer measures the SLC cache, and an average hides the
stall that produces the dropout.

Recording the SKU **and revision** is the whole defence against a silent controller change
inside a part number, which is a real and common failure in SD cards and would otherwise break a
shipped requirement with no change on our side.

**Cost to reverse.** The rule itself is free to change before the cards arrive and expensive
after — its value is precisely that it was fixed before anyone saw a result. Tape length is a
superblock field (`nominal_length_s`, ADR-008), so **the answer does not block the format freeze
or any software**; it changes a format-time constant, not a format.

---

## ADR-110 — Two hardware ADRs are superseded by Software-Lead and PM entries

**Date:** 2026-09-02 · **Decided by:** Hardware Lead (housekeeping, append-only)

**Decision.** `ADR-106` (`spec/hw` is versioned, not frozen) records the same decision as
**`ADR-021`**, landed independently by the Software Lead. **`ADR-021` is canonical**; ADR-106
stands as written but should be read as a duplicate, not a second decision.

`ADR-109` (tape length resolves on measurement, ≥ 2 SKUs at ≥ 35 MB/s → C-90) is **superseded by
`ADR-018`**: Michael chose C-60 directly, so the rule never fired. Card characterisation survives
as a *headroom measurement* rather than a gate.

**Rationale.** Two leads recorded the same decisions from opposite ends within a day of each
other, and an append-only log cannot be edited to fix that. Left alone, a reader nine months from
now finds two entries for one decision and cannot tell which was acted on. This is the cheap fix
and the reason the `ADR-1xx` range exists.

**Cost to reverse.** None — it is a pointer.

---

## ADR-111 — The charge window is met by a designed TS divider and a B = 3950 K thermistor

**Date:** 2026-09-02 · **Decided by:** Hardware Lead, closing PM Decisions 002-A §1

**Decision.** Route 1. `RT1` = 9.76 kΩ 1 %, `RT2` footprint kept but **not fitted**, and an NTC
of **B = 3950 K** — not the B = 3435 K 103AT part. Nominal suspend at 4.4 °C and 40.6 °C: a
**4.4 K inward margin** on each limit, so every tolerance corner lands inside 0 °C / 45 °C.

**Rationale.** The charger's TS thresholds are fixed fractions of REGN; the temperatures they
correspond to are ours to set. Two resistors, two constraints — but a B = 3435 K thermistor spans
*exactly* enough to place both thresholds on the limits and nothing more. Ask it for margin and
the required span exceeds what it can deliver, and the closed form returns a **negative
resistance**. A steeper thermistor is not a refinement; it is what makes this a design rather
than an arithmetic coincidence.

The margin is not optional because **safety here is one-sided**. Suspending early is harmless —
the device declines a charge it could have taken. Suspending late means charging a lithium cell
below freezing, or above 45 °C. Centring the nominal on the limits ships half the tolerance band
on the wrong side of a safety limit, and it would pass a spreadsheet.

`VT2` and `VT3` land inside the window and give reduced-current and reduced-voltage bands on the
way to each cutoff — the taper behaviour proposed as T-2, arriving free from the network.

**Cost to reverse.** Low before layout: three passives and a thermistor. **The threshold
fractions are `UNVERIFIED`** — `ti.com` is still blocked — so if the real values differ, `RT1`
moves and the required B may move with it. The method and the one-sided-margin argument hold
regardless; `hardware/thermal/charger_ts.py` takes the fractions as named constants, so
correcting them is one line and a re-run.

---

## ADR-112 — Solenoid duty is met by a dual monostable; the PPTC is a third layer

**Date:** 2026-09-02 · **Decided by:** Hardware Lead, closing PM Decisions 002-A §2

**Decision.** One `74HC221`: the A half sets a 30 ms pulse (429 kΩ, 100 nF **C0G**), the B half
holds a 1.2 s lockout (1.71 MΩ, 1 µF **film**). Worst case over ±16 % timing tolerance: pulse
≤ 34.8 ms against a 50 ms limit, duty **3.34 %** against a 5 % limit. The PPTC stays as a third
layer against faults the timing chain cannot see — a shorted FET, a wiring error, a coil that
fails low-resistance — and is **not** how the duty limit is met.

**Rationale.** The reviewers were right that a PPTC is history-dependent and cannot be given a
deterministic worst case. The two monostables can, and they are in one package, with the lockout
downstream of the pulse so no gate input can defeat it.

Dielectrics are load-bearing and are written down because they are exactly what gets substituted
silently at assembly: **X7R is not acceptable in either position** — it loses a large fraction of
its capacitance under DC bias and over temperature, which would widen the pulse and shorten the
lockout, both in the unsafe direction, while passing every bench test at room temperature. The
lockout capacitor is **film** rather than C0G because 1 µF C0G does not exist in a practical
package.

**Cost to reverse.** Trivial before layout. Note the behavioural cost: a 1.2 s lockout means the
transport releases at most once per 1.2 s. Invisible for the specified interlock, and it shrinks
if WP-04 shows the mechanism releases in less than 30 ms — the lockout scales with the pulse, and
it is one resistor.

---

## ADR-113 — The UHS-I entry gate moves to high-speed 4-bit

**Date:** 2026-09-02 · **Decided by:** Hardware Lead, resolving a conflict between two memos

**Decision.** The rev A entry gate is a 1 GB read and 1 GB write on **each** slot at **high-speed
4-bit, 3.3 V**, zero CRC retries, with an unmodified reference driver. SDR50 becomes a second,
optional gate if the 1.8 V circuit is ever populated.

**Rationale.** Decisions 001 §5 set the gate at SDR50. Decisions 002 §1 then made the 1.8 V
switching circuit unpopulated on rev A. **SDR50 is a UHS-I mode and requires 1.8 V signalling**,
so a board built to the second memo cannot run the gate set by the first. Neither memo is wrong;
they were written a day apart and the interaction fell between them.

High-speed 4-bit preserves everything the gate was for: it needs no delay-line tuning, so it
still tests hardware without depending on software's half, and at C-60 it meets the requirement
outright at ~29 s.

**Cost to reverse.** Free as text, and it must be settled **before fabrication** — a gate agreed
after the first failure is not a gate, it is an argument. Raised to the PM rather than resolved
silently, because it changes a criterion the PM wrote.

---

## ADR-114 — Cartridge contacts are mirrored top-to-bottom, stub ≤ 25 mm, terminated at the card

**Date:** 2026-09-02 · **Decided by:** PM (Decisions 002 §3, 002-A §6), raised by Hardware Lead (H-05)

**Decision.** The carrier routes CMD and DAT to both ends, mirrored **top-to-bottom on the same
edge** rather than end-to-end. Unused-end stub **≤ 25 mm**, series termination **at the card**,
TVS at the **slot on the mainboard** and never on the carrier. Hard gold preferred, **ENIG
acceptable** at family insertion counts. Verified on carrier rev A before the mainboard spin.

**Rationale.** End-to-end mirroring puts a carrier-length unterminated stub on every data line.
Top-to-bottom reduces it to the unused half of a short mirrored pair. C-60 helps more than any
termination choice does: the concern was framed at SDR104's 208 MHz, and high-speed 4-bit runs at
50 MHz. Keeping the TVS off the carrier keeps the cartridge cheap, which matters because there
will be many cartridges and one mainboard.

**Cost to reverse.** High after the carrier spin — it is the carrier's geometry. Cheap now, which
is why the carrier spike runs alongside WP-04 rather than waiting for WP-24.

---

## ADR-115 — The codec's second source is the same silicon in a smaller package

**Date:** 2026-09-02 · **Decided by:** Hardware Lead, closing PM Decisions 002-A §5

**Decision.** The named second source for `SGTL5000XNBA3` is **`SGTL5000XNLA3R2`** — the 20-pin
SGTL5000 — not another vendor's codec. `XNBA3` stays specified; order 1c buys eight of each so
the bench settles it.

**Rationale.** Same die, same I²S, same I²C, same register map. A supply failure costs a
**footprint change and no firmware work at all** — which is a far better hedge than a different
vendor's part with a different register map and its own bring-up.

The stock picture argues for it independently. From JLCPCB's parts API, the one vendor domain now
reachable: the 32-pin part has **74** in stock, the 20-pin has **1205**, and both are `Extended`
library parts, so assembly depends on stock on the day. The 20-pin's only functional difference
is a non-selectable I²C address, and we have exactly one codec. PJRC reached the same conclusion
under supply pressure in 2023.

**Cost to reverse.** Low now, high after layout — the packages are 5 × 5 and 3 × 3, so they are
not pad-compatible and a late switch is a re-layout of that block. The reason to buy both now is
precisely that the decision is cheap today and expensive in six weeks. **Open:** the 20-pin
part's reduced pin complement has not been checked against this design, and that needs a
datasheet `nxp.com` still will not serve.
