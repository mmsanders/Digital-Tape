# WP-06h verifier-owned product probe

The package supplies `wp06h_probe.c`. Software's task is mechanical: compile that exact verifier-owned source against the product's public header and engine, then run it through `runner.py`.

Invocation:

```text
wp06h_probe CASE_ID INPUT.vo08 OUTPUT.vo08
```

Stdout is one `WP06H-OBSERVATION-2` JSON object. Each CASE_ID tests **one** ordinary call in a fresh process:

- `NM-BEFORE-*`: initialize the instance, do not mount, issue exactly that ordinary call.
- `NM-AFTER-*`: initialize, mount healthy Side A, unmount successfully, then issue exactly that ordinary call.

The ordinary set is the Engine API §10 matrix: seek, set_rate, render, service, status, info, tell, arm, feed, commit, abort, set_side, reset_b, promote, respool, dup-as-source, and unmount. `tape_init`, `tape_mount`, `tape_format`, and destination-side `tape_dup` are explicit exceptions and are not probed as ordinary calls.

All arguments are valid and non-null so the state-row result is not confounded with argument validation. The `dup` probe uses a distinct valid raw destination device/context so the source's Not-mounted row is what is under test. For `tape_tell`, the probe initializes `*out_frame` to `0x1111111111111111` and reports both its before and after value.

The probe records source/destination callback-count deltas for each target call as diagnostic evidence. WP-06h's issued acceptance criterion does **not** separately require zero callbacks, so those counts are not promoted into an unstated pass/fail condition here.

The verifier envelope is not a product file format: `VO08`, little-endian `u32 block_count`, primary 512-byte superblock, mirror 512-byte superblock, then A0/A1/B0/B1 65536-byte slots. Other source reads return deterministic zeroes.

Integration may alter include/link flags or equivalent symbol plumbing only. Case scripts, result expectations, call sequencing, sentinel handling, and observation semantics return to Verification/PM.
