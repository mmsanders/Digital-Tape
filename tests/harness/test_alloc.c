/*
 * WP-07 — the allocator, and Rule 3.
 *
 * spec/tapefs-v1.md §7: "Ownership is not reference. A side may reference chunks
 * it does not own. It may only allocate and write within what it owns."
 *
 * That distinction is the whole copy-on-write mechanism, and DRAFT-3 got it
 * backwards: its invariant 4 forbade Side B from *referencing* below
 * a_high_water, which is exactly what reset-B produces, so no implementation
 * could satisfy both it and the format (V3-009).
 *
 * acceptance.md WP-07 is explicit about the consequence for testing: "the oracle
 * identifies ownership by allocation, not by chunk id." A test that flags a low
 * chunk id as a violation is testing the wrong thing.
 *
 * Software Lead scaffolding, not acceptance.
 */

#include "harness.h"
#include "tape_internal.h"

static struct tape_sb SB;

static void setup(uint32_t total_chunks, uint32_t a_high_water)
{
    memset(&SB, 0, sizeof SB);
    SB.total_chunks  = total_chunks;
    SB.a_high_water  = a_high_water;
}

int main(void);

int main(void)
{
    /* --- Rule 3: reference and allocation are different questions --- */
    setup(100u, 10u);

    /* Side B may REFERENCE anything in range, including Side A's chunks. */
    CHECK(tape_may_reference(&SB, TAPE_SIDE_B, 0u));
    CHECK(tape_may_reference(&SB, TAPE_SIDE_B, 9u));
    CHECK(tape_may_reference(&SB, TAPE_SIDE_B, 10u));
    CHECK(tape_may_reference(&SB, TAPE_SIDE_B, 99u));
    CHECK(!tape_may_reference(&SB, TAPE_SIDE_B, 100u));   /* out of range */

    /* Side B may ALLOCATE only at or above the mark. Same chunk ids, opposite
       answers — this asymmetry is Rule 3 and the reason for two predicates. */
    CHECK(!tape_may_allocate(&SB, TAPE_SIDE_B, 0u));
    CHECK(!tape_may_allocate(&SB, TAPE_SIDE_B, 9u));
    CHECK(tape_may_allocate(&SB, TAPE_SIDE_B, 10u));
    CHECK(tape_may_allocate(&SB, TAPE_SIDE_B, 99u));
    CHECK(!tape_may_allocate(&SB, TAPE_SIDE_B, 100u));

    /* Side A owns [0, a_high_water) and never allocates at runtime. Promote
       phase 2 is the sole writer below the mark and does not come through here. */
    CHECK(tape_may_reference(&SB, TAPE_SIDE_A, 9u));
    CHECK(!tape_may_reference(&SB, TAPE_SIDE_A, 10u));
    CHECK(!tape_may_allocate(&SB, TAPE_SIDE_A, 9u));
    CHECK(!tape_may_allocate(&SB, TAPE_SIDE_A, 0u));

    /* --- bump allocation of contiguous runs --- */
    {
        uint32_t free_next = 10u, first = 0u;

        CHECK_EQ_INT(tape_alloc_run(&SB, TAPE_SIDE_B, &free_next, 3u, &first), TAPE_OK);
        CHECK_EQ_U32(first, 10u);
        CHECK_EQ_U32(free_next, 13u);

        /* Contiguous and non-overlapping across calls: §5.1 entries describe
           runs over consecutive ids, so a fragmented allocation could not be
           expressed as one entry. */
        CHECK_EQ_INT(tape_alloc_run(&SB, TAPE_SIDE_B, &free_next, 2u, &first), TAPE_OK);
        CHECK_EQ_U32(first, 13u);
        CHECK_EQ_U32(free_next, 15u);

        /* Exactly filling the store is allowed; one more is not. */
        CHECK_EQ_INT(tape_alloc_run(&SB, TAPE_SIDE_B, &free_next, 85u, &first), TAPE_OK);
        CHECK_EQ_U32(first, 15u);
        CHECK_EQ_U32(free_next, 100u);
        CHECK_EQ_INT(tape_alloc_run(&SB, TAPE_SIDE_B, &free_next, 1u, &first),
                     TAPE_ERR_CARTRIDGE_FULL);
        CHECK_EQ_U32(free_next, 100u);        /* a refusal changes nothing */
    }

    /* --- the boundary Rule 3 exists to hold --- */
    {
        /* A stale or hostile free_next below the mark must not be able to
           allocate into the music, even though the arithmetic would work. */
        uint32_t free_next = 5u, first = 0u;
        CHECK_EQ_INT(tape_alloc_run(&SB, TAPE_SIDE_B, &free_next, 2u, &first),
                     TAPE_ERR_READ_ONLY);
        CHECK_EQ_U32(free_next, 5u);

        /* Side A cannot allocate at all. */
        free_next = 10u;
        CHECK_EQ_INT(tape_alloc_run(&SB, TAPE_SIDE_A, &free_next, 1u, &first),
                     TAPE_ERR_READ_ONLY);
        CHECK_EQ_U32(free_next, 10u);
    }

    /* --- a count large enough to wrap must not wrap into a pass --- */
    {
        uint32_t free_next = 10u, first = 0u;
        CHECK_EQ_INT(tape_alloc_run(&SB, TAPE_SIDE_B, &free_next, 0xFFFFFFFFu, &first),
                     TAPE_ERR_CARTRIDGE_FULL);
        CHECK_EQ_U32(free_next, 10u);
        CHECK_EQ_INT(tape_alloc_run(&SB, TAPE_SIDE_B, &free_next, 0u, &first),
                     TAPE_ERR_INVALID_ARG);
    }

    /* --- chunks needed for a frame count, ceiling, 64-bit --- */
    CHECK_EQ_U32(tape_chunks_for_frames(0u), 0u);
    CHECK_EQ_U32(tape_chunks_for_frames(1u), 1u);
    CHECK_EQ_U32(tape_chunks_for_frames(TAPE_CHUNK_FRAMES), 1u);
    CHECK_EQ_U32(tape_chunks_for_frames(TAPE_CHUNK_FRAMES + 1u), 2u);
    /* The C-60 number from spec §2 — 1212, not DRAFT-3's truncated 1211. */
    CHECK_EQ_U32(tape_chunks_for_frames(3600ull * TAPE_SAMPLE_RATE), 1212u);
    CHECK_EQ_U32(tape_chunks_for_frames(5400ull * TAPE_SAMPLE_RATE), 1817u);
    CHECK_EQ_U32(tape_chunks_for_frames(7200ull * TAPE_SAMPLE_RATE), 2423u);
    /* The whole addressable timeline still fits a u32 chunk count. */
    CHECK_EQ_U32(tape_chunks_for_frames(TAPE_MAX_TOTAL_FRAMES), 32768u);

    /* --- an empty Side A means Side B owns everything --- */
    setup(50u, 0u);
    {
        uint32_t free_next = 0u, first = 0u;
        CHECK(tape_may_allocate(&SB, TAPE_SIDE_B, 0u));
        CHECK_EQ_INT(tape_alloc_run(&SB, TAPE_SIDE_B, &free_next, 50u, &first), TAPE_OK);
        CHECK_EQ_U32(first, 0u);
    }

    /* --- a full Side A means Side B owns nothing --- */
    setup(50u, 50u);
    {
        uint32_t free_next = 50u, first = 0u;
        CHECK(!tape_may_allocate(&SB, TAPE_SIDE_B, 49u));
        CHECK(tape_may_reference(&SB, TAPE_SIDE_B, 49u));   /* still referable */
        CHECK_EQ_INT(tape_alloc_run(&SB, TAPE_SIDE_B, &free_next, 1u, &first),
                     TAPE_ERR_CARTRIDGE_FULL);
    }

    return TAPE_TEST_REPORT("allocator (WP-07)");
}
