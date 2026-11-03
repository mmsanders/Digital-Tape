/*
 * fw_play.h — the firmware render loop, over the public engine API only.
 *
 * Normative: docs/WP17-FIRMWARE-CONTRACT.md §5, spec/engine-api.md §6.3 and
 * §11. Portable C99, no board knowledge, so the same code runs on the Teensy
 * and in the off-target harness (host/fw_golden_host.c) that CI compares with
 * the WP-11 goldens. Nothing here seeks, mixes, interpolates or rates: every
 * frame comes out of tape_render (guardrail 12).
 *
 * Two contexts, never concurrent on one instance:
 *   - the audio interrupt calls fw_player_render only;
 *   - the main loop calls everything else, with the audio interrupt masked
 *     around each call (the Teensy glue does the masking; see main.cpp).
 * The engine never sees a preempted call, so nothing here relies on it being
 * reentrant.
 */

#ifndef FW_PLAY_H
#define FW_PLAY_H

#include <stdbool.h>
#include <stdint.h>
#include "tape.h"
#include "fw_sha256.h"

/* Blocks per tape_service call from the main loop. One audio block (128 frames)
   consumes one card block, so a budget of 16 refills far faster than playback
   drains while keeping each masked call short. */
#define FW_SERVICE_BUDGET 16u

/* Frames per audio interrupt: the Teensy Audio library's block. */
#define FW_AUDIO_FRAMES 128u

#define FW_RATE_1X 65536

struct fw_player {
    tape *t;
    volatile uint8_t playing;    /* main loop writes, interrupt reads and clears */
    volatile uint8_t ended;      /* interrupt sets: a forward shortfall with TAPE_OK */
    volatile uint8_t failed;     /* interrupt sets: tape_render returned an error */
    volatile uint32_t underruns; /* renders short because the play ring was */
    volatile uint64_t rendered;  /* frames tape_render produced */
    struct fw_sha256 *tap;       /* if set, every rendered frame is hashed (F1 live) */
};

void fw_player_bind(struct fw_player *p, tape *t);

/* Interrupt context. Fills `out` (interleaved stereo, `frames` frames): the
   engine's frames while playing, then silence. Never touches the card. */
void fw_player_render(struct fw_player *p, int16_t *out, uint32_t frames);

/* Main loop. Seek, then service until the play ring is full, then rate 1.0x and
   start rendering from the current position. */
tape_result fw_player_play(struct fw_player *p);

/* Main loop. Stop rendering; the position is kept (rate 0 renders nothing). */
tape_result fw_player_stop(struct fw_player *p);

/* Main loop. One tape_service call of FW_SERVICE_BUDGET blocks. */
tape_result fw_player_service(struct fw_player *p, bool *more);

/* F1, deterministic form (the desktop harness's order, engine-api §6.3): seek
   to `from`, rate 1.0x, then repeatedly service until no work remains and
   render up to `block` frames into `buf`, handing each rendered run to `sink`.
   Stops after `frames` frames, or at the first short render (the end of the
   side) when `frames` is 0. `*rendered` gets the total. */
typedef void (*fw_pcm_sink)(void *user, const int16_t *pcm, uint32_t frames);
tape_result fw_golden_render(tape *t, uint64_t from, uint64_t frames,
                             int16_t *buf, uint32_t block,
                             fw_pcm_sink sink, void *user, uint64_t *rendered);

#endif /* FW_PLAY_H */
