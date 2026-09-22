# WP-06a effective-writability assertion matrix

| ID | Assertion | Basis | Negative control |
|---|---|---|---|
| W06A-A01 | A device with a real non-NULL write callback carrying valid v1.1 media mounts `TAPE_OK` | TapeFS §4.3; Engine API §3.1 | non-product/non-writable-device observation refused |
| W06A-A02 | Every mounted case reports `writable == false`, `version_minor == 1` | Engine API §3.1, §5 | writable=true; minor=0 |
| W06A-A03 | Healthy v1.1: arm/reset_b/promote/respool return `TAPE_ERR_READ_ONLY` | Engine API §3.1, §10 W; WP-06a | arm/reset accepted |
| W06A-A04 | Healthy v1.1 idle feed/commit return `TAPE_ERR_BUSY` | Engine API §10; WP-06a | feed READ_ONLY |
| W06A-A05 | Invalid-partner and valid-stale-partner v1.1 mounts skip repair and report `needs_repair=true` | TapeFS §4.1 phase 4, §4.3 | needs_repair hidden |
| W06A-A06 | Zero `dev_write` callback invocations in every case | acceptance WP-06a, invariant 23 | injected write event |
| W06A-A07 | Requested side and required public call are actually exercised | verifier adapter contract | wrong side; omitted target |
| W06A-A08 | Final verifier media is byte-identical to input | consequence of zero-write contract | media mutation |

Flush callbacks are logged but not treated as an independent WP-06a failure; the issued criterion says zero `dev_write` calls. Excluded: WP-36 source-slot behavior, raw format/dup gating, crash/continuation coverage, and product-source acceptance.
