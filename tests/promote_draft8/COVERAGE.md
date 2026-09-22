# Promote classification and uninterrupted metadata-path matrix

| ID | Cases | Independent assertion | Normative basis |
|---|---|---|---|
| PR-A01 | `PR-EMPTY*` | Empty B returns `INVALID_ARG`, terminal `more_work=false`, zero writes even with stored counters at `0xFFFFFFFF` | TapeFS §9.3.0; Engine API inv. 22/30 |
| PR-A02 | `PR-DEGRADED` | Degraded-B is reached by mounting Side A; promote returns `NO_VALID_INDEX`, zero writes | TapeFS §4.4/§9.3.0; inv. 11c |
| PR-A03 | `PR-NOTHING*` | Live A/B entry arrays byte-identical → NOTHING TO DO `TAPE_OK`, zero writes; needed=0 ignores both exhausted counters | TapeFS §4.5/§9.3.0; inv. 29/33 |
| PR-A04 | `PR-ADOPT-*-EXHAUSTED` | Adopt-complete reserves 3 sequences + 2 generations; adopt-decline reserves 1 + 2; shortage refuses before first write | TapeFS §4.5 |
| PR-A05 | `PR-ALLOC-*-EXHAUSTED` | Allocating-complete reserves 4 sequences + 2 generations; each counter is preflighted independently in widened arithmetic | TapeFS §4.5 |
| PR-A06 | `PR-FULL` | Non-adopt FRESH with counter headroom but no staging run returns `CARTRIDGE_FULL`, zero writes | TapeFS §9.3.1 |
| PR-A07 | `PR-FULL-HEADROOM-FIRST` | When both branch headroom and capacity fail, `SEQUENCE_EXHAUSTED` wins | TapeFS §9.3.0 ordering / §4.5 |
| PR-A08 | three successful FRESH paths | Exact-boundary successes may consume counters through `0xFFFFFFFD`, never beyond | TapeFS §4.5/§5.5 |
| PR-A09 | `PR-ADOPT-COMPLETE` | Adopt skips phase-1 chunk copy and B commit; final sequences are base+1/base+2/base+3, H=len, stage/staging=0 | TapeFS §9.3.1–§9.3.2 |
| PR-A10 | `PR-ADOPT-DECLINE` | Adopt commits only A in phase 1; step 5 declines without chunk copy or another index commit; final sequence is base+1 and H=S+len | TapeFS §9.3.1–§9.3.2 |
| PR-A11 | `PR-ALLOC-COMPLETE` | Allocating path copies to staging, commits A then B, then phase 2 compacts to bottom and commits A then B; final sequence base+4 | TapeFS §9.3.1–§9.3.2 |
| PR-A12 | successful paths | Both ordinary superblock updates are mirror/partner first, primary/candidate last, with a flush after each copy; final generation is exactly base+2 | TapeFS §4.6/§9.3; inv. 7/32 |
| PR-A13 | successful paths | Chunk destinations equal only the branch-authorized runs; no below-H write occurs before phase 2 | TapeFS §9.3 steps 1/5/6; inv. 10/21 |
| PR-A14 | evidence | Product/synthetic identity, immutable provenance, DRAFT-8 spec bytes, input/output/observation and offline verdict are hash-bound | Verification charter / evidence boundary |

The high-sequence A partner in each normal fixture is structurally valid but
semantically invalid because its first chunk is exactly `a_high_water`.
`cartridge_sequence` must count it while Side A selection must reject it; this
prevents the fixture itself from changing the operation class.

Excluded: RESUME and all crash rows; second-interruption closure; copied chunk
contents/rendered audio; stored-position clearing integration; WP-12a
continuation identity/re-entry; random edit histories and broad product acceptance.
