# WP-10 R53 crash-injection product binding

Software-owned binding of the imported verifier package `tests/wp10_closure_r53`.

- Tree `2a514c902b9b38901abe6841017cc110987c1ecd`, Verification #105 / PR #109 commit
  `86904a30765eb415d1283fcd1cbb511f2569ed7c` (branch `verification/issue-105-wp10-closure`).
- Ledger `369566e2…27817`, case set `72717654…bf0e`. `model.py`'s pinned
  `format_dup_identity_draft8/fixture.py` blob `86df43a2` equals main's copy.
- Base: current main `6e88b0f`. Only docs changed since `39d2076`.

**Canonical result, decided by the package's own `replay.py`: PASS, 57,539 / 57,539.**
That is 57,532 exhaustive injections (28,766 flush-required and 28,766 write-through)
plus 6 completion cases and 1 empty-family case. There were zero `TAPE_ERR_CRC`
answers at the blank-mirror boundary; per the PM ruling, the engine's choice there is
unchanged.

## Engine fix, required by the package

Engine tree `054d27ab` → `81ad8ec2`, one change in `engine/src/raw_ops.c`.

For an **empty source**, tapefs §9.5 step 3 writes A0 and B0 as zero-entry headers
"exactly as `tape_format` §9.6 step 3 does": both headers, then **one** flush. The
duplicate instead flushed after each header (`A0h, F, B0h, F`), because its A0-header
phase always used the write-and-flush helper. The first run failed 6,171 cases on
that: every empty-source injection from the A0-header write on, plus the empty
completion traces. Format already did it right. The fix writes A0's header without
its own flush when the source is empty, so B0's write-and-flush produces
`A0h, B0h, F`. Non-empty duplicates are unchanged. That is the only difference
between the first and final runs.

**Effect on other accepted bindings.** Three Software bindings pin the old engine tree
in `run_product.py`: `crossrun_wp08_adapter`, `history_wp09_adapter` and
`sequential_wp06_adapter`. Their CI jobs fail provenance on this branch for that reason
alone. Run locally on the patched engine with only the pin check disabled (not
committed), all three regenerate their retained evidence **byte-identically**, once
Windows' text-mode CRLF (10,000 / 38 / 33 CRs) is normalised. Re-pinning accepted
bindings is not mechanical; it is returned to PM, and this branch does not edit those
pins.

## What runs

`run_product.py` writes the adapter's input from the package's own builders:

- the three destination shapes from `model.destination`;
- the 128-frame source: pinned-builder superblock with `high` 1, A0 `[(0,0,128)]` and
  B0 `[(0,0,128)]` via `model.index_blocks`, and chunk 0 block 0 = `model.SOURCE_AUDIO`;
- the tracked LBAs in sorted-name order;
- the UUIDs;
- the case list in `oracle.iter_cases()` order, restated from `model.injections`
  (three lines), so the oracle is never imported.

The empty source is a blank device written once by the Product `tape_format`.

`wp10c_adapter.c` includes only `engine/include` and runs every case on sparse
caller-owned devices. The destination injects exactly one power cut:

- `["write", k, landed]` cuts power during the k-th write callback. The first `landed`
  bytes of that block land over the durable contents.
- `["flush", j]` cuts power inside the j-th flush.

After the cut the device is dead: every later callback fails and is not traced. In
write-through mode every completed write is durable at once. In flush-required mode,
completed writes since the last flush are pending; the durable subset is fixed by the
case index, in the same enumeration order as `model.possible_images`. A torn block is
applied last.

The trace (`trace_sha256`) lists writes and flushes in ADAPTER.md's trace format. Reads
have no trace-format form and are not listed; `repair_events` is the same. The
empty-family `block_events` list every callback, reads included.

Each remount runs on a fresh device holding the durable bytes: `ro_A` (`write = NULL`),
`rw_A` (plus `pcm_sha256` of rendering the whole side at 1.0× from frame 0), and `rw_B`.

The dup source is a separate writable device, so a source write would be caught. Its
image hash is computed once per source fixture and recomputed after the operation only
if any write reached it. None did.

`complete` runs uninjected under flush-required semantics, so only flushed data counts
as durable. `empty_family` mounts the completed empty copy on Side B, then calls
promote, re-spool, arm and a zero-frame commit.

## Run

    make -C engine clean all
    make -C tests/wp10_closure_adapter clean all
    python3 tests/wp10_closure_adapter/run_product.py --evidence <fresh dir> \
        --retained tests/wp10_closure_adapter/evidence/p1-r53-product
    python3 tests/wp10_closure_adapter/run_product.py \
        --replay tests/wp10_closure_adapter/evidence/p1-r53-product --out <fresh dir>
    python3 -B tests/wp10_closure_adapter/negative_controls.py <dir>/observations.jsonl.gz

The adapter writes its JSONL to a file opened `"wb"`, so no platform translates line
endings. `negative_controls.py` is non-canonical. It requires the oracle to reject
single-fact mutations of real Product observations: trace order, durable bytes,
remount info, phase-4 repair, rendered audio, a written source, an unfired injection,
and an accepting empty promote. Result: 8/8 killed.

## Census (`evidence/p1-r53-product/case-census.json`, observed facts, not a verdict)

| Scenario | Flush-required | Write-through |
|---|---:|---:|
| DUP-EMPTY-BLANK | 4,108 | 4,108 |
| DUP-EMPTY-REUSABLE | 5,136 | 5,136 |
| DUP-REUSABLE-STALE | 6,679 | 6,679 |
| FMT-REUSABLE-STALE | 4,110 | 4,110 |
| FMT-BLANK | 3,082 | 3,082 |
| DUP-BLANK | 5,651 | 5,651 |

All 57,532 injections fired. Across all cases, each of the three remounts returned
`TAPE_OK` 9,179 times, `TAPE_ERR_INCOMPLETE` 25,769 times and `TAPE_ERR_BAD_MAGIC`
22,590 times; 18,140 remounts performed a phase-4 repair.

## Retained evidence (`evidence/p1-r53-product`)

Produced on Windows (MSYS2 UCRT64 gcc 16.2, OpenSSL) and regenerated byte-identically;
CI regenerates it on Linux. Under 1 MiB, so it is in-tree.

| File | SHA-256 |
|---|---|
| `observations.jsonl` (43 MB, not committed) | `26472ddbf65c99c032845caaddbbbe081322c5403df47a0e9dbbe54de22b280d` |
| `observations.jsonl.gz` (669,781 bytes) | `cbe3691a5d24a9a86056286b8fa1cdb0110a62a52cd49a6b62edd72427cb3438` |
| `build-identity.json` | `5d219d3c11240f8c681ff6234b4388a2ba843cfde91ea0979508813bb2edfc57` |
| `case-census.json` | `9c3da35bc002d600c25dbd723c09950df5f9206a8e88419a55d26d4032002d44` |

## Exclusions

The 48 already-accepted ledger rows (not re-run), the 9 backlog rows, WP-12/WP-12a,
WP-11, card atomicity, hardware, release, any acceptance, and any complete WP-10 claim.
