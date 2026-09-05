/*
 * tape_internal.h — the engine's private state and on-media parsers.
 * Normative: spec/tapefs-v1.md DRAFT-6 §4 and §5.
 */

#ifndef TAPE_INTERNAL_H
#define TAPE_INTERNAL_H

#include <stdbool.h>
#include "tape.h"

/* Parsed superblock. Field names match spec §4 exactly so a reader can diff the
   table against the struct. */
struct tape_sb {
    uint32_t sb_generation;
    uint8_t  state;
    uint8_t  cartridge_uuid[16];
    uint16_t version_major, version_minor;
    uint32_t sample_rate;
    uint16_t channels, bits_per_sample;
    uint32_t chunk_bytes, nominal_length_s, total_chunks, a_high_water;
    uint32_t index_slot_bytes;
    uint32_t lba_index_a0, lba_index_a1, lba_index_b0, lba_index_b1;
    uint32_t lba_chunk_base, lba_superblock_mirror;
    char     label[33];
    uint32_t format_epoch;
    /* DRAFT-5, offsets 124 and 128. The intermediate state says what it is
       rather than being inferred from index shapes — every "this shape can only
       arise from promote" argument was a reachability argument, and those are
       what have failed most often here (§4). */
    uint32_t promote_stage;
    uint32_t promote_staging_chunk;
};

/* spec §5.1 — a run over consecutive chunk ids. */
struct tape_entry {
    uint32_t first_chunk_id;
    uint32_t start_frame;   /* 0 … CHUNK_FRAMES-1, offset into the first chunk */
    uint32_t frame_count;   /* >= 1; MAY exceed CHUNK_FRAMES */
};

struct tape_index {
    uint32_t sequence;
    uint8_t  side;
    uint32_t entry_count;
    uint64_t total_frames;
    struct tape_entry entries[TAPE_MAX_ENTRIES];
};

struct tape {
    tape_dev dev;
    struct tape_sb sb;

    void   *play_ring;  size_t play_ring_len;
    void   *rec_ring;   size_t rec_ring_len;

    /*
     * BOTH sides' live indices, indexed by tape_side (§4.2). Mount validates
     * both regardless of which was requested, and it has to:
     *
     *   - free_next (§7) is defined over the live SIDE B index, so a Side-A
     *     mount that had not selected B could not compute it -- and respool and
     *     promote are both permitted from a Side-A mount and both allocate from
     *     it. Degenerating it to a_high_water would allocate straight over Side
     *     B's live chunks (invariant 10).
     *   - §9.3.1's adopt-in-place is safe only because Side A's entries satisfy
     *     §5.2's Side-A bound. That bound has to have been EVALUATED for the
     *     argument to hold, and on a Side-B mount it would not have been.
     *
     * It is also what the §9.3.3 stage oracle compares, and it is why the sort
     * scratch below is a permutation array rather than a third index: three
     * full indices would be 147 KiB of the 200 KiB budget on their own.
     */
    struct tape_index idx[2];

    unsigned char block[TAPE_BLOCK_SIZE];  /* staging; never on the stack */
    /* Raw entry bytes for the slot being parsed. In the instance, not a static:
       tape_dup mounts two cartridges at once, and a shared static would have
       them overwrite each other's index. The caller owns all storage (§4). */
    unsigned char entry_bytes[TAPE_MAX_ENTRIES * TAPE_INDEX_ENTRY_BYTES];
    /* §5.1's disjointness scratch: a permutation of entry indices, sorted by
       flattened start. 8 KiB at TAPE_MAX_ENTRIES, inside the caller's mem and
       counted in tape_instance_size() -- which §4 requires WP-13's gate to
       print rather than merely bound. */
    uint16_t sort_perm[TAPE_MAX_ENTRIES];

    tape_side side;
    uint64_t  position_frame;
    int32_t   rate_q16_16;
    uint32_t  free_next;         /* derived at mount, never stored (§7) */
    uint32_t  live_slot[2];      /* which of each side's two slots is live */
    bool      mounted;
    bool      needs_repair;
    bool      warm_start_used;
    /* §4.3's one permission predicate: (dev.write != NULL) && version_minor == 0.
       Computed once at mount, consulted by every mutator AND by phase-4 repair.
       NOT a device property and NOT a function of the mounted side -- the Side-A
       rule belongs to tape_arm and tape_feed alone (§10). */
    bool      effective_writable;
    bool      side_b_valid;      /* false in degraded-B (§4.4) */
    /* §7.2 quarantine. Set by any dev_write/dev_flush failure against this
       instance's own device; overrides every other mounted state; exits only
       through tape_unmount. Phase-4 repair failure is excluded by §4.1 -- it
       changes no logical state. */
    bool      faulted;
    bool      at_end, at_start;
    bool      play_ring_valid;   /* §5: invalidated by tape_set_side */
};

/* The mounted side's live index. There is no separate `live` member: it would be
   a second name for one of idx[], and two names for one thing is how they drift
   apart. */
#define TAPE_LIVE(t)   ((t)->idx[(t)->side])

/*
 * spec §5.1. The run extent is computed in CHECKED 64-BIT and narrowed
 * only after the bounds test:
 *
 *     span = (uint64_t)start_frame + (uint64_t)frame_count - 1
 *     last = (uint64_t)first_chunk_id + span / CHUNK_FRAMES
 *
 * DRAFT-3 expressed this in u32 and it wrapped: start_frame 131071 with
 * frame_count 0xFFFFFFFF gave last == 0, the most permissive value available,
 * which passed every bound including a_high_water (V3-001).
 */
uint64_t tape_entry_last_chunk(const struct tape_entry *e);

/*
 * spec §5.1: within one index, every pair of entries must have DISJOINT half-open
 * physical-frame intervals. Per index, not across sides — Side B referencing
 * chunks Side A also references is the copy-on-write mechanism (Rule 3) and is
 * required, not merely tolerated.
 *
 * Checkable from index metadata alone; NO CHUNK IS READ, which acceptance.md
 * WP-06c asserts directly by counting chunk-region reads during mount.
 *
 * `perm` is TAPE_MAX_ENTRIES u16 slots of working space and is clobbered.
 */
tape_result tape_index_check_overlap(const struct tape_index *idx, uint16_t *perm);

/* Little-endian readers. Explicit byte assembly: the engine must produce
   identical results on any host, and a struct overlay would not. */
uint16_t tape_rd16(const unsigned char *p);
uint32_t tape_rd32(const unsigned char *p);
uint64_t tape_rd64(const unsigned char *p);

/* §4: parse a 512-byte block. Returns TAPE_ERR_BAD_MAGIC or TAPE_ERR_CRC when
   the copy is not structurally valid; TAPE_OK otherwise. Does not validate
   geometry — that is §4.1 and happens after two-copy resolution. */
tape_result tape_sb_parse(const unsigned char *blk, struct tape_sb *out);

/*
 * §2.1 GEOMETRY_OK — the one geometry predicate, used at mount, in tape_dup and
 * in tape_format. On success *out_total_chunks is the derived chunk count: what
 * a format must write, and what a mount must find already stored.
 */
tape_result tape_geometry_ok(uint32_t nominal_length_s, uint32_t block_count,
                             uint32_t *out_total_chunks);

/* §4.1 phase 2 step 5: fixed constants, fixed LBAs, the mirror reservation, and
   GEOMETRY_OK with stored total_chunks EQUAL to the derived value. */
tape_result tape_sb_check_geometry(const struct tape_sb *sb, uint32_t block_count);

/* §5/§5.2: parse and validate one index slot from its header block plus entry
   bytes. `side` is the slot's assignment; `sb` supplies total_chunks and
   a_high_water for the run-bound checks. */
tape_result tape_index_parse(const unsigned char *hdr, const unsigned char *entries,
                             uint8_t side, const struct tape_sb *sb,
                             struct tape_index *out);

/* §7: free_next = max over live-B entries of (last_chunk_id + 1), floored at
   a_high_water. Derived, never stored. */
uint32_t tape_derive_free_next(const struct tape_index *idx, const struct tape_sb *sb,
                               tape_side side);

/* --- WP-07: allocation (spec §7, Rule 3) ---------------------------------- */

/*
 * Rule 3 — ownership is not reference. A side may REFERENCE chunks it does not
 * OWN; it may only ALLOCATE and WRITE within what it owns.
 *
 * These two predicates are the whole distinction, separated so that a caller
 * cannot accidentally use the wrong one. DRAFT-3's invariant conflated them and
 * was unsatisfiable: it forbade Side B from referencing below a_high_water,
 * which is exactly what reset-B produces (V3-009).
 */

/* May `side` reference chunk `id`? Side B: yes, anywhere in range — that is the
   copy-on-write mechanism. Side A: only what it owns. */
bool tape_may_reference(const struct tape_sb *sb, tape_side side, uint32_t id);

/* May `side` allocate or write chunk `id`? Side B: only at or above
   a_high_water. Side A: never at runtime — the sole exception is promote
   phase 2 (§9.3), which is not a general allocation and does not come here. */
bool tape_may_allocate(const struct tape_sb *sb, tape_side side, uint32_t id);

/*
 * Bump-allocate a contiguous run of `count` chunks for `side`.
 *
 * Contiguous because §5.1's entries describe runs over consecutive chunk ids, so
 * a fragmented allocation could not be expressed as one entry. Bump because
 * free_next is derived from the committed index (§7): chunks written by an
 * operation that never commits sit above free_next on the next mount and are
 * silently reused, so the aborted-write leak class does not exist.
 *
 * Advances *free_next on success. Returns TAPE_ERR_CARTRIDGE_FULL if the run
 * does not fit, TAPE_ERR_READ_ONLY if the side may not allocate, and writes
 * nothing — allocation is bookkeeping, not I/O.
 */
tape_result tape_alloc_run(const struct tape_sb *sb, tape_side side,
                           uint32_t *free_next, uint32_t count,
                           uint32_t *out_first);

/* Chunks needed for `frames`, ceiling. 64-bit; frames may be up to 2^32-1. */
uint32_t tape_chunks_for_frames(uint64_t frames);

#endif /* TAPE_INTERNAL_H */
