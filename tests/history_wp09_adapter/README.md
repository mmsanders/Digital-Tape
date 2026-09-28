# WP-09 R44 seeded record-history product binding

Software-owned binding of the imported R44 verifier package
`tests/history_wp09_r44`.

- Tree `fa4e2d1686914f9dfe9aa8c6c7705bdbfce0266f`.
- Verification PR #92 head `5c7121872e0fa4b9a4570b018fccd8eb6ddd0d5a`.
- 10,000 edits, 25 checkpoints; plan `c41c8159…e19c`.

Nothing here edits the verifier tree or decides a verdict. The package's own
`replay.py` and `oracle.check` decide the history. The package's
`evidence/synthetic.jsonl.gz` is verifier reproducibility material; it is not
used or cited here.

`wp09_adapter.c` includes only `engine/include` and does not import the oracle.
It generates the edit schedule itself from seed `0x9E3779B9` and the rules
`ADAPTER.md` names. The oracle's "edit schedule drift" and per-edit input
SHA-256 checks reject any divergence from `oracle.edits()`.

## One continuous history

1. `tape_format` a blank sparse device sized for 12,000 chunks, which is more
   than the 10,000 fresh allocations the history can make.
2. Mount Side B on one engine instance.
3. For every edit: `tape_seek(at)`, `tape_arm(mode)`, one `tape_feed` of the
   exact frames, `tape_service(256)` while `tape_status.frames_owed`, then
   `tape_commit`.

Every public result is recorded, along with every device callback in order
(`step`, `op`, `lba`, `count`, per-edit `ordinal`, `rc`). A failing call is
recorded and the history continues: nothing restarts, and no edit is skipped.

**Checkpoint (every 400th edit).**

1. At multiples of 800, `tape_unmount`, then a fresh `tape_init` and
   `tape_mount(B)` on the same device. `mount_events` records the callbacks
   made during that mount.
2. `tape_seek(0)` and `tape_set_rate(1.0)`.
3. Service until `more_work` is false, then render in 4,096-frame pieces until
   `total_frames` are out. Only `tape_render`'s callbacks go in
   `render_block_events`.
4. Record the public `tape_get_info` fields.
5. Read the raw bytes directly from the device, outside callback accounting:
   the candidate superblock (the valid copy with the higher `sb_generation`,
   primary on a tie), and both B-slot headers with exactly
   `entry_count × 12` entry bytes.

No selected-slot or `free_next` value is reported.

## Run

    make -C engine clean all
    make -C tests/history_wp09_adapter clean all
    python3 tests/history_wp09_adapter/run_product.py --evidence <fresh dir> \
        --retained tests/history_wp09_adapter/evidence/p1-r46-product
    python3 tests/history_wp09_adapter/run_product.py \
        --replay tests/history_wp09_adapter/evidence/p1-r46-product --out <fresh dir>
    python3 -B tests/history_wp09_adapter/negative_controls.py <dir>/observations.jsonl

`run_product.py` first checks:

- the verifier tree at HEAD;
- the import commit `d48e66b`, whose parent is the declared base `2890ea1e`;
- the issued engine tree `054d27ab`.

It then writes the unabridged `observations.jsonl` (9 MB), a deterministic
gzip, `build-identity.json` and `SHA256SUMS`. Finally it calls `replay.py`,
which writes the non-overwriting manifest bound to the Product commit/tree and
the adapter source SHA-256.

With `--retained`, the fresh JSONL must be byte-identical to the committed
evidence. `--replay` works offline and runs no adapter.

`negative_controls.py` is non-canonical. It requires the oracle to reject eight
single-fact mutations of this Product history:

- checkpoint PCM;
- a dropped final edit;
- a short accept;
- a restarted ID;
- a missing final commit flush;
- stale free chunks after remount;
- a missing B1 read on remount;
- render I/O.

## Retained evidence

`evidence/p1-r46-product/observations.jsonl.gz` is 726,593 bytes, under the
1 MiB tree limit. It is the complete raw history, losslessly compressed.
`SHA256SUMS` carries the hash of the decompressed JSONL. There is no committed
manifest, because a manifest names the commit that contains it. CI writes one
per run against the head it checked out.

## Result

**PASS**: 10,000 edits (3,334 overwrite, 3,333 overdub, 3,333 splice) and 25
checkpoints, 12 of them after a remount, with no engine change. That is a
Software run of issued tests; it is not acceptance.

The following stay outside this tranche:

- positive `TAPE_OK` short accept (excluded by the frozen contract);
- capacity short accept;
- full WP-09/WP-10;
- listened PCM and WP-11;
- hardware and card qualification.
