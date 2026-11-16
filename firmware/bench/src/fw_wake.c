/*
 * fw_wake.c — bench warm sleep and wake. See fw_wake.h.
 */

#include <string.h>

#include "fw_wake.h"
#include "fw_play.h"

struct warm_fill {
    int16_t *pcm;
    uint32_t frames;
};

static void warm_sink(void *user, const int16_t *pcm, uint32_t frames)
{
    struct warm_fill *f = (struct warm_fill *)user;
    if (frames > FW_WARM_FRAMES - f->frames) { frames = FW_WARM_FRAMES - f->frames; }
    memcpy(f->pcm + (size_t)f->frames * TAPE_CHANNELS, pcm, (size_t)frames * TAPE_FRAME_BYTES);
    f->frames += frames;
}

tape_result fw_wake_sleep(struct fw_wake *w, tape *t, tape_side side,
                          int16_t *pcm, int16_t *block)
{
    struct warm_fill fill;
    tape_info info;
    uint64_t pos = 0, done = 0, unused = 0;
    tape_result r;

    memset(w, 0, sizeof *w);
    fill.pcm = pcm;
    fill.frames = 0u;

    r = tape_tell(t, &pos);
    if (r == TAPE_OK) { r = tape_get_info(t, &info); }
    if (r == TAPE_OK) {
        r = fw_golden_render(t, pos, FW_WARM_FRAMES, block, FW_AUDIO_FRAMES, warm_sink, &fill, &done);
    }
    if (r == TAPE_OK) { r = tape_set_rate(t, 0); }
    if (r == TAPE_OK) { r = tape_unmount(t, &unused); }
    if (r != TAPE_OK) { return r; }

    w->position = pos;
    w->side = side;
    /* start_frame is 32-bit in the API; beyond it, wake is simply cold. */
    if (fill.frames > 0u && pos <= 0xFFFFFFFFu) {
        w->warm.data = pcm;
        w->warm.data_bytes = FW_WARM_FRAMES * TAPE_FRAME_BYTES;
        w->warm.valid_frames = fill.frames;
        w->warm.start_frame = (uint32_t)pos;
        memcpy(w->warm.uuid, info.uuid, sizeof w->warm.uuid);
        w->warm.side = side;
        w->have_warm = 1;
    }
    return TAPE_OK;
}

tape_result fw_wake_wake(struct fw_wake *w, tape *t)
{
    tape_info info;
    tape_result r = tape_mount(t, w->side, w->position, w->have_warm ? &w->warm : NULL);
    if (r == TAPE_OK) { r = tape_get_info(t, &info); }
    if (r == TAPE_OK) { w->warm_used = info.warm_start_used ? 1 : 0; }
    return r;
}

uint32_t fw_wake_us(uint32_t cycles, uint32_t cpu_hz)
{
    if (cpu_hz == 0u) { return 0u; }
    return (uint32_t)(((uint64_t)cycles * 1000000u + cpu_hz - 1u) / cpu_hz);
}
