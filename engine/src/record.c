/*
 * record.c — §7 recording. Normative: spec/engine-api.md §7, §7.1, §10, §11;
 * spec/tapefs-v1.md §5.1, §7, §8, §9.1.
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
 * The only independently landed operation tests for recording are VT8-001's two
 * cases, and the record case is a SPLICE at the exact end of the timeline.
 * TAPE_REC_OVERWRITE and TAPE_REC_OVERDUB have no landed coverage and are
 * explicitly excluded by that package, so they are NOT IMPLEMENTED: tape_arm
 * refuses them with TAPE_ERR_INVALID_ARG and writes nothing. That refusal is a
 * statement about THIS ENGINE, not about the format — the spec defines all
 * three modes and two of them are simply not built yet. It is the engine's
 * standing discipline applied to an argument instead of a symbol: an
 * unimplemented thing fails loudly at the call rather than quietly doing
 * something else. It is a divergence from §7 and it is PM's to dispose of.
 *
 * tape_abort is likewise not defined at all, so calling it is a link error.
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
 * tapefs §9.1 splice, plus engine-api §11's two boundary rows: a splice at the
 * exact end is an append, and a splice into an empty side creates the first
 * entry at position 0.
 *
 * The run containing the insertion point is split into two entries and the new
 * material goes between them. The tail's physical start is computed in §5.1's
 * flattened chunk-major space, so a split that crosses a chunk boundary lands
 * on the right chunk and the right offset instead of silently keeping the
 * original first_chunk_id.
 *
 * ONLY the append row is exercised by VT8-001-REC-ALLOCSEQ. The interior-split
 * and boundary-insert rows below are written from §9.1 and carry no independent
 * coverage.
 */
static tape_result splice_insert(struct tape_index *idx, uint64_t at,
                                 uint32_t chunk, uint64_t frames)
{
    uint64_t cursor = 0u;
    uint32_t i, pos, extra, k = 0u;

    for (i = 0; i < idx->entry_count; i++) {
        uint64_t n = (uint64_t)idx->entries[i].frame_count;
        if (at - cursor < n) { k = (uint32_t)(at - cursor); break; }
        cursor += n;
    }
    /* i == entry_count means the cursor sits at the exact end: append. */
    extra = (i < idx->entry_count && k > 0u) ? 2u : 1u;
    if (idx->entry_count + extra > TAPE_MAX_ENTRIES) { return TAPE_ERR_INDEX_FULL; }

    if (i < idx->entry_count && k > 0u) {
        struct tape_entry tail;
        uint64_t flat = (uint64_t)idx->entries[i].first_chunk_id * TAPE_CHUNK_FRAMES
                      + (uint64_t)idx->entries[i].start_frame + (uint64_t)k;

        tail.first_chunk_id = (uint32_t)(flat / TAPE_CHUNK_FRAMES);
        tail.start_frame    = (uint32_t)(flat % TAPE_CHUNK_FRAMES);
        tail.frame_count    = idx->entries[i].frame_count - k;
        idx->entries[i].frame_count = k;

        memmove(&idx->entries[i + 2u], &idx->entries[i + 1u],
                (size_t)(idx->entry_count - i - 1u) * sizeof idx->entries[0]);
        idx->entries[i + 1u] = tail;
        idx->entry_count++;
        pos = i + 1u;
    } else {
        pos = i;
    }

    memmove(&idx->entries[pos + 1u], &idx->entries[pos],
            (size_t)(idx->entry_count - pos) * sizeof idx->entries[0]);
    idx->entries[pos].first_chunk_id = chunk;
    idx->entries[pos].start_frame    = 0u;
    idx->entries[pos].frame_count    = (uint32_t)frames;
    idx->entry_count++;
    idx->total_frames += frames;
    return TAPE_OK;
}

/* --- §7 public operations -------------------------------------------------- */

tape_result tape_arm(tape *t, tape_rec_mode mode)
{
    uint32_t need_gen;
    tape_result rc;

    if (t == NULL)     { return TAPE_ERR_INVALID_ARG; }
    if (!t->mounted)   { return TAPE_ERR_NOT_MOUNTED; }
    if (t->faulted)    { return TAPE_ERR_FAULTED; }
    if (t->rec_armed)  { return TAPE_ERR_BUSY; }

    /*
     * §10: arm is the ONE call gated on the mounted side. W+SideB means an
     * effectively writable mount AND TAPE_SIDE_B; Side A is TAPE_ERR_READ_ONLY,
     * and so is the degraded-B row, where the mounted side is A by construction.
     */
    if (t->side != TAPE_SIDE_B) { return TAPE_ERR_READ_ONLY; }
    if (!t->effective_writable) { return TAPE_ERR_READ_ONLY; }

    /* See the coverage-boundary note at the top of this file. */
    if (mode != TAPE_REC_SPLICE) { return TAPE_ERR_INVALID_ARG; }

    /* tapefs §9.1: each splice costs two entries. */
    if (TAPE_LIVE(t).entry_count + 2u > TAPE_MAX_ENTRIES) { return TAPE_ERR_INDEX_FULL; }

    /* §4.5's tape_arm row: one `sequence` for the commit this arm authorises,
       and one `sb_generation` only if stage clearing applies. All three arm
       refusals above write nothing, which is why the headroom test comes after
       them and the stage-clearing write after that. */
    need_gen = (t->sb.promote_stage == TAPE_PROMOTE_STAGE_PHASE1) ? 1u : 0u;
    if (!tape_headroom_ok(t->cartridge_sequence, 1u))     { return TAPE_ERR_SEQUENCE_EXHAUSTED; }
    if (!tape_headroom_ok(t->sb.sb_generation, need_gen)) { return TAPE_ERR_SEQUENCE_EXHAUSTED; }

    /* tapefs §8: after the preconditions, before the first index or chunk
       write. Not reached on stage-0 media, which is every ordinary cartridge. */
    if (need_gen != 0u) {
        rc = tape_clear_promote_stage(t);
        if (rc != TAPE_OK) { return rc; }
    }

    rec_disarm(t);
    t->rec_armed       = true;
    /* §7: THE RECORDING CURSOR IS FIXED AT ARM TIME, which is why §10 forbids
       tape_seek and tape_set_rate while armed — there is exactly one position
       the edit can apply at (V3-011). */
    t->rec_cursor      = t->position_frame >> 32;
    t->rec_first_chunk = t->free_next;
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
tape_result tape_record_service(struct tape *t, uint32_t budget, uint32_t *used, bool *more)
{
    const unsigned char *src = t->rec_ring;
    uint64_t newbase;

    while (t->rec_written < t->rec_base + (uint64_t)t->rec_buf_frames) {
        uint64_t bstart, avail, phys;
        uint32_t n, lba;

        if (*used >= budget) { break; }

        /* The block containing the next unwritten frame. A partial final block
           is rewritten in place when later frames extend it, which is why
           rec_base never advances past a block boundary. */
        bstart = (t->rec_written / REC_FPB) * REC_FPB;
        avail  = (t->rec_base + (uint64_t)t->rec_buf_frames) - bstart;
        n      = (avail > (uint64_t)REC_FPB) ? (uint32_t)REC_FPB : (uint32_t)avail;

        memcpy(t->block,
               src + (size_t)(bstart - t->rec_base) * TAPE_FRAME_BYTES,
               (size_t)n * TAPE_FRAME_BYTES);
        if (n < REC_FPB) {
            /* tapefs §6: bytes beyond the referenced range are undefined on
               media. Zeroed here so the block is a function of the input alone
               (WP-11 compares bytes), not so the format requires it. */
            memset(t->block + (size_t)n * TAPE_FRAME_BYTES, 0,
                   (size_t)(REC_FPB - n) * TAPE_FRAME_BYTES);
        }

        /* The run starts at frame 0 of rec_first_chunk, and CHUNK_FRAMES is a
           whole number of blocks, so this division is exact at the boundary. */
        phys = (uint64_t)t->rec_first_chunk * TAPE_CHUNK_FRAMES + bstart;
        lba  = t->sb.lba_chunk_base + (uint32_t)(phys / REC_FPB);

        if (dev_write(&t->dev, lba, 1u, t->block) != 0) {
            t->faulted = true;
            return TAPE_ERR_IO;
        }
        (*used)++;
        t->rec_unflushed = true;
        t->rec_written   = bstart + n;
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
    tape_result rc;

    if (t == NULL)     { return TAPE_ERR_INVALID_ARG; }
    if (!t->mounted)   { return TAPE_ERR_NOT_MOUNTED; }
    if (t->faulted)    { return TAPE_ERR_FAULTED; }
    /* §10: commit is TAPE_ERR_BUSY in every row that is not armed. */
    if (!t->rec_armed) { return TAPE_ERR_BUSY; }
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

    rc = splice_insert(idx, t->rec_cursor, t->rec_first_chunk, t->rec_frames);
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
