# WP-08 R52 two-toolchain playback product binding

Software-owned binding of the imported verifier package `tests/portability_wp08_r52`.

- Tree `d803deeff4356b6f70ff7f255c9bd6f31aa09790`, from Verification #114 / PR #102
  commit `b843298b55a17d450905bc1ae56c4092f9cffa14` (branch
  `verification/issue-100-playback-portability`). It supersedes tree `d1ba52f7`, which
  was only on held #316.
- 41 vectors; canonical plan `6a8a87b1…b763c`, unchanged; oracle `5b5f1612…6559`;
  ADAPTER.md `5ce98138…ec9f`.
- Built on main `66c6abc6` (before #318); engine tree `054d27ab…`. The manifest
  records the engine tree, which is not pinned (the #320 pattern). No implementation
  fix was required.

**Canonical result, from the package's own `oracle.parse_jsonl`: PASS, 41 of 41.** The
GCC and Clang streams are byte-identical. This is returned for independent Verification
disposition; it is not acceptance.

## What runs

`run_product.py` writes `plan_vectors.h` from `evidence/plan.json` (each row verbatim,
plus its fixture identity as the package defines it: SHA-256 of the row's canonical
JSON). It then compiles **`engine/src/*.c` together with `wp08p_adapter.c`** twice,
once with GCC and once with Clang, using the package's `toolchains.FLAGS`
(`-std=c99 -O2 -Wall -Wextra -Werror -fno-strict-overflow`). The engine arithmetic
itself is therefore built by each compiler, not linked from one archive. It runs
both binaries and refuses to continue unless the two complete streams are
byte-identical, then applies `oracle.parse_jsonl` to the stream.

Per row, on a fresh device, `wp08p_adapter.c` builds a valid cartridge: every tapefs
§4 superblock field, an empty Side-A index, and B0 with one entry per plan run,
run *k* at chunk 2k+1 from frame 100, so runs are physically scattered and off chunk
start. It records the raw superblock, the B0 header with its CRC-covered entry bytes,
B1, and each run's PCM bytes. Then it performs ADAPTER.md's script:

1. `tape_mount(B)`
2. `tape_seek(seek)`
3. `tape_set_rate(rate)`
4. `tape_service(7)` until `more_work == false` (every call recorded)
5. one `tape_render(requested)`
6. `tape_tell` and `tape_status`

Each call's trace entry carries exactly the oracle's fields. Its `block_events` list
holds every callback that call caused, unfiltered, as `{op, lba, count, rc}` or
`{op: flush, rc}`. The fixture's `block_count` is at the top level (R53), and raw-media
fields are further top-level additions.

Observed callbacks:

- `tape_mount` reads on all 41 vectors, including both superblock copies.
- `tape_service` reads on 39 vectors; the two empty-timeline rows make no reads.
- Neither call writes or flushes.
- `tape_seek`, `tape_set_rate` and `tape_render` make no callbacks.

## Run

    python3 tests/portability_wp08_adapter/run_product.py --evidence <fresh dir> \
        --retained tests/portability_wp08_adapter/evidence/p1-r54-product
    python3 tests/portability_wp08_adapter/run_product.py \
        --replay tests/portability_wp08_adapter/evidence/p1-r54-product
    python3 -B tests/portability_wp08_adapter/negative_controls.py \
        tests/portability_wp08_adapter/evidence/p1-r54-product

Compilers default to `gcc` and `clang` on PATH (`--gcc` and `--clang` override). A
missing compiler, a failed build or run, or any byte of divergence is a hard failure.
`--retained` requires the fresh streams to equal the committed ones. `--replay` works
offline: it verifies the retained files, requires GCC ≡ Clang, and applies the oracle.

`negative_controls.py` is non-canonical. It prints `oracle.check`'s outcome per vector,
then requires the oracle to reject each of these mutations of this Product's records:

- a flipped PCM nibble;
- tell drift;
- a flipped `at_start`;
- a short render;
- a render callback;
- the `d5772c8` land-and-stop defect on the literal golden vector;
- a mount write;
- a service flush;
- a mount that skips the mirror superblock;
- a service read outside the device;
- a seek callback;
- a non-addressable `block_count`.

It also requires a one-byte Clang divergence to be detected. Result: 13/13 killed.

## Retained evidence (`evidence/p1-r54-product`)

The evidence was produced on Linux with GCC `gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0`
and Clang `Ubuntu clang version 18.1.3 (1ubuntu1)`, both with the package flags. A
second local run regenerated it byte-identically, and CI regenerates it on ubuntu-latest
and requires byte identity. The adapter writes its stream to a file opened `"wb"`, as
carried from #316.

| File | SHA-256 |
|---|---|
| `wp08p_adapter.c` | `0246a30b55d14239ebeb9c1a0e8c71550a8fed82dcdbda8c618eada75e27b38c` |
| stream (either compiler, 186,344 bytes uncompressed) | `8a2369d663a06cad91c205397d6a3a4e0af81706129328843b08613b09bcdd8b` |
| `gcc.jsonl.gz` = `clang.jsonl.gz` | `b100b5641e7f1612b02f9ef63913f9502697d61dfb019d7551907a94459de950` |
| `manifest.json` (compiler identities, flags, adapter, header, engine tree) | `b7740435804669bc37a84c2deff1264682c7f3f58eaf3f910ba124714e876a82` |

## Exclusions

The WP-11 portability gate (embedded target, narrow `int`, 1.5M-pair differential),
listening and goldens, complete WP-08, WP-10, hardware, release, and any acceptance.
