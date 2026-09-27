# WP-06 sequential coverage and exclusions

Issued DRAFT-9: TapeFS `3f08ec6d…`, Engine API `38381732…`, Acceptance `ae77d13c…`. Exact full source hashes are in issue #88. The case plan is deterministic (`oracle.digest_plan()`), 38 cases: 10 repair/retry, 21 degraded-B branches, 5 format/commit/remount, 2 refusal-after-validation. Fifteen degraded row columns are represented by `DEGRADED_CALLS`; `set_side` is split into Side A/B, and five equal-sequence-divergent branch probes ensure both causes. Every case demands raw superblock and index-header/entry bytes and callback logs.

| Coverage | Cases and independent observations | Source |
|---|---|---|
| Phase-4 repair after validation | 10 invalid/stale primary/mirror, failed write/flush and healthy retries; candidate identity, `needs_repair`, generation, partner convergence, phase-4-only writes | TapeFS §§4.1, 4.6; Engine API §7.2 |
| Both degraded causes | 16 row branches for neither valid B slot, five equal-sequence divergent B branches; Side-A admission, B refusal, free-next high-water, direct B0 reset at global sequence +1, remount winner, current-state set-side | TapeFS §§4.2, 4.4, 5.3, 5.5, 9.2; acceptance WP-06f |
| Round trip and bounded commit | one frame, chunk and entry-block boundaries, 4096 entries, zero-frame commit; raw identity, selected slot, entry totals, last header/flush, ≤97 writes, exactly two flushes | TapeFS §§5.1–5.3, 8; Engine API §7.1; acceptance WP-06 |
| Refused mounts | bad A and stage oracle with repairable partner; no media mutation or write | TapeFS §§4.1–4.2; acceptance WP-06g |

R45 observation correction: raw 65,536-byte slot images and superblock blocks are compared byte for byte on refusal, including invalid blocks. Candidate, live index, sequence and `free_next` are derived from raw media; only actual public `get_info` fields are compared. Callback reads before repair establish phase-4 ordering, without an adapter `phase` label. Two new invalid-block mutation controls and a private-label spoof invariance check supplement the original five red controls; the case census and exclusions do not grow.

Existing `mount_draft8` 289 one-shot cases, `writability_draft8` 8 barriers, `notmounted_draft8` 34 lifecycle cells, and `crash_core_draft8` crash cuts are **not re-accepted**. This package covers sequences rather than repeating those one-shot verdicts. Red controls target premature repair, stale B winner, missing final flush, over-budget commit, and a post-refusal write. Hardware latency, listening, WP-08/WP-09 and full WP-10 crash exhaustiveness are excluded.
