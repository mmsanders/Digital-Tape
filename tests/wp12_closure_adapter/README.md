# WP-12/WP-12a R53 closure-gap product binding

Software-owned binding of the imported verifier package `tests/wp12_closure_r53`.

- Tree `5641e39d5b72f367468e2a8d121f6a0e6106fc2f`, from Verification #115 / PR #106
  commit `c65ed4357c9d4b9fe915910e0a669d335e611a80` (branch
  `verification/issue-104-wp12-closure`). It supersedes tree `928fba57`, which was only
  on held #317.
- 3 gap rows and 7 cases. The ledger `795c05fe…6076d4` is unchanged; the canonical plan
  is `55e36eac…97dc`. `fixtures.py`'s pinned blobs (`respool_draft8/oracle.py`
  `3c63f190`, `promote_draft8/fixture.py` `51c676bf`) still equal the copies on main.
- Built on main `66c6abc6` (before #318); engine tree `054d27ab…`. `build-identity.json`
  records the engine tree, which is not pinned (the #320 pattern).

**Canonical result, decided by the package's own `replay.py`: PASS, 7 of 7.** This is
returned for independent Verification disposition; it is not acceptance.

## What runs

`run_product.py` writes each case's whole device image from the package's own
fixture builders. For the render and `respool_v3_003` fixtures that is
`fixtures.render_media` / `fixtures.respool_fault_media` (the pinned
`respool_draft8` builder), with `fixtures.chunk_audio(c)` in every chunk a live
Side-B entry references. For `promote_fresh_alloc_full` it is
`promote_draft8.scenario_initial("fresh_alloc_full")`, block for block. The package
oracle is never imported.

`wp12c_adapter.c` includes only `engine/include`. It loads the image into a
caller-owned simulator, reports the fixture metadata read back from the device
before mount (the driver hashes it into `fixture_metadata_sha256`), and follows
ADAPTER.md.

**Render cases.** Mount B. Then `pre`: `tape_seek(0)`, `tape_set_rate(65536)`,
repeatedly service (budget 64) to `more_work == false` and render 4,096 frames until a
render returns fewer; then tell, status and `tape_set_rate(0)`. Then
`tape_respool(64)` until done, recording raw B0/B1. Then `post_same_session`,
unmount, a fresh mount of B, and `post_remount`. Only `tape_render`'s own callbacks
are listed per render; service I/O is not part of the render record.

**Fault cases.** Mount, then call the operation with the plan budget. The simulator
fails exactly the planned callback and returns `1`; Engine API §3 requires only
non-zero, and the oracle requires a non-negative code. After the failing call
comes the whole-device hash, then the 15 probe columns in plan order on the same
instance, each with its own callback list. `dup` gets a separate blank destination
simulator whose callbacks are listed separately. The device is hashed again just
before the `unmount` probe. If the planned failure is never reached, the operation
runs to completion and the probes run anyway, so the evidence shows exactly what
happened.

**Injection rule (R53).** Three rows use `first_on_continuation`: F-RESPOOL-WRITE,
F-PROMOTE-WRITE and F-PROMOTE-FLUSH. The simulator fails the first own-device callback
of the planned kind on any continuation call (index ≥ 1). F-RESPOOL-HEADER-FLUSH keeps
`first_after_write`: the first flush after the pass-1 B1 header write at LBA 392. Every
fault case emits a top-level `fault_call_index` naming the call the failure fired on.

| Case | Budget | `fault_call_index` | Calls before it |
|---|---:|---:|---|
| F-RESPOOL-WRITE | 64 | 1 | call 0: 32 chunk writes, `TAPE_OK`, `more_work` |
| F-RESPOOL-HEADER-FLUSH | 64 | 64 | calls 0–63: `TAPE_OK`, `more_work` |
| F-PROMOTE-WRITE | 1 | 2 | calls 0–1: one read each, no write |
| F-PROMOTE-FLUSH | 1 | 2 | calls 0–1: one read each, no flush |

The promote shape is the one the #317 diagnostic reported. At budget 1 the Product
counts reads as blocks of work (Engine API §9), so calls 0 and 1 each read one chunk
block, and call 2 is the first to write and flush.

After each fault:

- every F column returned `TAPE_ERR_FAULTED` with zero callbacks;
- every allowed column (`render`, `status_info_tell`, `abort`, `unmount`) returned
  `TAPE_OK`;
- `dup` touched no destination;
- the device hash was unchanged up to the unmount probe.

## Run

    make -C engine clean all
    make -C tests/wp12_closure_adapter clean all
    python3 tests/wp12_closure_adapter/run_product.py --evidence <fresh dir> \
        --retained tests/wp12_closure_adapter/evidence/p1-r54-product
    python3 tests/wp12_closure_adapter/run_product.py \
        --replay tests/wp12_closure_adapter/evidence/p1-r54-product --out <fresh dir>
    python3 -B tests/wp12_closure_adapter/negative_controls.py <dir>/observations.jsonl.gz

`run_product.py` checks the verifier tree at HEAD, import `1c1c036` on base `66c6abc6`
and the plan's SHA-256, then retains a deterministic gzip, `case-census.json`
(observed calls, probe results and render facts per case, not a verdict),
`build-identity.json` and `SHA256SUMS`, and exits with `replay.py`'s status.
`--retained` requires byte identity with the committed evidence.

`negative_controls.py` is non-canonical. It prints every case's outcome, then
requires the oracle to reject these causal mutations of each passing case:

- wrong PCM (TWOPASS);
- a dropped final frame (DECLINE);
- render I/O (FRAGMENTED);
- service I/O on the faulted instance (RESPOOL-WRITE, PROMOTE-WRITE);
- `arm` accepted after the fault (RESPOOL-HEADER-FLUSH, PROMOTE-FLUSH);
- on all four fault cases, a `fault_call_index` that does not name the failing
  continuation.

Result: 11/11 killed. #317's call-2 diagnostic (`--adapter`) is removed, because the
plan now places the injection itself.

## Retained evidence (`evidence/p1-r54-product`)

The evidence was produced on Linux (gcc 13.3, OpenSSL for device hashes). It
regenerated byte-identically, and CI regenerates it on ubuntu-latest.

| File | SHA-256 |
|---|---|
| `wp12c_adapter.c` | `05d906fb14f224c77cd721cccfdc3be466faed0b0bcf73a02d98ad9f539098f3` |
| `observations.jsonl` (not committed) | `3e1fe20d41e60f0a51eed6b2ce1e9045ff9f39c96809360abe54678da5959ec2` |
| `observations.jsonl.gz` | `5e611991603a66b9c5b78d310b2104df827f41564eaa2d960d1aac8bb18f7c0e` |
| `build-identity.json` | `80759ec70b60316acc73b36b6bec43d4f1547302ec37ff1f3aca7716f3cd9066` |
| `case-census.json` | `87f390f441b0247a8d2c946cfdbdeefc4dde70e581dfb8772d8fa2317ec3b0ff` |

## Exclusions

The 28 already-accepted ledger rows (not re-run), the vacuous and unreachable rows,
the PM finding on "audio must not stop", WP-10 enumeration, listening and goldens,
hardware, release, any acceptance, and any complete WP-12/WP-12a claim.
