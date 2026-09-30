# WP-06 R52 closure-gap product binding (R54 rebind)

Software-owned binding of the imported, R53-corrected verifier package
`tests/wp06_closure_r52`.

- Tree `b216baa2a9c160b2a14b3eac25567c5a260eed2f`, from Verification commit
  `6b92e5f43de89efa71069084028376cdbc636bf4` (branch `verification/issue-108-wp06-floor`,
  PR #111, Verification #108). It supersedes tree `d4850f62`, which was only on held #312.
- Seven observable gap rows; gap plan `db9f826a…9b8119` and ledger `93f9c89e…71bd6`,
  both unchanged.
- Built on main `66c6abc6` (after #311, before #318); engine tree `054d27ab…`.
  Following the #320 pattern, `build-identity.json` records the engine tree, and
  `run_product.py` does not hard-fail on a later one.

**Canonical result, decided by the package's own `replay.py`: PASS, 7 of 7.** This is
returned for independent Verification disposition; it is not acceptance.

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
| `sideA_live_dense_fragmented_B` | 12 | 2 | 0 / 0 | A0 seq 5 `[{0,0,N}]` | B0 seq 6 `[{0,0,N},{2,0,N},{3,0,10}]` |

## The R53 floor fixture and trace

ADAPTER.md now needs two things from the floor rows.

**A dense, fragmented live-B floor fixture.** Live B has three runs, so promote
takes the allocating phase-1 path rather than adopt-in-place. It references A's
chunk 0, then owns chunks 2 and 3, so it densely fills `[a_high_water, floor)` =
`[2, 4)`. Its timeline is `2N + 10` frames, so `len` = 3. `total_chunks` is 12.

**A `data` field on every metadata write.** Every write below `LBA_CHUNK_BASE`, or
to the mirror LBA, carries the bytes written as lowercase hex.

Observed `exercise` writes (F = flush):

| Case | Phase 1 / pass 1 | Then | Phase 2 / pass 2 |
|---|---|---|---|
| F-LIVEB-PROMOTE-FLOOR | chunks 4–6, F | A1, B1 and the superblock (mirror, then primary), each flushed | chunks **0–2**, F; A0, B0 and the superblock, each flushed |
| F-LIVEB-RESPOOL-FLOOR | chunks 4–6, F | B1, flushed | none |

Promote's phase 2 is exactly `[0, len)`, after the phase-1 A and B commits and the
step-4 superblock. Re-spool has no pass 2, because no run of 3 chunks at or above
`a_high_water` = 2 is both lower than 4 and disjoint from the live set `{0, 4, 5, 6}`.
The oracle permits that (`if later:`).

## Run

    make -C engine clean all
    make -C tests/wp06_closure_adapter clean all
    python3 tests/wp06_closure_adapter/run_product.py --evidence <fresh dir> \
        --retained tests/wp06_closure_adapter/evidence/p1-r54-product
    python3 tests/wp06_closure_adapter/run_product.py \
        --replay tests/wp06_closure_adapter/evidence/p1-r54-product --out <fresh dir>
    python3 -B tests/wp06_closure_adapter/negative_controls.py <dir>/observations.jsonl

`run_product.py` checks the verifier tree at HEAD, import commit `051d292` on base
`66c6abc6`, and the plan's SHA-256, then retains `observations.jsonl` (8.9 MB, not
committed), a deterministic gzip, `case-census.json` (observed calls and chunk writes
per case, not a verdict), `build-identity.json` and `SHA256SUMS`, and calls
`replay.py`. It exits with `replay.py`'s status. With `--retained` the fresh JSONL
must be byte-identical to the committed evidence; that check runs before replay.

`negative_controls.py` is non-canonical. It prints `oracle.check`'s outcome for every
case, because replay stops at the first failure. It then requires the oracle to reject
one-fact mutations of each passing case's Product evidence (9 in all):

- a write during the Side-A refusal;
- `TAPE_OK` for the full re-spool;
- a missing stage-clear write on arm;
- a still-degraded remount;
- a remount that selects the pre-reset B;
- on both floor rows, a first chunk copy moved onto live-B chunk 3;
- promote with its phase 2 removed;
- a re-spool index write without its `data`.

## Retained evidence (`evidence/p1-r54-product`)

The evidence was produced on Linux with gcc 13.3. CI regenerates it on ubuntu-latest
and requires byte identity; a second local run was already byte-identical.

| File | SHA-256 |
|---|---|
| `wp06c_adapter.c` | `0af5652252d7b51d74dc87523bb439a7232c0a0028d0027e54ae91cbacf96fc9` |
| `observations.jsonl` (8,935,011 bytes, not committed) | `c494589ec12d2648a57b8b062e7a49986eef8d21a3b5996400db0b6114d75b07` |
| `observations.jsonl.gz` | `389d7340acf57800685757ec4d1aba3252b8a1d45718d682690b2514b1c45b83` |
| `build-identity.json` | `a74a70c082f70bc9341784c303b604009e3866909a28a394a6592f9455b759e1` |
| `case-census.json` | `6ad4daa8b4cc288c6c1bc6127a80fd4583346b3d6844da24eb3658a52b4efd61` |

## Exclusions

Full WP-06 closure, the two contract-blocked WP-06e rows (PM #308), WP-10, WP-11,
hardware/card atomicity, release, and any acceptance.
