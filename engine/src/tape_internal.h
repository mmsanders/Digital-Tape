/*
 * tape_internal.h — the engine's private state and on-media parsers.
 * Normative: spec/tapefs-v1.md DRAFT-7 §4, §5 and §5.5.
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
    /*
     * The RAW bytes of the superblock copy §4.1 phase 1 selected, kept from
     * mount. §8's stage clearing writes a superblock, and it may not read one
     * first: the §4.6 update is specified as two writes and two flushes, and a
     * read inside tape_arm would be a block callback the caller did not ask for
     * in a call that is otherwise pure bookkeeping. Patching the four bytes that
     * change, in the bytes that were actually selected, also preserves every
     * field this engine does not model -- a serialise-from-struct would silently
     * rewrite reserved and label bytes it does not round-trip.
     */
    unsigned char sb_block[TAPE_BLOCK_SIZE];
    /* §4.6's classification, decided once at mount because it is defined over
       what phase 1 saw. Partner is written first and candidate last. */
    uint32_t sb_candidate_lba, sb_partner_lba;
    /* §9.1 overdub reads existing frames before it adds. That read cannot land
       in `block`, which holds the outgoing mixed block at the same moment. */
    unsigned char mix_block[TAPE_BLOCK_SIZE];
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
    /*
     * §5.5: the base every commit increments from — the maximum `sequence` over
     * every STRUCTURALLY VALID slot of all four, not only the live ones and not
     * only the mounted side's. Derived at mount, never stored on media.
     *
     * The defect it fixes is ordinary rather than exotic. Side A live at
     * sequence 10 and Side B at 500 is what a cartridge looks like after a few
     * recordings; a side-local "live->sequence + 1" writes 11, B's OLD slot at
     * 500 still wins §5.3, and after promote's phase-1 superblock lands the
     * stage oracle sees A at the staging generation and B at the old one and
     * rejects the cartridge. Both numbers were in the mounted state and nothing
     * chose between them (V6-003).
     */
    uint32_t  cartridge_sequence;
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
    /*
     * §6.3's play ring, as a window over TIMELINE frames: play_ring holds
     * play_frames consecutive frames starting at timeline frame play_base.
     * tape_service fills it and is the only thing that touches the device;
     * tape_render reads nothing else, which is what makes "service to
     * completion then render" and "interleave them" produce identical bytes.
     */
    uint32_t  play_base;
    uint32_t  play_frames;
    /* The clamped resume position in WHOLE frames, kept for §5's warm-start
       comparison, which is specified over frames rather than 32.32 units. */
    uint64_t  resume_whole_frame;

    /*
     * §9.3 bounded promote continuation state. The independent promote_draft8
     * tranche covers classification and uninterrupted FRESH paths; these
     * scalars let that work honor block_budget without allocating or putting a
     * second full index on the 200 KiB instance. mix_block is the persistent
     * partial destination block while a compacting copy spans calls.
     */
    bool      promote_in_progress;
    bool      promote_adopt;
    bool      promote_phase2;
    uint8_t   promote_phase;
    uint32_t  promote_s;
    uint32_t  promote_len;
    uint32_t  promote_copy_block;
    uint32_t  promote_copy_frame;
    uint32_t  promote_next_sequence;
    uint64_t  promote_frames;

    /*
     * §9.4 / §10 incremental re-spool continuation. Classification is frozen
     * before the first write; these scalars retain that operation across
     * block-budgeted calls. respool_block is the one partial outgoing audio
     * block and must survive allowed tape_service/tape_render calls, which may
     * reuse the engine's ordinary block scratch.
     */
    bool      respool_in_progress;
    bool      respool_has_pass2;
    bool      respool_half;      /* first half of a two-block step is durable */
    uint8_t   respool_phase;
    uint32_t  respool_len;
    uint32_t  respool_pass1;
    uint32_t  respool_pass2;
    uint32_t  respool_dest;
    uint32_t  respool_copy_block;
    uint32_t  respool_copy_frame;
    uint32_t  respool_next_sequence;
    uint64_t  respool_frames;
    unsigned char respool_block[TAPE_BLOCK_SIZE];

    /*
     * §7 recording. Scalars only: every recorded frame lives in the CALLER's
     * rec_ring (§4), and the chunks it will occupy are a bump-allocated run,
     * so the engine needs no buffer of its own to describe either.
     *
     * rec_ring holds run-relative frames [rec_base, rec_base + rec_buf_frames).
     * rec_base is always a multiple of the frames-per-block, because a partial
     * final block has to stay in the buffer: the next tape_feed extends it and
     * tape_service rewrites that same block. Frames whose block is complete are
     * dropped from the front and are never written twice.
     *
     * rec_written counts frames already handed to dev_write; rec_frames counts
     * frames tape_feed accepted. Their difference is what §7 calls OWED, and
     * §7.1's tape_commit refusal is that difference plus rec_unflushed --
     * accepted frames are not durable until §8 step 2's flush has returned.
     */
    bool      rec_armed;
    tape_rec_mode rec_mode;      /* §9.1 mode, fixed at arm with the cursor */
    uint64_t  rec_cursor;        /* the edit point, fixed at arm (§7) */
    uint32_t  rec_first_chunk;   /* first chunk of the contiguous allocated run */
    uint32_t  rec_chunks;        /* chunks allocated to that run so far */
    uint64_t  rec_frames;        /* frames tape_feed has accepted */
    uint64_t  rec_written;       /* frames already written to media */
    uint64_t  rec_base;          /* run-relative index of rec_ring[0]; block aligned */
    uint32_t  rec_buf_frames;    /* frames currently held in rec_ring */
    bool      rec_unflushed;     /* a chunk write is not yet behind a flush */
    /* §9.1 overdub: frames of the staged block whose existing audio has already
       been summed in. Nonzero only between two tape_service calls that split one
       block, and always 0 for overwrite and splice. */
    uint32_t  rec_mix_done;
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

/* Little-endian readers and the one writer the superblock patch needs.
   Explicit byte assembly: the engine must produce identical results on any
   host, and a struct overlay would not. */
void     tape_wr32(unsigned char *p, uint32_t v);
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

/*
 * §5.5 STRUCTURAL validity: magic, entry_count <= MAX_ENTRIES, CRC. Nothing
 * else. Fills `out` from the bytes, including the raw `side` marker.
 *
 * Separate from §5.2 because cartridge_sequence (§5.5) is the maximum over every
 * STRUCTURALLY valid slot -- §5.2 validity is not stable across an operation, so
 * a base computed over it could be outranked later by a slot that becomes valid.
 */
tape_result tape_index_parse(const unsigned char *hdr, const unsigned char *entries,
                             struct tape_index *out);

/*
 * §5.2 validity, against the superblock already selected by §4.1: the side
 * marker, the entry bounds, the total_frames sum, the §5.4 cap, and §5.1's
 * interval disjointness. `perm` is the sort scratch and is clobbered.
 */
tape_result tape_index_validate(struct tape_index *idx, uint8_t side,
                                const struct tape_sb *sb, uint16_t *perm);

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

/* --- §8 commit protocol: byte production and the two writes ---------------- */

/* §8 step 3's block count: ceil(entry_count * 12 / 512), zero for zero entries. */
uint32_t tape_index_entry_blocks(uint32_t entry_count);

/*
 * Serialise `idx`'s entries into `out` and return the block count above.
 * `out` must be tape_index_entry_blocks(count) * 512 bytes; the instance's
 * entry_bytes is exactly 96 blocks, which is the TAPE_MAX_ENTRIES worst case.
 *
 * Bytes past the live entries are not CRC-covered and are undefined ON MEDIA
 * (§5) — they are zeroed here anyway, so the block a commit writes is a
 * function of the index alone. An output that depends on stale buffer contents
 * is not byte-reproducible, and WP-11 compares bytes.
 */
uint32_t tape_index_serialize_entries(const struct tape_index *idx, unsigned char *out);

/* §5's 64-byte header zero-padded to a block, with §8 step 5's CRC over bytes
   0…59 concatenated with the entry array just serialised. */
void tape_index_header_block(const struct tape_index *idx, const unsigned char *entries,
                             unsigned char *blk);

/*
 * §4.5's headroom test for ONE counter. `need == 0` is not consulted at all:
 * a zero-consumption branch must not be refused because a stored counter
 * already sits at 0xFFFFFFFE on crafted media (V7-002). 64-bit, because
 * 0xFFFFFFFC + 4 wraps to 0 in u32 and the check would pass.
 */
bool tape_headroom_ok(uint32_t current, uint32_t need);

/*
 * §8 steps 3–6 against one index slot: entry array, flush, header, flush.
 * At most 97 blocks and exactly two flushes (§8, engine-api §7.1).
 *
 * `idx` supplies the sequence, side, entry array and total_frames, and its
 * bytes are what lands. Any dev_write or dev_flush failure quarantines the
 * instance per §7.2 before returning TAPE_ERR_IO.
 */
tape_result tape_commit_index(struct tape *t, uint32_t slot_lba, const struct tape_index *idx);
/* The two §8 halves of tape_commit_index, for long operations that must be
   able to spend one block per call: entries + flush, then header + flush. */
tape_result tape_commit_index_entries(struct tape *t, uint32_t slot_lba,
                                      const struct tape_index *idx);
tape_result tape_commit_index_header(struct tape *t, uint32_t slot_lba,
                                     const struct tape_index *idx);

/* §8 steps 1–2 for recording: drain owed frames into the allocated run, at most
   `budget - *used` blocks, then flush once every accepted frame is on media.
   Called only by tape_service, which owns the budget. */
tape_result tape_record_service(struct tape *t, uint32_t budget, uint32_t *used, bool *more);

/*
 * §5.1/§6.3: map timeline frame `n` onto a physical frame index in the chunk
 * store, and report how many frames from `n` stay inside `n`'s own entry. Used
 * by playback to fill the play ring and by §9.1 overdub to find the existing
 * frames it must read before it adds. One implementation, because two would
 * disagree about the entry boundary eventually.
 */
bool tape_timeline_physical(const struct tape_index *idx, uint64_t n, uint64_t *out);
uint32_t tape_timeline_run(const struct tape_index *idx, uint64_t n);

/*
 * §8 stage clearing, performed through §4.6's partner-first superblock update:
 * promote_stage = 0, promote_staging_chunk = 0, a_high_water UNCHANGED and
 * sb_generation + 1, written to the partner, flushed, written to the candidate,
 * flushed. Exactly two writes and two flushes, and no read.
 *
 * The caller must already have passed its own preconditions, including §4.5
 * headroom for BOTH counters (§8, engine-api §7). Any failure quarantines the
 * instance per §7.2.
 */
tape_result tape_sb_clear_stage(struct tape *t);
/* The two §4.6 halves of tape_sb_clear_stage: partner + flush, then
   candidate + flush. The in-memory superblock changes only after the second. */
tape_result tape_sb_clear_stage_partner(struct tape *t);
tape_result tape_sb_clear_stage_candidate(struct tape *t);

/*
 * §9.1's one index edit, shared by all three record modes.
 *
 * The result is the timeline's head [0, at), then one new entry of `frames`
 * frames based at `chunk`, then the original timeline from `tail_at` onward:
 *
 *   splice    tail_at == at            (nothing is displaced)
 *   overdub   tail_at == at + frames   (the covered span is replaced)
 *   overwrite tail_at == UINT64_MAX    (everything from `at` is dropped)
 *
 * Returns TAPE_ERR_INDEX_FULL and leaves `idx` untouched if the result would
 * exceed TAPE_MAX_ENTRIES.
 */
tape_result tape_index_replace(struct tape_index *idx, uint64_t at, uint64_t tail_at,
                               uint32_t chunk, uint64_t frames);

/* §7's OWED predicate: frames tape_feed accepted that are not yet durable.
   §8.1 is why the pending flush counts — a write is not durable until a flush
   has returned, so tape_commit may not assume the barrier already happened. */
bool tape_frames_owed(const struct tape *t);

/* Return the instance to the disarmed state. tape_mount calls it so a remount
   on a reused instance cannot inherit a previous mount's armed bookkeeping. */
void tape_record_reset(struct tape *t);

#endif /* TAPE_INTERNAL_H */
