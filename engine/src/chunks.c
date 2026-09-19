/*
 * chunks.c — timeline-to-chunk arithmetic. spec/tapefs-v1.md §7.
 *
 * One pure function, split out of the accepted candidate's alloc.c so that the
 * chunk allocator itself stays out of this integration candidate.
 *
 * §9.3.3's promote-resume row 3 is a MOUNT-time shape check: it compares
 * a_high_water against the chunk length a timeline of n frames occupies. That
 * check is part of the independently landed mount package's coverage
 * (M-stage-row3 and M-stage-row3-H-boundary), so mount.c cannot link without
 * this, and mount.c is unmodified accepted bytes.
 *
 * What stayed behind in alloc.c is the allocator proper —
 * tape_may_reference, tape_may_allocate and tape_alloc_run — which nothing in
 * this candidate references and which VT8-001 leaves uncovered. tape_internal.h
 * still declares them; declarations bind no definition, and keeping the header
 * at its accepted bytes keeps that boundary visible rather than papered over.
 *
 * The body below is the accepted candidate's, byte for byte.
 */

#include "tape_internal.h"

uint32_t tape_chunks_for_frames(uint64_t frames)
{
    if (frames == 0u) {
        return 0u;
    }
    return (uint32_t)((frames + TAPE_CHUNK_FRAMES - 1u) / TAPE_CHUNK_FRAMES);
}
