# WP-36 source-slot assertion matrix

| ID | Assertion | Basis | Negative control |
|---|---|---|---|
| WP36-A01 | `tape_info.writable == false` with literal `dev.write == NULL` | Engine API §3.1 | writable=true |
| WP36-A02 | mount/seek/rate/service/render succeed on both sides; required calls cannot be omitted | Engine API §§5–6, §10 | missing render; failed service |
| WP36-A03 | Side-B arm and A/B reset_b/promote/respool return `TAPE_ERR_READ_ONLY` | Engine API §3.1, §10 W cells | reset succeeds |
| WP36-A04 | refused arm leaves feed/commit in mounted-idle `TAPE_ERR_BUSY` precedence | Engine API §10 | feed returns READ_ONLY |
| WP36-A05 | product process exits normally with debug assertions enabled; a NULL-device `dev_write` attempt therefore fails the run | Engine API §3.1; acceptance WP-36 | runner rejects nonzero process exit |
| WP36-A06 | source-slot mount skips superblock repair, reports `needs_repair=true`, and performs no repair write/flush | TapeFS §4.1 phase 4, §4.3 | repair hidden; flush event |
| WP36-A07 | final verifier envelope is byte-identical to input | source-slot zero-write contract | media mutation |

Not covered: the required 100,000-sequence fuzzer, v1.1 WP-06a, or raw-device format/duplicate gating. `format` and destination `dup` are deliberately excluded from the mounted-mutator language because Engine API §3.1 places them outside effective writability.
