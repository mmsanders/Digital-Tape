# WP-09 R52 capacity short-accept product binding

Software-owned binding of the imported verifier package `tests/capacity_wp09_r52`.

- Tree `85043f530c95257721347a6d991a0d205b299e4f`, Verification #99 commit
  `87ae5746f6892a41d2660d5ef05c4a97b2ea8cf5` (branch
  `verification/issue-99-capacity-short-accept`).
- 27 cases: overwrite/overdub/splice × start/middle/end × 1/17/4095-frame accepted
  prefix; canonical plan `620b8912…b278`.
- Engine tree `054d27ab6e3e72f61118ff7d99e19e48741d05b2`, unchanged from main
  `39d2076`. No engine change was needed.

Nothing here edits the verifier tree or decides a verdict. The package's own
`replay.py` and `oracle.check` decide. The package's synthetic evidence is not used
or cited here.

## What the adapter does

`capacity_adapter.c` includes only `engine/include` and does not import the oracle.
One invocation runs one plan row on a fresh flat device and prints one JSON object.
`run_product.py` reads each row from `evidence/plan.json`, passes the row plus the
two package-defined inputs ADAPTER.md names (the stimulus sample `oracle.input_sample`
and the 4,096-frame prefill split `oracle.prefill_requests`, both restated from their
published definitions, not imported), then encodes the PCM as zlib-9 + base64, adds
`fixture_sha256` over canonical `raw_before`, and calls `replay.py`.

Per row, in order, with every callback logged under the causing call's step:

1. Write the raw stage-0 fixture directly to media (no callbacks) and snapshot it.
2. `tape_mount(B)`, `tape_get_info`, `tape_seek(at)`, `tape_arm(mode)`.
3. Each prefill feed (`feed-NNNN`), then `tape_service(budget)` until `more_work`
   is false (`service-NNNN`, one record per call).
4. `feed-final`, then `tape_commit` once before any service (`premature-commit`),
   then service the accepted prefix to completion.
5. `tape_status`, `tape_commit`, `tape_unmount`, a fresh `tape_init`,
   `tape_mount(B)` (`remount`), `tape_get_info`.
6. `tape_seek(0)` and `tape_set_rate(1.0)` (`render-setup`), then render the whole
   timeline: service to `more_work == false` (`render-service`), then
   `tape_render` of up to 8,192 frames (`render`), repeated. Only `tape_render`'s
   own callbacks count toward `events_from_call`.
7. Snapshot raw media after.

## Fixture choices beyond ADAPTER.md's bullets

ADAPTER.md fixes the fields the oracle parses. Two further choices are needed for
a real engine to mount the media at all; both come from the frozen spec, not from
Product source:

- **A spec-valid superblock.** The package's synthetic stand-in writes only the
  fields the oracle reads (and a `block_count` at offset 36, where tapefs §4
  defines `sample_rate`). The Product fixture fills every §4 field:
  version 1.0, `sb_generation` 7, the §1 constants, the §3 LBAs, mirror at
  `block_count − 1`, label `WP09-R52`, epoch 1, and `nominal_length_s` 9 / 12 / 15 s,
  the smallest labels whose §2 ceiling derives exactly 4 / 5 / 6 chunks, so
  §4.1 phase 2's GEOMETRY_OK equality holds. UUID is ASCII `WP09-R52-capshrt`.
- **An empty Side-A index.** tapefs §4.2 step 1 fails any mount whose Side A has
  no selectable index. A0 is a valid zero-entry Side-A slot at sequence 1; A1 is
  zero. Neither is in the raw snapshot the oracle reads.

## Render piece size

The adapter first rendered in 4,096-frame pieces. Every chunk block was then read
exactly four times: each service after a render re-read the whole 16,384-frame
ring window. That is an engine playback-efficiency observation outside this
tranche's assertions, noted for PM, not changed here. Rendering half a ring
(8,192 frames) per call reads each block about twice and keeps the retained gzip
under the 1 MiB evidence limit. A full-ring request renders every frame but
reports `TAPE_ERR_UNDERRUN`, because a whole ring is never available at once.

## Run

    make -C engine clean all
    make -C tests/capacity_wp09_adapter clean all
    python3 tests/capacity_wp09_adapter/run_product.py --evidence <fresh dir> \
        --retained tests/capacity_wp09_adapter/evidence/p1-r53-product
    python3 tests/capacity_wp09_adapter/run_product.py \
        --replay tests/capacity_wp09_adapter/evidence/p1-r53-product --out <fresh dir>
    python3 -B tests/capacity_wp09_adapter/negative_controls.py <dir>/observations.jsonl

`run_product.py` first checks the verifier tree at HEAD, the import commit whose
parent is base `39d2076`, and the plan file's SHA-256. It writes the unabridged
`observations.jsonl` (14.7 MB, not committed), a deterministic gzip,
`case-census.json` (observed facts per case, not a verdict), `build-identity.json`
and `SHA256SUMS`, then calls `replay.py`, which writes the non-overwriting manifest
bound to the Product commit/tree and adapter source SHA-256. With `--retained`, the
fresh JSONL must be byte-identical to the committed evidence. `--replay` works
offline and runs no adapter.

`negative_controls.py` is non-canonical. It requires the verifier's oracle to
reject ten single-fact mutations of this Product evidence: a dropped case, a wrong
accepted count, feed I/O, an OK premature commit, an allocation below the floor, a
missing final commit flush, a missing B1 remount read, one flipped PCM bit, a stale
`free_chunks`, and a spoofed `PASS` label on corrupt PCM.

## Retained evidence (`evidence/p1-r53-product`)

Produced on Windows with MSYS2 UCRT64 gcc 16.2; the CI job regenerates it on
ubuntu-latest and requires byte identity.

| File | SHA-256 |
|---|---|
| `observations.jsonl` (not committed) | `30cef46bd2777f6e4fb8dd5cea255aed8071c6fc53f2e21c1eb09408ba71bc58` |
| `observations.jsonl.gz` | `a43dbfa7caf49023fda09c902b3509ab28b8c7946cb569d927435e7f6bc07bf9` |
| `build-identity.json` | `d59b7e3af6c092fa347ae4b584cb83fc88e13743aab61a994af4b8b00b16a586` |
| `case-census.json` | `53b6b19f8ccc8cb7244d68416e6736635594f8bc188286e84808227f0360958a` |

## Exclusions

Not claimed: the existing 10,000-edit history, full WP-09 or WP-10, WP-11
listening, hardware/card atomicity, release, and any acceptance. A passing replay is
mechanical evidence for independent Verification disposition, not self-acceptance.
