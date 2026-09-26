/*
 * respool.c — incremental DRAFT-8 re-spool / WP-12a implementation.
 *
 * Normative: spec/tapefs-v1.md §4.5, §7, §8 and §9.4; engine-api §9–§10.
 *
 * Classification is completed before the first write. The resulting operation
 * is retained in caller-owned instance state so every call performs at most
 * block_budget block reads/writes and can resume without repeating work.
 */
#include <string.h>

#include "tape_internal.h"
#include "dev.h"

#define RESPOOL_FRAMES_PER_BLOCK (TAPE_BLOCK_SIZE / TAPE_FRAME_BYTES)

/* Sparse tags keep the state machine as direct control flow under Guardrail 09. */
#define RESPOOL_PHASE_STAGE_CLEAR  7u
#define RESPOOL_PHASE_COPY_PASS1  31u
#define RESPOOL_PHASE_COMMIT_PASS1 73u
#define RESPOOL_PHASE_COPY_PASS2  127u
#define RESPOOL_PHASE_COMMIT_PASS2 191u

static bool entry_intersects_run(const struct tape_entry *e,
                                 uint32_t first, uint32_t count)
{
    uint64_t e_first = (uint64_t)e->first_chunk_id;
    uint64_t e_last = tape_entry_last_chunk(e);
    uint64_t r_first = (uint64_t)first;
    uint64_t r_last = r_first + (uint64_t)count - 1u;

    return e_first <= r_last && r_first <= e_last;
}

static bool index_intersects_run(const struct tape_index *idx,
                                 uint32_t first, uint32_t count)
{
    uint32_t i;

    for (i = 0u; i < idx->entry_count; i++) {
        if (entry_intersects_run(&idx->entries[i], first, count)) {
            return true;
        }
    }
    return false;
}

static bool runs_intersect(uint32_t a_first, uint32_t a_count,
                           uint32_t b_first, uint32_t b_count)
{
    uint64_t a_end = (uint64_t)a_first + (uint64_t)a_count;
    uint64_t b_end = (uint64_t)b_first + (uint64_t)b_count;

    return (uint64_t)a_first < b_end && (uint64_t)b_first < a_end;
}

static bool find_pass1(const struct tape *t, uint32_t len, uint32_t *out)
{
    uint32_t first;
    uint32_t last_start;

    if (len == 0u || len > t->sb.total_chunks) { return false; }
    if (t->sb.a_high_water > t->sb.total_chunks - len) { return false; }

    last_start = t->sb.total_chunks - len;
    for (first = t->sb.a_high_water; first <= last_start; first++) {
        if (index_intersects_run(&t->idx[TAPE_SIDE_A], first, len)) { continue; }
        if (index_intersects_run(&t->idx[TAPE_SIDE_B], first, len)) { continue; }
        *out = first;
        return true;
    }
    return false;
}

/* Pass 2 may reclaim the OLD B run after pass 1 commits; it must avoid A and
 * the pass-1 destination, which is the sole live B copy at that point. */
static bool find_pass2(const struct tape *t, uint32_t len, uint32_t pass1,
                       uint32_t *out)
{
    uint32_t first;
    uint32_t last_start;

    if (pass1 <= t->sb.a_high_water || len == 0u) { return false; }
    last_start = pass1 - 1u;

    for (first = t->sb.a_high_water; first <= last_start; first++) {
        uint64_t end = (uint64_t)first + (uint64_t)len;
        if (end > (uint64_t)t->sb.total_chunks) { break; }
        if (index_intersects_run(&t->idx[TAPE_SIDE_A], first, len)) { continue; }
        if (runs_intersect(first, len, pass1, len)) { continue; }
        *out = first;
        return true;
    }
    return false;
}

static void respool_reset_copy(tape *t)
{
    t->respool_copy_block = 0u;
    t->respool_copy_frame = 0u;
}

static void respool_finish(tape *t)
{
    t->respool_in_progress = false;
    t->respool_phase = 0u;
    t->respool_half = false;
    respool_reset_copy(t);
}

/*
 * Incrementally copy the CURRENT live B timeline into one compact run. The
 * dedicated respool_block persists across calls because tape_service is allowed
 * during respool and may reuse the engine's ordinary block scratch.
 *
 * Each device read/write consumes one unit of block_budget; flushes are barriers
 * and consume no block units.
 */
static tape_result respool_copy(tape *t, uint32_t dest_chunk,
                                uint32_t budget, uint32_t *used, bool *done)
{
    const struct tape_index *src = &t->idx[TAPE_SIDE_B];
    uint32_t total_blocks =
        (uint32_t)((t->respool_frames + (uint64_t)RESPOOL_FRAMES_PER_BLOCK - 1u)
                   / (uint64_t)RESPOOL_FRAMES_PER_BLOCK);

    *done = false;
    while (t->respool_copy_block < total_blocks) {
        uint64_t block_start =
            (uint64_t)t->respool_copy_block * (uint64_t)RESPOOL_FRAMES_PER_BLOCK;
        uint32_t want = RESPOOL_FRAMES_PER_BLOCK;

        if (t->respool_frames - block_start < (uint64_t)want) {
            want = (uint32_t)(t->respool_frames - block_start);
        }
        if (t->respool_copy_frame == 0u) {
            memset(t->respool_block, 0, TAPE_BLOCK_SIZE);
        }

        if (t->respool_copy_frame < want) {
            uint64_t timeline = block_start + (uint64_t)t->respool_copy_frame;
            uint64_t physical;
            uint32_t source_lba;
            uint32_t source_off;
            uint32_t source_room;
            uint32_t run;
            uint32_t take;

            if (*used >= budget) { return TAPE_OK; }
            if (!tape_timeline_physical(src, timeline, &physical)) {
                return TAPE_ERR_NO_VALID_INDEX;
            }
            source_lba = t->sb.lba_chunk_base
                       + (uint32_t)(physical / (uint64_t)RESPOOL_FRAMES_PER_BLOCK);
            source_off = (uint32_t)(physical % (uint64_t)RESPOOL_FRAMES_PER_BLOCK);
            source_room = RESPOOL_FRAMES_PER_BLOCK - source_off;
            run = tape_timeline_run(src, timeline);
            take = want - t->respool_copy_frame;
            if (take > source_room) { take = source_room; }
            if (take > run) { take = run; }
            if (take == 0u) { return TAPE_ERR_NO_VALID_INDEX; }

            if (dev_read(&t->dev, source_lba, 1u, t->block) != 0) {
                return TAPE_ERR_IO;
            }
            (*used)++;
            memcpy(t->respool_block
                       + (size_t)t->respool_copy_frame * TAPE_FRAME_BYTES,
                   t->block + (size_t)source_off * TAPE_FRAME_BYTES,
                   (size_t)take * TAPE_FRAME_BYTES);
            t->respool_copy_frame += take;
            continue;
        }

        if (*used >= budget) { return TAPE_OK; }
        {
            uint64_t dest_lba =
                (uint64_t)t->sb.lba_chunk_base
                + (uint64_t)dest_chunk * (uint64_t)TAPE_CHUNK_BLOCKS
                + (uint64_t)t->respool_copy_block;
            if (dest_lba >= (uint64_t)t->dev.block_count) {
                return TAPE_ERR_GEOMETRY;
            }
            if (dev_write(&t->dev, (uint32_t)dest_lba, 1u,
                          t->respool_block) != 0) {
                t->faulted = true;
                return TAPE_ERR_IO;
            }
        }
        (*used)++;
        t->respool_copy_block++;
        t->respool_copy_frame = 0u;
    }

    if (dev_flush(&t->dev) != 0) {
        t->faulted = true;
        return TAPE_ERR_IO;
    }
    *done = true;
    return TAPE_OK;
}

static uint32_t inactive_b_slot(const struct tape *t)
{
    return (t->live_slot[TAPE_SIDE_B] == 0u) ? 1u : 0u;
}

static uint32_t b_slot_lba(const struct tape *t, uint32_t slot)
{
    return slot == 0u ? t->sb.lba_index_b0 : t->sb.lba_index_b1;
}

/*
 * One §8 index commit, as two single-block halves so a call with
 * block_budget == 1 still makes progress (engine-api §9). The entries half
 * installs the new one-run index in memory and writes its entry block; the
 * header half writes block 0 — the commit point — and only then moves the
 * live slot, the sequence and free_next. Between the halves the new index is
 * in memory but not yet selectable on media; the pass destination it names
 * was fully copied and flushed before either half, so playback of it in the
 * allowed render/service columns is byte-identical to the old timeline.
 */
static tape_result respool_commit_entries(tape *t, uint32_t dest_chunk, uint32_t *used)
{
    struct tape_index *b = &t->idx[TAPE_SIDE_B];

    b->sequence = t->respool_next_sequence;
    b->side = (uint8_t)TAPE_SIDE_B;
    b->entry_count = 1u;
    b->total_frames = t->respool_frames;
    b->entries[0].first_chunk_id = dest_chunk;
    b->entries[0].start_frame = 0u;
    b->entries[0].frame_count = (uint32_t)t->respool_frames;

    *used += tape_index_entry_blocks(b->entry_count);   /* 1 for one run */
    return tape_commit_index_entries(t, b_slot_lba(t, inactive_b_slot(t)), b);
}

static tape_result respool_commit_header(tape *t, uint32_t *used)
{
    struct tape_index *b = &t->idx[TAPE_SIDE_B];
    uint32_t slot = inactive_b_slot(t);
    tape_result rc;

    (*used)++;
    rc = tape_commit_index_header(t, b_slot_lba(t, slot), b);
    if (rc != TAPE_OK) { return rc; }

    t->live_slot[TAPE_SIDE_B] = slot;
    t->cartridge_sequence = t->respool_next_sequence;
    t->respool_next_sequence++;
    t->free_next = tape_derive_free_next(b, &t->sb, TAPE_SIDE_B);
    return TAPE_OK;
}

/* Classify the whole operation before its first write. */
static tape_result respool_begin(tape *t, bool *terminal)
{
    const struct tape_index *b = &t->idx[TAPE_SIDE_B];
    uint32_t len;
    uint32_t pass1;
    uint32_t pass2 = 0u;
    uint32_t seq_need;
    bool pass2_possible;
    bool stage_clear;

    *terminal = true;
    if (b->total_frames == 0u) { return TAPE_OK; }

    len = tape_chunks_for_frames(b->total_frames);
    if (len == 0u) { return TAPE_ERR_NO_VALID_INDEX; }
    if (!find_pass1(t, len, &pass1)) { return TAPE_ERR_CARTRIDGE_FULL; }

    pass2_possible = find_pass2(t, len, pass1, &pass2);
    if (pass2_possible && tape_headroom_ok(t->cartridge_sequence, 2u)) {
        seq_need = 2u;
    } else {
        seq_need = 1u;
    }
    if (!tape_headroom_ok(t->cartridge_sequence, seq_need)) {
        return TAPE_ERR_SEQUENCE_EXHAUSTED;
    }

    stage_clear = (t->sb.promote_stage == TAPE_PROMOTE_STAGE_PHASE1);
    if (stage_clear && !tape_headroom_ok(t->sb.sb_generation, 1u)) {
        return TAPE_ERR_SEQUENCE_EXHAUSTED;
    }

    t->respool_in_progress = true;
    t->respool_has_pass2 = (seq_need == 2u);
    t->respool_len = len;
    t->respool_pass1 = pass1;
    t->respool_pass2 = pass2;
    t->respool_dest = pass1;
    t->respool_frames = b->total_frames;
    t->respool_next_sequence = t->cartridge_sequence + 1u;
    respool_reset_copy(t);
    t->respool_half = false;
    t->respool_phase = stage_clear ? RESPOOL_PHASE_STAGE_CLEAR
                                   : RESPOOL_PHASE_COPY_PASS1;
    *terminal = false;
    return TAPE_OK;
}

tape_result tape_respool(tape *t, uint32_t block_budget, bool *more_work)
{
    uint32_t used = 0u;
    tape_result rc;
    bool terminal;

    if (t == NULL || more_work == NULL) { return TAPE_ERR_INVALID_ARG; }
    if (!t->mounted) { return TAPE_ERR_NOT_MOUNTED; }
    *more_work = false;
    if (t->faulted) { return TAPE_ERR_FAULTED; }

    /* A continuation has already passed every operation precondition. */
    if (t->respool_in_progress) {
        if (block_budget == 0u) { return TAPE_ERR_INVALID_ARG; }
    } else {
        if (!t->side_b_valid) { return TAPE_ERR_NO_VALID_INDEX; }
        if (t->rec_armed || t->rate_q16_16 != 0 || t->promote_in_progress) {
            return TAPE_ERR_BUSY;
        }
        if (!t->effective_writable) { return TAPE_ERR_READ_ONLY; }
        if (block_budget == 0u) { return TAPE_ERR_INVALID_ARG; }

        rc = respool_begin(t, &terminal);
        if (rc != TAPE_OK || terminal) {
            *more_work = false;
            return rc;
        }
    }

    while (t->respool_in_progress) {
        bool done = false;

        if (t->respool_phase == RESPOOL_PHASE_STAGE_CLEAR) {
            /* §4.6 partner then candidate, one block each, so a budget of 1
               cannot stall here (engine-api §9: the loop must terminate). */
            if (used >= block_budget) { goto budget_done; }
            used++;
            if (!t->respool_half) {
                rc = tape_sb_clear_stage_partner(t);
                if (rc != TAPE_OK) { goto fail; }
                t->respool_half = true;
            } else {
                rc = tape_sb_clear_stage_candidate(t);
                if (rc != TAPE_OK) { goto fail; }
                t->respool_half = false;
                t->respool_phase = RESPOOL_PHASE_COPY_PASS1;
            }
        } else if (t->respool_phase == RESPOOL_PHASE_COPY_PASS1) {
            rc = respool_copy(t, t->respool_pass1, block_budget, &used, &done);
            if (rc != TAPE_OK) { goto fail; }
            if (!done) { goto budget_done; }
            respool_reset_copy(t);
            t->respool_phase = RESPOOL_PHASE_COMMIT_PASS1;
        } else if (t->respool_phase == RESPOOL_PHASE_COMMIT_PASS1) {
            if (used >= block_budget) { goto budget_done; }
            if (!t->respool_half) {
                rc = respool_commit_entries(t, t->respool_pass1, &used);
                if (rc != TAPE_OK) { goto fail; }
                t->respool_half = true;
                goto next_step;
            }
            rc = respool_commit_header(t, &used);
            if (rc != TAPE_OK) { goto fail; }
            t->respool_half = false;
            if (t->respool_has_pass2) {
                t->respool_dest = t->respool_pass2;
                respool_reset_copy(t);
                t->respool_phase = RESPOOL_PHASE_COPY_PASS2;
            } else {
                respool_finish(t);
                *more_work = false;
                return TAPE_OK;
            }
        } else if (t->respool_phase == RESPOOL_PHASE_COPY_PASS2) {
            rc = respool_copy(t, t->respool_pass2, block_budget, &used, &done);
            if (rc != TAPE_OK) { goto fail; }
            if (!done) { goto budget_done; }
            respool_reset_copy(t);
            t->respool_phase = RESPOOL_PHASE_COMMIT_PASS2;
        } else if (t->respool_phase == RESPOOL_PHASE_COMMIT_PASS2) {
            if (used >= block_budget) { goto budget_done; }
            if (!t->respool_half) {
                rc = respool_commit_entries(t, t->respool_pass2, &used);
                if (rc != TAPE_OK) { goto fail; }
                t->respool_half = true;
                goto next_step;
            }
            rc = respool_commit_header(t, &used);
            if (rc != TAPE_OK) { goto fail; }
            t->respool_half = false;
            respool_finish(t);
            *more_work = false;
            return TAPE_OK;
        } else {
            rc = TAPE_ERR_INCONSISTENT;
            goto fail;
        }

next_step:
        if (used >= block_budget) { goto budget_done; }
    }

budget_done:
    *more_work = t->respool_in_progress;
    return TAPE_OK;

fail:
    respool_finish(t);
    *more_work = false;
    return rc;
}
