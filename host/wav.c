/*
 * wav.c — see wav.h. Little-endian byte assembly throughout, so the bytes on
 * disk do not depend on the host's endianness.
 */

#include "wav.h"

#include <string.h>

static uint32_t rd32(const unsigned char *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static uint16_t rd16(const unsigned char *p)
{
    return (uint16_t)((unsigned)p[0] | ((unsigned)p[1] << 8));
}

static void wr32(unsigned char *p, uint32_t v)
{
    p[0] = (unsigned char)v; p[1] = (unsigned char)(v >> 8);
    p[2] = (unsigned char)(v >> 16); p[3] = (unsigned char)(v >> 24);
}

static void wr16(unsigned char *p, uint16_t v)
{
    p[0] = (unsigned char)v; p[1] = (unsigned char)(v >> 8);
}

static int fail(FILE *fp, char *err, size_t errlen, const char *why)
{
    if (fp != NULL) { (void)fclose(fp); }
    (void)snprintf(err, errlen, "%s", why);
    return 1;
}

int wav_open_read(struct wav_in *w, const char *path, char *err, size_t errlen)
{
    unsigned char h[12], ch[8], fmt[16];
    int have_fmt = 0;
    FILE *fp;

    memset(w, 0, sizeof *w);
    fp = fopen(path, "rb");
    if (fp == NULL) { return fail(NULL, err, errlen, "cannot open WAV"); }
    if (fread(h, 1, 12, fp) != 12 || memcmp(h, "RIFF", 4) != 0 || memcmp(h + 8, "WAVE", 4) != 0) {
        return fail(fp, err, errlen, "not a RIFF/WAVE file");
    }
    for (;;) {
        uint32_t size;
        if (fread(ch, 1, 8, fp) != 8) { return fail(fp, err, errlen, "no data chunk"); }
        size = rd32(ch + 4);
        if (memcmp(ch, "fmt ", 4) == 0) {
            if (size < 16 || fread(fmt, 1, 16, fp) != 16) { return fail(fp, err, errlen, "short fmt chunk"); }
            if (rd16(fmt) != 1u) { return fail(fp, err, errlen, "not PCM (format tag must be 1)"); }
            if (rd16(fmt + 2) != WAV_CHANNELS) { return fail(fp, err, errlen, "not stereo"); }
            if (rd32(fmt + 4) != WAV_RATE) { return fail(fp, err, errlen, "not 44100 Hz"); }
            if (rd16(fmt + 14) != WAV_BITS) { return fail(fp, err, errlen, "not 16-bit"); }
            if (rd32(fmt + 8) != WAV_RATE * WAV_FRAME || rd16(fmt + 12) != WAV_FRAME) {
                return fail(fp, err, errlen, "inconsistent byte rate or block align");
            }
            /* Skip any fmt extension, plus the RIFF pad byte for an odd size. */
            if (fseek(fp, (long)(size - 16u) + (long)(size & 1u), SEEK_CUR) != 0) {
                return fail(fp, err, errlen, "truncated fmt chunk");
            }
            have_fmt = 1;
        } else if (memcmp(ch, "data", 4) == 0) {
            if (!have_fmt) { return fail(fp, err, errlen, "data chunk before fmt chunk"); }
            if (size % WAV_FRAME != 0u) { return fail(fp, err, errlen, "data size is not whole frames"); }
            w->fp = fp;
            w->frames = size / WAV_FRAME;
            w->remaining = w->frames;
            return 0;
        } else {
            /* Unknown chunk (LIST, INFO, ...): skipped, with its pad byte. */
            if (fseek(fp, (long)size + (long)(size & 1u), SEEK_CUR) != 0) {
                return fail(fp, err, errlen, "truncated chunk");
            }
        }
    }
}

uint32_t wav_read_frames(struct wav_in *w, int16_t *buf, uint32_t max, int *bad)
{
    unsigned char raw[1024 * WAV_FRAME];
    uint32_t want, i;

    *bad = 0;
    if (w->remaining == 0u) { return 0u; }
    if (max > 1024u) { max = 1024u; }
    want = (w->remaining < max) ? w->remaining : max;
    if (fread(raw, WAV_FRAME, want, w->fp) != want) { *bad = 1; return 0u; }
    for (i = 0; i < want * WAV_CHANNELS; i++) {
        buf[i] = (int16_t)rd16(raw + 2u * i);
    }
    w->remaining -= want;
    return want;
}

void wav_close_read(struct wav_in *w)
{
    if (w->fp != NULL) { (void)fclose(w->fp); }
    w->fp = NULL;
}

static void header(unsigned char h[44], uint32_t frames)
{
    uint32_t data = frames * WAV_FRAME;
    memcpy(h, "RIFF", 4); wr32(h + 4, 36u + data); memcpy(h + 8, "WAVE", 4);
    memcpy(h + 12, "fmt ", 4); wr32(h + 16, 16u); wr16(h + 20, 1u); wr16(h + 22, WAV_CHANNELS);
    wr32(h + 24, WAV_RATE); wr32(h + 28, WAV_RATE * WAV_FRAME); wr16(h + 32, WAV_FRAME);
    wr16(h + 34, WAV_BITS); memcpy(h + 36, "data", 4); wr32(h + 40, data);
}

int wav_open_write(struct wav_out *w, const char *path, char *err, size_t errlen)
{
    unsigned char h[44];

    w->frames = 0;
    w->fp = fopen(path, "wb");
    if (w->fp == NULL) { return fail(NULL, err, errlen, "cannot create output WAV"); }
    header(h, 0);
    if (fwrite(h, 1, 44, w->fp) != 44) {
        FILE *fp = w->fp;
        w->fp = NULL;
        return fail(fp, err, errlen, "cannot write output WAV");
    }
    return 0;
}

int wav_write_frames(struct wav_out *w, const int16_t *buf, uint32_t frames)
{
    unsigned char raw[128 * WAV_FRAME];
    uint32_t done = 0;

    while (done < frames) {
        uint32_t n = frames - done, i;
        if (n > 128u) { n = 128u; }
        if (w->frames > (0xFFFFFFFFu - 36u) / WAV_FRAME - n) { return 1; }   /* RIFF size limit */
        for (i = 0; i < n * WAV_CHANNELS; i++) {
            wr16(raw + 2u * i, (uint16_t)buf[(size_t)done * WAV_CHANNELS + i]);
        }
        if (fwrite(raw, WAV_FRAME, n, w->fp) != n) { return 1; }
        done += n;
        w->frames += n;
    }
    return 0;
}

int wav_close_write(struct wav_out *w)
{
    unsigned char h[44];
    int rc = 0;

    header(h, w->frames);
    if (fseek(w->fp, 0, SEEK_SET) != 0 || fwrite(h, 1, 44, w->fp) != 44) { rc = 1; }
    if (fclose(w->fp) != 0) { rc = 1; }
    w->fp = NULL;
    return rc;
}
