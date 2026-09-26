/*
 * record.c — §7 recording. Normative: spec/engine-api.md §7, §7.1, §10, §11;
 * spec/tapefs-v1.md §4.5, §4.6, §5.1, §7, §8, §9.1.
 *
 * Four facts shape everything here.
 *
 *   1. The caller owns the buffer. Fed frames live in rec_ring (§4); the engine
 *      keeps scalars describing it and allocates nothing.
 *   2. The sequence is reserved at ARM, not at commit (§4.5). Discovering at
 *      commit that no sequence remains would refuse after the child had
 *      recorded, and lose the recording. The refusal happens before the record
 *      light comes on.
 *   3. tape_feed reserves before it accepts, from total_chunks and the
 *      in-memory bump pointer, WITHOUT I/O (§7).
 *   4. tape_commit is synchronous and writes metadata only (§7.1). All chunk
 *      data is already durable by the time it is callable, which is what makes
 *      its 97-block bound true.
 *
 * COVERAGE BOUNDARY — READ THIS BEFORE EXTENDING.
 *
 * All three §9.1 modes are implemented here, and §8's stage clearing on
 * tape_arm with them. That is not a widening of the engine's discipline: the
 * independently authored WP-09 package (tests/record_draft8, imported ahead of
 * this work) covers exactly overwrite / overdub / splice, the zero-accepted
 * commit matrix, the armed-BUSY and refusal rows, abort, and stage clearing
 * from a mountable §9.3.3 row-1 state. P1-R21's TAPE_ERR_INVALID_ARG on the two
 * unbuilt modes and TAPE_ERR_BUSY on stage-1 media were coverage boundaries,
 * and the coverage landed; both are gone.
 *
 * What is still NOT here:
 *
 *   - tape_reset_side_b's stage clearing. §8 states the rule on tape_arm AND on
 *     tape_reset_side_b, and only tape_arm's is independently covered. ops.c
 *     keeps its documented TAPE_ERR_BUSY refusal until reset-B's lands.
 *   - a positive SHORT accept (0 < accepted < requested) followed by service and
 *     commit. WP-09's cartridge-full row starts already full and proves only the
 *     zero-accept boundary; its own COVERAGE.md names the short accept as a
 *     later tranche.
 *   - product PCM identity for any mode. The verifier's VO08 envelope carries
 *     superblocks and index slots and no chunk data at all, so nothing in this
 *     tranche observes a recorded or overdubbed sample. The overdub mix below is
 *     written from §9.1 and engine-api §8 and is UNOBSERVED by these tests;
 *     WP-11 listening remains the gate.
 */

#include <string.h>

#include "tape_internal.h"
#include "dev.h"

/* Frames per 512-byte block; physical frames are contiguous within a chunk. */
#define REC_FPB (TAPE_BLOCK_SIZE / TAPE_FRAME_BYTES)   /* 128 */

static void rec_disarm(struct tape *t)
{
    t->rec_armed      = false;
    t->rec_cursor     = 0u;
    t->rec_first_chunk= 0u;
    t->rec_chunks     = 0u;
    t->rec_frames     = 0u;
    t->rec_written    = 0u;
    t->rec_base       = 0u;
    t->rec_buf_frames = 0u;
    t->rec_unflushed  = false;
    t->rec_mix_done   = 0u;
    t->rec_mode       = TAPE_REC_OVERWRITE;
}

void tape_record_reset(struct tape *t)
{
    rec_disarm(t);
}

bool tape_frames_owed(const struct tape *t)
{
    /* §7: accepted frames are OWED until they are on media, and §8.1 says a
       write is not durable until a flush has returned — so the barrier is part
       of the debt, not something commit can assume happened. */
    return (t->rec_written < t->rec_frames) || t->rec_unflushed;
}

/*
 * tapefs §9.1's three edits are ONE edit.
 *
 * Every mode produces: the timeline's head [0, at), then the newly recorded run,
 * then the original timeline from `tail_at` onward. Only `tail_at` differs —
 * splice displaces nothing (tail_at == at), overdub replaces exactly the span it
 * covered (at + frames), overwrite keeps nothing after the cursor (UINT64_MAX).
 * Writing it once is the point: three transcriptions of "split the run at the
 * cursor and fix the physical start of the tail" drift, and §9.1's warning that
 * a trim leaving two entries on the same physical frame is a defect applies
 * identically to all three.
 *
 * The tail's physical start is computed in §5.1's flattened chunk-major space,
 * so a split crossing a chunk boundary lands on the right chunk at the right
 * offset instead of silently keeping the original first_chunk_id.
 *
 * In place, with one memmove, because a second struct tape_index is 48 KiB of a
 * 200 KiB budget (guardrail 08). The memmove runs BEFORE the head trim: when the
 * cursor and the tail start fall in the SAME original entry, the tail copy must
 * be taken from that entry's untrimmed frame_count.
 */
tape_result tape_index_replace(struct tape_index *idx, uint64_t at, uint64_t tail_at,
                               uint32_t chunk, uint64_t frames)
{
    uint32_t orig = idx->entry_count;
    uint32_t i, head_count = orig, head_trim = 0u, tail_i = orig, tail_off = 0u;
    uint32_t new_count;
    uint64_t cursor, total;
    bool head_trimmed = false;

    /* §5.2: every entry carries at least one frame, so a zero-frame edit has no
       entry to add. tape_commit's §7.1 no-op returns before it reaches here. */
    if (frames == 0u || frames > (uint64_t)TAPE_MAX_TOTAL_FRAMES) {
        return TAPE_ERR_INVALID_ARG;
    }

    for (cursor = 0u, i = 0; i < orig; i++) {
        uint64_t n = (uint64_t)idx->entries[i].frame_count;
        if (at - cursor < n) {
            uint32_t k = (uint32_t)(at - cursor);
            if (k == 0u) { head_count = i; }
            else         { head_count = i + 1u; head_trim = k; head_trimmed = true; }
            break;
        }
        cursor += n;
    }
    /* Falling out of the loop means `at` is at or past the end: every entry is
       head and the new run appends. That is engine-api §11's append row. */

    /* UINT64_MAX never satisfies the test below, so overwrite finds no tail
       without needing a branch of its own. */
    for (cursor = 0u, i = 0; i < orig; i++) {
        uint64_t n = (uint64_t)idx->entries[i].frame_count;
        if (tail_at - cursor < n) {
            tail_i   = i;
            tail_off = (uint32_t)(tail_at - cursor);
            break;
        }
        cursor += n;
    }

    new_count = head_count + 1u + (orig - tail_i);
    if (new_count > TAPE_MAX_ENTRIES) { return TAPE_ERR_INDEX_FULL; }

    if (tail_i < orig) {
        memmove(&idx->entries[head_count + 1u], &idx->entries[tail_i],
                (size_t)(orig - tail_i) * sizeof idx->entries[0]);
    }
    if (head_trimmed) { idx->entries[head_count - 1u].frame_count = head_trim; }

    idx->entries[head_count].first_chunk_id = chunk;
    idx->entries[head_count].start_frame    = 0u;
    idx->entries[head_count].frame_count    = (uint32_t)frames;

    if (tail_i < orig && tail_off > 0u) {
        struct tape_entry *e = &idx->entries[head_count + 1u];
        uint64_t flat = (uint64_t)e->first_chunk_id * TAPE_CHUNK_FRAMES
                      + (uint64_t)e->start_frame + (uint64_t)tail_off;
        e->first_chunk_id = (uint32_t)(flat / TAPE_CHUNK_FRAMES);
        e->start_frame    = (uint32_t)(flat % TAPE_CHUNK_FRAMES);
        e->frame_count   -= tail_off;
    }

    idx->entry_count = new_count;
    /* Summed rather than adjusted. total_frames is §5.2-checked against this
       exact sum at every mount, so the commit may as well compute what the next
       mount will verify. */
    for (total = 0u, i = 0; i < new_count; i++) {
        total += (uint64_t)idx->entries[i].frame_count;
    }
    idx->total_frames = total;
    return TAPE_OK;
}

/*
 * engine-api §8's saturating overdub sum, on one block's worth of samples.
 * int32 intermediate and a clamp to [-32768, 32767]: §9.1 says saturating,
 * never wrapping, and a wrap is the loudest possible artefact — full-scale
 * noise where the child expected two voices.
 *
 * memcpy rather than a cast: t->block and t->mix_block are unsigned char arrays
 * inside the instance and nothing guarantees int16_t alignment.
 */
static void overdub_saturate(unsigned char *dst, const unsigned char *src, uint32_t samples)
{
    uint32_t i;

    for (i = 0; i < samples; i++) {
        int16_t a, b;
        int32_t sum;

        memcpy(&a, dst + (size_t)i * 2u, sizeof a);
        memcpy(&b, src + (size_t)i * 2u, sizeof b);
        sum = (int32_t)a + (int32_t)b;
        if (sum >  32767) { sum =  32767; }
        if (sum < -32768) { sum = -32768; }
        a = (int16_t)sum;
        memcpy(dst + (size_t)i * 2u, &a, sizeof a);
    }
}

/* --- §7 public operations -------------------------------------------------- */

tape_result tape_arm(tape *t, tape_rec_mode mode)
{
    uint32_t entries_needed;
    tape_result rc;

    if (t == NULL)     { return TAPE_ERR_INVALID_ARG; }
    if (!t->mounted)   { return TAPE_ERR_NOT_MOUNTED; }
    if (t->faulted)    { return TAPE_ERR_FAULTED; }
    if (t->rec_armed)  { return TAPE_ERR_BUSY; }
    if (tape_dup_row_busy(t)) { return TAPE_ERR_BUSY; }

    /*
     * §10: arm is the ONE call gated on the mounted side. W+SideB means an
     * effectively writable mount AND TAPE_SIDE_B; Side A is TAPE_ERR_READ_ONLY,
     * and so is the degraded-B row, where the mounted side is A by construction.
     */
    if (t->side != TAPE_SIDE_B) { return TAPE_ERR_READ_ONLY; }
    if (!t->effective_writable) { return TAPE_ERR_READ_ONLY; }

    /*
     * engine-api §7: TAPE_ERR_INDEX_FULL "if entries_free is insufficient for
     * the requested mode", and §9.1's shapes say what each mode can cost.
     * Overwrite keeps nothing after the cursor, so at worst it trims the entry
     * the cursor is in and appends one. Overdub and splice keep the tail as
     * well, so the entry the cursor is in can become three.
     *
     * Reserved here rather than discovered at commit, for the same reason §4.5's
     * sequence is: a refusal after the child has recorded loses the recording.
     */
    switch (mode) {
    case TAPE_REC_OVERWRITE: entries_needed = 1u; break;
    case TAPE_REC_OVERDUB:
    case TAPE_REC_SPLICE:    entries_needed = 2u; break;
    default:                 return TAPE_ERR_INVALID_ARG;
    }
    if (TAPE_LIVE(t).entry_count + entries_needed > TAPE_MAX_ENTRIES) {
        return TAPE_ERR_INDEX_FULL;
    }

    /*
     * §4.5's tape_arm row: one `sequence` for the commit this arm authorises,
     * plus one `sb_generation` WHEN STAGE CLEARING APPLIES. Both are tested
     * before either is spent, and both are tested after every zero-write
     * refusal above — §8 is explicit that clearing happens after a call's own
     * preconditions pass, so that READ_ONLY and INDEX_FULL still write nothing
     * (invariant 25a).
     */
    if (!tape_headroom_ok(t->cartridge_sequence, 1u)) { return TAPE_ERR_SEQUENCE_EXHAUSTED; }

    if (t->sb.promote_stage == TAPE_PROMOTE_STAGE_PHASE1) {
        if (!tape_headroom_ok(t->sb.sb_generation, 1u)) { return TAPE_ERR_SEQUENCE_EXHAUSTED; }
        /*
         * §8: an interrupted promote must not poison ordinary use, and no index
         * commit may land on stage-1 media. This is the engine's only superblock
         * write outside §4.1 phase-4 repair, and it happens at most once after
         * an interrupted promote. §4.6 owns the order; tape_sb_clear_stage owns
         * the bytes. A failure there has already quarantined the instance.
         */
        rc = tape_sb_clear_stage(t);
        if (rc != TAPE_OK) { return rc; }
    }

    rec_disarm(t);
    t->rec_armed       = true;
    t->rec_mode        = mode;
    /* §7: THE RECORDING CURSOR IS FIXED AT ARM TIME, which is why §10 forbids
       tape_seek and tape_set_rate while armed — there is exactly one position
       the edit can apply at (V3-011). */
    t->rec_cursor      = t->position_frame >> 32;
    t->rec_first_chunk = t->free_next;
    return TAPE_OK;
}

/*
 * §7.1 / §10: abort discards owed frames and pending chunks. It writes nothing
 * and reads nothing, which is why §7.2 permits it in FAULTED — without it
 * frames_owed could never clear there.
 *
 * The chunks tape_feed reserved are simply abandoned. free_next is DERIVED from
 * the committed index (§7), so the next mount reuses them: the aborted-write
 * leak class does not exist. Re-deriving it here makes that true within this
 * mount too, so an arm/abort/arm cycle does not walk the bump pointer up the
 * cartridge.
 */
tape_result tape_abort(tape *t)
{
    if (t == NULL)     { return TAPE_ERR_INVALID_ARG; }
    if (!t->mounted)   { return TAPE_ERR_NOT_MOUNTED; }
    /* §10: not armed is TAPE_ERR_BUSY, like every other row that is not the
       armed one. Deliberately NOT gated on faulted (§7.2). */
    if (!t->rec_armed) { return TAPE_ERR_BUSY; }
    if (tape_dup_row_busy(t)) { return TAPE_ERR_BUSY; }

    rec_disarm(t);
    t->free_next = tape_derive_free_next(&t->idx[TAPE_SIDE_B], &t->sb, TAPE_SIDE_B);
    return TAPE_OK;
}

tape_result tape_feed(tape *t, const int16_t *in, uint32_t frames, uint32_t *accepted)
{
    uint64_t run_capacity, timeline_room, room, take, need;
    uint32_t ring_frames, ring_free, first;
    size_t   cap;
    unsigned char *dst;
    tape_result rc;

    if (t == NULL || accepted == NULL)  { return TAPE_ERR_INVALID_ARG; }
    if (in == NULL && frames != 0u)     { return TAPE_ERR_INVALID_ARG; }
    if (!t->mounted)                    { return TAPE_ERR_NOT_MOUNTED; }
    if (t->faulted)                     { return TAPE_ERR_FAULTED; }
    if (!t->rec_armed)                  { return TAPE_ERR_BUSY; }
    if (tape_dup_row_busy(t))           { return TAPE_ERR_BUSY; }

    *accepted = 0u;
    if (frames == 0u) { return TAPE_OK; }

    /*
     * §7's reservation, and it performs NO I/O. The run is contiguous from
     * rec_first_chunk (§5.1 entries describe runs over CONSECUTIVE chunk ids,
     * so a fragmented allocation could not be expressed as one entry), so the
     * frames it can ever hold are bounded by the chunks above that point.
     */
    run_capacity = (t->sb.total_chunks > t->rec_first_chunk)
                 ? (uint64_t)(t->sb.total_chunks - t->rec_first_chunk) * TAPE_CHUNK_FRAMES
                 : 0u;
    /* §5.4's cap is a capacity limit too: the committed timeline may not exceed
       what the position representation can address. */
    timeline_room = (uint64_t)TAPE_MAX_TOTAL_FRAMES - TAPE_LIVE(t).total_frames;
    if (run_capacity > timeline_room) { run_capacity = timeline_room; }
    room = (run_capacity > t->rec_frames) ? run_capacity - t->rec_frames : 0u;

    /* Narrowed the way play_capacity() narrows the play ring, and for the same
       reason: rec_ring_len is a size_t the caller chose, and a ring of 2^32
       frames or more would truncate to a SMALLER number than rec_buf_frames.
       ring_free would then underflow and tape_feed would accept frames past the
       end of the caller's buffer. */
    cap         = t->rec_ring_len / TAPE_FRAME_BYTES;
    ring_frames = (cap > 0xFFFFFFFFu) ? 0xFFFFFFFFu : (uint32_t)cap;
    ring_free   = ring_frames - t->rec_buf_frames;

    take = frames;
    if (take > room)               { take = room; }
    if (take > (uint64_t)ring_free) { take = (uint64_t)ring_free; }

    if (take > 0u) {
        need = tape_chunks_for_frames(t->rec_frames + take);
        if (need > (uint64_t)t->rec_chunks) {
            rc = tape_alloc_run(&t->sb, TAPE_SIDE_B, &t->free_next,
                                (uint32_t)(need - (uint64_t)t->rec_chunks), &first);
            if (rc != TAPE_OK) { return rc; }
            /* The first allocation establishes the run's base. Nothing else
               allocates while armed, so every later one extends it. */
            if (t->rec_chunks == 0u) { t->rec_first_chunk = first; }
            t->rec_chunks = (uint32_t)need;
        }

        dst = t->rec_ring;
        dst += (size_t)t->rec_buf_frames * TAPE_FRAME_BYTES;
        memcpy(dst, in, (size_t)take * TAPE_FRAME_BYTES);
        t->rec_buf_frames += (uint32_t)take;
        t->rec_frames     += take;
    }

    *accepted = (uint32_t)take;

    /*
     * §7 / tapefs §9.1: a short accept is TAPE_ERR_CARTRIDGE_FULL only when the
     * CARTRIDGE is what ran out — reported in the call that hit the wall, so
     * tape_service never has to discover fullness on its own. A short accept
     * because the ring is full is TAPE_OK: the caller services and feeds again,
     * and the child has not lost anything. THE CHILD KEEPS EVERYTHING RECORDED
     * UP TO THE MOMENT IT FILLED.
     */
    if (room < (uint64_t)frames && take == room) { return TAPE_ERR_CARTRIDGE_FULL; }
    return TAPE_OK;
}

/*
 * §8 steps 1–2 for a recording: get the accepted frames onto media, then put
 * one flush behind them all. Called only from tape_service, which owns the
 * block budget and passes the count it has already spent.
 */
/*
 * §9.1 overdub's read side, for the block currently staged in t->block.
 *
 * The staged block holds the child's new frames; the timeline underneath holds
 * what is already there. Each pass resolves ONE physical block of existing
 * audio, adds it, and charges one block to the budget — so a call that runs out
 * mid-block returns with *more_work true and resumes here on the next one.
 * rec_mix_done is how far into the staged block the sum has reached.
 *
 * Past the end of the timeline there is nothing to add: the remaining frames
 * stand as fed, with no read at all. That is the overdub-past-the-end row, and
 * it is why the loop can finish without ever calling the device.
 */
static tape_result overdub_block(struct tape *t, uint64_t bstart, uint32_t n,
                                 uint32_t budget, uint32_t *used)
{
    const struct tape_index *idx = &t->idx[TAPE_SIDE_B];

    while (t->rec_mix_done < n) {
        uint64_t tl = t->rec_cursor + bstart + (uint64_t)t->rec_mix_done;
        uint64_t phys;
        uint32_t lba, off, take, run;

        if (!tape_timeline_physical(idx, tl, &phys)) {
            t->rec_mix_done = n;        /* nothing there; the fed frames stand */
            break;
        }
        if (*used >= budget) { return TAPE_OK; }   /* resume next tape_service */

        lba = t->sb.lba_chunk_base + (uint32_t)(phys / REC_FPB);
        if (dev_read(&t->dev, lba, 1u, t->mix_block) != 0) {
            /* A read failure is not §7.2 quarantine: nothing was written and no
               durability is in doubt. The owed frames stay owed. */
            return TAPE_ERR_IO;
        }
        (*used)++;

        off  = (uint32_t)(phys % REC_FPB);
        take = REC_FPB - off;                      /* rest of the physical block */
        run  = tape_timeline_run(idx, tl);         /* rest of this entry */
        if (run < take)                { take = run; }
        if (n - t->rec_mix_done < take) { take = n - t->rec_mix_done; }

        overdub_saturate(t->block + (size_t)t->rec_mix_done * TAPE_FRAME_BYTES,
                         t->mix_block + (size_t)off * TAPE_FRAME_BYTES,
                         take * TAPE_CHANNELS);
        t->rec_mix_done += take;
    }
    return TAPE_OK;
}

/*
 * §8 steps 1–2 for a recording: get the accepted frames onto media, then put
 * one flush behind them all. Called only from tape_service, which owns the
 * block budget and passes the count it has already spent.
 */
tape_result tape_record_service(struct tape *t, uint32_t budget, uint32_t *used, bool *more)
{
    const unsigned char *src = t->rec_ring;
    uint64_t newbase;

    while (t->rec_written < t->rec_base + (uint64_t)t->rec_buf_frames) {
        uint64_t bstart, avail;
        uint32_t n;

        if (*used >= budget) { break; }

        /* The block containing the next unwritten frame. A partial final block
           is rewritten in place when later frames extend it, which is why
           rec_base never advances past a block boundary. */
        bstart = (t->rec_written / REC_FPB) * REC_FPB;
        avail  = (t->rec_base + (uint64_t)t->rec_buf_frames) - bstart;
        n      = (avail > (uint64_t)REC_FPB) ? (uint32_t)REC_FPB : (uint32_t)avail;

        /* Stage only the part not already summed. A budget exhausted part-way
           through an overdub leaves mixed frames in t->block, and restaging the
           whole block would overwrite them with the raw input. Everything below
           rec_mix_done is already correct; everything above it is raw, and for
           the two non-overdub modes rec_mix_done is always 0 and this is the
           whole block. */
        memcpy(t->block + (size_t)t->rec_mix_done * TAPE_FRAME_BYTES,
               src + (size_t)(bstart + t->rec_mix_done - t->rec_base) * TAPE_FRAME_BYTES,
               (size_t)(n - t->rec_mix_done) * TAPE_FRAME_BYTES);
        if (n < REC_FPB) {
            /* tapefs §6: bytes beyond the referenced range are undefined on
               media. Zeroed here so the block is a function of the input alone
               (WP-11 compares bytes), not so the format requires it. */
            memset(t->block + (size_t)n * TAPE_FRAME_BYTES, 0,
                   (size_t)(REC_FPB - n) * TAPE_FRAME_BYTES);
        }

        if (t->rec_mode == TAPE_REC_OVERDUB) {
            tape_result rc = overdub_block(t, bstart, n, budget, used);
            if (rc != TAPE_OK)          { return rc; }
            if (t->rec_mix_done < n)    { break; }   /* budget spent mid-block */
            if (*used >= budget)        { break; }
        }

        /* The run starts at frame 0 of rec_first_chunk, and CHUNK_FRAMES is a
           whole number of blocks, so this division is exact at the boundary. */
        {
            uint64_t phys = (uint64_t)t->rec_first_chunk * TAPE_CHUNK_FRAMES + bstart;
            uint32_t lba  = t->sb.lba_chunk_base + (uint32_t)(phys / REC_FPB);

            if (dev_write(&t->dev, lba, 1u, t->block) != 0) {
                t->faulted = true;
                return TAPE_ERR_IO;
            }
        }
        (*used)++;
        t->rec_unflushed = true;
        t->rec_written   = bstart + n;
        /* The next pass stages a different block — or this same partial block
           again once tape_feed extends it, and then every frame of it is raw
           input that has not been summed yet. */
        t->rec_mix_done  = 0u;
    }

    /* Frames whose block is complete are never written again, so drop them and
       keep only the partial tail. */
    newbase = (t->rec_written / REC_FPB) * REC_FPB;
    if (newbase > t->rec_base) {
        uint32_t drop = (uint32_t)(newbase - t->rec_base);
        unsigned char *ring = t->rec_ring;
        memmove(ring, ring + (size_t)drop * TAPE_FRAME_BYTES,
                (size_t)(t->rec_buf_frames - drop) * TAPE_FRAME_BYTES);
        t->rec_buf_frames -= drop;
        t->rec_base        = newbase;
    }

    /* §8 step 2 — ONE barrier, once every accepted frame is on media. A flush
       per block would be correct and ruinous, and §7.1's bound assumes this
       flush has already happened before tape_commit is callable. */
    if (t->rec_unflushed && t->rec_written >= t->rec_frames) {
        if (dev_flush(&t->dev) != 0) { t->faulted = true; return TAPE_ERR_IO; }
        t->rec_unflushed = false;
    }

    *more = tape_frames_owed(t);
    return TAPE_OK;
}

tape_result tape_commit(tape *t)
{
    struct tape_index *idx;
    uint32_t dest_slot, dest_lba, seq;
    uint64_t tail_at;
    tape_result rc;

    if (t == NULL)     { return TAPE_ERR_INVALID_ARG; }
    if (!t->mounted)   { return TAPE_ERR_NOT_MOUNTED; }
    if (t->faulted)    { return TAPE_ERR_FAULTED; }
    /* §10: commit is TAPE_ERR_BUSY in every row that is not armed. */
    if (!t->rec_armed) { return TAPE_ERR_BUSY; }
    if (tape_dup_row_busy(t)) { return TAPE_ERR_BUSY; }
    /* §7.1: it refuses while frames are owed. The caller services until
       frames_owed clears, then commits. */
    if (tape_frames_owed(t)) { return TAPE_ERR_BUSY; }

    /*
     * §7.1: a commit with zero accepted frames is a ZERO-WRITE no-op in all
     * three modes, and it still disarms — otherwise the only way out of the
     * armed state after an empty commit would be tape_abort. Pressing record
     * and instantly releasing must not truncate the tape (V5-008).
     */
    if (t->rec_frames == 0u) { rec_disarm(t); return TAPE_OK; }

    /* Armed implies the mounted side is B (§10), and §10 forbids tape_set_side
       while armed, so the live index cannot have changed under us. */
    idx = &t->idx[TAPE_SIDE_B];
    seq = t->cartridge_sequence + 1u;   /* §5.5; the headroom was reserved at arm */

    /*
     * §9.1's one difference between the three modes: where the surviving tail
     * starts. Overwrite "replaces the timeline from the current position", so it
     * has none; overdub replaces exactly what it covered; splice displaces
     * nothing. The mode was fixed at arm along with the cursor.
     */
    switch (t->rec_mode) {
    case TAPE_REC_SPLICE:  tail_at = t->rec_cursor;                  break;
    case TAPE_REC_OVERDUB: tail_at = t->rec_cursor + t->rec_frames;  break;
    default:               tail_at = 0xFFFFFFFFFFFFFFFFu;            break;
    }

    rc = tape_index_replace(idx, t->rec_cursor, tail_at, t->rec_first_chunk, t->rec_frames);
    if (rc != TAPE_OK) { return rc; }   /* nothing written; idx is unchanged */
    idx->sequence = seq;
    idx->side     = (uint8_t)TAPE_SIDE_B;

    /* §8: the INACTIVE slot for this side. Writing the live one would destroy
       the fallback the protocol depends on. */
    dest_slot = (t->live_slot[TAPE_SIDE_B] == 0u) ? 1u : 0u;
    dest_lba  = (dest_slot == 0u) ? t->sb.lba_index_b0 : t->sb.lba_index_b1;

    rc = tape_commit_index(t, dest_lba, idx);
    if (rc != TAPE_OK) { return rc; }   /* quarantined; only unmount gets out */

    t->live_slot[TAPE_SIDE_B] = dest_slot;
    t->cartridge_sequence     = seq;
    /* §7: derived from the COMMITTED index, never stored. */
    t->free_next = tape_derive_free_next(idx, &t->sb, TAPE_SIDE_B);
    rec_disarm(t);

    /* The timeline moved under the play ring, so what it holds no longer maps
       to the window it claims. tape_render owes the caller a tape_service. */
    t->play_ring_valid = false;
    t->play_frames     = 0u;
    if ((t->position_frame >> 32) > idx->total_frames) {
        t->position_frame = idx->total_frames << 32;
    }
    return TAPE_OK;
}
