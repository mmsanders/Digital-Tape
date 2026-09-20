/*
 * ops.c — §9 cartridge operations. This candidate implements exactly one:
 * tape_reset_side_b. Normative: spec/tapefs-v1.md §8, §9.2; engine-api §10.
 *
 * tape_promote, tape_respool, tape_dup and tape_format stay DECLARED AND NOT
 * DEFINED — calling one is a link error, which is the intended loud failure
 * rather than a stub that appears to work.
 */

#include "tape_internal.h"

/*
 * §9.2 — copy the live Side A index into Side B and commit per §8.
 *
 * It MOVES NO AUDIO. The resulting Side B references Side A's chunks, which
 * Rule 3 permits and which is the whole copy-on-write mechanism: "start over"
 * is instant and Side B stays nearly free until it is edited. DRAFT-3's
 * invariant 4 forbade exactly this and no implementation could satisfy both
 * (V3-009).
 *
 * The destination and the sequence are both §9.2's, and the second is what
 * makes the recovery work in BOTH degraded-B causes. In cause (b) — B0 and B1
 * both valid at equal `sequence` — a "highest LIVE sequence + 1" rule writes a
 * number the stale partner still beats, so the call would return success and
 * change nothing on the very next mount. cartridge_sequence is the maximum over
 * every STRUCTURALLY valid slot, so it writes above both (V6-001).
 */
tape_result tape_reset_side_b(tape *t)
{
    uint32_t dest_slot, dest_lba, seq;
    tape_result rc;

    if (t == NULL)   { return TAPE_ERR_INVALID_ARG; }
    if (!t->mounted) { return TAPE_ERR_NOT_MOUNTED; }
    if (t->faulted)  { return TAPE_ERR_FAULTED; }

    /* §10: reset_b is TAPE_ERR_BUSY in Playing and in every armed and
       long-operation row; it is permitted from Mounted-idle, including the
       degraded-B row, where it is the ONLY recovery there is. */
    if (t->rec_armed)        { return TAPE_ERR_BUSY; }
    if (t->rate_q16_16 != 0) { return TAPE_ERR_BUSY; }

    /* §4.3, via §10's W. About the MOUNT, not the mounted side: reset_b writes
       a region chosen by the operation, so it is permitted from a Side-A
       mount — which is where degraded-B recovery always starts. */
    if (!t->effective_writable) { return TAPE_ERR_READ_ONLY; }

    /* NARROWING, NOT A SPEC CLAIM. §8 requires this call to CLEAR a stale
       promote_stage before its first index write; clearing it is a §4.6
       superblock update, which is promote-recovery behaviour neither accepted
       VT8-001 observation covers. This split refuses instead of committing an
       index onto stage-1 media, which §8 forbids. Zero writes. The accepted
       reset observation is promote_stage == 0, so this branch is not exercised.
       See the header note in engine/src/record.c. */
    if (t->sb.promote_stage == TAPE_PROMOTE_STAGE_PHASE1) { return TAPE_ERR_BUSY; }

    /* §4.5's tape_reset_side_b row: one `sequence`. No sb_generation is
       consumed, because nothing in this split writes a superblock. */
    if (!tape_headroom_ok(t->cartridge_sequence, 1u)) { return TAPE_ERR_SEQUENCE_EXHAUSTED; }

    if (t->side_b_valid) {
        dest_slot = (t->live_slot[TAPE_SIDE_B] == 0u) ? 1u : 0u;
    } else {
        /* §9.2: in degraded-B there is no live B index, so "inactive" is
           undefined. The destination is B0, written directly. */
        dest_slot = 0u;
    }
    dest_lba = (dest_slot == 0u) ? t->sb.lba_index_b0 : t->sb.lba_index_b1;

    seq = t->cartridge_sequence + 1u;

    /* Side A's entries, verbatim, marked as Side B's. Side A's index satisfied
       §5.2's Side-A bound at mount, and every entry it holds is therefore below
       a_high_water — which Side B MAY reference and may not allocate. */
    t->idx[TAPE_SIDE_B]          = t->idx[TAPE_SIDE_A];
    t->idx[TAPE_SIDE_B].side     = (uint8_t)TAPE_SIDE_B;
    t->idx[TAPE_SIDE_B].sequence = seq;

    rc = tape_commit_index(t, dest_lba, &t->idx[TAPE_SIDE_B]);
    if (rc != TAPE_OK) { return rc; }   /* quarantined; only unmount gets out */

    t->live_slot[TAPE_SIDE_B] = dest_slot;
    /* §10's set_side refusal is keyed to state NOW, not to mount time, so a
       successful reset makes Side B reachable without an eject and reinsert. */
    t->side_b_valid           = true;
    t->cartridge_sequence     = seq;
    t->free_next = tape_derive_free_next(&t->idx[TAPE_SIDE_B], &t->sb, TAPE_SIDE_B);

    /* If Side B is the mounted side, its timeline just changed underneath the
       playhead and the ring. Same reasoning as §5's side switch: a stale ring
       plays audio the caller did not ask for (invariant 31). */
    if (t->side == TAPE_SIDE_B) {
        t->play_ring_valid = false;
        t->play_frames     = 0u;
        t->at_end          = false;
        t->at_start        = false;
        if ((t->position_frame >> 32) > t->idx[TAPE_SIDE_B].total_frames) {
            t->position_frame = t->idx[TAPE_SIDE_B].total_frames << 32;
        }
    }
    return TAPE_OK;
}
