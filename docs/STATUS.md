# STATUS

**Updated:** 2026-09-02 · **Phase:** 1 (engine) · **Updated by:** Software Lead
**Charter Rev C · specs DRAFT-3 · CI 6/7 green**

---

## What changed since last time

**DRAFT-3 landed**, mechanically and byte-identical to the PM's files (verified with `cmp`).
`spec/tapefs-v1.md`, `spec/engine-api.md`, and the new `spec/acceptance.md`.

**The Verification Lead's infrastructure is in the repo.** Its crash harness and fault block
device were pulled from `Digital-Tape-Verification` per the new transport rule and **built and
passed unmodified** — no mechanical fix was needed. They now run in CI. This is the first time
the seam has actually carried anything, and it worked.

**WP-06 read path is implemented**: superblock parse, the §4.1 two-copy protocol, version
refusal before repair, `state`, full geometry validation, §5.2 index validation, and §7
`free_next` derivation. 60 checks cover **every refusal path in §4.1 and §5.2** — the WP-06
acceptance criterion — including the one §5.2 calls out by name: a Side A run that *starts*
below `a_high_water` and *ends* above it, which a first-chunk-only check would accept.

**The commit path is deliberately not written.** Structural Rule 1 (ADR-022): it waits for
WP-10's tests on `main`.

**CI split into four jobs** so the build goes green independently of the golden suite, and a
**KiCad ERC/DRC gate** is wired for the Hardware Lead — it skips cleanly with no boards and
fails loudly if boards exist without `kicad-cli`.

## In flight

| Work | Owner | State |
|---|---|---|
| DRAFT-3 landing | Software Lead | **Done** |
| WP-06 read path | Software Lead | **Done**, unconfirmed |
| WP-06 commit path | Software Lead | **Held** by structural Rule 1 |
| WP-07 allocator, CoW Side B | Software Lead | Next, after WP-10 tests land |
| WP-10 crash harness | Verification | Infrastructure landed; DRAFT-3 unblocks its adapters |
| WP-11 golden suite | Verification | Runner built and proven; fixtures owed |

## Blocked

**Nothing.** Branch protection is on (Michael), so that item closes.

## Acceptance criteria flipped to passing

**None.** The 129 self-test checks are the Software Lead's own claims about its own code and are
explicitly not acceptance. `spec/acceptance.md` requires the Verification Lead's independent
confirmation, and nothing has had it.

## What will hurt in three weeks

- **Two real defects were found by my own gates this round, and both were invisible to every
  other check.** `.bss` held 98 KB of `static` buffers in the mount path — not allocation, so
  every existing gate passed them, but engine-owned RAM outside the caller's instance and a
  **reentrancy bug**: `tape_dup(src, dst)` mounts two cartridges and they would have overwritten
  each other's index. It would have surfaced when duplicate was implemented, looking like media
  corruption. Caught only because the memory gate started counting `tape_instance_size()`.
  The lesson worth keeping: a gate that measures the wrong quantity reads as green.
- **RAM is at 72 % before the record path exists.** Two index arrays are 48 KiB each and
  dominate. The commit path needs staging, and `TAPE_MAX_ENTRIES` is an engine memory constraint
  rather than a media one (`engine-api` §4). If it gets tight, the honest lever is that constant,
  not the budget.
- **The golden suite is still the only red gate**, and it is red for a good reason. But WP-11's
  fixtures are now the last thing standing between the engine and a cross-target contract that
  can actually fail.
- **`engine/port/dev_sim.c` and the verifier's `fault_block_device.c` overlap**, and theirs is
  better: it models flush-required durability, where mine assumes every completed write is
  durable. Raised as issue #16 with a recommendation to retire mine.
