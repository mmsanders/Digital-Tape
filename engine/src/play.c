/*
 * play.c — transport and playback. spec/engine-api.md §6.1–§6.3 and §8.
 *
 * Four public operations, and nothing else: tape_seek, tape_set_rate,
 * tape_service, tape_render. The normative algorithms are transcribed from the
 * frozen contract for the WHOLE valid input domain, not narrowed to the ±1.0×
 * examples the first independent package happens to exercise.
 *
 * The division of labour is contract 2 and §6.3:
 *
 *   tape_render  pulls from the caller's play ring ONLY. Zero block-device
 *                calls, never blocks. Interrupt-safe.
 *   tape_service does all card I/O, at most block_budget blocks per call, and
 *                reports *more_work while its window is not yet filled.
 *
 * "A desktop harness services to completion then renders; firmware interleaves
 * them. Both produce identical bytes." That holds here because the ring is a
 * window over TIMELINE frames and rendering reads only that window: what has
 * been loaded never changes what a loaded frame decodes to.
 */

#include <string.h>

#include "tape_internal.h"
#include "dev.h"
#include "read1_observe.h"

/* Frames per 512-byte block. Physical frames are contiguous within a chunk. */
#define FRAMES_PER_BLOCK (TAPE_BLOCK_SIZE / TAPE_FRAME_BYTES)   /* 128 */

/* --- helpers ------------------------------------------------------------- */

/* §6.1: max_pos = total_frames << 32. tapefs §5.4 caps total_frames at 2^32-1,
   validated at mount, so this cannot overflow. */
static uint64_t play_max_pos(const tape *t)
{
    return (t->faulted ? t->play_total_frames : TAPE_LIVE(t).total_frames) << 32;
}

/* §6.1: step = rate_q16_16 * 65536, widening 16.16 to 32.32. |step| <= 2^47,
   which is what makes -step always defined in the reverse branch. */
static int64_t play_step(const tape *t)
{
    return (int64_t)t->rate_q16_16 * 65536;
}

/*
 * Map timeline frame n onto a physical frame index within the chunk store.
 * The timeline is the concatenation of the live index's entries in order; each
 * entry is physically contiguous, and entries may jump anywhere in the store.
 */
bool tape_timeline_physical(const struct tape_index *idx, uint64_t n, uint64_t *out)
{
    uint64_t cursor = 0;
    uint32_t e;

    for (e = 0; e < idx->entry_count; e++) {
        const struct tape_entry *x = &idx->entries[e];
        if (n - cursor < (uint64_t)x->frame_count) {
            *out = (uint64_t)x->first_chunk_id * (uint64_t)TAPE_CHUNK_FRAMES
                 + (uint64_t)x->start_frame + (n - cursor);
            return true;
        }
        cursor += (uint64_t)x->frame_count;
    }
    return false;
}

/* How many timeline frames from n onward stay inside n's own entry, and so stay
   physically contiguous. Zero if n is past the timeline. */
uint32_t tape_timeline_run(const struct tape_index *idx, uint64_t n)
{
    uint64_t cursor = 0;
    uint32_t e;

    for (e = 0; e < idx->entry_count; e++) {
        const struct tape_entry *x = &idx->entries[e];
        if (n - cursor < (uint64_t)x->frame_count) {
            return (uint32_t)((uint64_t)x->frame_count - (n - cursor));
        }
        cursor += (uint64_t)x->frame_count;
    }
    return 0u;
}

/* Frames the caller's play ring can hold. */
static uint32_t play_capacity(const tape *t)
{
    size_t cap = t->play_ring_len / TAPE_FRAME_BYTES;
    return (cap > 0xFFFFFFFFu) ? 0xFFFFFFFFu : (uint32_t)cap;
}

/* The window tape_service is trying to hold, given the playhead and direction.
   Forward wants the playhead first; reverse wants the playhead (and its
   interpolation partner) at the window's END, because rendering walks down. */
static void play_target(const tape *t, uint32_t *first, uint32_t *end)
{
    uint64_t total = TAPE_LIVE(t).total_frames;
    uint32_t cap   = play_capacity(t);
    uint64_t i     = t->position_frame >> 32;

    if (total == 0u || cap == 0u) { *first = 0u; *end = 0u; return; }
    if (i > total - 1u) { i = total - 1u; }      /* includes position == max_pos */

    if (play_step(t) < 0) {
        uint64_t e = i + 2u;                     /* playhead plus partner frame */
        if (e > total) { e = total; }
        *end   = (uint32_t)e;
        *first = (e > (uint64_t)cap) ? (uint32_t)(e - cap) : 0u;
    } else {
        uint64_t e = i + (uint64_t)cap;
        if (e > total) { e = total; }
        *first = (uint32_t)i;
        *end   = (uint32_t)e;
    }
}

/* A loaded timeline frame, or NULL when the ring does not hold it. */
static const int16_t *play_frame(const tape *t, uint32_t n)
{
    const unsigned char *base;

    if (!t->play_ring_valid || t->play_frames == 0u) { return NULL; }
    if (n < t->play_base) { return NULL; }
    if (n - t->play_base >= t->play_frames) { return NULL; }

    base = t->play_ring;
    return (const int16_t *)(const void *)(base + (size_t)(((uint64_t)t->play_slot + n - t->play_base) % play_capacity(t)) * TAPE_FRAME_BYTES);
}

/*
 * §8 variable-rate interpolation, verbatim.
 *
 * Both operands are cast BEFORE subtracting (V5-006): int16_t promotes to int,
 * and a conforming C99 target may have a 16-bit int, on which b - a overflows
 * before any widening. The negative branch avoids >> on a negative signed value
 * (V4-013), which is implementation-defined in C99 and would let two conforming
 * builds emit different PCM for the same cartridge.
 */
static int16_t play_interpolate(int16_t a, int16_t b, uint32_t f)
{
    int64_t d = ((int64_t)b - (int64_t)a) * (int64_t)f;   /* |d| < 2^48 */
    int64_t q;

    if (d >= 0) {
        q = (int64_t)((uint64_t)d >> 32);                 /* floor, by definition */
    } else {
        uint64_t m = (uint64_t)(-d);                      /* defined: |d| < 2^48 */
        q = -(int64_t)((m + 0xFFFFFFFFu) >> 32);          /* -ceil(m/2^32) == floor(d/2^32) */
    }
    /* No clamp: with f/2^32 in [0,1), a + q lies in [min(a,b), max(a,b)], which
       is inside int16 by construction. A clamp here would hide a bug. */
    return (int16_t)((int32_t)a + (int32_t)q);
}

/*
 * §6.2 the advance, verbatim. Each direction clears the other's flag, and
 * at_start is set only when the playhead was ALREADY at 0 — never on the step
 * that lands there, or §6.3's pre-emit test would drop frame 0 on every rewind.
 */
static void play_advance(tape *t)
{
    int64_t  step = play_step(t);
    uint64_t mx   = play_max_pos(t);

    if (step > 0) {
        uint64_t s = (uint64_t)step;
        t->at_start = false;
        /* Compared without subtracting the step from the endpoint (V4-009): the
           other form wraps for a large valid rate on a short timeline. */
        if (t->position_frame >= mx || s >= mx - t->position_frame) {
            t->position_frame = mx;
            t->at_end = true;
        } else {
            t->position_frame += s;
        }
    } else if (step < 0) {
        uint64_t s = (uint64_t)(-step);
        t->at_end = false;
        if (t->position_frame == 0u)      { t->at_start = true; }
        else if (t->position_frame <= s)  { t->position_frame = 0u; }
        else                              { t->position_frame -= s; }
    }
}

/* --- public operations --------------------------------------------------- */

/*
 * §6: beyond end clamps and still returns TAPE_OK. Clamping to total_frames
 * rather than the last frame matches tape_mount's resume clamp and §6.1's
 * max_pos, so "seek past the end then play forward" reports at_end instead of
 * silently rewinding.
 */
tape_result tape_seek(tape *t, uint64_t frame)
{
    uint64_t total;

    if (t == NULL)   { return TAPE_ERR_INVALID_ARG; }
    if (!t->mounted) { return TAPE_ERR_NOT_MOUNTED; }
    if (t->faulted)  { return TAPE_ERR_FAULTED; }
    if (tape_long_op_row_busy(t)) { return TAPE_ERR_BUSY; }
    /* §10: forbidden while armed. The recording cursor is fixed at arm time
       (§7) — you cannot seek a tape deck while it is recording, because the
       head is where the head is. */
    if (t->rec_armed || t->respool_in_progress) { return TAPE_ERR_BUSY; }

    total = TAPE_LIVE(t).total_frames;
    if (frame > total) { frame = total; }

    t->position_frame = frame << 32;
    t->at_end   = false;      /* §6: seek clears both, or reversing away from a */
    t->at_start = false;      /* boundary would be impossible */
    return TAPE_OK;
}

/* §6: signed 16.16; 0x00010000 is 1.0x, negative reverses, zero is stopped.
   Instantaneous rates only — the scrub ramp is the caller's schedule. */
tape_result tape_set_rate(tape *t, int32_t rate_q16_16)
{
    if (t == NULL)   { return TAPE_ERR_INVALID_ARG; }
    if (!t->mounted) { return TAPE_ERR_NOT_MOUNTED; }
    if (t->faulted)  { return TAPE_ERR_FAULTED; }
    if (t->rec_armed) { return TAPE_ERR_BUSY; }   /* §10, with tape_seek */
    if (tape_long_op_row_busy(t)) { return TAPE_ERR_BUSY; }

    t->rate_q16_16 = rate_q16_16;
    t->at_end   = false;
    t->at_start = false;
    return TAPE_OK;
}

/*
 * §6 status. Permitted in every mounted row of the §10 matrix, INCLUDING Faulted:
 * it touches neither media nor operation state, and quarantine still has to be
 * observable. Not-mounted is TAPE_ERR_NOT_MOUNTED like every ordinary call.
 *
 * recording_armed and frames_owed are read from the instance now that §7 has a
 * path that arms. They were hard false while nothing could arm, which was true
 * then and would be a lie now.
 */
tape_result tape_status(const tape *t, tape_status_t *out)
{
    if (t == NULL || out == NULL) { return TAPE_ERR_INVALID_ARG; }
    if (!t->mounted)              { return TAPE_ERR_NOT_MOUNTED; }

    out->at_end          = t->at_end;
    out->at_start        = t->at_start;
    out->recording_armed = t->rec_armed;
    out->frames_owed     = tape_frames_owed(t);
    /* Same derivations tape_get_info uses, so the two can never disagree. */
    out->entries_free    = TAPE_MAX_ENTRIES - TAPE_LIVE(t).entry_count;
    out->free_chunks     = (t->sb.total_chunks > t->free_next)
                         ? t->sb.total_chunks - t->free_next : 0u;
    return TAPE_OK;
}

/* Cursor walks in timeline order, independent of physical entry ordering. */
static bool play_map(tape *t, uint32_t n, uint64_t *phys, uint32_t *run)
{
    const struct tape_index *idx = &TAPE_LIVE(t);
    if (!t->play_map_valid) { t->play_map_entry = 0u; t->play_map_base = 0u; t->play_map_valid = true; }
    while (t->play_map_entry < idx->entry_count) {
        const struct tape_entry *x = &idx->entries[t->play_map_entry];
#ifdef TAPE_READ1_OBSERVE
        TAPE_READ1_LOOP(); TAPE_READ1_VISIT();
#endif
        if (n < t->play_map_base) {
            if (t->play_map_entry == 0u) { return false; }
            --t->play_map_entry;
#ifdef TAPE_READ1_OBSERVE
            TAPE_READ1_VISIT();
#endif
            t->play_map_base -= idx->entries[t->play_map_entry].frame_count;
        } else if ((uint64_t)n - t->play_map_base >= x->frame_count) {
            t->play_map_base += x->frame_count;
            ++t->play_map_entry;
        } else {
            uint32_t off = (uint32_t)((uint64_t)n - t->play_map_base);
            *phys = (uint64_t)x->first_chunk_id * TAPE_CHUNK_FRAMES + x->start_frame + off;
            *run = x->frame_count - off;
            return true;
        }
    }
    return false;
}

static void play_copy(tape *t, uint32_t n, const unsigned char *src, uint32_t frames)
{
    uint32_t cap = play_capacity(t);
    uint32_t dest = (uint32_t)(((uint64_t)t->play_slot + cap + n - t->play_base) % cap);
    uint32_t part = cap - dest;
    unsigned char *ring = t->play_ring;
    if (part > frames) { part = frames; }
#ifdef TAPE_READ1_OBSERVE
    TAPE_READ1_COPY(ring + (size_t)dest * TAPE_FRAME_BYTES, src, (size_t)part * TAPE_FRAME_BYTES, refill);
    TAPE_READ1_COPY(ring, src + (size_t)part * TAPE_FRAME_BYTES, (size_t)(frames-part) * TAPE_FRAME_BYTES, refill);
#else
    memcpy(ring + (size_t)dest * TAPE_FRAME_BYTES, src, (size_t)part * TAPE_FRAME_BYTES);
    memcpy(ring, src + (size_t)part * TAPE_FRAME_BYTES, (size_t)(frames-part) * TAPE_FRAME_BYTES);
#endif
}

/*
 * §6.3: tape_service does ALL card I/O, at most block_budget blocks per call,
 * and sets *more_work while its window is not yet filled.
 *
 * block_budget == 0 is TAPE_ERR_INVALID_ARG with no state change (§9's rule,
 * for the same reason: "at most zero blocks" permits no progress forever).
 */
tape_result tape_service(tape *t, uint32_t block_budget, bool *more_work)
{
    const struct tape_index *idx;
    uint32_t first, end, used = 0u;
    bool rec_more = false;

    if (t == NULL || more_work == NULL) { return TAPE_ERR_INVALID_ARG; }
    if (!t->mounted)                    { return TAPE_ERR_NOT_MOUNTED; }
    if (t->faulted)                     { return TAPE_ERR_FAULTED; }
    /* §10 permits service in the Dup-in-progress row; §9.1 re-entry does not. */
    if (t->in_callback)                 { return TAPE_ERR_BUSY; }
    if (block_budget == 0u)             { return TAPE_ERR_INVALID_ARG; }

    /*
     * §7 first: tape_service is the call that clears owed frames, which is why
     * §10 permits it in both armed rows. It runs ahead of the play window
     * because a frame the child has already recorded is owed and a frame the
     * child has not reached yet is not, and because §8 step 2's barrier has to
     * be behind every chunk write before tape_commit becomes callable.
     */
    if (t->rec_armed) {
        tape_result rc = tape_record_service(t, block_budget, &used, &rec_more);
        if (rc != TAPE_OK) { return rc; }
    }

    idx = &TAPE_LIVE(t);
    t->play_total_frames = idx->total_frames;
#ifdef TAPE_READ1_OBSERVE
    if (TAPE_READ1_CONTROL("retained-movement") && t->play_ring_valid &&
        t->play_frames >= 64u && (t->position_frame >> 32) > t->play_base) {
        unsigned char tape_read1_saved[256];
        TAPE_READ1_COPY(tape_read1_saved, play_frame(t, t->play_base), sizeof tape_read1_saved, move);
        TAPE_READ1_COPY((unsigned char *)t->play_ring + (size_t)t->play_slot * TAPE_FRAME_BYTES,
                        tape_read1_saved, sizeof tape_read1_saved, move);
    }
#endif
    play_target(t, &first, &end);
    if (!t->play_ring_valid) {
        t->play_frames = 0u;
        t->play_slot = 0u;
        t->play_base = first;
        t->play_goal_first = first;
        t->play_goal_end = end;
        t->play_fill_next = first;
        t->play_map_valid = false;
        t->play_cache_valid = false;
        t->play_ring_valid = true;
    }
    /* A completed covered window remains untouched until half its capacity is
       consumed. A refill retains overlapping samples in their original slots. */
    if (t->play_frames != 0u && t->play_base == t->play_goal_first &&
        t->play_base + t->play_frames == t->play_goal_end) {
        uint32_t i = (uint32_t)(t->position_frame >> 32);
        uint32_t limit = t->play_base + t->play_frames;
        bool covered = i >= t->play_base && i < limit;
        if ((uint64_t)i >= idx->total_frames && play_step(t) < 0 && limit == idx->total_frames) {
            i = limit - 1u;
            covered = true;
        }
        if (covered && ((play_step(t) < 0)
            ? (t->play_base == 0u || i - t->play_base >= play_capacity(t)/2u)
            : (limit == idx->total_frames || limit - i > play_capacity(t)/2u))) {
#ifdef TAPE_READ1_OBSERVE
            if (TAPE_READ1_CONTROL("idle-nine-loops")) {
                uint32_t tape_read1_j;
                for (tape_read1_j=0u; tape_read1_j<9u; ++tape_read1_j) { TAPE_READ1_LOOP(); }
            }
            if (TAPE_READ1_CONTROL("idle-mapping") && idx->entry_count) {
                volatile uint32_t tape_read1_sink = idx->entries[0].frame_count;
                (void)tape_read1_sink; TAPE_READ1_VISIT();
            }
            if (!TAPE_READ1_CONTROL("whole-window-reread")) {
#endif
                *more_work = rec_more;
                return TAPE_OK;
#ifdef TAPE_READ1_OBSERVE
            }
            t->play_frames = 0u;
#endif
        }
        t->play_goal_first = first;
        t->play_goal_end = end;
        t->play_fill_next = first;
    }
    /* Discontinuous seek, or a fresh half-window refill. */
    if (first != t->play_goal_first || end != t->play_goal_end) {
        t->play_goal_first = first;
        t->play_goal_end = end;
        t->play_fill_next = first;
    }
    if (t->play_frames != 0u) {
        uint32_t old_end = t->play_base + t->play_frames;
        uint32_t keep_first = first > t->play_base ? first : t->play_base;
        uint32_t keep_end = end < old_end ? end : old_end;
        if (keep_end > keep_first) {
            t->play_slot = (uint32_t)(((uint64_t)t->play_slot + keep_first - t->play_base) % play_capacity(t));
            t->play_base = keep_first;
            t->play_frames = keep_end - keep_first;
        } else { t->play_frames = 0u; t->play_base = first; t->play_slot = 0u; }
    } else { t->play_base = first; }
    while (t->play_base > first || t->play_base + t->play_frames < end) {
        uint64_t phys;
        uint32_t n, stop, run, off, count, take, lba, source;
        bool prepend = t->play_base > first;
#ifdef TAPE_READ1_OBSERVE
        TAPE_READ1_LOOP();
#endif
        if (used >= block_budget) { break; }
        n = prepend ? t->play_fill_next : t->play_base + t->play_frames;
        stop = prepend ? t->play_base : end;
        if (!play_map(t, n, &phys, &run)) { break; }
        lba = t->sb.lba_chunk_base + (uint32_t)(phys / FRAMES_PER_BLOCK);
        off = (uint32_t)(phys % FRAMES_PER_BLOCK);
        take = stop - n;
        if (take > run) { take = run; }
        if (t->play_cache_valid && t->play_cache_lba == lba) {
            source = t->play_cache_offset + off * TAPE_FRAME_BYTES;
            if (take > FRAMES_PER_BLOCK - off) { take = FRAMES_PER_BLOCK - off; }
        } else {
            count = (uint32_t)(((uint64_t)take + off + FRAMES_PER_BLOCK - 1u) / FRAMES_PER_BLOCK);
            if (count > 64u) { count = 64u; }
            if (count > block_budget - used) { count = block_budget - used; }
#ifdef TAPE_READ1_OBSERVE
            if (TAPE_READ1_CONTROL("tiny-transfer")) { count = 1u; }
            if (TAPE_READ1_CONTROL("budget-overrun")) { count = block_budget - used + 1u; }
            if (TAPE_READ1_CONTROL("full-index-rescan")) {
                uint32_t tape_read1_b, tape_read1_e;
                for (tape_read1_b=0u; tape_read1_b<count; ++tape_read1_b) {
                    TAPE_READ1_LOOP();
                    for (tape_read1_e=0u; tape_read1_e<idx->entry_count; ++tape_read1_e) {
                        volatile uint32_t tape_read1_sink = idx->entries[tape_read1_e].frame_count;
                        (void)tape_read1_sink; TAPE_READ1_VISIT(); TAPE_READ1_LOOP();
                    }
                }
            }
#endif
            t->play_cache_valid = false;
            if (dev_read(&t->dev, lba, count, t->play_read) != 0) { return TAPE_ERR_IO; }
            used += count;
            source = off * TAPE_FRAME_BYTES;
            if (take > count * FRAMES_PER_BLOCK - off) { take = count * FRAMES_PER_BLOCK - off; }
            t->play_cache_lba = lba + count - 1u;
            t->play_cache_offset = (count - 1u) * TAPE_BLOCK_SIZE;
            t->play_cache_valid = true;
        }
        if (prepend) {
            /* Publish the left gap only once complete; ascending batches use
               their final circular slots without moving retained PCM. */
            play_copy(t, n, t->play_read + source, take);
            t->play_fill_next += take;
            if (t->play_fill_next == t->play_base) {
                uint32_t added = t->play_base - t->play_goal_first;
                t->play_slot = (uint32_t)(((uint64_t)t->play_slot + play_capacity(t) - added) % play_capacity(t));
                t->play_base = t->play_goal_first;
                t->play_frames += added;
                first = t->play_goal_first;
            }
        } else {
            play_copy(t, n, t->play_read + source, take);
            t->play_frames += take;
        }
    }
    *more_work = rec_more || t->play_base > t->play_goal_first ||
                 t->play_base + t->play_frames < t->play_goal_end;
    return TAPE_OK;
}

/*
 * §6.3 the render loop, verbatim: FETCH, EMIT, THEN ADVANCE. tape_seek(N)
 * followed by tape_render emits frame N as its first output (V4-010).
 *
 * Zero block-device calls here, by construction: every sample comes from the
 * window tape_service loaded.
 */
tape_result tape_render(tape *t, int16_t *out, uint32_t frames, uint32_t *rendered)
{
    uint64_t total, mx;
    int64_t  step;
    uint32_t n;
    bool     ring_short = false;

    if (t == NULL || out == NULL || rendered == NULL) { return TAPE_ERR_INVALID_ARG; }
    if (!t->mounted) { return TAPE_ERR_NOT_MOUNTED; }
    /* §7.2 / §10: render stays allowed in FAULTED. It touches only the ring,
       and with tape_service refused there it drains and then underruns, which
       is the audible signal that the tape stopped. */

    /*
     * §7.2/§10 permits render in FAULTED so already-buffered audio can drain.
     * It performs no device I/O; once the retained ring is exhausted the normal
     * ring-short path reports UNDERRUN.
     */
    *rendered = 0u;
    total = t->faulted ? t->play_total_frames : TAPE_LIVE(t).total_frames;
    mx    = play_max_pos(t);
    step  = play_step(t);

    if (total == 0u) { t->at_end = true; return TAPE_OK; }  /* empty: checked first */
    if (t->rate_q16_16 == 0) { return TAPE_OK; }            /* stopped: no flag change */

    /* The snap (V5-005). With a negative rate at max_pos there is no frame under
       the playhead. Snap to the LAST FRAME ON THE GRID — not max_pos - 1, which
       is one fixed-point unit short and makes every sample after the first wrong. */
    if (step < 0 && t->position_frame >= mx) {
        t->position_frame = (total - 1u) << 32;
    }

    for (n = 0u; n < frames; n++) {
#ifdef TAPE_READ1_OBSERVE
        TAPE_READ1_LOOP();
#endif
        uint32_t i, f;
        const int16_t *a, *b;

        if (step > 0 && t->position_frame >= mx) { t->at_end = true; break; }
        if (step < 0 && t->at_start)             { break; }

        i = (uint32_t)(t->position_frame >> 32);
        f = (uint32_t)t->position_frame;

        a = play_frame(t, i);
        if (a == NULL) { ring_short = true; break; }
        if ((uint64_t)i + 1u < total) {
            b = play_frame(t, i + 1u);
#ifdef TAPE_READ1_OBSERVE
            if (TAPE_READ1_CONTROL("missing-lookahead")) { b = a; }
#endif
            if (b == NULL) { ring_short = true; break; }
        } else {
            b = a;                                  /* past the last frame: b = a */
        }

        out[(size_t)n * 2u]      = play_interpolate(a[0], b[0], f);
        out[(size_t)n * 2u + 1u] = play_interpolate(a[1], b[1], f);
        (*rendered)++;

        play_advance(t);
    }

    /* TAPE_ERR_UNDERRUN only when the shortfall was the ring's fault. A
       shortfall from at_end, at_start or rate == 0 is TAPE_OK: the caller pads
       with silence either way, but only one of them is a problem. */
    if (ring_short) { return TAPE_ERR_UNDERRUN; }
    return TAPE_OK;
}
