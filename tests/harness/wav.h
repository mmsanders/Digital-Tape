/*
 * wav.h — minimal WAV I/O for the golden suite.
 *
 * Deliberately narrow: 44.1 kHz, 16-bit, stereo, PCM. Anything else is an
 * error, not a conversion. Guardrail 01 says the format is raw PCM at exactly
 * that rate and every other design decision rests on it — a reader that
 * silently accepted a 48 kHz fixture would hide a guardrail violation inside a
 * passing test.
 *
 * Scaffolding, not tests. Software Lead.
 */

#ifndef TAPE_TEST_WAV_H
#define TAPE_TEST_WAV_H

#include <stddef.h>
#include <stdint.h>

#define WAV_RATE      44100u
#define WAV_CHANNELS  2u
#define WAV_BITS      16u
#define WAV_FRAME     4u    /* bytes: 2 channels x 16 bits */

struct wav {
    int16_t *frames;      /* interleaved L,R */
    size_t   frame_count;
};

/* 0 on success. On failure returns non-zero and writes a reason to `err`. */
int  wav_read(const char *path, struct wav *w, char *err, size_t errlen);
int  wav_write(const char *path, const struct wav *w, char *err, size_t errlen);
void wav_free(struct wav *w);

#endif /* TAPE_TEST_WAV_H */
