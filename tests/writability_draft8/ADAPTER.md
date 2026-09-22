# WP-06a verifier-owned product probe

The package supplies `wp06a_probe.c`. Software's integration task is mechanical: compile that exact verifier-owned source against the product's public header and engine, then run:

```text
wp06a_probe CASE_ID INPUT.vo08 OUTPUT.vo08
```

Stdout must contain one `WP06A-OBSERVATION-2` JSON object. The probe itself sets the source `tape_dev.write` to a **real non-NULL callback** and records every block-device callback; trace overflow is explicitly reported and is a verifier failure. Do not substitute a NULL source slot (that is WP-36), suppress callbacks, rewrite expected results, or replace the verifier probe with product-side logic.

The verifier envelope is not a product file format: `VO08`, little-endian `u32 block_count`, primary 512-byte superblock, mirror 512-byte superblock, then A0/A1/B0/B1 65536-byte slots. These map to their normative partition LBAs. Other reads are zero-filled; these cases must refuse before mutation and do not test PCM.

Scripts:
- `W06A-ARM`: healthy v1.1, mount B, info, arm overwrite, unmount.
- `W06A-RESET-B`: healthy v1.1, mount A, info, reset B, unmount.
- `W06A-PROMOTE`: healthy v1.1, mount A, info, promote with positive budget, unmount.
- `W06A-RESPOOL`: healthy v1.1, mount B, info, respool with positive budget, unmount.
- `W06A-FEED`: healthy v1.1, mount B, info, feed one frame while idle, unmount.
- `W06A-COMMIT`: healthy v1.1, mount B, info, commit while idle, unmount.
- `W06A-REPAIR-INVALID`: valid v1.1 primary plus structurally invalid partner; mount A, info, unmount.
- `W06A-REPAIR-STALE`: valid v1.1 primary plus structurally valid lower-generation partner; mount A, info, unmount.

Every successful mount must report `writable=false` and `version_minor=1`. The two repair cases must report `needs_repair=true`. The verifier requires zero **write callbacks** and byte-identical final media in every case. Flush callbacks are retained in the trace but are not independently forbidden by WP-06a's issued acceptance text.

Integration may alter include/link flags or equivalent symbol plumbing only. Assertions, fixtures, scripts, result sets, callback accounting, or observation semantics return to Verification/PM.
