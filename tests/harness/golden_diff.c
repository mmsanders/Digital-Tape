/*
 * golden_diff — compare a produced WAV against a golden reference.
 *
 *     golden_diff <reference.wav> <actual.wav> [diff.wav]
 *
 * Exit 0 if bit-identical, 1 if not, 2 if something could not be read.
 *
 * Contract 3 says the golden fixtures ARE the definition of correct behaviour
 * and that firmware must be bit-identical at 1.0x playback. So the comparison
 * is exact: no tolerance, no epsilon. A "close enough" golden suite cannot
 * enforce a cross-target contract, because the divergence it permits is exactly
 * the divergence you are trying to detect.
 *
 * On failure it writes a difference WAV — reference minus actual, per sample.
 * Identical passages are silence, so you hear only what went wrong and where.
 * That is the charter's "audible diff": a number tells you a test failed, and
 * this tells you whether it is a click at a splice, a whole channel inverted,
 * or an offset by one frame.
 *
 * Scaffolding, not tests. Software Lead.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "wav.h"

static int32_t clamp16(int32_t v)
{
    if (v > 32767)  { return 32767; }
    if (v < -32768) { return -32768; }
    return v;
}

static const char *chan(size_t i) { return (i % WAV_CHANNELS) == 0 ? "L" : "R"; }

static void hms(size_t frame, char *out, size_t n)
{
    double s = (double)frame / (double)WAV_RATE;
    (void)snprintf(out, n, "%u:%06.3f", (unsigned)(s / 60.0), s - 60.0 * (double)(unsigned)(s / 60.0));
}

int main(int argc, char **argv)
{
    struct wav ref, act, diff;
    char err[256] = { 0 };
    size_t n, i, first = 0, ndiff = 0;
    int32_t peak = 0;
    int found = 0;
    char t[32];

    if (argc < 3) {
        (void)fprintf(stderr, "usage: golden_diff <reference.wav> <actual.wav> [diff.wav]\n");
        return 2;
    }
    if (wav_read(argv[1], &ref, err, sizeof err) != 0) {
        (void)fprintf(stderr, "  %s\n", err);
        return 2;
    }
    if (wav_read(argv[2], &act, err, sizeof err) != 0) {
        (void)fprintf(stderr, "  %s\n", err);
        wav_free(&ref);
        return 2;
    }

    if (ref.frame_count != act.frame_count) {
        hms(ref.frame_count, t, sizeof t);
        (void)printf("        length differs: reference %lu frames (%s), actual %lu\n",
                     (unsigned long)ref.frame_count, t, (unsigned long)act.frame_count);
    }

    n = (ref.frame_count < act.frame_count) ? ref.frame_count : act.frame_count;

    diff.frame_count = (ref.frame_count > act.frame_count) ? ref.frame_count : act.frame_count;
    diff.frames = calloc(diff.frame_count ? diff.frame_count * WAV_CHANNELS : 1u,
                         sizeof(int16_t));
    if (diff.frames == NULL) {
        (void)fprintf(stderr, "  out of memory\n");
        wav_free(&ref); wav_free(&act);
        return 2;
    }

    for (i = 0; i < n * WAV_CHANNELS; i++) {
        int32_t d = (int32_t)ref.frames[i] - (int32_t)act.frames[i];
        if (d != 0) {
            if (!found) { first = i; found = 1; }
            ndiff++;
            if (d > peak)  { peak = d; }
            if (-d > peak) { peak = -d; }
        }
        diff.frames[i] = (int16_t)clamp16(d);
    }
    /* Beyond the shorter file, the difference is the longer file's content. */
    for (i = n * WAV_CHANNELS; i < diff.frame_count * WAV_CHANNELS; i++) {
        const struct wav *longer = (ref.frame_count > act.frame_count) ? &ref : &act;
        int32_t d = longer->frames[i];
        diff.frames[i] = (int16_t)d;
        if (d > peak)  { peak = d; }
        if (-d > peak) { peak = -d; }
        ndiff++;
    }

    if (ndiff == 0 && ref.frame_count == act.frame_count) {
        (void)printf("        identical: %lu frames\n", (unsigned long)ref.frame_count);
        wav_free(&ref); wav_free(&act); wav_free(&diff);
        return 0;
    }

    hms(found ? first / WAV_CHANNELS : n, t, sizeof t);
    (void)printf("        first difference at frame %lu (%s), channel %s\n",
                 (unsigned long)(found ? first / WAV_CHANNELS : n), t,
                 found ? chan(first) : "-");
    if (found) {
        (void)printf("        reference %6d   actual %6d   delta %d\n",
                     ref.frames[first], act.frames[first],
                     (int)((int32_t)ref.frames[first] - (int32_t)act.frames[first]));
    }
    {
        size_t total = diff.frame_count * WAV_CHANNELS;
        double pct = (total > 0u) ? 100.0 * (double)ndiff / (double)total : 0.0;
        (void)printf("        %lu of %lu samples differ (%.4f%%), peak |delta| %ld\n",
                     (unsigned long)ndiff, (unsigned long)total, pct, (long)peak);
    }

    if (argc >= 4) {
        if (wav_write(argv[3], &diff, err, sizeof err) == 0) {
            (void)printf("        audible diff written to %s — silence where they agree\n",
                         argv[3]);
        } else {
            (void)fprintf(stderr, "  %s\n", err);
        }
    }

    wav_free(&ref); wav_free(&act); wav_free(&diff);
    return 1;
}
