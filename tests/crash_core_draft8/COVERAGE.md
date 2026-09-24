# WP-10 core crash coverage matrix — DRAFT-8

## Exact injection census

Canonical case-set SHA-256:

`6c924fd7bdd54b180084fe58cc50ef49d96fc068b968b8022383685ecf235c96`

| Family / variant | First interruption | V7-001 closure | Total |
|---|---:|---:|---:|
| Record commit — overwrite | 2,056 | — | 2,056 |
| Record commit — overdub | 2,056 | — | 2,056 |
| Record commit — splice | 2,056 | — | 2,056 |
| Reset B — healthy live B | 2,056 | — | 2,056 |
| Reset B — degraded/equal-sequence | 2,056 | — | 2,056 |
| Stage clear — arm | 2,056 | 4,104 | 6,160 |
| Stage clear — reset B | 2,056 | 4,104 | 6,160 |
| Stage clear — re-spool | 2,056 | 4,104 | 6,160 |
| **Total** | **16,448** | **12,312** | **28,760** |

Each first-interruption scenario is exactly:
- 2 durability modes;
- 2 targeted 512-byte writes;
- per write: before (0 landed), every torn prefix 1…511, after (512 landed);
- 2 target flush faults.

That is `2 * (2*513 + 2) = 2056`.

Each stage-clear closure caller is exactly:
- 4 one-copy/stale-partner recovery seeds;
- 2 durability modes;
- next partner write at 0…512 landed bytes.

That is `4 * 2 * 513 = 4104`.

Across the whole tranche:
- flush-required cases: **14,380**;
- write-through cases: **14,380**;
- torn-write cases: **28,616**;
- before-write/partner cases: **56**;
- after-write/partner cases: **56**;
- first-interruption flush-fault cases: **32**.

Clean baselines and closure reachability/setup faults are evidence setup and are **not**
included in the 28,760 injection count.

## Frozen coverage assertions

| ID | Assertion | Independent mechanism |
|---|---|---|
| C10-01 | Every targeted write boundary is enumerated in both durability modes | Verifier-owned immutable planner/count/digest |
| C10-02 | Every targeted block write is torn exhaustively | Prefix lengths 1…511 for each write ordinal |
| C10-03 | Flush-required and write-through are not conflated | Byte-level durable-media simulation; same injection may require different bytes |
| C10-04 | Crash remount uses durable bytes only | Adapter dual-image contract; compact snapshot taken before fresh remount |
| C10-05 | Record commit is atomic old/new | Verifier predicts exact inactive-slot bytes; raw snapshot parser selects only legal generation |
| C10-06 | Already-durable record audio cannot be corrupted by commit crash | Every chunk SHA-256 after crash must equal pre-commit durable snapshot |
| C10-07 | Reset-B is atomic and moves no audio | Only target index blocks may be written; all chunk hashes unchanged |
| C10-08 | Degraded-B reset admits its distinct surviving-B1 intermediate | Raw B0/B1 CRC/selection oracle, not a two-state shortcut |
| C10-09 | Stage clear uses §4.6 partner-first order | Exact target LBAs and block hashes checked against selected candidate/partner |
| C10-10 | Stage clear is reached through arm/reset/respool public paths | Baseline must reach first post-clear chunk/index write without landing it |
| C10-11 | Stage clear preserves H and advances generation while clearing stage | Exact superblock bytes + independent raw selection |
| C10-12 | V7-001 two-interruption closure | Four recovery seed orientations × all three callers × both modes × 513 partner outcomes |
| C10-13 | No rollback to stale H that invalidates live Side A | Closure stale copy has H=1 while current live A is chunk 2; fresh durable-byte mount must remain usable |
| C10-14 | Every structurally valid committed index obeys §5.2 | Independent CRC, extent, Side-A bound and interval-disjointness parser |
| C10-15 | Compact deterministic failure reproducer | First failure retains case, seed/mode/injection, raw snapshots and independently simulated expected bytes |

## Record fixture

Initial:
- healthy superblocks, generation 10, `a_high_water = 2`;
- A0 sequence 10: `{0,0,131072}`;
- B0 sequence 20: `{0,0,131072}`;
- B1 invalid;
- chunk 2 is free.

The crash scope begins only after one input frame has been accepted and serviced to
durability in chunk 2.

Frozen post-commit indices at B1 sequence 21:

| Mode | New live B entries |
|---|---|
| overwrite | `{2,0,1}` |
| overdub | `{2,0,1}, {0,1,131071}` |
| splice | `{2,0,1}, {0,0,131072}` |

Each requires exactly one entry-array block, flush, one header block, flush.

## Reset fixtures

### Healthy

- A0 seq 10: chunk 0;
- B0 seq 20: chunk 1;
- reset targets inactive B1 at seq 21 with A's entry.

### Degraded/equal-sequence

- A0 seq 10: chunk 0;
- B0 seq 500: chunk 1;
- B1 seq 500: chunk 0.

Both B slots are valid but equal-sequence/divergent, so Side-A mount is degraded-B.
Reset writes B0 at seq 501.

When B0's entry block has landed but its block-0 header has not, B0's previous CRC is
invalid and B1 may be the sole valid B generation. This is an explicit permitted
recovery state, not corruption.

## Stage-clear fixture

Healthy stage-1 fixture:
- both superblocks generation 10;
- `promote_stage = 1`;
- `promote_staging_chunk = 2`;
- `a_high_water = 3`;
- live A seq 100 and B seq 101 both exactly `{2,0,131072}`.

This is exactly §9.3.3 RESUME row 1 (resume at step 5).

Cleared state:
- generation 11;
- `promote_stage = 0`;
- `promote_staging_chunk = 0`;
- `a_high_water = 3` unchanged.

Healthy-pair target order is mirror partner first, primary candidate last.

## V7-001 closure seeds

All four have current stage-1 generation 10/H=3 and the same valid live indices.

1. primary current; mirror invalid;
2. mirror current; primary invalid;
3. primary current; mirror stale generation 9/H=1;
4. mirror current; primary stale generation 9/H=1.

For stale seeds, H=1 rejects the live Side-A entry at chunk 2. Therefore a faulty
mirror-first/primary-first choice that destroys the current candidate and exposes the
stale copy is observed as an unusable cartridge, exactly the V7-001 regression.

Before testing the second interruption, product mount repair is failed before any
repair byte lands so the permitted unrepaired shape reaches the logical stage-clear
update with `needs_repair=true`.

## Negative controls

The verifier self-test must demonstrate rejection of:
- a planned injection that never fires;
- flush-required evidence interpreted as write-through;
- a non-permitted torn-write durable image;
- stale-partner rollback that strands Side A;
- omission of one second-interruption seed family;
- malformed provenance/fixture identity.

## Explicit exclusions

This package is **not complete WP-10**. It excludes:
- full promote crash enumeration and all eleven §9.3.4 rows;
- format/duplicate barrier + identity-assignment crash tables;
- full re-spool pass-1/pass-2 crash enumeration;
- shared-sequence and counter/headroom boundary families;
- equal-generation-divergent raw destination families;
- final format/dup superblock identity-boundary cases;
- general WP-12a continuation/re-entry/FAULTED acceptance beyond reachability needed
  for the bounded stage-clear path;
- media atomicity hardware validation;
- WP-07, WP-09, WP-11 and WP-13 acceptance.
