# Transport extra assertion matrix

This is independent, pre-product verification coverage. “Covered” means a
specific public observation is asserted; it does not imply listened/golden
acceptance.

| ID | Assertion | Basis | Targeted control |
|---|---|---|---|
| SS-A01 | Playing A→B is reachable: +1.0x A is serviced/rendered to `at_end=true`, then set_side(B) succeeds | Engine API §5; §10 Playing row; acceptance WP-08 | pre-`at_end` mutation |
| SS-A02 | Successful Playing switch resets position 0, clears both flags, sets `warm_start_used=false`, and exposes B's 64-frame / 1-entry metadata | Engine API §5 transition table; invariant 31 | old-position / old-flag / old-metadata mutations |
| SS-A03 | Playing switch invalidates the old ring: before B service, nonzero-rate render returns `TAPE_ERR_UNDERRUN`, rendered 0 | Engine API §5; §6.3; acceptance WP-08 | stale-ring rendered mutation |
| SS-A04 | Playing switch retains exact +1.0x: after B service, one rendered frame advances tell from 0 to 1 | Engine API §5 V6-005; acceptance WP-08 | tell=2 mutation |
| SS-A05 | Idle A→B performs the same transition; rate is set nonzero only after switch and pre-service render still underruns | acceptance WP-08 part (ii) | old-position / no-underrun / zero-rate mutations |
| SS-A06 | Successful same-side A call is allowed and applies the success transition | Engine API §5; §10 | retained-position mutation |
| SS-A07 | Degraded-B set_side(B) returns `NO_VALID_INDEX`, zero writes, and leaves Side-A position/metadata unchanged | Engine API §5; §10 N/ᴮ | allowed-switch / changed-position / B-metadata mutations |
| SS-A08 | Degraded-B set_side(A) remains allowed | Engine API §10 ᴮ | wrong-NO_VALID_INDEX mutation |
| SS-A09 | Armed set_side returns `BUSY`, zero writes, preserves B position/metadata, then abort/unmount succeeds | Engine API §10 armed row | allowed-switch / changed-position / abort-failure mutations |
| WARM-A01 | NULL descriptor cold-mounts without descriptor-field observations | Engine API §5 V5-007 | fabricated-present mutation |
| WARM-A02 | `data==NULL` cold-mounts with all later metadata otherwise valid | Engine API §5 V5-007 | data-present mutation |
| WARM-A03 | `valid_frames==0` cold-mounts | Engine API §5 | nonzero mutation |
| WARM-A04 | `data_bytes=63` for 16 stereo int16 frames cold-mounts | Engine API §5; acceptance WP-11 mutation 7 | sufficient-buffer mutation |
| WARM-A05 | ordinary past-end range cold-mounts | Engine API §5 | in-range mutation |
| WARM-A06 | `start_frame=0xFFFFFFF8, valid_frames=16` is rejected using checked 64-bit end arithmetic | Engine API §5 V4-011; acceptance WP-11 | low-start mutation |
| WARM-A07 | resume exactly at exclusive end of otherwise-valid range cold-mounts | Engine API §5 | in-range resume mutation |
| WARM-A08 | UUID-only mismatch cold-mounts; earlier predicates are asserted valid | Engine API §5 | matching UUID mutation + earlier-predicate control |
| WARM-A09 | side-only mismatch cold-mounts; UUID and every earlier predicate are asserted valid | Engine API §5 | matching side mutation + UUID-order control |
| WARM-A10 | Fully valid descriptor metadata reaches `warm_start_used=true` | Engine API §5 | force-cold mutation |

## Deliberate exclusions

Still outside this tranche:

- byte-exact/listened validation of the **samples** supplied by a valid warm
  start; WP-11 owns that golden;
- broader playback/rate goldens already assigned to WP-08;
- crash injection and long-operation continuation/state rows.

The positive warm row is intentionally narrower than WP-11: it proves the
ordered metadata algorithm can actually reach `use`, so the negative rows
cannot all pass because an implementation ignores warm starts globally.
