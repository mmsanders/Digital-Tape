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

/* Frames per 512-byte block. Physical frames are contiguous within a chunk. */
#define FRAMES_PER_BLOCK (TAPE_BLOCK_SIZE / TAPE_FRAME_BYTES)   /* 128 */

/* --- helpers ------------------------------------------------------------- */

/* §6.1: max_pos = total_frames << 32. tapefs §5.4 caps total_frames at 2^32-1,
   validated at mount, so this cannot overflow. */
static uint64_t play_max_pos(const tape *t)
{
    return TAPE_LIVE(t).total_frames << 32;
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
static bool timeline_physical(const struct tape_index *idx, uint64_t n, uint64_t *out)
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
static uint32_t timeline_run(const struct tape_index *idx, uint64_t n)
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
    return (const int16_t *)(const void *)(base + (size_t)(n - t->play_base) * TAPE_FRAME_BYTES);
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
 * recording_armed and frames_owed are always false here because §7 recording is
 * not implemented in this candidate. That is the correct answer for every state
 * this engine can actually reach, not a stub: there is no path that arms.
 */
tape_result tape_status(const tape *t, tape_status_t *out)
{
    if (t == NULL || out == NULL) { return TAPE_ERR_INVALID_ARG; }
    if (!t->mounted)              { return TAPE_ERR_NOT_MOUNTED; }

    out->at_end          = t->at_end;
    out->at_start        = t->at_start;
    out->recording_armed = false;
    out->frames_owed     = false;
    /* Same derivations tape_get_info uses, so the two can never disagree. */
    out->entries_free    = TAPE_MAX_ENTRIES - TAPE_LIVE(t).entry_count;
    out->free_chunks     = (t->sb.total_chunks > t->free_next)
                         ? t->sb.total_chunks - t->free_next : 0u;
    return TAPE_OK;
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

    if (t == NULL || more_work == NULL) { return TAPE_ERR_INVALID_ARG; }
    if (!t->mounted)                    { return TAPE_ERR_NOT_MOUNTED; }
    if (t->faulted)                     { return TAPE_ERR_FAULTED; }
    if (block_budget == 0u)             { return TAPE_ERR_INVALID_ARG; }

    idx = &TAPE_LIVE(t);
    play_target(t, &first, &end);

    if (end <= first) {                 /* empty timeline, or no ring capacity */
        t->play_frames = 0u;
        t->play_base = first;
        t->play_ring_valid = true;
        *more_work = false;
        return TAPE_OK;
    }

    /* The window moved: restart it. Keeping a partial window that no longer
       contains the playhead would let tape_render emit from the wrong region. */
    if (!t->play_ring_valid || t->play_base != first) {
        t->play_base = first;
        t->play_frames = 0u;
        t->play_ring_valid = true;
    }

    while ((uint32_t)(t->play_base + t->play_frames) < end) {
        uint64_t n = (uint64_t)t->play_base + (uint64_t)t->play_frames;
        uint64_t phys;
        uint32_t lba, off, take, run, room;
        unsigned char *dst;

        if (used >= block_budget) { break; }

        if (!timeline_physical(idx, n, &phys)) { break; }   /* past the timeline */

        lba = t->sb.lba_chunk_base + (uint32_t)(phys / FRAMES_PER_BLOCK);
        if (dev_read(&t->dev, lba, 1u, t->block) != 0) {
            /* A read failure is not §7.2 quarantine: that is for writes and
               flushes with indeterminate durability. Report and leave the
               window short so the caller can retry. */
            return TAPE_ERR_IO;
        }
        used++;

        off  = (uint32_t)(phys % FRAMES_PER_BLOCK);
        take = FRAMES_PER_BLOCK - off;                      /* rest of this block */
        run  = timeline_run(idx, n);                        /* rest of this entry */
        if (run < take) { take = run; }
        room = end - (uint32_t)n;                           /* rest of the window */
        if (room < take) { take = room; }
        if (take == 0u) { break; }

        dst = t->play_ring;
        dst += (size_t)t->play_frames * TAPE_FRAME_BYTES;
        memcpy(dst, t->block + (size_t)off * TAPE_FRAME_BYTES,
                    (size_t)take * TAPE_FRAME_BYTES);
        t->play_frames += take;
    }

    *more_work = ((uint32_t)(t->play_base + t->play_frames) < end);
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
    if (t->faulted)  { return TAPE_ERR_FAULTED; }

    *rendered = 0u;
    total = TAPE_LIVE(t).total_frames;
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
