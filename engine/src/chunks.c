/*
 * chunks.c — chunk arithmetic and WP-07 allocation. spec/tapefs-v1.md §7.
 *
 * tape_chunks_for_frames arrived first, split out of the accepted candidate's
 * alloc.c so that the allocator itself stayed out of the P1-R16 integration
 * candidate: §9.3.3's promote-resume row 3 is a MOUNT-time shape check that
 * compares a_high_water against the chunk length a timeline of n frames
 * occupies, so mount.c could not link without it.
 *
 * P1-R17 brings in the allocator proper, because VT8-001-REC-ALLOCSEQ is an
 * independent assertion about exactly this: allocation begins at the derived
 * free_next and never below a_high_water (VT8-A05). Ownership and reference are
 * separate predicates and are kept separate here so a caller cannot reach for
 * the wrong one — DRAFT-3's engine invariant 4 conflated them and was
 * unsatisfiable, since it forbade Side B from referencing below a_high_water,
 * which is exactly what tape_reset_side_b produces (V3-009, now Rule 3).
 *
 * tape_may_reference stays DECLARED AND NOT DEFINED. Nothing in this slice
 * evaluates it, and the engine's discipline is that an unimplemented symbol is
 * a link error rather than a body nobody has exercised.
 */

#include "tape_internal.h"

uint32_t tape_chunks_for_frames(uint64_t frames)
{
    if (frames == 0u) {
        return 0u;
    }
    return (uint32_t)((frames + TAPE_CHUNK_FRAMES - 1u) / TAPE_CHUNK_FRAMES);
}

bool tape_may_allocate(const struct tape_sb *sb, tape_side side, uint32_t id)
{
    if (id >= sb->total_chunks) { return false; }
    /* §7: Side A owns [0, a_high_water) and NO runtime path writes there. The
       sole exception is promote phase 2, which is not a general allocation and
       does not come through here. */
    if (side != TAPE_SIDE_B)    { return false; }
    return id >= sb->a_high_water;
}

tape_result tape_alloc_run(const struct tape_sb *sb, tape_side side,
                           uint32_t *free_next, uint32_t count,
                           uint32_t *out_first)
{
    uint64_t first, end;

    if (sb == NULL || free_next == NULL || out_first == NULL) { return TAPE_ERR_INVALID_ARG; }
    if (count == 0u)                                          { return TAPE_ERR_INVALID_ARG; }

    first = (uint64_t)*free_next;
    end   = first + (uint64_t)count;

    /* Permission before capacity: Side A is refused on a full cartridge and an
       empty one alike, and the two refusals are different facts. */
    if (side != TAPE_SIDE_B)                     { return TAPE_ERR_READ_ONLY; }
    if (first < (uint64_t)sb->a_high_water)      { return TAPE_ERR_READ_ONLY; }
    /* Widened: free_next + count cannot wrap into a run that looks like it fits. */
    if (end > (uint64_t)sb->total_chunks)        { return TAPE_ERR_CARTRIDGE_FULL; }

    /* The run is [first, end) with first >= a_high_water and end <= total_chunks,
       so every chunk in it is allocatable. Asserting it on the LAST chunk is the
       cheap check that would catch a future bound going the wrong way. */
    if (!tape_may_allocate(sb, side, (uint32_t)(end - 1u))) { return TAPE_ERR_READ_ONLY; }

    *out_first = (uint32_t)first;
    /* §7: allocation is bookkeeping, not I/O. Nothing is written here, and a
       run that is never committed sits above the next mount's derived free_next
       and is silently reused — the aborted-write leak class does not exist. */
    *free_next = (uint32_t)end;
    return TAPE_OK;
}
