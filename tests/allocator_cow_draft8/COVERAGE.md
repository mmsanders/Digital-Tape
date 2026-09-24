# WP-07 allocator/COW coverage matrix

## Frozen acceptance rows

| ID | Frozen assertion | Verifier mechanism |
|---|---|---|
| W07-A01 | `tape_reset_side_b` completes in < 1 s | Verifier-owned maximum-entry-count reset fixture; adapter-side hard watchdog; CLOCK_MONOTONIC elapsed ns; environment retained; verifier requires < 1,000,000,000 ns |
| W07-A02 | Reset moves no chunk | Every scoped `dev_write` callback retained; verifier maps LBA ranges to chunk ids and requires zero chunk-region writes |
| W07-A03 | Exactly 10,000 random edit sequences | Fixed SplitMix64-v1 generator, master seed `573037a110c02026`, no production count/seed override |
| W07-A04 | Side-B allocation/write destinations never below `a_high_water` | Every positive recording is fully serviced and committed, forcing reserved chunks to appear as raw chunk-region writes; verifier maps raw LBAs and rejects any chunk id < 3 |
| W07-A05 | Below-water Side-B references are legal | Initial fixture includes Side-B references to A-owned chunks and two disjoint entries sharing chunk 0; reset produces B referencing A exactly; parser accepts them |
| W07-A06 | Remount `free_next` equals invariant 12 | Verifier selects live B from raw B0/B1 bytes, derives `max(a_high_water, max(last+1))`, then a noncommitting one-frame allocation probe must first write that exact chunk |
| W07-A07 | Every committed index has disjoint physical-frame intervals | Raw post-commit B slot headers/entries are CRC-checked and parsed independently after every action; every structurally valid slot is required to satisfy the §5.1 half-open interval rule |
| W07-A08 | Failure is compact/reproducible | Runner stores only aggregate summary on success; on failure retains exact sequence index/seed/plan + failing observation/media metadata |

## Deterministic generator census

The immutable generator produces:

- sequences: **10,000**
- total random actions: **65,026**
- edit actions: **59,423**
- reset actions: **5,603**

Edit modes:

| Mode | Count |
|---|---:|
| overwrite | 19,880 |
| overdub | 19,792 |
| splice | 19,751 |

Seek/input shapes:

| Selector | Count |
|---|---:|
| start | 6,622 |
| midpoint | 6,531 |
| end | 6,600 |
| quarter | 6,594 |
| three-quarter | 6,597 |
| half-chunk boundary | 6,670 |
| exact chunk boundary | 6,634 |
| chunk boundary − 1 | 6,605 |
| chunk boundary + 1 | 6,570 |

Feed sizes:

| Frames | Count |
|---:|---:|
| 1 | 7,303 |
| 2 | 7,390 |
| 31 | 7,486 |
| 128 | 7,412 |
| 511 | 7,554 |
| 1,024 | 7,562 |
| 4,096 | 7,364 |
| 8,192 | 7,352 |

Service budgets:

| Blocks | Count |
|---:|---:|
| 1 | 9,881 |
| 2 | 9,758 |
| 8 | 9,946 |
| 64 | 9,989 |
| 256 | 9,861 |
| 1,024 | 9,988 |

Canonical 10,000-sequence plan SHA-256:

`dd2a25b5d45ee5fe343cf48d2168ffa275bbb5adb6f3cd398559ae56529da9cd`

Every sequence ends with an edit; resets are never consecutive. This guarantees the
campaign repeatedly returns from legal shared/reference states into actual COW writes.

## Crafted reference-vs-allocation case

The fuzz fixture sets `a_high_water = 3`.

Its Side-B live index contains:
- chunk 0 frames [0, 65536);
- chunk 0 frames [65536, 131072);
- all of chunk 1;
- all of chunk 2.

Thus Side B legally references A-owned chunks below 3, and two entries legally share
one chunk while remaining frame-disjoint. Derived `free_next` is exactly 3.

The verifier self-test proves:
1. this raw index is accepted;
2. a write/allocation destination at chunk 2 is rejected;
3. a post-remount allocation probe starting at chunk 4 rather than derived chunk 3 is rejected;
4. overlapping physical-frame entries are rejected even with a correct index CRC.

## Reset stress shape

The reset-stress fixture has `a_high_water = 1` and Side A contains 4,096 one-frame
entries at physical frames 0…4095 of chunk 0. This is the maximum entry count, yet all
intervals are disjoint. A successful reset must commit all 4,096 references to Side B
without copying/writing chunk data.

The timing result is deliberately separated from the no-movement result: a fast reset
that copies chunks fails, and a zero-copy reset that takes >=1 s also fails.

## Negative controls

Verifier self-tests force red for:
- below-floor allocation/write;
- wrong remount-derived `free_next`;
- interval overlap;
- reset chunk movement;
- reset elapsed time at the 1-second boundary;
- fewer than 10,000 completed sequences;
- malformed generator provenance.

A positive crafted control separately proves below-high-water **references** are
accepted.

## Explicit exclusions

This package does not establish:
- WP-09 record-mode audio/golden correctness;
- overdub sample arithmetic;
- exact overwrite/splice rendered PCM;
- crash/torn-write durability (WP-10);
- re-spool/promote semantics (WP-12/WP-12a);
- long-operation re-entry/faulted semantics;
- WP-13 resource/structural readiness;
- any hardware timing other than the specified host/product reset API measurement.

A later exact product run must return to independent Verification before this package
can close WP-07.
