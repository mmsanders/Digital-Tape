# WP-08 mapped-run rows product binding (`wp08_mapping_r56`)

Software-owned binding of the imported verifier package `tests/wp08_mapping_r56` (#345).

- Tree `466bf8193e53a39a4e5a51710ede9cd2b2458858`, from Verification commit
  `5b7c3641e972bdbf080885ac01142927434487fa` (Verification #129, PR #125). Case set `9eca914a…4e30`, 62 cases:
  - row 1 `WP08.seek_boundary.mapped_runs`: 60;
  - row 2 `WP08.reverse_end.mapped_timeline`: 2.
- Built on main `48012109` (#343 integrated); import commit `acdf0043`, engine tree `81ad8ec2…`.
  `build-identity.json` records the engine tree, and the runner does not pin it (the #320 pattern).
  No engine change.

**Canonical result, decided by the package's own `replay.py`: PASS, 62 / 62.**

## What runs

`wp08m_adapter.c` includes only `engine/include` and uses the public API. `run_product.py` restates the plan
order from `rows.py`, and the restated case set must hash to `9eca914a…` before anything runs. The package's
`oracle.py` is never imported. `rows.image()` is written once to a file, and each case loads it onto a fresh
caller-owned flat device.

Every case makes these calls:
1. `tape_mount(side, 0, NULL)`;
2. `tape_seek`;
3. `tape_set_rate`;
4. `tape_service(64)` until `more_work == false`;
5. `tape_render`, `tape_tell` and `tape_status`.

Row 1 renders 4 frames once. Row 2 seeks to 559, sets the rate to −1.0×, and repeats steps 4–5 with 32-frame
renders until one returns short. Each call records every read, write and flush callback made during it.

`negative_controls.py` runs the package oracle over the Product stream and prints the census. It then requires
the oracle to reject eight single-fact mutations of this Product's own passing observations: a wrong frame,
swapped frames, an off-by-one tell, a render that reads the device, a service that writes, and a wrong reverse
`at_start`. **8/8 are killed.**

## Retained evidence (`evidence/p1-r57-product`)

The bundle is listed in `tests/IMPORTS.json` under `retained_unaccepted_bundles`, with the reason "held for
independent disposition (Product #345)". It moves to `product_evidence_pins` at integration after a PASS.

| File | SHA-256 |
|---|---|
| `observations.jsonl` (in the gzip, 117,648 B) | `6098222435464a3861643e2d90e1ae9f7d3dc213bfe2445c8fa7065e1a26c003` |
| `observations.jsonl.gz` (3,982 B) | `136c77ed0c9f299ebb11e991e37fc7cef2005b9865bb6c09ca9e13ef620b82a2` |
| `build-identity.json` | `864dd874de069d4dda45a73916181497d59366be61097f49010a90ab1f012de4` |
| adapter source (`adapter_source_sha256`) | `ba4565b31db9a2cf800286b743aa0d2ac38f20222e10b221b58061d743d18793` |

The CI job `wp08-mapping-r56-package` runs the package audit and self-test, then builds on Linux. It replays the
retained bundle offline, regenerates the JSONL and requires it to equal the committed SHA-256, then runs the
controls.

A green run is mechanical evidence only. It is not a disposition and not acceptance.
