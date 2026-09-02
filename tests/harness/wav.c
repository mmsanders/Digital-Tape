#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "wav.h"

static void fail(char *err, size_t n, const char *fmt, const char *a, unsigned long b)
{
    if (err != NULL && n > 0) {
        (void)snprintf(err, n, fmt, a, b);
    }
}

static uint32_t rd32(const unsigned char *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8)
         | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static uint16_t rd16(const unsigned char *p)
{
    return (uint16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}

int wav_read(const char *path, struct wav *w, char *err, size_t errlen)
{
    FILE *f;
    unsigned char hdr[12], ch[8], fmt[16];
    int seen_fmt = 0;
    size_t i;

    w->frames = NULL;
    w->frame_count = 0;

    f = fopen(path, "rb");
    if (f == NULL) {
        fail(err, errlen, "%s: cannot open", path, 0);
        return 1;
    }
    if (fread(hdr, 1, 12, f) != 12
        || memcmp(hdr, "RIFF", 4) != 0 || memcmp(hdr + 8, "WAVE", 4) != 0) {
        fail(err, errlen, "%s: not a RIFF/WAVE file", path, 0);
        (void)fclose(f);
        return 1;
    }

    /* Walk chunks. Anything that is not fmt/data is skipped, so fixtures may
       carry LIST/INFO metadata without breaking the reader. */
    while (fread(ch, 1, 8, f) == 8) {
        uint32_t size = rd32(ch + 4);

        if (memcmp(ch, "fmt ", 4) == 0) {
            if (size < 16 || fread(fmt, 1, 16, f) != 16) {
                fail(err, errlen, "%s: truncated fmt chunk", path, 0);
                (void)fclose(f);
                return 1;
            }
            if (rd16(fmt) != 1) {
                fail(err, errlen, "%s: not PCM (format tag %lu)", path, rd16(fmt));
                (void)fclose(f); return 1;
            }
            if (rd16(fmt + 2) != WAV_CHANNELS) {
                fail(err, errlen, "%s: %lu channels, expected stereo", path, rd16(fmt + 2));
                (void)fclose(f); return 1;
            }
            if (rd32(fmt + 4) != WAV_RATE) {
                fail(err, errlen, "%s: %lu Hz, expected 44100", path, rd32(fmt + 4));
                (void)fclose(f); return 1;
            }
            if (rd16(fmt + 14) != WAV_BITS) {
                fail(err, errlen, "%s: %lu-bit, expected 16", path, rd16(fmt + 14));
                (void)fclose(f); return 1;
            }
            seen_fmt = 1;
            if (size > 16 && fseek(f, (long)(size - 16), SEEK_CUR) != 0) {
                fail(err, errlen, "%s: seek failed", path, 0);
                (void)fclose(f); return 1;
            }
        } else if (memcmp(ch, "data", 4) == 0) {
            unsigned char *raw;
            if (!seen_fmt) {
                fail(err, errlen, "%s: data chunk before fmt", path, 0);
                (void)fclose(f); return 1;
            }
            w->frame_count = size / WAV_FRAME;
            raw = malloc(size ? size : 1u);
            if (raw == NULL) {
                fail(err, errlen, "%s: out of memory", path, 0);
                (void)fclose(f); return 1;
            }
            if (fread(raw, 1, size, f) != size) {
                fail(err, errlen, "%s: truncated data chunk", path, 0);
                free(raw); (void)fclose(f); return 1;
            }
            w->frames = malloc((w->frame_count ? w->frame_count : 1u)
                               * WAV_CHANNELS * sizeof(int16_t));
            if (w->frames == NULL) {
                fail(err, errlen, "%s: out of memory", path, 0);
                free(raw); (void)fclose(f); return 1;
            }
            for (i = 0; i < w->frame_count * WAV_CHANNELS; i++) {
                w->frames[i] = (int16_t)rd16(raw + i * 2u);
            }
            free(raw);
            (void)fclose(f);
            return 0;
        } else {
            if (fseek(f, (long)size + (size & 1u), SEEK_CUR) != 0) {
                break;
            }
        }
    }

    fail(err, errlen, "%s: no data chunk", path, 0);
    (void)fclose(f);
    return 1;
}

int wav_write(const char *path, const struct wav *w, char *err, size_t errlen)
{
    FILE *f;
    unsigned char h[44];
    uint32_t data = (uint32_t)(w->frame_count * WAV_FRAME);
    uint32_t riff = 36u + data;
    size_t i;
    int ok = 1;

    f = fopen(path, "wb");
    if (f == NULL) {
        fail(err, errlen, "%s: cannot create", path, 0);
        return 1;
    }
    memcpy(h, "RIFF", 4);
    h[4]=(unsigned char)(riff); h[5]=(unsigned char)(riff>>8);
    h[6]=(unsigned char)(riff>>16); h[7]=(unsigned char)(riff>>24);
    memcpy(h + 8, "WAVEfmt ", 8);
    h[16]=16; h[17]=0; h[18]=0; h[19]=0;          /* fmt size */
    h[20]=1;  h[21]=0;                             /* PCM */
    h[22]=(unsigned char)WAV_CHANNELS; h[23]=0;
    h[24]=(unsigned char)(WAV_RATE); h[25]=(unsigned char)(WAV_RATE>>8);
    h[26]=(unsigned char)(WAV_RATE>>16); h[27]=(unsigned char)(WAV_RATE>>24);
    {   uint32_t br = WAV_RATE * WAV_FRAME;
        h[28]=(unsigned char)(br); h[29]=(unsigned char)(br>>8);
        h[30]=(unsigned char)(br>>16); h[31]=(unsigned char)(br>>24); }
    h[32]=(unsigned char)WAV_FRAME; h[33]=0;
    h[34]=(unsigned char)WAV_BITS;  h[35]=0;
    memcpy(h + 36, "data", 4);
    h[40]=(unsigned char)(data); h[41]=(unsigned char)(data>>8);
    h[42]=(unsigned char)(data>>16); h[43]=(unsigned char)(data>>24);

    if (fwrite(h, 1, 44, f) != 44) { ok = 0; }
    for (i = 0; ok && i < w->frame_count * WAV_CHANNELS; i++) {
        unsigned char s[2];
        s[0] = (unsigned char)((uint16_t)w->frames[i] & 0xFFu);
        s[1] = (unsigned char)(((uint16_t)w->frames[i] >> 8) & 0xFFu);
        if (fwrite(s, 1, 2, f) != 2) { ok = 0; }
    }
    if (fclose(f) != 0) { ok = 0; }
    if (!ok) {
        fail(err, errlen, "%s: write failed", path, 0);
        return 1;
    }
    return 0;
}

void wav_free(struct wav *w)
{
    free(w->frames);
    w->frames = NULL;
    w->frame_count = 0;
}
