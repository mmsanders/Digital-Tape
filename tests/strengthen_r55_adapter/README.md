# #126 strengthening rows product binding (`strengthen_r55`)

Software-owned binding of the imported verifier package `tests/strengthen_r55` (#340).

- Tree `72d24675fc40432c29d7f225bac3169124e5d12f`, from Verification commit
  `7a914cd7c76bcc933e896a26fa0b3b7349c11b2d` (PR #125). Case set `9ee1c5d6…ebea`, 40 cases:
  - row 1 `WP10.dup.destination_shape.copied_audio_every_block`: 12;
  - row 2 `WP06f.sideA_liveB.respool_pass2_run`: 1;
  - row 3 `WP09.capacity.fixture_a_slot_premise`: 27.
- The same import carries the `capacity_wp09_r52` maintenance re-import, tree `4c754247…`, which
  replaces `85043f53…`. `strengthen_r55/pins.py` needs its new `synthetic.py` (`edf6d9b0…`).
- Built on main `00c69783` (#335 and #336 integrated); import commit `6feb6fe3`, engine tree `81ad8ec2…`.
  `build-identity.json` records the engine tree, and the runner does not pin it (the #320 pattern).
  No engine change.

**Canonical result, decided by the package's own `replay.py`: PASS, 40 / 40.**

## What runs

Both programs include only `engine/include` and use the public API. `run_product.py` restates the
plan order from `rows.py` and the capacity `plan.json`; the restated case set must hash to
`9ee1c5d6…` before anything runs. The package's `oracle.py` is never imported. `rows.py` is, because
ADAPTER.md requires every fixture image to be built byte for byte from it. Each image is written to
a file and loaded onto a caller-owned flat write-through device.

- **Row 1 (`str55_adapter dup`).**
  - The source is `rows.dup_source_image(frames)` on its own device, with a NULL write callback
    (guardrail 06). The destination is `rows.dup_destination_image(destination)`.
  - The runner mounts the source on Side A, then calls `tape_dup(src, dst, FRESH_DUP_UUID, 0, 9,
    65535)` until `more_work == false`.
  - It records both image hashes from before the call, and the source's Side A rendered at 1.0×
    on a fresh read-only mount. It also records the SHA-256 of the destination's raw bytes
    `[2048·512, 2048·512 + frames·4)`, read straight from the device after the call.
  - Finally it makes fresh Side-A and Side-B mounts of copies of the destination and renders each.
- **Row 2 (`str55_adapter pass2`).**
  - `rows.pass2_image()` is mounted on Side A, then `tape_respool(64)` runs until
    `more_work == false`.
  - Every write and flush from those calls is recorded. A write outside the chunk store carries its
    blocks as hex.
  - Then a fresh Side-B mount of a copy is rendered.
- **Row 3 (`str55_capacity`).** This is the accepted #311 capacity binding
  (`tests/capacity_wp09_adapter/capacity_adapter.c`), byte for byte except two things:
  - its name;
  - `raw_before` also carries `A0` and `A1`, read from media before the operation.

  `run_product.py` drives it exactly as the #311 runner does. It then adds `case` and
  `capacity_case`, and computes `fixture_sha256` over all six keys.

`negative_controls.py` runs the package oracle over the Product stream and prints the per-row
census. It then requires the oracle to reject nine single-fact mutations of this Product's own
passing observations, three per row. These include a block not copied, pass 2 declining, pass 2
landing on the then-live chunk, A0 at sequence 3, and a valid A1. **9/9 are killed.**

## Retained evidence (`evidence/p1-r56-product`)

The gzip is 972,402 bytes, under the 1 MiB tree limit, so it is committed.

| File | SHA-256 |
|---|---|
| `observations.jsonl` (in the gzip) | `877a5dc7aa8f9ae5687202138eee6e1c84c0b7a7bc6935cac12f7e9464672aa8` |
| `observations.jsonl.gz` | `f6c975daec0293736c15dd5cbe03d78d30315d09568cd7208ab2ce76a16f63b2` |
| `build-identity.json` | `27871c5da7bdfc861dbfddecc176b676b41347191f5c083969a5078d53fd929d` |
| adapter sources (`adapter_source_sha256`) | `18ed238934df525909d886c8d4d6f2c15a05f351a47601b72e67c837ef123558` |

The CI job `strengthen-r55-package` runs the package audit and self-test, then builds on Linux. It
replays the retained bundle offline, regenerates the JSONL and requires it to equal the committed
SHA-256, then runs the controls.

## Capacity maintenance re-import

`tests/capacity_wp09_adapter/run_product.py` now requires `tests/capacity_wp09_r52` at HEAD to be the
maintenance tree `4c754247…`, carried by this branch's import commit. It also requires
`oracle.py`, `replay.py`, `selftest.py` and `evidence/plan.json` to be byte-identical between
`85043f53…` and `4c754247…`; PM's carry-over ruling rests on exactly that. The accepted Product
evidence (`p1-r53-product`, stream `30cef46b…`) is unchanged. It still replays **27/27** and
regenerates byte-identically on the current engine.

A green run is mechanical evidence only. It is not a disposition and not acceptance.
