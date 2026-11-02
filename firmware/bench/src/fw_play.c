/*
 * fw_play.c — the firmware render loop. See fw_play.h.
 */

#include "fw_play.h"

static void silence(int16_t *out, uint32_t from, uint32_t frames)
{
    uint32_t i;
    for (i = from * TAPE_CHANNELS; i < frames * TAPE_CHANNELS; i++) { out[i] = 0; }
}

void fw_player_bind(struct fw_player *p, tape *t)
{
    p->t = t;
    p->playing = 0;
    p->ended = 0;
    p->failed = 0;
    p->underruns = 0;
    p->rendered = 0;
    p->tap = NULL;
}

void fw_player_render(struct fw_player *p, int16_t *out, uint32_t frames)
{
    uint32_t got = 0;
    tape_result r;

    if (p->t == NULL || !p->playing) { silence(out, 0, frames); return; }
    r = tape_render(p->t, out, frames, &got);
    if (r == TAPE_ERR_UNDERRUN) {
        p->underruns++;
    } else if (r != TAPE_OK) {
        /* Not a frame of it is trusted. The main loop reports and stops. */
        p->failed = 1;
        p->playing = 0;
        silence(out, 0, frames);
        return;
    } else if (got < frames) {
        /* engine-api §6.3: a TAPE_OK shortfall at 1.0x is the end of the side. */
        p->ended = 1;
        p->playing = 0;
    }
    if (got > 0u) {
        p->rendered += got;
        if (p->tap != NULL) { fw_sha256_update(p->tap, out, (size_t)got * TAPE_FRAME_BYTES); }
    }
    silence(out, got, frames);
}

tape_result fw_player_service(struct fw_player *p, bool *more)
{
    return tape_service(p->t, FW_SERVICE_BUDGET, more);
}

tape_result fw_player_play(struct fw_player *p)
{
    bool more = true;
    tape_result r = tape_set_rate(p->t, FW_RATE_1X);
    while (r == TAPE_OK && more) { r = fw_player_service(p, &more); }
    if (r != TAPE_OK) { return r; }
    p->ended = 0;
    p->failed = 0;
    p->playing = 1;
    return TAPE_OK;
}

tape_result fw_player_stop(struct fw_player *p)
{
    p->playing = 0;
    return tape_set_rate(p->t, 0);
}

tape_result fw_golden_render(tape *t, uint64_t from, uint64_t frames,
                             int16_t *buf, uint32_t block,
                             fw_pcm_sink sink, void *user, uint64_t *rendered)
{
    tape_result r;
    *rendered = 0;
    r = tape_seek(t, from);
    if (r == TAPE_OK) { r = tape_set_rate(t, FW_RATE_1X); }
    while (r == TAPE_OK && (frames == 0u || *rendered < frames)) {
        uint32_t want = block, got = 0;
        bool more = true;
        if (frames != 0u && frames - *rendered < want) { want = (uint32_t)(frames - *rendered); }
        while (r == TAPE_OK && more) { r = tape_service(t, FW_SERVICE_BUDGET, &more); }
        if (r != TAPE_OK) { break; }
        r = tape_render(t, buf, want, &got);
        if (r != TAPE_OK) { break; }
        if (got > 0u) { sink(user, buf, got); *rendered += got; }
        if (got < want) { break; }
    }
    return r;
}
