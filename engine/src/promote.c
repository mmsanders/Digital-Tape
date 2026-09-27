/*
 * promote.c — bounded DRAFT-8 tape_promote implementation for the independently
 * published promote_draft8 FRESH/classification tranche.
 *
 * Covered here: §9.3.0 classification; §4.5 branch-exact headroom and precedence;
 * §9.3.1 FRESH adopt/allocate phase 1; §9.3.2 uninterrupted decline/complete
 * phase 2; §4.6 partner-first superblock durability; block-budgeted chunk copy.
 *
 * Deliberately not claimed by this tranche: §9.3.3 RESUME/crash closure, stored
 * position integration (caller-owned), progress-callback/re-entry semantics, and
 * copied-audio golden/listening acceptance. Stage-1 entry therefore refuses
 * loudly rather than pretending RESUME has been implemented.
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
#define PROMOTE_PHASE_COPY_STAGE       7u
#define PROMOTE_PHASE_COMMIT_A_STAGE  23u
#define PROMOTE_PHASE_COMMIT_B_STAGE  41u
#define PROMOTE_PHASE_SB_STAGE        67u
#define PROMOTE_PHASE_SB_DECLINE     101u
#define PROMOTE_PHASE_COPY_FINAL     137u
#define PROMOTE_PHASE_COMMIT_A_FINAL 173u
#define PROMOTE_PHASE_COMMIT_B_FINAL 211u
#define PROMOTE_PHASE_SB_FINAL       251u

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

static uint32_t promote_slot_lba(const struct tape *t, tape_side side,
                                 uint32_t slot)
{
    if (side == TAPE_SIDE_A) {
        return (slot == 0u) ? t->sb.lba_index_a0 : t->sb.lba_index_a1;
    }
    return (slot == 0u) ? t->sb.lba_index_b0 : t->sb.lba_index_b1;
}

static void promote_make_index(struct tape_index *idx, tape_side side,
                               uint32_t sequence, uint32_t first_chunk,
                               uint64_t frames)
{
    idx->sequence = sequence;
    idx->side = (uint8_t)side;
    idx->entry_count = 1u;
    idx->total_frames = frames;
    idx->entries[0].first_chunk_id = first_chunk;
    idx->entries[0].start_frame = 0u;
    idx->entries[0].frame_count = (uint32_t)frames;
}

/*
 * §4.6 ordinary superblock update. The selected raw bytes are patched in place
 * so fields the engine does not model stay byte-identical. Partner first,
 * candidate last, a flush behind each; exactly the same ordering as stage clear.
 */
static tape_result promote_sb_update(tape *t, uint32_t high,
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
    if (dev_write(&t->dev, t->sb_candidate_lba, 1u, blk) != 0) {
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
 * Incremental compacting copy. mix_block persists in the caller-owned instance,
 * so a tiny budget may stop after any source read and resume without repeating
 * it. Every accepted source frame is copied in timeline order; bytes after the
 * last frame of the final destination chunk are deterministically zero.
 *
 * Reads and writes each consume one unit of block_budget. Flushes are barriers,
 * not blocks, and therefore consume no block units.
 */
static tape_result promote_copy(tape *t, const struct tape_index *src,
                                uint32_t dst_first, uint32_t budget,
                                uint32_t *used, bool *done)
{
    uint64_t total_blocks =
        (uint64_t)t->promote_len * (uint64_t)TAPE_CHUNK_BLOCKS;

    *done = false;
    while ((uint64_t)t->promote_copy_block < total_blocks) {
        uint64_t timeline_frame =
            (uint64_t)t->promote_copy_block * (uint64_t)PROMOTE_FRAMES_PER_BLOCK
            + (uint64_t)t->promote_copy_frame;

        if (t->promote_copy_frame == 0u) {
            memset(t->mix_block, 0, TAPE_BLOCK_SIZE);
        }

        if (t->promote_copy_frame < PROMOTE_FRAMES_PER_BLOCK
            && timeline_frame < src->total_frames) {
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
            if ((uint64_t)take > src->total_frames - timeline_frame) {
                take = (uint32_t)(src->total_frames - timeline_frame);
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
            memcpy(t->mix_block
                       + (size_t)t->promote_copy_frame * TAPE_FRAME_BYTES,
                   t->block + (size_t)source_offset * TAPE_FRAME_BYTES,
                   (size_t)take * TAPE_FRAME_BYTES);
            t->promote_copy_frame += take;
            continue;
        }

        /* Final partial block: the remainder was zeroed when this block began. */
        if (t->promote_copy_frame < PROMOTE_FRAMES_PER_BLOCK) {
            t->promote_copy_frame = PROMOTE_FRAMES_PER_BLOCK;
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
        t->promote_copy_block++;
        t->promote_copy_frame = 0u;
    }

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
 * Classify a FRESH operation completely before the first write. That is what
 * makes §4.5's exact branch reservation and the headroom-before-capacity
 * precedence decidable.
 */
static tape_result promote_begin(tape *t, bool *terminal)
{
    const struct tape_index *b = &t->idx[TAPE_SIDE_B];
    bool adopt, phase2;
    uint32_t len, s, seq_need;

    *terminal = true;

    if (!t->side_b_valid) { return TAPE_ERR_NO_VALID_INDEX; }
    if (b->total_frames == 0u) { return TAPE_ERR_INVALID_ARG; }

    if (t->sb.promote_stage == TAPE_PROMOTE_STAGE_PHASE1) {
        /* §9.3.3 is intentionally outside this independently asserted tranche. */
        return TAPE_ERR_BUSY;
    }

    if (promote_entries_equal(&t->idx[TAPE_SIDE_A], b)) {
        return TAPE_OK; /* NOTHING TO DO: zero counters consulted, zero writes. */
    }

    len = tape_chunks_for_frames(b->total_frames);
    adopt = b->entry_count == 1u
         && b->entries[0].start_frame == 0u
         && b->entries[0].first_chunk_id >= t->sb.a_high_water;
    s = adopt ? b->entries[0].first_chunk_id : t->free_next;
    phase2 = s >= len;

    if (adopt) {
        seq_need = phase2 ? 3u : 1u;
    } else {
        seq_need = phase2 ? 4u : 2u;
    }

    /* §4.5 first: both counters, widened, before any capacity refusal. */
    if (!tape_headroom_ok(t->cartridge_sequence, seq_need)
        || !tape_headroom_ok(t->sb.sb_generation, 2u)) {
        return TAPE_ERR_SEQUENCE_EXHAUSTED;
    }

    if (!adopt
        && (uint64_t)t->sb.total_chunks - (uint64_t)t->free_next
           < (uint64_t)len) {
        return TAPE_ERR_CARTRIDGE_FULL;
    }

    t->promote_in_progress = true;
    t->promote_adopt = adopt;
    t->promote_phase2 = phase2;
    t->promote_s = s;
    t->promote_len = len;
    t->promote_frames = b->total_frames;
    t->promote_next_sequence = t->cartridge_sequence + 1u;
    promote_reset_copy(t);
    t->promote_phase = adopt ? PROMOTE_PHASE_COMMIT_A_STAGE
                             : PROMOTE_PHASE_COPY_STAGE;
    *terminal = false;
    return TAPE_OK;
}

static tape_result promote_commit_one(tape *t, tape_side side,
                                      uint32_t first_chunk, uint32_t *used)
{
    uint32_t dst_slot = (t->live_slot[side] == 0u) ? 1u : 0u;
    uint32_t lba = promote_slot_lba(t, side, dst_slot);
    tape_result rc;

    promote_make_index(&t->idx[side], side, t->promote_next_sequence,
                       first_chunk, t->promote_frames);
    rc = tape_commit_index(t, lba, &t->idx[side]);
    *used += 2u; /* one entry-array block + one header block */
    if (rc != TAPE_OK) { return rc; }

    t->live_slot[side] = dst_slot;
    t->cartridge_sequence = t->promote_next_sequence;
    t->promote_next_sequence++;
    return TAPE_OK;
}

tape_result tape_promote(tape *t, uint32_t block_budget, bool *more_work,
                         tape_progress_fn cb, void *user)
{
    uint32_t used = 0u;
    tape_result rc;
    bool terminal;

    /* Progress delivery/re-entry is not asserted by promote_draft8. Keep the
       parameters source-compatible without manufacturing unverified semantics. */
    (void)cb;
    (void)user;

    if (t == NULL || more_work == NULL) { return TAPE_ERR_INVALID_ARG; }
    *more_work = false;
    if (!t->mounted) { return TAPE_ERR_NOT_MOUNTED; }
    if (t->faulted) { return TAPE_ERR_FAULTED; }
    if (t->rec_armed || t->rate_q16_16 != 0) { return TAPE_ERR_BUSY; }
    if (tape_dup_row_busy(t)) { return TAPE_ERR_BUSY; }
    if (!t->effective_writable) { return TAPE_ERR_READ_ONLY; }
    if (block_budget == 0u) { return TAPE_ERR_INVALID_ARG; }

    if (!t->promote_in_progress) {
        rc = promote_begin(t, &terminal);
        if (rc != TAPE_OK || terminal) {
            *more_work = false;
            return rc;
        }
    }

    while (t->promote_in_progress) {
        bool done = false;

        /*
         * Deliberately an if/else chain rather than a switch. Guardrail 09's
         * link-time backstop rejects compiler-generated jump tables because a
         * stored engine function address is indistinguishable from an authored
         * dispatch table. The state space is tiny; explicit control flow keeps
         * that invariant mechanically decidable.
         */
        if (t->promote_phase == PROMOTE_PHASE_COPY_STAGE) {
            rc = promote_copy(t, &t->idx[TAPE_SIDE_B], t->promote_s,
                              block_budget, &used, &done);
            if (rc != TAPE_OK) { goto fail; }
            if (!done) { goto budget_done; }
            promote_reset_copy(t);
            t->promote_phase = PROMOTE_PHASE_COMMIT_A_STAGE;
        } else if (t->promote_phase == PROMOTE_PHASE_COMMIT_A_STAGE) {
            if (block_budget - used < 2u) { goto budget_done; }
            rc = promote_commit_one(t, TAPE_SIDE_A, t->promote_s, &used);
            if (rc != TAPE_OK) { goto fail; }
            t->promote_phase = t->promote_adopt
                             ? PROMOTE_PHASE_SB_STAGE
                             : PROMOTE_PHASE_COMMIT_B_STAGE;
        } else if (t->promote_phase == PROMOTE_PHASE_COMMIT_B_STAGE) {
            if (block_budget - used < 2u) { goto budget_done; }
            rc = promote_commit_one(t, TAPE_SIDE_B, t->promote_s, &used);
            if (rc != TAPE_OK) { goto fail; }
            t->promote_phase = PROMOTE_PHASE_SB_STAGE;
        } else if (t->promote_phase == PROMOTE_PHASE_SB_STAGE) {
            if (block_budget - used < 2u) { goto budget_done; }
            rc = promote_sb_update(t, t->promote_s + t->promote_len,
                                   TAPE_PROMOTE_STAGE_PHASE1, t->promote_s);
            used += 2u;
            if (rc != TAPE_OK) { goto fail; }
            t->free_next = t->promote_s + t->promote_len;
            if (t->promote_phase2) {
                promote_reset_copy(t);
                t->promote_phase = PROMOTE_PHASE_COPY_FINAL;
            } else {
                t->promote_phase = PROMOTE_PHASE_SB_DECLINE;
            }
        } else if (t->promote_phase == PROMOTE_PHASE_SB_DECLINE) {
            if (block_budget - used < 2u) { goto budget_done; }
            rc = promote_sb_update(t, t->sb.a_high_water,
                                   TAPE_PROMOTE_STAGE_NONE, 0u);
            used += 2u;
            if (rc != TAPE_OK) { goto fail; }
            t->free_next = tape_derive_free_next(&t->idx[TAPE_SIDE_B],
                                                  &t->sb, TAPE_SIDE_B);
            promote_finish(t);
            *more_work = false;
            return TAPE_OK;
        } else if (t->promote_phase == PROMOTE_PHASE_COPY_FINAL) {
            rc = promote_copy(t, &t->idx[TAPE_SIDE_B], 0u,
                              block_budget, &used, &done);
            if (rc != TAPE_OK) { goto fail; }
            if (!done) { goto budget_done; }
            promote_reset_copy(t);
            t->promote_phase = PROMOTE_PHASE_COMMIT_A_FINAL;
        } else if (t->promote_phase == PROMOTE_PHASE_COMMIT_A_FINAL) {
            if (block_budget - used < 2u) { goto budget_done; }
            rc = promote_commit_one(t, TAPE_SIDE_A, 0u, &used);
            if (rc != TAPE_OK) { goto fail; }
            t->promote_phase = PROMOTE_PHASE_COMMIT_B_FINAL;
        } else if (t->promote_phase == PROMOTE_PHASE_COMMIT_B_FINAL) {
            if (block_budget - used < 2u) { goto budget_done; }
            rc = promote_commit_one(t, TAPE_SIDE_B, 0u, &used);
            if (rc != TAPE_OK) { goto fail; }
            t->promote_phase = PROMOTE_PHASE_SB_FINAL;
        } else if (t->promote_phase == PROMOTE_PHASE_SB_FINAL) {
            if (block_budget - used < 2u) { goto budget_done; }
            rc = promote_sb_update(t, t->promote_len,
                                   TAPE_PROMOTE_STAGE_NONE, 0u);
            used += 2u;
            if (rc != TAPE_OK) { goto fail; }
            t->free_next = tape_derive_free_next(&t->idx[TAPE_SIDE_B],
                                                  &t->sb, TAPE_SIDE_B);
            promote_finish(t);
            *more_work = false;
            return TAPE_OK;
        } else {
            rc = TAPE_ERR_INCONSISTENT;
            goto fail;
        }

        if (used >= block_budget) { goto budget_done; }
    }

budget_done:
    *more_work = t->promote_in_progress;
    return TAPE_OK;

fail:
    t->promote_in_progress = false;
    t->promote_phase = 0u;
    *more_work = false;
    return rc;
}
