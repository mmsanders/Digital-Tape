/*
 * promote.c — DRAFT-8/9 tape_promote.
 *
 * Covered here: §9.3.0 classification; §4.5 branch-exact headroom and
 * precedence; §9.3.1 FRESH adopt/allocate phase 1; §9.3.2 phase 2 and its
 * decline; §9.3.3 RESUME from every stage-1 row; §4.6 partner-first superblock
 * durability; engine-api §9.1's incremental contract, including a budget of 1,
 * the progress callback and its no-re-entry rule.
 *
 * One unit of block_budget is one block read or one block write. Flushes are
 * barriers, not blocks, and cost nothing. Every write in the operation is its
 * own step, so a budget of 1 always makes progress: a commit is an entry-block
 * step and a header step, and a superblock update is a partner step and a
 * candidate step, each with its own flush behind it (§8, §4.6).
 *
 * Stored positions are the caller's (engine-api §9.2). The engine has no
 * position table, so there is nothing here to clear.
 */

#include <string.h>

#include "tape_internal.h"
#include "tape_crc32.h"
#include "dev.h"

/*
 * Sparse state tags are intentional. The indirect-call gate rejects compiler
 * generated jump tables (a .rodata relocation into .text is indistinguishable
 * from an authored dispatch table), so keep these far enough apart that -Os
 * lowers the state machine to direct comparisons.
 */
#define PROMOTE_PHASE_COPY_STAGE         7u   /* §9.3.1 step 1 */
#define PROMOTE_PHASE_A_STAGE_ENTRIES   19u   /* step 2 */
#define PROMOTE_PHASE_A_STAGE_HEADER    31u
#define PROMOTE_PHASE_B_STAGE_ENTRIES   43u   /* step 3 */
#define PROMOTE_PHASE_B_STAGE_HEADER    59u
#define PROMOTE_PHASE_SB_STAGE_PARTNER  71u   /* step 4 */
#define PROMOTE_PHASE_SB_STAGE_CAND     83u
#define PROMOTE_PHASE_SB_DECLINE_PARTNER 101u /* step 5, decline */
#define PROMOTE_PHASE_SB_DECLINE_CAND   113u
#define PROMOTE_PHASE_COPY_FINAL        131u  /* step 6 */
#define PROMOTE_PHASE_A_FINAL_ENTRIES   149u  /* step 7 */
#define PROMOTE_PHASE_A_FINAL_HEADER    163u
#define PROMOTE_PHASE_B_FINAL_ENTRIES   181u  /* step 8 */
#define PROMOTE_PHASE_B_FINAL_HEADER    197u
#define PROMOTE_PHASE_SB_FINAL_PARTNER  211u  /* step 9 */
#define PROMOTE_PHASE_SB_FINAL_CAND     229u

#define PROMOTE_FRAMES_PER_BLOCK (TAPE_BLOCK_SIZE / TAPE_FRAME_BYTES)

static bool promote_entries_equal(const struct tape_index *a,
                                  const struct tape_index *b)
{
    uint32_t i;

    if (a->entry_count != b->entry_count) { return false; }
    for (i = 0u; i < a->entry_count; i++) {
        if (a->entries[i].first_chunk_id != b->entries[i].first_chunk_id
            || a->entries[i].start_frame != b->entries[i].start_frame
            || a->entries[i].frame_count != b->entries[i].frame_count) {
            return false;
        }
    }
    return true;
}

/* §9.3.3's "single entry {first, 0, N}". */
static bool promote_single_at(const struct tape_index *x, uint32_t first,
                              uint64_t frames)
{
    return x->entry_count == 1u
        && x->entries[0].first_chunk_id == first
        && x->entries[0].start_frame == 0u
        && (uint64_t)x->entries[0].frame_count == frames
        && x->total_frames == frames;
}

static uint32_t promote_slot_lba(const struct tape *t, tape_side side,
                                 uint32_t slot)
{
    if (side == TAPE_SIDE_A) {
        return (slot == 0u) ? t->sb.lba_index_a0 : t->sb.lba_index_a1;
    }
    return (slot == 0u) ? t->sb.lba_index_b0 : t->sb.lba_index_b1;
}

/* Timeline blocks of the compacted copy: ceil(frames / 128). Bytes after the
   last referenced frame of a chunk are undefined (§6), so the copy writes
   exactly these blocks and not the rest of the final chunk. */
static uint32_t promote_data_blocks(uint64_t frames)
{
    return (uint32_t)((frames + PROMOTE_FRAMES_PER_BLOCK - 1u)
                      / PROMOTE_FRAMES_PER_BLOCK);
}

/*
 * Units a compacting copy of `src` costs: every source read promote_copy will
 * issue, plus one write per destination block. Walks the timeline exactly as
 * promote_copy does, without I/O, so the progress total is a count and not an
 * estimate. A source that is already one block-aligned run costs one read per
 * block.
 */
static uint32_t promote_copy_units(const struct tape_index *src, uint64_t frames)
{
    uint64_t n = 0u;
    uint32_t units = 0u;
    uint32_t in_block = 0u;

    while (n < frames) {
        uint64_t physical;
        uint32_t run, off, take;

        if (!tape_timeline_physical(src, n, &physical)) { break; }
        run = tape_timeline_run(src, n);
        if (run == 0u) { break; }
        off = (uint32_t)(physical % PROMOTE_FRAMES_PER_BLOCK);
        take = PROMOTE_FRAMES_PER_BLOCK - in_block;
        if (take > PROMOTE_FRAMES_PER_BLOCK - off) {
            take = PROMOTE_FRAMES_PER_BLOCK - off;
        }
        if (take > run) { take = run; }
        if ((uint64_t)take > frames - n) { take = (uint32_t)(frames - n); }
        units++;                                   /* the read */
        in_block += take;
        n += take;
        if (in_block == PROMOTE_FRAMES_PER_BLOCK) {
            units++;                               /* the write */
            in_block = 0u;
        }
    }
    if (in_block != 0u) { units++; }
    return units;
}

/* The phase-2 source is one block-aligned run: one read and one write per
   timeline block. */
static uint32_t promote_aligned_copy_units(uint64_t frames)
{
    return 2u * promote_data_blocks(frames);
}

/*
 * Units still to do from the phase about to run, for the progress callback's
 * blocks_total. Evaluated once, when the operation starts or resumes.
 */
static uint32_t promote_remaining_units(const struct tape *t, uint8_t phase)
{
    uint32_t tail = t->promote_phase2
                  ? promote_aligned_copy_units(t->promote_frames) + 6u
                  : 2u;                        /* decline write */
    uint32_t units = 0u;

    if (phase == PROMOTE_PHASE_COPY_STAGE) {
        units = promote_copy_units(&t->idx[TAPE_SIDE_B], t->promote_frames)
              + 6u + tail;                     /* steps 2, 3, 4 */
    } else if (phase == PROMOTE_PHASE_A_STAGE_ENTRIES) {
        units = 4u + tail;                     /* adopt: steps 2, 4 */
    } else if (phase == PROMOTE_PHASE_SB_DECLINE_PARTNER) {
        units = 2u;                            /* resume, step 5 declines */
    } else if (phase == PROMOTE_PHASE_COPY_FINAL) {
        units = tail;                          /* resume at step 5 */
    } else if (phase == PROMOTE_PHASE_B_FINAL_ENTRIES) {
        units = 4u;                            /* resume at step 8 */
    } else if (phase == PROMOTE_PHASE_SB_FINAL_PARTNER) {
        units = 2u;                            /* resume at step 9 */
    }
    return units;
}

/*
 * §4.6 ordinary superblock update, one write per call step. The selected raw
 * bytes are patched in place so fields the engine does not model stay
 * byte-identical; the partner step patches, writes and flushes, and the
 * candidate step writes the same bytes and flushes. The in-memory superblock
 * agrees with the media only once both copies carry the new generation.
 */
static tape_result promote_sb_partner(tape *t, uint32_t high,
                                      uint32_t stage, uint32_t staging)
{
    unsigned char *blk = t->sb_block;

    tape_wr32(blk + 12u, t->sb.sb_generation + 1u);
    tape_wr32(blk + 56u, high);
    tape_wr32(blk + 124u, stage);
    tape_wr32(blk + 128u, staging);
    tape_wr32(blk + 508u, tape_crc32(blk, 508u));

    if (dev_write(&t->dev, t->sb_partner_lba, 1u, blk) != 0) {
        t->faulted = true;
        return TAPE_ERR_IO;
    }
    if (dev_flush(&t->dev) != 0) {
        t->faulted = true;
        return TAPE_ERR_IO;
    }
    return TAPE_OK;
}

static tape_result promote_sb_candidate(tape *t, uint32_t high,
                                        uint32_t stage, uint32_t staging)
{
    if (dev_write(&t->dev, t->sb_candidate_lba, 1u, t->sb_block) != 0) {
        t->faulted = true;
        return TAPE_ERR_IO;
    }
    if (dev_flush(&t->dev) != 0) {
        t->faulted = true;
        return TAPE_ERR_IO;
    }

    t->sb.sb_generation += 1u;
    t->sb.a_high_water = high;
    t->sb.promote_stage = stage;
    t->sb.promote_staging_chunk = staging;
    t->sb_candidate_lba = TAPE_LBA_SUPERBLOCK;
    t->sb_partner_lba = t->dev.block_count - 1u;
    t->needs_repair = false;
    return TAPE_OK;
}

/*
 * §8 step 3–4 for promote's one-entry index: the single entry block into the
 * inactive slot, then the barrier. The live in-memory index is not touched
 * until the header lands.
 */
static tape_result promote_commit_entries(tape *t, tape_side side,
                                          uint32_t first_chunk)
{
    uint32_t dst_slot = (t->live_slot[side] == 0u) ? 1u : 0u;
    uint32_t lba = promote_slot_lba(t, side, dst_slot);

    memset(t->block, 0, TAPE_BLOCK_SIZE);
    tape_wr32(t->block, first_chunk);
    tape_wr32(t->block + 4u, 0u);
    tape_wr32(t->block + 8u, (uint32_t)t->promote_frames);
    if (dev_write(&t->dev, lba + 1u, 1u, t->block) != 0) {
        t->faulted = true;
        return TAPE_ERR_IO;
    }
    if (dev_flush(&t->dev) != 0) {
        t->faulted = true;
        return TAPE_ERR_IO;
    }
    return TAPE_OK;
}

/* §8 steps 5–6: header at next_sequence, the commit point, then the barrier.
   The entry array is re-serialised from the same index so the CRC binds the
   header to exactly the bytes the previous step wrote. */
static tape_result promote_commit_header(tape *t, tape_side side,
                                         uint32_t first_chunk)
{
    uint32_t dst_slot = (t->live_slot[side] == 0u) ? 1u : 0u;
    uint32_t lba = promote_slot_lba(t, side, dst_slot);
    struct tape_index *idx = &t->idx[side];

    idx->sequence = t->promote_next_sequence;
    idx->side = (uint8_t)side;
    idx->entry_count = 1u;
    idx->total_frames = t->promote_frames;
    idx->entries[0].first_chunk_id = first_chunk;
    idx->entries[0].start_frame = 0u;
    idx->entries[0].frame_count = (uint32_t)t->promote_frames;
    (void)tape_index_serialize_entries(idx, t->entry_bytes);
    tape_index_header_block(idx, t->entry_bytes, t->block);
    if (dev_write(&t->dev, lba, 1u, t->block) != 0) {
        t->faulted = true;
        return TAPE_ERR_IO;
    }
    if (dev_flush(&t->dev) != 0) {
        t->faulted = true;
        return TAPE_ERR_IO;
    }

    t->live_slot[side] = dst_slot;
    t->cartridge_sequence = t->promote_next_sequence;
    t->promote_next_sequence++;
    return TAPE_OK;
}

/*
 * Incremental compacting copy of exactly promote_data_blocks(frames) blocks.
 * mix_block persists in the caller-owned instance, so a budget of 1 may stop
 * after any source read and resume without repeating it. Bytes after the last
 * frame of the final block are deterministically zero; the remaining blocks of
 * the final chunk are not written (§6 leaves them undefined).
 */
static tape_result promote_copy(tape *t, const struct tape_index *src,
                                uint32_t dst_first, uint32_t budget,
                                uint32_t *used, bool *done)
{
    uint32_t total_blocks = promote_data_blocks(t->promote_frames);

    *done = false;
    while (t->promote_copy_block < total_blocks) {
        uint64_t timeline_frame =
            (uint64_t)t->promote_copy_block * (uint64_t)PROMOTE_FRAMES_PER_BLOCK
            + (uint64_t)t->promote_copy_frame;

        if (t->promote_copy_frame == 0u) {
            memset(t->mix_block, 0, TAPE_BLOCK_SIZE);
        }

        if (t->promote_copy_frame < PROMOTE_FRAMES_PER_BLOCK
            && timeline_frame < t->promote_frames) {
            uint64_t physical;
            uint32_t run, source_offset, take;
            uint64_t source_lba;

            if (*used >= budget) { return TAPE_OK; }
            if (!tape_timeline_physical(src, timeline_frame, &physical)) {
                return TAPE_ERR_INCONSISTENT;
            }
            run = tape_timeline_run(src, timeline_frame);
            if (run == 0u) { return TAPE_ERR_INCONSISTENT; }

            source_offset = (uint32_t)(physical % PROMOTE_FRAMES_PER_BLOCK);
            take = PROMOTE_FRAMES_PER_BLOCK - t->promote_copy_frame;
            if (take > PROMOTE_FRAMES_PER_BLOCK - source_offset) {
                take = PROMOTE_FRAMES_PER_BLOCK - source_offset;
            }
            if (take > run) { take = run; }
            if ((uint64_t)take > t->promote_frames - timeline_frame) {
                take = (uint32_t)(t->promote_frames - timeline_frame);
            }

            source_lba = (uint64_t)t->sb.lba_chunk_base
                       + physical / (uint64_t)PROMOTE_FRAMES_PER_BLOCK;
            if (source_lba >= (uint64_t)t->dev.block_count) {
                return TAPE_ERR_GEOMETRY;
            }
            if (dev_read(&t->dev, (uint32_t)source_lba, 1u, t->block) != 0) {
                return TAPE_ERR_IO;
            }
            (*used)++;
            t->promote_done++;
            memcpy(t->mix_block
                       + (size_t)t->promote_copy_frame * TAPE_FRAME_BYTES,
                   t->block + (size_t)source_offset * TAPE_FRAME_BYTES,
                   (size_t)take * TAPE_FRAME_BYTES);
            t->promote_copy_frame += take;
            continue;
        }

        if (*used >= budget) { return TAPE_OK; }
        {
            uint64_t dst_lba =
                (uint64_t)t->sb.lba_chunk_base
                + (uint64_t)dst_first * (uint64_t)TAPE_CHUNK_BLOCKS
                + (uint64_t)t->promote_copy_block;
            if (dst_lba >= (uint64_t)t->dev.block_count) {
                return TAPE_ERR_GEOMETRY;
            }
            if (dev_write(&t->dev, (uint32_t)dst_lba, 1u,
                          t->mix_block) != 0) {
                t->faulted = true;
                return TAPE_ERR_IO;
            }
        }
        (*used)++;
        t->promote_done++;
        t->promote_copy_block++;
        t->promote_copy_frame = 0u;
    }

    /* §8 step 2: the data barrier, in the same call as the last data write. */
    if (dev_flush(&t->dev) != 0) {
        t->faulted = true;
        return TAPE_ERR_IO;
    }
    *done = true;
    return TAPE_OK;
}

static void promote_reset_copy(tape *t)
{
    t->promote_copy_block = 0u;
    t->promote_copy_frame = 0u;
}

static void promote_finish(tape *t)
{
    uint64_t total = TAPE_LIVE(t).total_frames;

    t->promote_in_progress = false;
    t->promote_phase = 0u;
    promote_reset_copy(t);
    t->play_ring_valid = false;
    t->play_frames = 0u;
    t->at_end = false;
    t->at_start = false;
    if ((t->position_frame >> 32) > total) {
        t->position_frame = total << 32;
    }
}

/*
 * §9.3.0 classification, completely before the first write. That is what
 * makes §4.5's exact branch reservation and the headroom-before-capacity
 * precedence decidable. On return with *terminal false an operation is armed
 * at t->promote_phase; with *terminal true the call ends with the result.
 */
static tape_result promote_begin(tape *t, bool *terminal)
{
    const struct tape_index *a = &t->idx[TAPE_SIDE_A];
    const struct tape_index *b = &t->idx[TAPE_SIDE_B];
    uint64_t n;
    uint32_t len, s, seq_need, gen_need;
    uint8_t phase;
    bool adopt = false, phase2;

    *terminal = true;

    if (!t->side_b_valid) { return TAPE_ERR_NO_VALID_INDEX; }
    n = b->total_frames;
    if (n == 0u) { return TAPE_ERR_INVALID_ARG; }
    len = tape_chunks_for_frames(n);

    if (t->sb.promote_stage == TAPE_PROMOTE_STAGE_PHASE1) {
        /*
         * §9.3.3 RESUME. The three rows partition stage-1 media (S > 0 on
         * rows 2 and 3); mount already refused media matching none, and the
         * check is repeated here rather than trusted.
         */
        uint32_t H = t->sb.a_high_water;

        s = t->sb.promote_staging_chunk;
        phase2 = s >= len;
        if (promote_single_at(a, s, n) && promote_entries_equal(a, b)) {
            /* Row 1 — resume at step 5, which runs or declines. */
            if (phase2) {
                seq_need = 2u;
                phase = PROMOTE_PHASE_COPY_FINAL;
            } else {
                seq_need = 0u;
                phase = PROMOTE_PHASE_SB_DECLINE_PARTNER;
            }
        } else if (s > 0u && promote_single_at(a, 0u, n)
                   && promote_single_at(b, s, n)) {
            /* Row 2 — phase 2 committed A only: resume at step 8. [0, len)
               is durable because A committed after step 6's flush. */
            seq_need = 1u;
            phase = PROMOTE_PHASE_B_FINAL_ENTRIES;
            phase2 = true;
        } else if (s > 0u && promote_single_at(a, 0u, n)
                   && promote_entries_equal(a, b) && H > len) {
            /* Row 3 — both indices committed: resume at step 9. */
            seq_need = 0u;
            phase = PROMOTE_PHASE_SB_FINAL_PARTNER;
            phase2 = true;
        } else {
            return TAPE_ERR_INCONSISTENT;
        }
        gen_need = 1u;
    } else {
        if (promote_entries_equal(a, b)) {
            return TAPE_OK; /* NOTHING TO DO: zero counters consulted, zero writes. */
        }
        adopt = b->entry_count == 1u
             && b->entries[0].start_frame == 0u
             && b->entries[0].first_chunk_id >= t->sb.a_high_water;
        s = adopt ? b->entries[0].first_chunk_id : t->free_next;
        phase2 = s >= len;
        if (adopt) {
            seq_need = phase2 ? 3u : 1u;
            phase = PROMOTE_PHASE_A_STAGE_ENTRIES;
        } else {
            seq_need = phase2 ? 4u : 2u;
            phase = PROMOTE_PHASE_COPY_STAGE;
        }
        gen_need = 2u;
    }

    /* §4.5 first: both counters, widened, before any capacity refusal. */
    if (!tape_headroom_ok(t->cartridge_sequence, seq_need)
        || !tape_headroom_ok(t->sb.sb_generation, gen_need)) {
        return TAPE_ERR_SEQUENCE_EXHAUSTED;
    }

    if (t->sb.promote_stage != TAPE_PROMOTE_STAGE_PHASE1 && !adopt
        && (uint64_t)t->sb.total_chunks - (uint64_t)t->free_next
           < (uint64_t)len) {
        return TAPE_ERR_CARTRIDGE_FULL;
    }

    t->promote_in_progress = true;
    t->promote_adopt = adopt;
    t->promote_phase2 = phase2;
    t->promote_s = s;
    t->promote_len = len;
    t->promote_frames = n;
    t->promote_next_sequence = t->cartridge_sequence + 1u;
    promote_reset_copy(t);
    t->promote_phase = phase;
    t->promote_done = 0u;
    t->promote_total = promote_remaining_units(t, phase);
    *terminal = false;
    return TAPE_OK;
}

/*
 * One step of the operation. Returns TAPE_OK with *stop set when the budget is
 * spent before the step could start, and with *finished set when the operation
 * completed. Every step that starts performs exactly one block write (a copy
 * step may also read), so a budget of 1 always advances.
 */
static tape_result promote_step(tape *t, uint32_t budget, uint32_t *used,
                                bool *stop, bool *finished)
{
    uint8_t ph = t->promote_phase;
    tape_result rc = TAPE_OK;
    bool done = false;

    *stop = false;
    *finished = false;

    if (ph == PROMOTE_PHASE_COPY_STAGE || ph == PROMOTE_PHASE_COPY_FINAL) {
        bool final = ph == PROMOTE_PHASE_COPY_FINAL;
        rc = promote_copy(t, &t->idx[TAPE_SIDE_B],
                          final ? 0u : t->promote_s, budget, used, &done);
        if (rc != TAPE_OK) { return rc; }
        if (!done) { *stop = true; return TAPE_OK; }
        promote_reset_copy(t);
        t->promote_phase = final ? PROMOTE_PHASE_A_FINAL_ENTRIES
                                 : PROMOTE_PHASE_A_STAGE_ENTRIES;
        return TAPE_OK;
    }

    if (*used >= budget) { *stop = true; return TAPE_OK; }
    (*used)++;
    t->promote_done++;

    if (ph == PROMOTE_PHASE_A_STAGE_ENTRIES) {
        rc = promote_commit_entries(t, TAPE_SIDE_A, t->promote_s);
        t->promote_phase = PROMOTE_PHASE_A_STAGE_HEADER;
    } else if (ph == PROMOTE_PHASE_A_STAGE_HEADER) {
        rc = promote_commit_header(t, TAPE_SIDE_A, t->promote_s);
        t->promote_phase = t->promote_adopt ? PROMOTE_PHASE_SB_STAGE_PARTNER
                                            : PROMOTE_PHASE_B_STAGE_ENTRIES;
    } else if (ph == PROMOTE_PHASE_B_STAGE_ENTRIES) {
        rc = promote_commit_entries(t, TAPE_SIDE_B, t->promote_s);
        t->promote_phase = PROMOTE_PHASE_B_STAGE_HEADER;
    } else if (ph == PROMOTE_PHASE_B_STAGE_HEADER) {
        rc = promote_commit_header(t, TAPE_SIDE_B, t->promote_s);
        t->promote_phase = PROMOTE_PHASE_SB_STAGE_PARTNER;
    } else if (ph == PROMOTE_PHASE_SB_STAGE_PARTNER) {
        rc = promote_sb_partner(t, t->promote_s + t->promote_len,
                                TAPE_PROMOTE_STAGE_PHASE1, t->promote_s);
        t->promote_phase = PROMOTE_PHASE_SB_STAGE_CAND;
    } else if (ph == PROMOTE_PHASE_SB_STAGE_CAND) {
        rc = promote_sb_candidate(t, t->promote_s + t->promote_len,
                                  TAPE_PROMOTE_STAGE_PHASE1, t->promote_s);
        t->free_next = t->promote_s + t->promote_len;
        /* §9.3.2 step 5: [0, len) against the live set [S, S+len). */
        t->promote_phase = t->promote_phase2 ? PROMOTE_PHASE_COPY_FINAL
                                             : PROMOTE_PHASE_SB_DECLINE_PARTNER;
    } else if (ph == PROMOTE_PHASE_SB_DECLINE_PARTNER) {
        rc = promote_sb_partner(t, t->sb.a_high_water,
                                TAPE_PROMOTE_STAGE_NONE, 0u);
        t->promote_phase = PROMOTE_PHASE_SB_DECLINE_CAND;
    } else if (ph == PROMOTE_PHASE_SB_DECLINE_CAND) {
        rc = promote_sb_candidate(t, t->sb.a_high_water,
                                  TAPE_PROMOTE_STAGE_NONE, 0u);
        *finished = true;
    } else if (ph == PROMOTE_PHASE_A_FINAL_ENTRIES) {
        rc = promote_commit_entries(t, TAPE_SIDE_A, 0u);
        t->promote_phase = PROMOTE_PHASE_A_FINAL_HEADER;
    } else if (ph == PROMOTE_PHASE_A_FINAL_HEADER) {
        rc = promote_commit_header(t, TAPE_SIDE_A, 0u);
        t->promote_phase = PROMOTE_PHASE_B_FINAL_ENTRIES;
    } else if (ph == PROMOTE_PHASE_B_FINAL_ENTRIES) {
        rc = promote_commit_entries(t, TAPE_SIDE_B, 0u);
        t->promote_phase = PROMOTE_PHASE_B_FINAL_HEADER;
    } else if (ph == PROMOTE_PHASE_B_FINAL_HEADER) {
        rc = promote_commit_header(t, TAPE_SIDE_B, 0u);
        t->promote_phase = PROMOTE_PHASE_SB_FINAL_PARTNER;
    } else if (ph == PROMOTE_PHASE_SB_FINAL_PARTNER) {
        rc = promote_sb_partner(t, t->promote_len,
                                TAPE_PROMOTE_STAGE_NONE, 0u);
        t->promote_phase = PROMOTE_PHASE_SB_FINAL_CAND;
    } else if (ph == PROMOTE_PHASE_SB_FINAL_CAND) {
        rc = promote_sb_candidate(t, t->promote_len,
                                  TAPE_PROMOTE_STAGE_NONE, 0u);
        *finished = true;
    } else {
        rc = TAPE_ERR_INCONSISTENT;
    }

    if (rc == TAPE_OK && *finished) {
        t->free_next = tape_derive_free_next(&t->idx[TAPE_SIDE_B],
                                              &t->sb, TAPE_SIDE_B);
        promote_finish(t);
    }
    return rc;
}

tape_result tape_promote(tape *t, uint32_t block_budget, bool *more_work,
                         tape_progress_fn cb, void *user)
{
    uint32_t used = 0u;
    tape_result rc;
    bool terminal;

    if (t == NULL || more_work == NULL) { return TAPE_ERR_INVALID_ARG; }
    /* engine-api §9.1: a call from inside a progress callback is BUSY with no
       state change, and it never ends the operation. */
    if (t->in_callback) {
        *more_work = t->promote_in_progress;
        return TAPE_ERR_BUSY;
    }
    *more_work = false;
    if (!t->mounted) { return TAPE_ERR_NOT_MOUNTED; }
    if (t->faulted) { return TAPE_ERR_FAULTED; }
    if (t->rec_armed || t->rate_q16_16 != 0) { return TAPE_ERR_BUSY; }
    if (t->dup_in_progress || t->respool_in_progress) { return TAPE_ERR_BUSY; }
    if (!t->effective_writable) { return TAPE_ERR_READ_ONLY; }
    /* §9.1: after the state matrix and writability, no state change. */
    if (block_budget == 0u) {
        *more_work = t->promote_in_progress;
        return TAPE_ERR_INVALID_ARG;
    }

    if (!t->promote_in_progress) {
        rc = promote_begin(t, &terminal);
        if (rc != TAPE_OK || terminal) {
            *more_work = false;
            return rc;
        }
    }

    while (t->promote_in_progress) {
        bool stop, finished;

        rc = promote_step(t, block_budget, &used, &stop, &finished);
        if (rc != TAPE_OK) {
            /* §9.1 termination. An own-device write or flush failure has
               already quarantined the instance (§7.2). */
            t->promote_in_progress = false;
            t->promote_phase = 0u;
            promote_reset_copy(t);
            *more_work = false;
            return rc;
        }
        if (stop || finished) { break; }
    }

    *more_work = t->promote_in_progress;
    if (cb != NULL) {
        t->in_callback = true;
        dev_progress(cb, user, t->promote_done, t->promote_total);
        t->in_callback = false;
    }
    return TAPE_OK;
}
