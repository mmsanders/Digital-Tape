# WP-09 record adapter (Software-owned)

The mechanical product adapter and driver for the independent WP-09 record
package at `tests/record_draft8`, which is Verification-owned, imported verbatim
from publication `af15a8f4e7069aff9e9d5a98728530702a4f1f56` (subtree
`b7eb335d08f35b70f55fb54b5a0966c52a25688b`, declared in `tests/IMPORTS.json`) and
**not modified by anything here**.

| File | What it is |
|---|---|
| `wp09_rec_probe.c` | The adapter `tests/record_draft8/ADAPTER.md` specifies: drives the frozen public API through each scripted case and reports public-call results plus every block callback. |
| `run_product.py` | The driver. Builds each input VO08 from the verifier's own fixture, invokes the adapter, and hands the result to `oracle.check`, `refusals.check_refusal` and `extra.check_extra`, imported unmodified. |
| `evidence/` | Retained raw observations from a product run. |

## Why the driver lives here and not in the package

`tests/record_draft8` ships no product runner — unlike `ops_draft8`,
`playback_draft8` and the other packages that carry a `runner.py`. `ADAPTER.md`
specifies the probe's invocation, but nothing in the publication invokes it.
The plumbing therefore had to come from somewhere, and Software's charter is
explicit that a verifier package tree is never touched after the import commit:
a wrong package is a finding returned to Verification, not an edit.

So the driver sits outside the package and contains **no assertion of its own**.
Every verdict it prints comes from a function it imported. It has no fixtures,
no expected values, no tolerances and no orderings, because it defines none.

## Running it

```sh
make -C engine all
make -C tests/record_adapter all
python3 tests/record_adapter/run_product.py --expect-blocked WP09-ARMED-BUSY
```

## The one declared blocker

`WP09-ARMED-BUSY` cannot pass with any conforming product adapter.
`oracle.py`'s check for that case asserts `not events` — an entirely empty block
trace — while TapeFS §4.1 requires `tape_mount` to read the superblock and both
index slots, and `ADAPTER.md` requires the wrapper to record **every** callback
and never to filter observations to make a verdict pass. The product run of that
case observes 13 events, all of them `mount` reads: zero writes, zero flushes,
and no block I/O at all from the armed probes, the abort or the unmount.

The package's own sibling rows check the same property the other way:
`refusals.check_refusal` judges `WP09-ABORT-DISARM` — the identical arm / abort /
unmount shape — with `not _writes(events)` and `not _flushes(events)`, and that
case passes against the product engine. The zero-accepted commit rows use the
same pair. `WP09-ARMED-BUSY` is the outlier.

That is a finding for Verification and PM, not something to fix here.
`--expect-blocked` changes the process exit code and nothing else: the case still
runs, its verdict is still printed in full, and the runner **fails if the named
case ever passes**, so the exception cannot outlive the reason for it.

## What a green run is not

It is a raw product observation for blind Verification disposition. It is not
package acceptance, not WP-09 acceptance, and not a listened golden. The VO08
envelope carries superblocks and index slots only — no chunk data — so **no
recorded or overdubbed sample is observed anywhere in this tranche**. Product
PCM identity and WP-11 listening remain later gates.
