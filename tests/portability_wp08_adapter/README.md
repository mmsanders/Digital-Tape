# WP-08 R52 two-toolchain playback product binding

Software-owned binding of the imported verifier package `tests/portability_wp08_r52`.

- Tree `d1ba52f7a756ee982cdcf03e0369a2b91bc44301`, Verification #103 / PR #102 commit
  `3dbd22520f0c9d30da38d60fe883c7b4f8e9fbe7` (branch
  `verification/issue-100-playback-portability`).
- 41 vectors; canonical plan `6a8a87b1…b763c`; oracle `c8d497f1…7933`.
- Engine tree `054d27ab6e3e72f61118ff7d99e19e48741d05b2`, unchanged from main
  `39d2076`. No implementation fix was required: reverse frame 0 and the reverse
  grid snap already behave as the oracle's model and the literal golden require.

**Canonical result, from the package's own `oracle.parse_jsonl`: FAIL, `setup trace`,
on every vector.** This is a public-contract blocker in the oracle, not an engine
defect; see [Blocker](#blocker-the-setup-trace-forbids-mount-and-service-io).

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

Each call's trace entry carries exactly the oracle's fields, and its `block_events`
list holds every callback it caused. Raw-media fields are top-level additions.

## Blocker: the setup trace forbids mount and service I/O

`oracle.check` requires the first four trace entries to equal fixed dicts in which
`tape_mount` and `tape_service` have `"block_events": []`. The package's
`reference_adapter.c` is a pure arithmetic model with no device, and it prints those
empty lists as literals. A device-backed engine cannot satisfy them:

- `tape_mount` must read both superblock copies and the index slots (tapefs §4.1–§4.2).
  It made callbacks on all 41 vectors.
- `tape_service` is where the engine fetches PCM into the play ring (Engine API §6).
  It made callbacks on 39 vectors; the two exceptions are the empty-timeline rows.

ADAPTER.md requires recording "every callback caused by each public call" and forbids
filtering events or rewriting consumed fields. So a faithful binding must fail the
setup trace. Suggested correction for Verification: require `block_events == []` only
for `tape_render` (and seek/set_rate, which were empty here). For mount and service,
either leave the lists unconstrained or assert something checkable about them, such
as read-only operations within the fixture's LBAs.

What the rest of the oracle concludes is shown, as information only, by
`negative_controls.py`. It runs `oracle.check` on a copy with the four setup lists
blanked and nothing else touched. **41/41 vectors pass** on exact PCM, tell,
endpoint flags, render count, an empty render callback list, one service call, and
the literal `[0,1000,2000]` → `2000,1000,0` golden (rendered 3, tell 0, `at_start`).
That relaxed result is not a verdict.

## Run

    python3 tests/portability_wp08_adapter/run_product.py --evidence <fresh dir> \
        --retained tests/portability_wp08_adapter/evidence/p1-r53-product
    python3 tests/portability_wp08_adapter/run_product.py \
        --replay tests/portability_wp08_adapter/evidence/p1-r53-product
    python3 -B tests/portability_wp08_adapter/negative_controls.py \
        tests/portability_wp08_adapter/evidence/p1-r53-product

Compilers default to `gcc` and `clang` on PATH (`--gcc` and `--clang` override). A
missing compiler, a failed build or run, or any byte of divergence is a hard failure.
`--retained` requires the fresh streams to equal the committed ones. `--replay` works
offline: it verifies the retained files, requires GCC ≡ Clang, and applies the oracle.

`negative_controls.py` is non-canonical. On the relaxed copy it requires the oracle to
reject a flipped PCM nibble, tell drift, a flipped `at_start`, a short render, a
render callback, and the `d5772c8` land-and-stop defect on the literal golden vector.
It also requires a one-byte Clang divergence to be detected. Result: 7/7 killed.

## Retained evidence (`evidence/p1-r53-product`)

Produced on Windows: GCC `gcc.EXE (Rev4, Built by MSYS2 project) 16.2.0` and Clang
`clang version 22.1.8` (MSYS2 UCRT64), both with the package flags. The CI job
regenerates it with ubuntu-latest's GCC and Clang and requires byte identity. A second
local run regenerated it byte-identically, and the stream equals the one ubuntu-latest's
GCC 13.3.0 and Clang 18.1.3 produced in CI: four builds, one byte stream.

The adapter writes its stream to a file opened `"wb"`. The first retained evidence
went through `stdout`, whose text mode on Windows turned each of the 41 newlines into
CRLF. That was the only difference from the Linux stream, and it is why that first CI
regeneration did not match.

| File | SHA-256 |
|---|---|
| stream (either compiler, uncompressed) | `2f6ed528d01d188b284ef5d481140c4721922ce1d60c227e1223c961948cef47` |
| `gcc.jsonl.gz` = `clang.jsonl.gz` | `906f5790ac5fa35e5df4642c63057c8f5f979f08f64866ef3da00dab0548fe4d` |
| `manifest.json` (compiler identities, flags, adapter, header, engine tree) | `078cbaedef27a968b7f9639455e7b030bfee248173517773df7260344b90b2f9` |

## Exclusions

The WP-11 portability gate (embedded target, narrow `int`, 1.5M-pair differential),
listening and goldens, complete WP-08, WP-10, hardware, release, and any acceptance.
