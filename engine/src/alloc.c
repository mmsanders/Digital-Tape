/*
 * alloc.c — chunk allocation. spec/tapefs-v1.md §7 and Rule 3.
 *
 * Pure bookkeeping: nothing here touches the block device. Allocation decides
 * which chunk ids an operation may use; the commit protocol (§8) decides when
 * anything reaches media.
 *
 * The ownership partition (§7):
 *
 *   [0, a_high_water)          owned by Side A. No runtime path writes here.
 *                              The sole exception is promote phase 2, which is
 *                              not a general allocation and does not come here.
 *   [a_high_water, free_next)  allocated to Side B.
 *   [free_next, total_chunks)  unallocated.
 */

#include "tape_internal.h"

bool tape_may_reference(const struct tape_sb *sb, tape_side side, uint32_t id)
{
    if (id >= sb->total_chunks) {
        return false;
    }
    /* Side B may reference anything in range, including chunks owned by Side A.
       That is not a loophole — it is the copy-on-write mechanism that makes
       "start over" instant and Side B nearly free until it is edited. */
    if (side == TAPE_SIDE_B) {
        return true;
    }
    return id < sb->a_high_water;
}

bool tape_may_allocate(const struct tape_sb *sb, tape_side side, uint32_t id)
{
    if (id >= sb->total_chunks) {
        return false;
    }
    /* The asymmetry with tape_may_reference is the entire point of Rule 3. */
    if (side == TAPE_SIDE_B) {
        return id >= sb->a_high_water;
    }
    return false;
}

uint32_t tape_chunks_for_frames(uint64_t frames)
{
    if (frames == 0u) {
        return 0u;
    }
    return (uint32_t)((frames + TAPE_CHUNK_FRAMES - 1u) / TAPE_CHUNK_FRAMES);
}

tape_result tape_alloc_run(const struct tape_sb *sb, tape_side side,
                           uint32_t *free_next, uint32_t count,
                           uint32_t *out_first)
{
    uint64_t first, end;

    if (sb == NULL || free_next == NULL || out_first == NULL) {
        return TAPE_ERR_INVALID_ARG;
    }
    if (count == 0u) {
        return TAPE_ERR_INVALID_ARG;
    }
    if (side != TAPE_SIDE_B) {
        /* Side A owns its region and never allocates at runtime. */
        return TAPE_ERR_READ_ONLY;
    }

    first = (uint64_t)*free_next;

    /* free_next is floored at a_high_water by §7's derivation, but assert it
       rather than assume it: this is the boundary Rule 3 exists to hold, and a
       caller passing a stale free_next must not be able to allocate into the
       music. */
    if (first < (uint64_t)sb->a_high_water) {
        return TAPE_ERR_READ_ONLY;
    }

    /* 64-bit so a large count cannot wrap past total_chunks into a pass. */
    end = first + (uint64_t)count;
    if (end > (uint64_t)sb->total_chunks) {
        return TAPE_ERR_CARTRIDGE_FULL;
    }

    *out_first  = (uint32_t)first;
    *free_next  = (uint32_t)end;
    return TAPE_OK;
}
