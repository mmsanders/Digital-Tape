/*
 * respool.c — WP-12 deterministic re-spool tranche.
 *
 * Normative: spec/tapefs-v1.md §4.5, §7, §8 and §9.4; engine-api §9.
 *
 * This slice implements the independently covered one-call semantic tranche:
 * empty/no-op, pass classification, one/two-pass copying, commit ordering,
 * sequence headroom, degraded/full refusals and §8 stage clearing. WP-12a's
 * small-budget continuation/state machine remains deliberately outside this
 * issue; a positive budget too small to finish the already-classified semantic
 * operation is refused before the first write rather than silently exceeding
 * the caller's budget.
 */

#include <string.h>

#include "tape_internal.h"
#include "dev.h"

#define RESPOOL_FRAMES_PER_BLOCK (TAPE_BLOCK_SIZE / TAPE_FRAME_BYTES)

static uint32_t respool_data_blocks(uint64_t frames)
{
    return (uint32_t)((frames + (uint64_t)RESPOOL_FRAMES_PER_BLOCK - 1u)
                      / (uint64_t)RESPOOL_FRAMES_PER_BLOCK);
}

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

/* Lowest pass-1 run satisfying §9.4(a,b). */
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

/* Lowest qualifying run below pass 1 after pass 1 is the live Side-B layout. */
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

/*
 * Copy the timeline represented by src into a compact run beginning at
 * dest_chunk. The output layout starts at frame 0 of the first destination
 * chunk. One block of engine scratch is the outgoing block and mix_block is the
 * source block, so no heap or large stack buffer is introduced.
 */
static tape_result copy_timeline(struct tape *t, const struct tape_index *src,
                                 uint32_t dest_chunk)
{
    uint64_t frame = 0u;
    uint64_t total = src->total_frames;
    uint32_t out_block = 0u;

    while (frame < total) {
        uint32_t want = RESPOOL_FRAMES_PER_BLOCK;
        uint32_t made = 0u;
        uint64_t left = total - frame;
        uint32_t dest_lba;

        if (left < (uint64_t)want) { want = (uint32_t)left; }
        memset(t->block, 0, TAPE_BLOCK_SIZE);

        while (made < want) {
            uint64_t physical;
            uint32_t source_lba;
            uint32_t source_off;
            uint32_t source_room;
            uint32_t run;
            uint32_t take;
            uint64_t timeline = frame + (uint64_t)made;

            if (!tape_timeline_physical(src, timeline, &physical)) {
                return TAPE_ERR_NO_VALID_INDEX;
            }
            source_lba = t->sb.lba_chunk_base
                       + (uint32_t)(physical / (uint64_t)RESPOOL_FRAMES_PER_BLOCK);
            source_off = (uint32_t)(physical % (uint64_t)RESPOOL_FRAMES_PER_BLOCK);
            source_room = RESPOOL_FRAMES_PER_BLOCK - source_off;
            run = tape_timeline_run(src, timeline);
            take = want - made;
            if (take > source_room) { take = source_room; }
            if (take > run) { take = run; }
            if (take == 0u) { return TAPE_ERR_NO_VALID_INDEX; }

            if (dev_read(&t->dev, source_lba, 1u, t->mix_block) != 0) {
                t->faulted = true;
                return TAPE_ERR_IO;
            }
            memcpy(t->block + (size_t)made * TAPE_FRAME_BYTES,
                   t->mix_block + (size_t)source_off * TAPE_FRAME_BYTES,
                   (size_t)take * TAPE_FRAME_BYTES);
            made += take;
        }

        dest_lba = t->sb.lba_chunk_base
                 + dest_chunk * TAPE_CHUNK_BLOCKS + out_block;
        if (dev_write(&t->dev, dest_lba, 1u, t->block) != 0) {
            t->faulted = true;
            return TAPE_ERR_IO;
        }

        frame += (uint64_t)want;
        out_block++;
    }

    /* §8 step 2: no index bytes land before copied audio is durable. */
    if (dev_flush(&t->dev) != 0) {
        t->faulted = true;
        return TAPE_ERR_IO;
    }
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

static tape_result commit_compact_pass(struct tape *t, uint32_t dest_chunk)
{
    struct tape_index *b = &t->idx[TAPE_SIDE_B];
    uint64_t frames = b->total_frames;
    uint32_t slot = inactive_b_slot(t);
    uint32_t sequence = t->cartridge_sequence + 1u;
    tape_result rc;

    rc = copy_timeline(t, b, dest_chunk);
    if (rc != TAPE_OK) { return rc; }

    b->sequence = sequence;
    b->side = (uint8_t)TAPE_SIDE_B;
    b->entry_count = 1u;
    b->total_frames = frames;
    b->entries[0].first_chunk_id = dest_chunk;
    b->entries[0].start_frame = 0u;
    b->entries[0].frame_count = (uint32_t)frames;

    rc = tape_commit_index(t, b_slot_lba(t, slot), b);
    if (rc != TAPE_OK) { return rc; }

    t->live_slot[TAPE_SIDE_B] = slot;
    t->cartridge_sequence = sequence;
    t->free_next = tape_derive_free_next(b, &t->sb, TAPE_SIDE_B);
    return TAPE_OK;
}

/*
 * Conservative block-work estimate for this tranche. It counts one source read
 * plus one destination write for each copied data block, the one-entry array
 * and header writes for each commit, and the two superblock writes if §8 stage
 * clearing applies. Flushes are barriers rather than blocks.
 *
 * The published semantic budget (65535) comfortably exceeds every fixture. A
 * smaller positive budget belongs to WP-12a; this slice refuses it before any
 * write instead of violating "at most block_budget".
 */
static bool semantic_budget_fits(uint32_t block_budget, uint32_t data_blocks,
                                 uint32_t passes, bool stage_clear)
{
    uint64_t need = (uint64_t)passes
                  * ((uint64_t)data_blocks * 2u + 2u);
    if (stage_clear) { need += 2u; }
    return (uint64_t)block_budget >= need;
}

tape_result tape_respool(tape *t, uint32_t block_budget, bool *more_work)
{
    struct tape_index *b;
    uint64_t frames;
    uint32_t len;
    uint32_t pass1;
    uint32_t pass2 = 0u;
    uint32_t seq_need;
    uint32_t data_blocks;
    bool pass2_possible;
    bool stage_clear;
    tape_result rc;

    if (t == NULL || more_work == NULL) { return TAPE_ERR_INVALID_ARG; }
    if (!t->mounted) { return TAPE_ERR_NOT_MOUNTED; }
    *more_work = false;
    if (t->faulted) { return TAPE_ERR_FAULTED; }

    /* §10 degraded-B overrides the ordinary idle/playing rows for respool. */
    if (!t->side_b_valid) { return TAPE_ERR_NO_VALID_INDEX; }

    /* Respool starts only from mounted-idle. */
    if (t->rec_armed || t->rate_q16_16 != 0) { return TAPE_ERR_BUSY; }

    /* §4.3 permission is about the mount, not the mounted side. */
    if (!t->effective_writable) { return TAPE_ERR_READ_ONLY; }

    /* §9.1: checked after state/writability. */
    if (block_budget == 0u) { return TAPE_ERR_INVALID_ARG; }

    b = &t->idx[TAPE_SIDE_B];
    frames = b->total_frames;

    /* §9.4 / V4-005: zero-consumption no-op. Do not consult either counter. */
    if (frames == 0u) { return TAPE_OK; }

    len = tape_chunks_for_frames(frames);
    if (len == 0u) { return TAPE_ERR_NO_VALID_INDEX; }

    /* All zero-write refusals are classified before stage clearing or copying. */
    if (!find_pass1(t, len, &pass1)) { return TAPE_ERR_CARTRIDGE_FULL; }

    pass2_possible = find_pass2(t, len, pass1, &pass2);

    /*
     * §4.5: pass 2 is optional. If geometry permits it but only one sequence
     * remains, reserve one and stop after mandatory pass 1.
     */
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

    data_blocks = respool_data_blocks(frames);
    if (!semantic_budget_fits(block_budget, data_blocks, seq_need, stage_clear)) {
        return TAPE_ERR_INVALID_ARG;
    }

    /* §8: after every operation precondition, before the first chunk/index write. */
    if (stage_clear) {
        rc = tape_sb_clear_stage(t);
        if (rc != TAPE_OK) { return rc; }
    }

    rc = commit_compact_pass(t, pass1);
    if (rc != TAPE_OK) { return rc; }

    if (seq_need == 2u) {
        rc = commit_compact_pass(t, pass2);
        if (rc != TAPE_OK) { return rc; }
    }

    return TAPE_OK;
}
