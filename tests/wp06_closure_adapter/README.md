# WP-06 R52 closure-gap product binding

Software-owned binding of the imported verifier package `tests/wp06_closure_r52`.

- Tree `d4850f628443707bf967ec65bbd781be9eaad9f2`, Verification #101 Return C commit
  `778413d3c2dca7255aa086b5f8fda8f5094c674e` (branch `verification/issue-101-wp06-closure`).
- Seven observable gap rows; gap plan `db9f826a…9b8119`, ledger `93f9c89e…71bd6`.
- Engine tree `054d27ab6e3e72f61118ff7d99e19e48741d05b2`, unchanged from main `39d2076`.

**Canonical result, decided by the package's own `replay.py`: FAIL.** Five rows pass
`oracle.check`; the two Side-A live-B floor rows fail on the oracle's floor predicate.
The engine behaviour behind both failures is what the frozen spec requires; see
[Finding](#finding-the-floor-predicate-rejects-lawful-second-phase-writes). This is
returned for Verification/PM disposition. No engine change was made to satisfy it,
and none would be lawful.

Not claimed: full WP-06 closure. The two WP-06e rows the package marks
contract-blocked are PM #308 and have no fixture here.

## What the adapter does

`wp06c_adapter.c` includes only `engine/include` and does not import the oracle. One
invocation runs one `gap_plan.json` case on a fresh flat device and prints one
`wp06-r52-observation-v1` object: every public call with its step, every device
callback in order with a global ordinal, and the named raw snapshots (both
superblocks and all four whole 64 KiB index slots, read directly from media).
`run_product.py` runs all seven, retains them, and calls `replay.py`.

Long operations use a 2^20-block budget and are driven until `more_work == false`
under one step, as ADAPTER.md requires. Each completed in a single call.

| Case | Calls, by step |
|---|---|
| E-SIDEA-REFUSE | mount A · exercise `tape_arm(overwrite)` |
| E-RESPOOL-FULL | mount B · exercise `tape_respool` |
| E-RECORD-PROMOTE | mount B · arm `tape_arm(overwrite)` · record `tape_feed` (10 frames at 0), `tape_service` · commit · promote `tape_promote` · remount `tape_unmount`, fresh `tape_mount(B)` |
| F-STAGE-DEGRADED-* | mount A + `tape_get_info` · reset `tape_reset_side_b` · remount `tape_unmount`, fresh `tape_mount(A)` + `tape_get_info` · switch `tape_set_side(B)` |
| F-LIVEB-*-FLOOR | mount A · exercise `tape_promote` or `tape_respool` |

## Fixtures

Every superblock fills all tapefs §4 fields (version 1.0, `sb_generation` 10, §1
constants, §3 LBAs, mirror at `block_count − 1`, UUID ASCII `WP06-R52-closure`) with
`nominal_length_s` the smallest label whose §2 ceiling derives exactly `total_chunks`.
`N` = 131,072 frames. Referenced chunks carry distinct non-zero audio.

| Fixture | total_chunks | H | stage / S | Live A | Live B |
|---|---:|---:|---|---|---|
| `stage1_row1` | 8 | 3 | 1 / 2 | A0 seq 5 `[{2,0,N}]` | B0 seq 6 `[{2,0,N}]` — §9.3.3 row 1 |
| `stage1_row1_no_destination` | 3 | 3 | 1 / 2 | as above | as above; no chunk at or above H exists |
| `stage1_degraded_absent` | 8 | 3 | 1 / 2 | A0 seq 5 `[{2,0,N}]` | B0, B1 zero |
| `stage1_degraded_divergent` | 8 | 3 | 1 / 2 | A0 seq 5 `[{2,0,N}]` | B0 seq 6 `[{2,0,N}]`, B1 seq 6 `[{2,0,N−1}]` |
| `sideA_live_recorded_B` | 8 | 2 | 0 / 0 | A0 seq 5 `[{0,0,N}]` | B0 seq 6 `[{0,0,N},{3,0,10}]`: A's chunk plus a recorded run at chunk 3 |

## Finding: the floor predicate rejects lawful second-phase writes

`oracle.check` for both F-LIVEB rows requires every chunk write in the `exercise`
step to land at or above the live-B high-water measured **before** the operation
(here chunk 4). Observed chunk writes, in order:

| Case | Phase 1 / pass 1 | Then | Phase 2 / pass 2 |
|---|---|---|---|
| F-LIVEB-PROMOTE-FLOOR | chunks 4–5 | commit A1, B1; superblock (mirror, then primary) | chunks **0–1**, commit A0, B0; superblock (mirror, then primary) |
| F-LIVEB-RESPOOL-FLOOR | chunks 4–5 | commit B1 | chunks **2–3**, commit B0 |

Every first-phase write honours the floor. The second-phase writes are required by
the frozen spec:

- **Promote.** tapefs §9.3.2 step 5 checks `[0, len)` against the live set of both
  sides *after* phase 1, which by then is only `[S, S+len)`; step 6 then writes
  `[0, len)`. Because a Side-B timeline of `len` chunks references at least `len`
  distinct chunks below `free_next = S` (§5.1 disjointness), `len ≤ S` always, so
  step 5 cannot decline on any fixture of this class. A complete promote therefore
  always writes chunk 0, below any positive floor. Driving promote in smaller
  increments would not help: the oracle also requires exactly one `tape_promote`
  call in the step.
- **Re-spool.** tapefs §9.4 pass 2 runs whenever a run of `len` chunks exists at or
  above `a_high_water`, disjoint from the live set *at that moment*, strictly lower
  than pass 1's start. After pass 1 commits, B's old chunks are no longer live, so
  pass 2 lawfully reclaims them, as §9.4's own worked example does.

The floor the spec protects (invariant 10, tapefs §4.2) is disjointness from the live
set at the time of each write, not from the pre-operation set. Suggested correction
for Verification: apply the floor to writes before the step's first index commit, or
check each chunk write against the live set current at that write. For re-spool
alone, a fixture whose B references Side-A chunks so that no lower run fits would
avoid pass 2; this binding does not switch to it, because choosing a fixture to evade
a strict assertion is tuning the stimulus to the oracle.

## Run

    make -C engine clean all
    make -C tests/wp06_closure_adapter clean all
    python3 tests/wp06_closure_adapter/run_product.py --evidence <fresh dir> \
        --retained tests/wp06_closure_adapter/evidence/p1-r53-product
    python3 tests/wp06_closure_adapter/run_product.py \
        --replay tests/wp06_closure_adapter/evidence/p1-r53-product --out <fresh dir>
    python3 -B tests/wp06_closure_adapter/negative_controls.py <dir>/observations.jsonl

`run_product.py` checks the verifier tree at HEAD, import commit `ffd87a8` on base
`39d2076`, and the plan's SHA-256, then retains `observations.jsonl` (8.6 MB, not
committed), a deterministic gzip, `case-census.json` (observed calls and chunk writes
per case, not a verdict), `build-identity.json` and `SHA256SUMS`, and calls
`replay.py`. It exits with `replay.py`'s status. With `--retained` the fresh JSONL
must be byte-identical to the committed evidence; that check runs before replay.

`negative_controls.py` is non-canonical. It prints `oracle.check`'s outcome for every
case (replay stops at the first failure), then requires the oracle to reject one
causal mutation of each passing case's Product evidence: a write during the Side-A
refusal, `TAPE_OK` for the full re-spool, a missing stage-clear candidate write on
arm, a still-degraded remount, and a remount selecting the pre-reset B.

## Retained evidence (`evidence/p1-r53-product`)

Produced on Windows with MSYS2 UCRT64 gcc 16.2; CI regenerates it on ubuntu-latest and
requires byte identity. A second local run regenerated it byte-identically.

| File | SHA-256 |
|---|---|
| `observations.jsonl` (not committed) | `13742ebe288ee0a187f34a2d2b23ec659887e7710fcb9c921c548f3bbd76e06b` |
| `observations.jsonl.gz` | `9570dbe7127f5eb73a4d4be89271f60ad002aeb22736ca931823e21524246b2a` |
| `build-identity.json` | `2346203fe89c5ccefcd45d75a45a339c18842990239fe3310258505e23ddb380` |
| `case-census.json` | `8a8893bf3626186b4169ec45d58b25b5c5749306ce135a62ad0442017a74eeb1` |

## Exclusions

Full WP-06 closure, the two contract-blocked WP-06e rows (PM #308), WP-10, WP-11,
hardware/card atomicity, release, and any acceptance.
