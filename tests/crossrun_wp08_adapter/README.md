# WP-08 R44 cross-run playback product binding

Software-owned binding of the imported R44 verifier package
`tests/crossrun_wp08_r44`.

- Tree `9ed67a8594476822ba5ee35e07a1bf048e23100e`.
- Verification PR #93 head `58ca7599157d1da7c13794fb0f0859feb2210374`.
- 33 cases; plan `08f584f6…7d6c`.

Nothing here edits the verifier tree or decides a verdict. The package's own
`replay.py` and `oracle.check` decide every case.

`wp08_adapter.c` includes only `engine/include` and does not import the oracle.
The case table is written out by hand, and `replay.py`'s census rejects a
missing, extra or duplicated case. For every case the adapter records:

- every `tape_service` call: budget, result, `more_work`, and each device
  callback (`op`, `lba`, `count`) made during that call;
- every `tape_render` call: requested and rendered frames, the exact output PCM,
  and the callbacks made during that call;
- after each render, the public `tape_tell` frame and the `tape_status`
  `at_start`/`at_end` flags;
- the raw media: the primary superblock, both B-slot header blocks with their
  CRC-covered entry bytes, and the first block of every chunk the live B index
  names. These are read directly from the device buffer, never through the
  engine.

It reports no hidden position, run label or block total.

## Run

    make -C engine clean all
    make -C tests/crossrun_wp08_adapter clean all
    python3 tests/crossrun_wp08_adapter/run_product.py --evidence <fresh dir> \
        --retained tests/crossrun_wp08_adapter/evidence/p1-r46-product
    python3 tests/crossrun_wp08_adapter/run_product.py \
        --replay tests/crossrun_wp08_adapter/evidence/p1-r46-product --out <fresh dir>
    python3 -B tests/crossrun_wp08_adapter/negative_controls.py <dir>/observations.jsonl

`run_product.py` first checks:

- the verifier tree at HEAD;
- the import commit `2928853`, whose parent is the declared base `2890ea1e`;
- the issued engine tree `054d27ab`.

It then writes `observations.jsonl`, `fixture.json` (every non-zero block of the
constructed image), `build-identity.json` and `SHA256SUMS`. Finally it calls
`replay.py`, which writes the non-overwriting manifest bound to the Product
commit/tree and the adapter source SHA-256.

With `--retained`, the fresh JSONL and fixture must be byte-identical to the
committed evidence. `--replay` works offline and runs no adapter.

`negative_controls.py` is non-canonical. It mutates one observed fact of one
case in the Product JSONL and requires the verifier's oracle to reject it. The
seven mutations are: output PCM, tell, an endpoint flag, render I/O, service
over budget, raw chunk PCM, and an incomplete service.

## Retained evidence

`evidence/p1-r46-product/` holds the 358,800-byte JSONL, which is under 1 MiB,
so no release asset is needed. There is no committed manifest, because a
manifest names the commit that contains it. CI writes one per run against the
head it checked out.

## Binding choices for Verification to audit

**B1 — Fixture.**

1. `tape_format` a blank 60 s device: 21 chunks, `a_high_water` 0, so it has
   empty Side A and Side B indices.
2. Write one new Side B index into the B slot that does not hold the higher
   valid sequence (B1 on this image), at sequence (highest existing + 1),
   `side` 1. It has four entries `{chunk 1..4, start_frame 0, 5/3/7/2 frames}`,
   `total_frames` 17, and a CRC32 over bytes 0–59 plus the entry array,
   computed in the adapter.
3. Write the seeded frames, little-endian interleaved from frame 0, into the
   first block of chunks 1–4. The frames come from xorshift32 from
   `0xA51CE55D`: left = low 16 bits − 32768, right = high 16 bits − 32768.

The superblock is the engine's own format output, unmodified.

**B2 — Isolation.** Each variant (whole/single/uneven) restores the constructed
image and starts a new instance: `tape_init`, then `tape_mount(B)`,
`tape_seek`, `tape_set_rate`. The seek, rate and mount results are reported as
extra fields.

**B3 — Service.** The adapter calls `tape_service(budget)` until `more_work`
is false, and only then renders. No service call runs between renders.

**B4 — Raw snapshot.** The snapshot is taken after the case. Playback issues no
writes, so it equals the constructed image; `fixture.json` retains that image
separately.

## Result

**PASS, 33 of 33** in the canonical replay. That is a Software run of issued
tests; it is not acceptance. This is non-listening arithmetic coverage only.
It is not WP-11 goldens, full WP-08, hardware timing, two-toolchain portability
or side-switch transition coverage.
