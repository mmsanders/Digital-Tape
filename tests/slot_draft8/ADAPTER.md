# WP-36 mechanical product-adapter contract

Invocation is fixed:

```text
wp36_slot_probe CASE_ID INPUT.vo08 OUTPUT.vo08
```

The adapter must link the real product public API. Its source device **must have `write == NULL`**. A non-NULL wrapper that merely swallows/counts writes is a defect.

The engine must be built with the frozen Engine API §3.1 `dev_write` debug assertion enabled. Stdout must contain exactly one JSON object:

```json
{"format":"WP36-SLOT-OBSERVATION-2","adapter_kind":"product","debug_assertions":true,"calls":[],"events":[]}
```

A normal process exit is part of the observation. With `write == NULL`, an erroneous internal `dev_write` call cannot be observed through a device callback; it is observed by the required debug assertion terminating the adapter. `runner.py` treats every nonzero exit, signal, timeout, or malformed/missing observation as failure. Product evidence with `debug_assertions != true` is rejected.

The verifier envelope is not a product file format: `VO08`, little-endian `u32 block_count`, primary 512-byte superblock, mirror 512-byte superblock, then A0/A1/B0/B1 65536-byte index slots. Map those bytes to their normative partition LBAs. All other readable blocks, including audio chunk blocks, are deterministic zero-filled blocks; WP-36 checks capability separation and transport success, not PCM identity.

Required scripts:

1. `WP36-SRC-A` / `WP36-SRC-B`: mount requested side with `warm == NULL`; query info; seek 0; set 1.0× rate; service until `more_work=false`; render exactly 8 frames; unmount.
2. `WP36-SRC-MUTATORS-B`: mount B; query info; arm overwrite; feed one frame; commit; reset B; promote with positive budget; respool with positive budget; unmount.
3. `WP36-SRC-MUTATORS-A`: same refusal sequence from A. The A-side case exists specifically to prove reset/promote/respool use mount writability rather than mounted-side identity.
4. `WP36-SRC-REPAIR-A`: mount A on the supplied one-valid/one-invalid-superblock fixture; query info; unmount.

Record every public call/result and every actual block callback. Output media must represent the final device bytes. The runner owns all expected values, call-presence checks, media comparison, and disposition. Integration may change include/link paths and equivalent symbol plumbing only; expected results, scripts, skips, observation semantics, or fixture interpretation return to Verification.
