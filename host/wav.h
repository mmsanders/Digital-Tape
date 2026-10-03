/*
 * wav.h — tapectl's WAV I/O (docs/WP11-CLI-CONTRACT.md, "WAV I/O").
 *
 * RIFF PCM, 44.1 kHz, 16-bit, stereo only. Anything else is rejected, never
 * converted: guardrail 01 fixes the format, and a reader that quietly accepted
 * 48 kHz or mono would hide a guardrail violation behind a working command.
 * Unknown chunks are skipped on read. Output is a canonical 44-byte header
 * followed by the data.
 *
 * Streaming, so a whole C-60 never has to sit in memory.
 */

#ifndef TAPECTL_WAV_H
#define TAPECTL_WAV_H

#include <stdint.h>
#include <stdio.h>

#define WAV_RATE      44100u
#define WAV_CHANNELS  2u
#define WAV_BITS      16u
#define WAV_FRAME     4u          /* bytes per frame: 2 channels x 16 bits */

struct wav_in {
    FILE    *fp;
    uint32_t frames;              /* total frames in the data chunk */
    uint32_t remaining;           /* frames not yet read */
};

/* Validates the header and positions at the data. 0 on success; otherwise
   non-zero with a reason in `err`. On failure nothing stays open. */
int wav_open_read(struct wav_in *w, const char *path, char *err, size_t errlen);

/* Reads up to `max` frames (interleaved L,R) into `buf`. Returns the number of
   frames read; 0 at the end. A short or failed read of data the header
   promised sets *bad. */
uint32_t wav_read_frames(struct wav_in *w, int16_t *buf, uint32_t max, int *bad);

void wav_close_read(struct wav_in *w);

struct wav_out {
    FILE    *fp;
    uint32_t frames;
};

/* Writes a placeholder canonical header; wav_close_write fixes the sizes. */
int  wav_open_write(struct wav_out *w, const char *path, char *err, size_t errlen);
int  wav_write_frames(struct wav_out *w, const int16_t *buf, uint32_t frames);
int  wav_close_write(struct wav_out *w);

#endif /* TAPECTL_WAV_H */
