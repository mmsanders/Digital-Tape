# WP-09 record assertion and exclusion matrix

This matrix is the coverage boundary for this independent verifier package.
“Covered” means the verifier has a concrete public-observation assertion. The
Control column names a targeted negative control where one exists; “reference
vectors” and “conforming synthetic” are self-checks, not product evidence.
Nothing in this table implies whole-work-package acceptance, golden PCM
acceptance, source acceptance, or product-engine acceptance.

| Assertion ID | Case | Independent assertion | Normative basis | Control |
|---|---|---|---|---|
| WP09-A01 | OW-MID | Overwrite at frame 128 for 64 frames leaves `[(0,0,128),(3,0,64)]`, total 192 | TapeFS §9.1 overwrite trim | kept-tail mutation |
| WP09-A02 | OW-END | Overwrite at exact end appends; `[(0,0,256),(3,0,64)]`, total 320 | Engine API §11; TapeFS §9.1 | conforming synthetic |
| WP09-A03 | OD-MID | Overdub mid keeps timeline length 256 and splits around the edit | TapeFS §9.1 overdub | truncated-timeline mutation |
| WP09-A04 | SP-T0 | Splice at 0 inserts a new first entry | TapeFS §9.1; Engine API §11 | conforming synthetic |
| WP09-A05 | SP-MID | Splice mid splits the live run and keeps the suffix | TapeFS §9.1 splice | dropped-suffix mutation |
| WP09-A06 | SP-END | Splice at exact end appends | Engine API §11 | live-only sequence-base mutation |
| WP09-A07 | EMPTY-OW-MID | Zero-accepted overwrite commit is `TAPE_OK`, zero writes/flushes, byte-identical media, and the pre-existing timeline still renders | Engine API §7.1 V5-008; acceptance WP-09 | write / flush / tail-render mutations |
| WP09-A08 | BUSY | Exactly one armed `tape_seek` and one armed `tape_set_rate` both return `TAPE_ERR_BUSY`; abort then permits unmount | Engine API §7, §10 | seek-allowed and set-rate-allowed mutations |
| WP09-A09 | non-empty core | Allocation starts at derived `free_next==H==3`; service writes stay in chunk 3 | TapeFS §7 | service-write-below-H mutation |
| WP09-A10 | non-empty core | B1 commit is entries → flush → one-block header → flush; exactly two commit flushes; sequence 701 | TapeFS §8; Engine API §7.1 | missing-flush and header-before-flush mutations |
| WP09-A11 | ordinary stage-0 record | No write callback intersects either superblock, even if final bytes would be unchanged | TapeFS §8–§9.1; Engine API invariant 7 | same-byte superblock-write event mutation |
| WP09-A12 | feed | `tape_feed` reports an explicit zero callback count and no raw block callback is tagged to the feed call | Engine API §7 | missing-count and raw-callback mutations |
| WP09-A13 | arithmetic reference | Independent reference function clamps signed 16-bit overdub sums to +32767/−32768 and never wraps | Engine API §8 | seven reference vectors; **not product PCM evidence** |
| WP09-A14 | RO-SIDE-A | `tape_arm` on Side A returns `TAPE_ERR_READ_ONLY` and writes nothing | Engine API §7, §10 `W+SideB` | Side-A arm allowed |
| WP09-A15 | SEQ-EXHAUSTED | `cartridge_sequence == 0xFFFFFFFD` refuses `tape_arm` with `TAPE_ERR_SEQUENCE_EXHAUSTED` and zero writes | TapeFS §4.5 arm row; Engine API §7 | conforming synthetic |
| WP09-A16 | INDEX-FULL | Live B at `TAPE_MAX_ENTRIES` refuses splice-arm with `TAPE_ERR_INDEX_FULL` and zero writes | TapeFS §9.1; Engine API §7 | conforming synthetic |
| WP09-A17 | CART-FULL | `free_next == total_chunks`: arm succeeds; `tape_feed(64)` returns `TAPE_ERR_CARTRIDGE_FULL`, `accepted==0`, explicit zero callback count, and no feed I/O | Engine API §7; TapeFS §9.1 | feed-write and missing-count mutations |
| WP09-A18 | ABORT-DISARM | `tape_abort` after arm with no accepted frames is `TAPE_OK`, writes nothing, and a following unmount succeeds | Engine API §7.1, §10 armed row | unmount-still-BUSY mutation |
| WP09-A19 | STAGE-REFUSE | A mountable §9.3.3 row-1 stage-1 cartridge plus sequence exhaustion leaves `promote_stage` unchanged; refusal writes nothing | TapeFS §4.2 stage oracle; §4.5; §8 | refusal-cleared-stage mutation |
| WP09-A20 | OW-MULTICHUNK | Overwrite of `CHUNK_FRAMES+64` allocates exactly chunks 3–4, creates one spanning entry, and does not write any other chunk | TapeFS §§6–7, §9.1 | missing-chunk and extra-chunk mutations |
| WP09-A21 | SP-EMPTY-B | Splice on a valid empty Side B creates exactly one new entry at position 0 | Engine API §11; TapeFS §9.1 | structural assertion |
| WP09-A22 | SP-BOUNDARY | Splice at an exact existing run boundary inserts between the two runs without a zero-length split or dropped suffix | acceptance WP-09; TapeFS §9.1 | dropped-following-run mutation |
| WP09-A23 | EMPTY 3×3 | Zero-accepted commit is a zero-write/zero-flush no-op for overwrite, overdub and splice at start, middle and end; each case leaves media byte-identical and renders an existing frame afterwards | acceptance WP-09; Engine API §7.1 V5-008 | flush and tail-render mutations |
| WP09-A24 | STAGE-CLEAR | From a mountable §9.3.3 row-1 state, successful arm clears stage with partner → flush → candidate → flush, generation +1, staging=0, H unchanged, before the first record write | TapeFS §4.6, §8; invariant 25a/32 | stage-left-set and candidate-before-flush mutations |
| WP09-A25 | service completion / persistence | Non-empty cases service until `more_work==false`, commit, unmount and remount successfully; feed request/accept counts are exact | Engine API §§6–7 | service-never-completed mutation |

## Deliberate exclusions / later gates

This package is still **pre-product independent coverage**. It intentionally does
not claim:

- product observations from the real engine or source acceptance;
- golden WAV / human listening (WP-11);
- product PCM byte identity for overwrite/overdub/splice;
- product-level overdub saturation (A13 is reference arithmetic only);
- the seeded 10 000-edit property history required to close the broader allocator/edit invariants;
- WP-10 crash injection / both durability modes;
- long-operation continuation or FAULTED-state closure (WP-12a);
- WP-36 source-slot isolation; or
- hardware/media atomicity.

The current cartridge-full row starts already full and proves the zero-accept
boundary. A later capacity/property tranche should also exercise a positive
short accept (`0 < accepted < requested`) followed by service and commit if the
public buffering contract permits that request shape.

This package does not establish complete WP-09, WP-07, WP-10, WP-11 or WP-12a
acceptance. A synthetic green run proves the verifier package only.
