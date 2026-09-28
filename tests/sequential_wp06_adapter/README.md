# WP-06 R44 sequential product binding

Software-owned binding of the imported, R48-corrected R44 verifier package
`tests/sequential_wp06_r44`.

- Tree `3fe181069f452bbe6c2cd0c252517310690c9915`.
- Verification commit `87d41f58e33e63b7265defcef392d6f4d3219ca7` (Verification #97).
- Oracle SHA-256 `6df1911d…13d8`.
- 38 cases; plan `0a6100ce…6ba0`, unchanged from the superseded tree `21d45071`.

Nothing here edits the verifier tree or decides a verdict. The package's own
`runner.py` and `oracle.check` decide every case.

`wp06_adapter.c` includes only `engine/include`. It builds each case on a fresh
sparse in-memory block device and runs it on a fresh `tape_t`. It records:

- every `tape_*` result;
- the public `tape_get_info` fields;
- every `dev_read`/`dev_write`/`dev_flush` callback in order, including
  injected failures;
- the six raw regions at each named snapshot (superblocks, and the full
  128-block A0/A1/B0/B1 slots), read outside the engine.

It reports no private phase, candidate, selected slot or `free_next`.

## Run

    make -C engine clean all
    make -C tests/sequential_wp06_adapter clean all
    python3 tests/sequential_wp06_adapter/run_product.py --evidence <fresh dir> \
        --retained tests/sequential_wp06_adapter/evidence/p1-r48-product
    python3 tests/sequential_wp06_adapter/run_product.py \
        --replay tests/sequential_wp06_adapter/evidence/p1-r48-product --out <fresh dir>
    python3 -B tests/sequential_wp06_adapter/negative_controls.py <dir>/observations.jsonl

`run_product.py` first checks:

- the verifier tree at HEAD;
- the import commit `29c1470`, whose parent is the declared base `fa25ae07`;
- the issued engine tree `054d27ab`.

It then runs the adapter and writes the unabridged `observations.jsonl`, a
deterministic gzip, `build-identity.json` (sources, build command and
per-case fixture SHA-256), `commit-census.json` and `SHA256SUMS`. Finally it
calls `runner.py`, which writes the non-overwriting manifest bound to the
Product commit/tree and the adapter source SHA-256.

With `--retained`, the fresh JSONL must be byte-identical to the committed
evidence. `--replay` works offline: it checks the committed hashes and replays
the retained JSONL through `runner.py`, with no adapter run.

## Retained evidence

`evidence/p1-r48-product/` holds the gzip (under 1 MiB), so no release asset is
needed. `SHA256SUMS` carries the hash of the decompressed 40 MB JSONL. There is
no committed manifest, because a manifest names the commit that contains it.
CI writes one per run against the head it checked out.

## Binding choices for Verification to audit

**B1 — Base cartridge.** Degraded and refusal fixtures start from one real
cartridge built through the public API:

1. format (nominal 60 s, 21 chunks, fixed UUID);
2. mount B;
3. record 100 frames;
4. commit;
5. promote to completion;
6. unmount.

**B2 — Degradations.** Only named fields are rewritten, and CRCs are
recomputed.

| Case | Rewrite |
|---|---|
| Repair, invalid | Partner superblock zeroed |
| Repair, stale | Partner `sb_generation − 1` |
| Degraded-invalid | B0 and B1 headers zeroed |
| Degraded-divergent | Live B header copied into the other slot at the same sequence, with `frame_count`/`total_frames` halved |
| Refusal, bad A | A0/A1 made equal-sequence divergent the same way |
| Refusal, bad stage | Primary set to `promote_stage = 1`, staging chunk 5 |

Both refusals also make the mirror stale.

**B3 — Repair failure injection.** The first partner write or flush inside
`tape_mount` returns rc 5. The retry uses a new instance on the same device
with healthy callbacks, after unmounting the first.

**B4 — Round trips.** Each round trip formats a fresh device sized for its
own `nominal_length_s`: 60 s (21 chunks) by default, with two exceptions:

- entry-block-boundary uses 128 s (44 chunks);
- max-entries uses 12,175 s (4,097 chunks).

Records append with `TAPE_REC_OVERWRITE` at the timeline end, and every
recording is serviced until owed frames clear. Entry-block-boundary makes 42
preparatory one-frame commits, and max-entries makes 4,095. Each is followed by
the measured recording.

- `TAPE_REC_SPLICE` was not used: engine-api reserves two entries for it, so
  the 4,096th entry would be refused (`TAPE_ERR_INDEX_FULL`).
- The measured `tape_commit` is step `commit`. Earlier commits are in step
  `mount1`.

**B5 — Degraded operations.**

- `dup_source` loops `tape_dup` with budget 65,536 to a blank destination
  device.
- The `reset_b` flow is: `after_reset` snapshot; `remount` (unmount, new
  instance, mount A, info); `after_remount` snapshot; `switch`
  (`tape_set_side(B)`); `exercise` info.

## Product-evidence controls

`negative_controls.py` is non-canonical. It mutates one observed fact of one
case in the Product JSONL and requires the verifier's oracle to reject it. The
unmutated case must pass. The nine mutations are:

- the `tape_reset_side_b` symbol renamed;
- the degraded state not cleared after reset;
- the entry-array callback one block over budget;
- the entry-array callback one block short;
- a two-block header write;
- a missing final commit flush;
- a repair written to the wrong partner;
- a wrong `needs_repair` indicator;
- a refused mount that changed raw media.

## Result

The canonical replay is **PASS, 38 of 38**, with no engine change: engine tree
`054d27ab` is unchanged. That is a Software run of issued tests; it is not
acceptance.

This binding follows the #286 round, which failed 4 of 38 against the
superseded tree `21d45071`. Its two findings, F1 and F2, are resolved in the
verifier by Verification #97:

- **F1:** the `reset_b` operation is the public `tape_reset_side_b`.
- **F2:** the commit budget is the sum of callback `count` in 512-byte blocks,
  at most 97.

The adapter source and the retained evidence bytes are unchanged from #286:

- adapter `4feff86f…`;
- JSONL `ede1620a…`;
- gzip `1ecb3228…`.

Only `build-identity.json` changes, because it names the new verifier tree,
source commit, import commit, base and `run_product.py` digest. The #286
`diagnostic_findings.py` translation is gone; nothing is relabelled.

## Boundary

The following stay outside this tranche: full WP-06/WP-10, card atomicity, the
WP-11 golden/listening check, and hardware. A Software run is evidence, not
acceptance.
