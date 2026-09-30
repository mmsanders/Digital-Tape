# WP-12/WP-12a R53 closure-gap product binding

Software-owned binding of the imported verifier package `tests/wp12_closure_r53`.

- Tree `928fba57db92c13a311cbc5336e37b4af0f270a6`, Verification #104 / PR #106 commit
  `bbaa4f083a78316575a2f974a22b19ecdcf33fab` (branch `verification/issue-104-wp12-closure`).
- 3 gap rows, 7 cases; ledger `795c05fe…6076d4`, canonical plan `2333ec34…c68ea`.
  `fixtures.py`'s pinned blobs (`respool_draft8/oracle.py` `3c63f190`,
  `promote_draft8/fixture.py` `51c676bf`) equal the copies on main.
- Engine tree `054d27ab6e3e72f61118ff7d99e19e48741d05b2`, unchanged from main `39d2076`.

**Canonical result, decided by the package's own `replay.py`: FAIL. 5/7 cases pass
`oracle.check`.** Every render case and both re-spool fault cases pass, including
the V5-001 pass-1 header-flush path. The two promote fault cases fail with
`planned injection point never reached`. That is a plan assumption about budget
accounting, not an engine defect; see [Finding](#finding-the-promote-injection-point-is-a-read-at-budget-1).

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

Observed on the two re-spool fault cases: every F column returned
`TAPE_ERR_FAULTED`, every allowed column (`render`, `status_info_tell`, `abort`,
`unmount`) returned `TAPE_OK`, no probe touched media, `dup` touched no destination,
and the device hash was unchanged.

## Finding: the promote injection point is a read at budget 1

The plan fails the first `write` (F-PROMOTE-WRITE) or `flush` (F-PROMOTE-FLUSH) of
continuation **call 1**, at `block_budget` 1. The Product counts every block the
operation touches against the budget, reads included; Engine API §9 says "at most
`block_budget` blocks of work per call". So at budget 1 the calls are:

| Call | Callbacks |
|---:|---|
| 0 | read chunk 1 block 0 (B's first run) |
| 1 | read chunk 2 block 0 (B's second run) |
| 2 | write staging chunk 3 block 0, flush |
| 3–8 | A1 entries, A1 header, B1 entries, B1 header, superblock mirror, primary — each write + flush |
| 9 | read chunk 3 block 0 |
| 10–16 | phase 2 writes and flushes; call 16 returns `more_work = false` |

Call 1 has no write or flush, so the plan's point is never reached, the promote
completes, and the probes run on a healthy instance. Counting reads as work is a
lawful reading of "blocks of work", and changing the engine to fit the plan would be
tuning the implementation to an assumption. Suggested correction for Verification:
target call 2, or use a "first write/flush on any continuation" rule.

`negative_controls.py --adapter` runs both promote cases once more with the injection
at call 2. This is labelled non-canonical and uses the unchanged oracle. **Both
pass**: calls 0–1 return `TAPE_OK` with `more_work`, call 2 fails with `TAPE_ERR_IO`
and `more_work = false`, `arm`/`feed`/`service` and the other F columns are refused
`TAPE_ERR_FAULTED` with zero callbacks, and the media is unchanged. So the engine
behaviour both rows describe is present. Only the planned call index is unreachable.

## Run

    make -C engine clean all
    make -C tests/wp12_closure_adapter clean all
    python3 tests/wp12_closure_adapter/run_product.py --evidence <fresh dir> \
        --retained tests/wp12_closure_adapter/evidence/p1-r53-product
    python3 tests/wp12_closure_adapter/run_product.py \
        --replay tests/wp12_closure_adapter/evidence/p1-r53-product --out <fresh dir>
    python3 -B tests/wp12_closure_adapter/negative_controls.py <dir>/observations.jsonl.gz --adapter

`run_product.py` checks the verifier tree at HEAD, import `158a803` on base `39d2076`
and the plan's SHA-256, then retains a deterministic gzip, `case-census.json`
(observed calls, probe results and render facts per case, not a verdict),
`build-identity.json` and `SHA256SUMS`, and exits with `replay.py`'s status.
`--retained` requires byte identity with the committed evidence.

`negative_controls.py` is non-canonical. It prints every case's outcome, then
requires the oracle to reject one causal mutation per passing case: wrong PCM
(TWOPASS), a dropped final frame (DECLINE), render I/O (FRAGMENTED), service I/O on
the faulted instance (RESPOOL-WRITE), and `arm` accepted after the header-flush
fault (RESPOOL-HEADER-FLUSH). Result: 5/5 killed.

## Retained evidence (`evidence/p1-r53-product`)

Produced on Windows (MSYS2 UCRT64 gcc 16.2, OpenSSL for device hashes) and
regenerated byte-identically; CI regenerates it on Linux.

| File | SHA-256 |
|---|---|
| `observations.jsonl` (not committed) | `ee127132848ec7f217c9723e79d23788e3dc012c64194ce71b5585e4018cd5da` |
| `observations.jsonl.gz` | `854059bb1938a1e9c3f062a0dfbba31d0afd0155ad96ac6eeaf7c2fe699613a6` |
| `build-identity.json` | `b759d16a67bb696966eb91e2e4577a507ab545595f49b4afa3fff34f93460266` |
| `case-census.json` | `517afe2955f4e623b0da0b8aceb59e940c7d83481afc7008770ef7ef937a45e8` |

## Exclusions

The 28 already-accepted ledger rows (not re-run), the vacuous and unreachable rows,
the PM finding on "audio must not stop", WP-10 enumeration, listening and goldens,
hardware, release, any acceptance, and any complete WP-12/WP-12a claim.
