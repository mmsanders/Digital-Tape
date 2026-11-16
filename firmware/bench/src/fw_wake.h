/*
 * fw_wake.h — bench warm sleep and wake (FW-1 F3, guardrail 04).
 *
 * Portable C99 over the public engine API only, so the same code runs on the
 * Teensy and in the off-target harness. The engine's own warm start does the
 * work (engine-api §5): before sleeping, the firmware renders a short run of
 * audio ahead of the stop position into a caller-owned buffer; on wake it
 * mounts with that buffer, and the first audio block needs no card read.
 *
 * Nothing here mixes, seeks around or computes audio: every retained frame
 * came out of tape_render (guardrail 12).
 */

#ifndef FW_WAKE_H
#define FW_WAKE_H

#include <stdbool.h>
#include <stdint.h>
#include "tape.h"

/* Frames retained across sleep: about 186 ms at 44.1 kHz, 32 KiB. */
#define FW_WARM_FRAMES 8192u

struct fw_wake {
    tape_warm_start warm;   /* valid only when have_warm */
    uint64_t position;      /* the frame playback resumes from */
    tape_side side;
    uint8_t have_warm;
    uint8_t warm_used;      /* set by fw_wake_wake: the engine accepted the buffer */
};

/* Main loop, player stopped. Renders up to FW_WARM_FRAMES ahead of the current
   position into `pcm` (which must hold that many stereo frames and must outlive
   the sleep), then unmounts. `block` is scratch for one FW_AUDIO_FRAMES render.
   On any failure the instance is left as it was and the caller drops the card. */
tape_result fw_wake_sleep(struct fw_wake *w, tape *t, tape_side side,
                          int16_t *pcm, int16_t *block);

/* Main loop. Mounts at the saved position with the retained buffer. Follow it
   with fw_player_play_now, not fw_player_play: a seek or a prefill would
   discard the warm audio. If the engine declines the buffer (a different
   cartridge, say) this is an ordinary cold mount and the first blocks underrun
   until the loop services. */
tape_result fw_wake_wake(struct fw_wake *w, tape *t);

/* Cycle count to microseconds, rounded UP so a time is never under-reported.
   Returns 0 when cpu_hz is 0. */
uint32_t fw_wake_us(uint32_t cycles, uint32_t cpu_hz);

#endif /* FW_WAKE_H */
