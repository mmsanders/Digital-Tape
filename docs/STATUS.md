# STATUS

**Updated:** 2026-09-05 · **Phase:** 1 (engine) · **Updated by:** Software Lead
**Charter Rev C · spec bundle DRAFT-6 on `main` · CI 8/9 green**

---

## What changed since last time

**The read path is reconciled to DRAFT-6.** Mount is four phases and only the last one writes;
both sides are selected and validated whichever was requested; degraded-B is decided **before** the
stage oracle; the oracle itself is implemented against §9.3.3's three rows including both `S > 0`
guards. 260 checks, up from 102.

**WP-06's eight sub-criteria are exercised** — 06a effective writability on v1.1 media, 06b
undefined field values, 06c disjointness with zero chunk reads asserted, 06d geometry, 06e stale
`promote_stage` (mount half; the `tape_arm` half is held), 06f both-side mount and degraded-B, 06g
mount-writes-nothing-when-it-fails, 06h the Not-mounted contract.

**Invariant 26 is now true rather than claimed.** Every refusal path runs on a writable device with
a torn mirror — repair genuinely pending — and asserts zero writes and zero flushes. That is the
assertion DRAFT-5's ordering could not satisfy.

**The number the PM asked for: `tape_instance_size()` is 156 456 bytes, 76 % of 200 KiB**, printed
by WP-13's gate on every run. Holding both sides cost 8 KiB net, not 49: §5.1's sort only needs to
order entry *indices*, so the third index buffer became a permutation array and the freed one holds
the other side (ADR-033). Stack is 1 536 of 8 192 bytes; `.rodata` 1 040 of 32 768.

**I introduced a defect in this work and caught it before it shipped** (ADR-034). `select_side`
parsed the second slot into the *other side's* buffer — free during Side A's selection, and holding
Side A's selected index during Side B's. A cartridge with two valid Side B slots would have had
Side A's index silently replaced by a Side B slot. **All 245 checks passed**, because §5.3's
resting state is exactly one valid slot, so no fixture in the suite had a valid partner. The test
that catches it was written afterwards and verified to go red against the reintroduced bug.

**One correction.** I reported to the PM that the RAM gate measured `.data + .bss` alone and owed
`tape_instance_size()`. It does not and never did — `audit-memory.sh` has linked a probe and summed
the instance since it was written. I carried a stale sentence forward from my own README without
reading the script beside it, which is the same class of error as a spec header asserting its own
consistency.

## In flight

| Work | Owner | State |
|---|---|---|
| DRAFT-6 bundle | Software Lead | **On `main`**, gate green |
| WP-06 read path, DRAFT-6 | Software Lead | **Done**, unconfirmed. PR #20 |
| WP-06 sub-criteria 06a–06h | Software Lead | **Exercised**, unconfirmed |
| WP-07 allocator | Software Lead | **Done**, unconfirmed. `tapefs` §7 and Rule 3 are unchanged in DRAFT-6; re-read and no code follows |
| WP-06/07 commit paths | Software Lead | **Held** by structural Rule 1 |
| `TAPE_ERR_FAULTED` quarantine | Software Lead | State plumbed, no producer yet — see below |
| WP-10 crash injection | Verification | Infrastructure in CI. DRAFT-6 adds both durability modes and the §4.5 counter boundaries |
| WP-11 golden suite | Verification | Runner proven; fixtures owed. **The only red gate** |

## Blocked

Nothing. The commit path is held by instruction, not blocked.

## Acceptance criteria flipped to passing

**None.** 364 self-test checks are the Software Lead's claims about its own code. `acceptance.md`
requires the Verification Lead's independent confirmation and nothing has had it.

## What will hurt in three weeks

- **`FAULTED` has no producer, and that is honest rather than finished.** §7.2 quarantines an
  instance after any indeterminate write or flush on the mounted device, overrides every mounted
  row, and permits four calls. The read path has exactly one write — phase-4 repair — and §4.1
  explicitly excludes it, because it changes no logical state. So the state, the error code and the
  refusals are plumbed and nothing can currently reach them. **It becomes real with the commit
  path, which structural Rule 1 holds**, and WP-12a's eleven `F` cells are what will prove it.
- **RAM is 76 % before the commit and record paths add their state.** The remaining headroom is
  48 KiB and one more `tape_index`-sized structure would exhaust it. If it tightens the answer is
  escalation, not a smaller `TAPE_MAX_ENTRIES` — 4 096 entries is roughly two thousand splices, a
  child's editing budget and therefore a product number.
- **Nothing yet checks that code matches the bundle it claims to implement.** The manifest gate
  covers `spec/` against itself. The engine claiming DRAFT-6 in a header comment is a claim, and
  this round it was wrong twice in a row before anyone noticed. I do not have a decidable gate for
  this and I am not sure one exists; it is the honest gap in the gate set.
- **The PM's calibration note applies to me too.** Two of the six blockers in DRAFT-6's own audit
  were introduced by fixes for the previous round's findings. My `select_side` defect is the same
  shape: written last, under the most pressure, to close a hole that had just been found. The
  suite caught it only because I went looking for what the fixtures could not see.
