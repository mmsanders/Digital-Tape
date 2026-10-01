# #130 rows product binding (`wp09_gaps_r56`)

Software-owned binding of the imported verifier package `tests/wp09_gaps_r56` (#345).

- Tree `d8d6d6f8a9df02cb6125b73bedbde422afe5d909`, from Verification commit
  `508ada857a5badf376da4428e87791333f1f0657` (Verification #130, PR #125). Case set `5b140626…5fe0`, 8 cases:
  - row 1 `WP09.overdub.full_scale_saturation`: 3 (start, middle, straddle-end);
  - row 2 `WP10.respool_render.trace_floor` (V-R55-01): 5 fixtures.
- Built on main `48012109` (#343 integrated); import commit `acdf0043`, engine tree `81ad8ec2…`.
  `build-identity.json` records the engine tree, and the runner does not pin it (the #320 pattern).
  No engine change.

**Canonical result, decided by the package's own `replay.py`: PASS, 8 / 8.**

## What runs

`run_product.py` restates the plan order from `rows.py`, and the restated case set must hash to `5b140626…`
before anything runs. The package's `oracle.py` is never imported.

- **Row 1 (`wp09g_adapter.c`, public API only).** Each case starts from a fresh copy of `rows.overdub_image()`
  on a caller-owned writable flat device. The calls are:
  1. `tape_mount(B)`, `tape_seek(at)`, `tape_arm(TAPE_REC_OVERDUB)`;
  2. `tape_feed` of `rows.input_frames(at)` (16 frames, passed as hex from the runner);
  3. `tape_service(64)` to completion, then `tape_commit` and `tape_unmount`;
  4. on the same device, `tape_mount(B)`, `tape_seek(0)` and `tape_set_rate(65536)`;
  5. repeated `tape_service(64)` to completion and `tape_render(32)` until a render is short.

  Every call is recorded with its arguments, result and outputs.
- **Row 2 (no engine run).** Each case wraps, unchanged, the `wp10_final_r54` row-3 record of that fixture from
  the accepted #336 bundle `tests/wp10_final_adapter/evidence/p1-r55-product` (pinned, Verification #128). The
  runner fetches that bundle's release asset into memory, never into the pinned directory. It refuses the asset
  unless both the gzip and its JSONL hash to the bundle's committed `SHA256SUMS` (`1e3fc673…`, `3ba932d2…`).

`negative_controls.py` runs the package oracle over the Product stream and prints the census. It then requires
the oracle to reject five single-fact mutations of this Product's own passing observations. **5/5 are killed.**
- Row 1: a wrapped rail instead of a clamp, a dropped appended frame, and a short `accepted`.
- Row 2: a dropped flush and a dropped second commit in the clean trace. Both are rejected by the pinned #118
  row-3 check, which runs before the floor check: the trace length no longer matches the crash enumeration. The
  package's own self-test proves the floor check itself goes red.

## Retained evidence (`evidence/p1-r57-product`)

The bundle is listed in `tests/IMPORTS.json` under `retained_unaccepted_bundles`, with the reason "held for
independent disposition (Product #345)". It moves to `product_evidence_pins` at integration after a PASS.

| File | SHA-256 |
|---|---|
| `observations.jsonl` (in the gzip, 9,082,706 B) | `4c93da494e2f4523c64d8217180620dc3e379c3419d89cb512958bb0318c79d2` |
| `observations.jsonl.gz` (91,316 B) | `ba361839e5caf7056915cda61dbbd50efbb05c846e6d29dfde0aca0bdada1b3e` |
| `build-identity.json` | `354e82ce59c1eb283b384f392f3b0302abb4ed6c9468610581a2ca8c2763faf1` |
| adapter source (`adapter_source_sha256`) | `118d9a998b723dde98f320b8caa91232e086cd2c5d254156954c2ad330b2af1f` |

The CI job `wp09-gaps-r56-package` runs the package audit and self-test, then builds on Linux. It replays the
retained bundle offline, regenerates the JSONL (row 2 fetches the #336 asset) and requires it to equal the
committed SHA-256, then runs the controls.

A green run is mechanical evidence only. It is not a disposition and not acceptance.
