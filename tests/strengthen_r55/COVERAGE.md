# #126 strengthening rows: coverage

| Row | Strengthens | Cases | Controls (exact kill sets) |
|---|---|---|---|
| `WP10.dup.destination_shape.copied_audio_every_block` | #116 row 3, finding V-R54-02 (#120) | 12 = 6 source lengths × {blank, reusable} | `copy_only_first_block`, `copy_skips_second_block` and `copy_skips_last_block`, each on exactly the 10 multi-block cases |
| `WP06f.sideA_liveB.respool_pass2_run` | #108 floor row, pass-2 run branch (#121) | 1 | `pass2_onto_then_live_chunk` (rule b), `pass2_declines` (rule c) and `pass1_below_floor` (rule b, since the fixture is dense) |
| `WP09.capacity.fixture_a_slot_premise` | #99 row, A-slot premise (#107 finding 1) | 27 | `a0_at_sequence_3`, `a1_structurally_valid` and `a_slots_not_snapshotted`, each on all 27 |

The case-set SHA-256 is `9ee1c5d6083dda0e9fd3f331a56dbc4903d659a157daa91615ff30212101ebea`.

The accepted subtrees are unchanged. These are new rows in a new package. The only change to `capacity_wp09_r52`
is maintenance: its `ADAPTER.md` fixture text and `synthetic.py`. Its oracle, replay, self-test assertions and plan
are unchanged, and it has a new subtree.

## Row 1

Source lengths:

| Frames | Layout |
|---|---|
| 128 | one block |
| 129 | a block boundary |
| 1,000 | eight blocks |
| `CHUNK_FRAMES` | a whole chunk |
| `CHUNK_FRAMES + 1` | a chunk boundary |
| `2·CHUNK_FRAMES + 77` | three chunks |

- **Distinct frames.** Every source frame is coordinate-unique and non-zero. The reusable destination is
  pre-filled with a disjoint coordinate-unique pattern, so a skipped block cannot coincide with the source,
  whether it stays zero or keeps the old album.
- **Frame-for-frame copy.** The raw copied frames and both sides' renders must equal the pattern-derived source
  timeline (tapefs §9.5 layout `{0,0,frames}`). The engine's write partitioning is not pinned (#115).
- **V-R54-02.** In #116, ONE-CHUNK and CHUNK-PLUS-ONE carried all-zero audio, so a copy of block 0 alone passed.
  Here that mutant is red on every multi-block case.

## Row 2

The fixture is `a_high_water` 2, A `{0,0,10}`, and live B `[{2,0,10},{3,0,10}]`, mounted on Side A. The floor is 4,
`len` is 1 and `floor − H = 2 ≥ len`. Pass 1 must allocate at or above the floor; with 5 chunks that is chunk 4.
Pass 1 then commits, and `[2, 4)` holds a lawful lower run.

These are the #108 rules (tapefs §9.3.1–§9.3.2 and §9.4, invariant 10), each asserted on raw callbacks:

- **(a)** Pass 1 is one run of `len` at or above the floor, before the first index commit.
- **(b)** Every chunk write is disjoint from both sides' live set, rebuilt from the raw commits seen so far.
- **(c)** Pass 2 **runs**: it is at or above `a_high_water`, strictly lower than pass 1, one run of `len`, and it
  is committed to the other B slot.

After those rules:

- The final Side B is one entry at the pass-2 run.
- It renders bit-identically, and no superblock is written.
- §9.4 "Pass 2 runs only if such a run exists", with acceptance WP-12 "must … run pass 2", makes the run
  mandatory here.

## Row 3

**The premise.** The #99 oracle expects the commit at sequence 4, which holds only if `cartridge_sequence` is 3.
tapefs §5.5 takes that value as the maximum over every structurally valid slot, including Side A.

**What this row checks, from raw bytes read before the operation:**

- A0 is a valid, empty Side-A index at sequence 1.
- A1 is structurally invalid.
- The maximum sequence over all four slots is 3.

It then replays the unchanged #99 oracle on the four-key `raw_before` that the #99 oracle binds.

## Excluded

Product bindings, V-R55-01 (the #128 row-3 enumeration floor; it is PM's to route), WP-11, hardware and release.
