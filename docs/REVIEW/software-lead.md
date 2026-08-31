# Software Lead — review packet

## Round 1 · 2026-08-31 · charter revision of 31 Aug

Read the revised charter against the copy I built from. Four changes, summarised in §1. My
substantive response is §2 (the two spec defects) and §3 (what I need). §4 carries items
already open that the PM should see while it is processing everything else.

**Bottom line.** Both defects are real and the proposed resolution is close to right. Defect B's
resolution as written **cannot be implemented without violating guardrail 09** — the fix is one
extra parameter, detailed below. Defect A's resolution is sound but has an unstated consequence
that is Michael's call, not an engineering one. Separately, the highest-risk item in this
revision is not a defect at all: it is that the Verification seam has no stated mechanism, and
it is the highest-frequency interaction in the project.

---

## 1. What changed

| | |
|---|---|
| **Verification Lead is now ChatGPT**, not a Claude instance. Scope gains *adversarial spec review* | Absorbed. `CLAUDE.md` §2 updated |
| **New: "The seam with Verification"** — three rules, and it has no repository access | Absorbed into `CLAUDE.md` §2. Two of the three rules need a definition before I can follow them — §3.1, §3.2 |
| **Action 02 now says** resolve the two defects before freezing | Absorbed. WP-02 will draft but not freeze |
| **New: two open spec defects (A, B)** with a proposed resolution to treat as a starting position | Worked below |

Nothing else changed. Guardrails, streams, contracts, escalation, reporting and the hardware
section are byte-identical to the previous revision.

**Process note.** The charter was revised in place with no version marker. I caught the delta
only because I had kept the previous copy. `spec/` is upstream of the code and the charter is
upstream of `spec/` — it should carry a revision the way the plan carries "Rev B", so a lead
can tell at a glance whether it is working from current text. **Recommendation:** add a revision
line to the charter masthead. Cheap, and it removes a whole class of silent desync.

---

## 2. The two spec defects

### Defect B first — it has a concrete blocking flaw

**Proposed:** *"`tape_dup` assigns the destination a freshly generated UUID."*

**Agreed on intent.** Two cartridges claiming one identity is a real bug and it silently corrupts
any device-side state keyed by UUID — including, circularly, the position table that Defect A's
resolution introduces.

**But the engine cannot generate a UUID.** A UUID needs entropy. The engine has no entropy
source, no clock, and no RNG, and it may not acquire one:

- Guardrail 09 — the engine knows nothing about hardware. An entropy source is a hardware concept
- Guardrail 08 — no allocation, no libc file I/O. `/dev/urandom` and `time()` are both out
- §6 rejected-on-sight — any dependency beyond libc

So "generate" has to happen above the engine. **The fix is one parameter:**

```c
tape_dup(src, dst, const uint8_t new_uuid[16], cb)
```

The caller — firmware from its hardware RNG, `tapectl` from the host OS — supplies the identity;
the engine writes it. This keeps guardrail 09 intact, keeps the engine deterministic (which the
golden fixtures in contract 3 require — an engine that generates its own UUIDs is not
bit-reproducible), and costs nothing.

**Recommendation:** adopt with the parameter. Same treatment for any format call, which has the
identical problem at cartridge creation.

**Three consequences the proposal does not cover, which WP-02 must:**

1. **Write ordering.** "Assign a fresh UUID" sounds like a first step. It must be the *last*.
   Guardrail 07 requires the destination be unmountable-or-unchanged throughout; a fresh identity
   written before the chunk copy completes yields a cartridge with a new name and partial
   contents. Order must be: chunks → flush → index → superblock. The destination's *existing*
   superblocks must be invalidated before the copy begins, or a yank mid-dup leaves a cartridge
   whose superblock describes content that is no longer there. There are two superblocks, at both
   ends, so the invalidate-and-rewrite order is itself a crash-injection surface. **This is
   squarely WP-10's business and I would like Verification to attack it specifically.**
2. **`tape_promote` must invalidate stored position.** Promote rewrites Side A's content under an
   unchanged UUID. Any position stored for (UUID, side A) then points into a timeline that no
   longer exists. Cheap to handle; silent and confusing if missed.
3. **The UUID needs a stated sole consumer.** Right now the position table is the only thing
   keyed by it. If a second consumer appears later, this defect returns in a new form.
   **Recommendation:** state in `spec/tapefs-v1.md` that the position table is the UUID's only
   sanctioned consumer, and that adding another is an escalation.

### Defect A — resolution is sound, but it breaks the metaphor and that is Michael's call

**Proposed:** device keeps a table in its own flash mapping cartridge UUID → position, last ~64
cartridges.

**Agreed, and it does not violate guardrail 06** — the write goes to device flash, not to the
cartridge, so the source slot stays untouched. Sizing is trivial: 64 entries × 32 B ≈ 2 KB. A
position fits in a `uint32` counted in *frames* with 12× headroom even against a Side B grown to
its 1.50× limit; counted in *bytes* the headroom is only 3.0×, so **the spec should store frames,
not bytes.**

**Three things the proposal leaves unstated. The first is the one that matters.**

**1. The table must be firmware-owned, not engine-owned.** Device flash is hardware; guardrail 09
puts it out of the engine's reach, and the block-device contract is two function pointers for the
*cartridge*, not for device-local storage. Letting the engine own this would widen the one
interface the charter says to escalate rather than widen (contract 2).

So the split is: the engine exposes position; firmware persists it. **Which means the engine API
needs calls it does not currently have.** Plan Rev B §05 lists nine calls and **none of them is a
seek or a position query** — yet WP-08 is *"Playback, seek, variable-rate scrub"* and asserts
*"seek is O(1) in the map"*. Seek is specified in the acceptance criteria and missing from the
API table. Defect A cannot be resolved without it. **WP-03 will add `tape_seek` and a position
getter and flag them as additions to the plan's list rather than silently including them.**

**2. Position stops travelling with the cartridge, and there will be four players in this house.**
This is the real cost and it is not an engineering question. A real cassette resumes where you
left it because *the tape is physically at that spot* — the position is a property of the
cartridge. Move a device-side table into that role and the same cartridge resumes at a different
place in a sibling's player, or at a sibling's position in yours.

The alternative — store position on the card — is available *only* in the work slot, because the
source slot is read-only. That would make the same cartridge behave differently depending on
which slot it is in, which fails the seven-year-old tiebreaker outright. **So I recommend the
device-side table for both slots, uniformly, and I recommend logging it as a deliberate departure
from the tape metaphor rather than letting it arrive as an accident.** Queued for Michael as
Q-004 — "your tape remembers where you were, but only in your own player" is a feel question.

**3. "Later" is doing unexamined work.** *"Put it back later, resume where it was"* — within a
session, or across days? Only the second requires flash at all; the first is RAM and no
persistence mechanism exists. I think the second is right, on the authenticity argument above,
but it is worth saying that authenticity is what settles it, because convenience points the other
way.

**Eviction:** LRU at 64 entries. A child whose cartridge falls off the end gets a tape that starts
at the beginning — benign, and self-explanatory without a screen. Good default.

### On the resolution as a whole

The PM's framing — *"one change closes both"* — is right, and the two defects are genuinely
coupled: Defect A introduces the UUID-keyed state that makes Defect B's duplicate identities
harmful. Worth noting that **the ordering matters for the freeze**: if Defect A's resolution were
rejected and nothing keyed off the UUID, Defect B would drop from a corruption bug to a cosmetic
one. They should be decided together, not separately.

---

## 3. What I need

### 3.1 A mechanism for the Verification seam — my largest concern in this revision

The Verification Lead has no repository access, receives `spec/` as text, and returns findings and
test source. **The charter does not say who moves the text.**

This is not a detail. It is the highest-frequency interaction in the project: Stream 2 works
against every spec revision and every work package in Streams 1, 3, 4 and 5, and the charter puts
independent sign-off on *every* work package through it. If the transport is a human pasting
documents, then the one structure built specifically to remove Michael as a bottleneck has a human
bottleneck at its centre, and the "never block a whole stream" rule collides with it immediately.

**Recommendation:** the PM states the mechanism explicitly before Stream 1 starts — who carries
text in each direction, at what cadence, and what happens when Stream 2 is mid-review and Stream 1
is ready to proceed. If the answer is "the PM relays", then the PM's twice-weekly cadence becomes
Stream 2's maximum review rate, and Phase 1 should be scheduled against that number rather than
against agent throughput.

### 3.2 Rule 1 is not enforceable by me, and I can offer a structural version that is

*"Do not show it the engine implementation before it has written the tests for that behaviour."*

**The repository is public.** Anything I push is world-readable. I can decline to *volunteer*
code, but I cannot prevent it being read, and the charter's own reasoning — guardrails 05 and 06,
which insist on structural enforcement over flags and permission checks — says discipline is the
weak form.

**Recommendation, and I can implement this unilaterally if the PM approves:** engine
implementation stays on unmerged branches until Stream 2's tests for that behaviour have landed
on `main`. Then `main` carries spec-then-tests-then-implementation in that order, permanently and
visibly, and the rule holds structurally instead of by good intentions. Costs a slightly longer
branch life in Phase 1 and nothing else.

### 3.3 A definition of "mechanically" before I need it

*"If a test it wrote does not compile, fix it mechanically. Weakening the assertion is not a fix."*

I agree with the intent and I want a bright line before the first failing case, not during it.
**Proposed, for the PM to accept or replace:**

> A fix is **mechanical** if it cannot change whether the test passes against a correct
> implementation. Include paths, symbol renames, harness plumbing, type widths that do not change
> a comparison, and formatting are mechanical. Anything touching an assertion's value, tolerance,
> ordering, or scope is not — nor is deleting a case, marking one skipped, or narrowing an input
> range.

One case sits outside that line and needs its own answer: **a test that calls an API that does not
exist.** Adding it is a spec change (escalation trigger #1), not a mechanical fix — but a test
asserting behaviour the spec omits is exactly what adversarial review is *for*, and it is likely
to happen on the first pass given §2's finding about the missing seek call. **Recommendation:**
treat it as a spec finding, route it to the PM, and do not add the call to make the test build.

### 3.4 An agreed shape for returned test source

CI already has a golden-suite runner wired and failing. It expects fixtures in `tests/golden/`
and an executable `tests/golden/run.sh`. If Verification returns tests in a different shape, I
land them and they do not run, which looks like a Stream 2 failure and is not one.

**Proposed contract, for Verification to accept or amend:** test cases as C99 source compiled
against `engine/include/tape.h` only, no framework dependency; audio fixtures as WAV; one
manifest listing case name, fixture, and expected result. I will adapt the runner to whatever
shape is agreed — I would just rather agree it once than discover it.

### 3.5 Confirmation the PM can actually read GitHub issues

The charter routes non-Michael escalations to issues labelled `pm-decision`. **I have filed three
(#2, #3, #4) and I do not know whether the PM has seen any of them.** §03 says the repo is public
so `STATUS.md` can be read from `raw.githubusercontent.com` — that mechanism serves *files*, not
issues, and the PM has no GitHub connector.

**Recommendation:** if issues are not readable, the escalation channel should move into the repo
as files, and I will mirror the three open ones. Cheap to fix now; expensive if a month of
escalations turns out to have been written to a channel nobody reads.

### 3.6 Still needed, unchanged from the last report

- **A Hardware Lead.** WP-34 (thermal and safety budget) is a Phase 0 package, not started. The
  plan is explicit that it is *"written before the schematic, not after"*.
- **`main` branch protection.** Plan §03 says nothing merges without Michael's review. Repository
  settings are not mine to change.

---

## 4. Already open, for the PM to see in one place

| | |
|---|---|
| **Issue #2** | Does the 200 KB static budget include `.rodata`, or is it RAM only? CI enforces RAM-only. Needs an answer at WP-03 |
| **Issue #3** | **The 512 KiB preroll cache does not fit the 200 KB engine budget** — 2.5× over, not a rounding problem. Recommending a caller-provided buffer. Note this is now the *second* place where the resolution is "the caller supplies it" (see Defect B); that is a pattern worth naming in `spec/engine-api.md` rather than two coincidences |
| **Issue #4** | **Side B can only grow to 1.50×** before the 32 KiB index slot overflows. No screen to explain the wall. Mechanism is mine; felt behaviour is Michael's (Q-003) |
| **`FOR-MICHAEL.md` Q-002** | 90 vs 60 minutes. Touches the format; cheaper before the freeze than after |
| **Plan Rev B §09** | The Phase 5 body paragraph still carries Revision A text — *"RP2350 at about a dollar"* and *"copy time down from ten minutes to two"* — both contradicted by Correction 2 and by the WP-26/27/28 rows in the same table. Not ambiguous in practice, but the plan is a source of truth that currently contradicts itself in one paragraph |

## 5. What I am doing while this is processed

Not blocking. WP-02 proceeds as a **draft**, not a freeze, per the revised action 02:

- Region layout, chunk map entry format, mount and recovery rules, and the failure-mode
  enumeration do not depend on either defect and are being written now
- The superblock's UUID field, `tape_dup`'s write ordering, and anything touching resume position
  are being written **with the resolutions above marked as provisional**, so that Verification's
  attack lands on a concrete proposal rather than a blank
- Nothing is frozen and nothing goes to Michael until Verification has had its pass

If the PM would rather I hold entirely, say so — but the charter's own instruction is to take the
reversible path and flag it, and a draft is exactly that.
