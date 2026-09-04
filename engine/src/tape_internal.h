/*
 * tape_internal.h — the engine's private state and on-media parsers.
 * Normative: spec/tapefs-v1.md DRAFT-3 §4 and §5.
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

    struct tape_index live;      /* the mounted side's committed index */
    struct tape_index scratch;   /* built during an edit; committed by §8 */

    unsigned char block[TAPE_BLOCK_SIZE];  /* staging; never on the stack */
    /* Raw entry bytes for the slot being parsed. In the instance, not a static:
       tape_dup mounts two cartridges at once, and a shared static would have
       them overwrite each other's index. The caller owns all storage (§4). */
    unsigned char entry_bytes[TAPE_MAX_ENTRIES * TAPE_INDEX_ENTRY_BYTES];

    tape_side side;
    uint64_t  position_frame;
    int32_t   rate_q16_16;
    uint32_t  free_next;         /* derived at mount, never stored (§7) */
    uint32_t  live_slot;         /* which of the side's two slots is live */
    bool      mounted;
    bool      needs_repair;
    bool      warm_start_used;
    bool      writable;
};

/*
 * spec §5.1, DRAFT-4. The run extent is computed in CHECKED 64-BIT and narrowed
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
 * spec §5.1: entry ranges must not overlap. Two entries' chunk extents may share
 * chunks only where their frame ranges within those chunks are disjoint.
 *
 * `scratch` is used as working space for the sort and is clobbered.
 */
tape_result tape_index_check_overlap(struct tape_index *idx, struct tape_index *scratch);

/* Little-endian readers. Explicit byte assembly: the engine must produce
   identical results on any host, and a struct overlay would not. */
uint16_t tape_rd16(const unsigned char *p);
uint32_t tape_rd32(const unsigned char *p);
uint64_t tape_rd64(const unsigned char *p);

/* §4: parse a 512-byte block. Returns TAPE_ERR_BAD_MAGIC or TAPE_ERR_CRC when
   the copy is not structurally valid; TAPE_OK otherwise. Does not validate
   geometry — that is §4.1 and happens after two-copy resolution. */
tape_result tape_sb_parse(const unsigned char *blk, struct tape_sb *out);

/* §4.1 geometry checks, against the caller's untrusted block_count. */
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
